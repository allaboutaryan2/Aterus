"""No-network connector lifecycle fixtures; never creates a public URL."""
import importlib.util
import io
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('connectivity', ROOT / 'connectivity.py')
connectivity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(connectivity)
ORIGIN = 'https://fixture-only-address.trycloudflare.com'


class LogPipe:
    def __init__(self):
        self.blocks = queue.Queue()
        self.closed = False

    def read(self, size):
        return self.blocks.get()

    def write_log(self, text):
        self.blocks.put(text.encode())

    def close(self):
        self.closed = True


class Connector:
    def __init__(self, ignore_terminate=False):
        self.stdout = LogPipe()
        self.code = None
        self.done = threading.Event()
        self.ignore_terminate = ignore_terminate
        self.terminations = 0
        self.kills = 0

    def poll(self):
        return self.code

    def finish(self, code=0):
        self.code = code
        self.done.set()
        self.stdout.blocks.put(b'')

    def wait(self, timeout=None):
        if not self.done.wait(timeout):
            raise subprocess.TimeoutExpired('fixture-cloudflared', timeout)
        return self.code

    def terminate(self):
        self.terminations += 1
        if not self.ignore_terminate:
            self.finish(-15)

    def kill(self):
        self.kills += 1
        self.finish(-9)


class ConnectorExecutableTests(unittest.TestCase):
    def test_path_takes_priority_over_bundle(self):
        with patch.object(connectivity.shutil, 'which', return_value='/installed/cloudflared'):
            self.assertEqual(connectivity.connector_executable(), '/installed/cloudflared')

    def test_bundle_requires_executable_and_missing_path_fails_clearly(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(connectivity, 'CONNECTOR_ROOT', Path(directory)), patch.object(connectivity.shutil, 'which', return_value=None):
            binary = Path(directory) / 'vendor' / 'bin' / ('cloudflared.exe' if os.name == 'nt' else 'cloudflared')
            binary.parent.mkdir(parents=True)
            self.assertIsNone(connectivity.connector_executable())
            binary.write_bytes(b'fixture only')
            binary.chmod(0o700)
            self.assertEqual(connectivity.connector_executable(), str(binary))
            if os.name != 'nt':
                binary.chmod(0o600)
                self.assertIsNone(connectivity.connector_executable())

    def test_windows_uses_exe_bundle_and_ignores_shell_wrapper(self):
        windows_os = SimpleNamespace(name='nt', access=os.access, X_OK=os.X_OK)
        with tempfile.TemporaryDirectory() as directory, patch.object(connectivity, 'CONNECTOR_ROOT', Path(directory)), patch.object(connectivity.shutil, 'which', return_value='C:\\bin\\cloudflared.cmd'), patch.object(connectivity, 'os', windows_os):
            binary = Path(directory) / 'vendor' / 'bin' / 'cloudflared.exe'
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'fixture only')
            binary.chmod(0o700)
            self.assertEqual(connectivity.connector_executable(), str(binary))


class QuickTunnelTests(unittest.TestCase):
    def setUp(self):
        self.origins = []
        self.connector = Connector()
        self.tunnel = connectivity.QuickTunnel(4380, self.origins.append, startup_timeout=.4, stop_timeout=.05)
        self.patches = [patch.object(connectivity, 'connector_executable', return_value='/fixture/cloudflared'),
                        patch.object(connectivity.Path, 'is_file', return_value=False),
                        patch.object(connectivity.subprocess, 'Popen', return_value=self.connector)]
        self.mocks = [p.start() for p in self.patches]

    def tearDown(self):
        self.tunnel.stop()
        for p in reversed(self.patches):
            p.stop()

    def until(self, check):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not check():
            time.sleep(.01)
        self.assertTrue(check(), self.tunnel.status())

    def ready(self):
        self.tunnel.start()
        self.connector.stdout.write_log('| ' + ORIGIN + ' |\n')
        self.connector.stdout.write_log('2026 INF Registered tunnel connection connIndex=0\n')
        self.until(lambda: self.tunnel.status()['state'] == 'ready')

    def test_command_loopback_no_shell_and_readiness(self):
        with patch.dict(os.environ, {'TUNNEL_TOKEN': 'fixture-secret', 'TUNNEL_URL': 'http://wrong-origin', 'NO_AUTOUPDATE': 'false'}):
            self.ready()
        args, kwargs = self.mocks[2].call_args
        self.assertEqual(args[0], ['/fixture/cloudflared', 'tunnel', '--no-autoupdate', '--url', 'http://127.0.0.1:4380'])
        self.assertFalse(kwargs['shell'])
        self.assertEqual(kwargs['stderr'], subprocess.STDOUT)
        self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
        self.assertNotIn('TUNNEL_TOKEN', kwargs['env'])
        self.assertNotIn('TUNNEL_URL', kwargs['env'])
        self.assertEqual(kwargs['env']['NO_AUTOUPDATE'], 'true')
        self.assertEqual(self.origins, [ORIGIN])
        self.assertFalse(self.tunnel.status()['phone_verified'])
        self.assertTrue(self.tunnel.enabled)
        self.tunnel.start()
        self.assertEqual(self.mocks[2].call_count, 1)

    def test_url_without_edge_registration_is_not_ready(self):
        self.tunnel.start()
        self.connector.stdout.write_log('| ' + ORIGIN + ' |\n')
        time.sleep(.07)
        self.assertEqual(self.tunnel.status()['state'], 'starting')
        self.assertEqual(self.origins, [])
        self.until(lambda: self.tunnel.status()['state'] == 'failed')
        self.until(lambda: self.connector.poll() is not None)
        self.assertEqual(self.tunnel.status()['origin'], '')

    def test_exit_revokes_origin_and_does_not_leak_logs(self):
        self.ready()
        self.connector.stdout.write_log('PRIVATE_TOKEN=fixture-do-not-show https://evil.example/secret\n')
        self.connector.finish(1)
        self.until(lambda: self.tunnel.status()['state'] == 'failed')
        self.assertEqual(self.origins, [ORIGIN, ''])
        self.assertEqual(self.tunnel.status()['origin'], '')
        self.assertNotIn('fixture-do-not-show', json.dumps(self.tunnel.status()))

    def test_stop_escalates_only_own_process_and_clears_trust(self):
        self.connector.ignore_terminate = True
        self.ready()
        result = self.tunnel.stop()
        self.assertEqual(result['state'], 'stopped')
        self.assertFalse(self.tunnel.enabled)
        self.assertEqual(self.origins, [ORIGIN, ''])
        self.assertEqual(self.connector.terminations, 1)
        self.assertEqual(self.connector.kills, 1)
        self.assertEqual(self.tunnel.stop()['state'], 'stopped')
        self.assertEqual(self.origins, [ORIGIN, ''])

    def test_restart_does_not_reuse_stale_origin(self):
        self.ready()
        self.tunnel.stop()
        old = self.connector
        self.connector = Connector()
        self.mocks[2].return_value = self.connector
        self.assertEqual(self.tunnel.start()['state'], 'starting')
        old.stdout.write_log('| https://stale.trycloudflare.com |\n')
        self.connector.stdout.write_log('| https://fresh.trycloudflare.com |\nRegistered tunnel connection\n')
        self.until(lambda: self.tunnel.status()['state'] == 'ready')
        self.assertEqual(self.origins, [ORIGIN, '', 'https://fresh.trycloudflare.com'])

    def test_missing_cli_has_install_instructions_and_no_process(self):
        self.mocks[0].return_value = None
        status = self.tunnel.start()
        self.assertEqual(status['state'], 'failed')
        self.assertFalse(status['installed'])
        self.assertIn('install cloudflared', status['message'])
        self.assertTrue(status['install_url'].startswith('https://developers.cloudflare.com/'))
        self.mocks[2].assert_not_called()
        self.assertEqual(self.origins, [])

    def test_unused_stop_and_missing_connector_do_not_touch_manual_origin(self):
        manual = {'origin': 'https://manual.example'}
        self.tunnel.on_origin = lambda origin: manual.update(origin=origin)
        self.tunnel.stop()
        self.mocks[0].return_value = None
        self.tunnel.start()
        self.tunnel.stop()
        self.assertEqual(manual['origin'], 'https://manual.example')

    def test_existing_configuration_is_not_modified(self):
        self.mocks[1].return_value = True
        self.assertEqual(self.tunnel.start()['state'], 'failed')
        self.assertIn('not modify', self.tunnel.status()['message'])
        self.mocks[2].assert_not_called()

    def test_strict_origin_parsing_rejects_suffix_paths_credentials_and_ports(self):
        for value in ['http://good.trycloudflare.com', 'https://good.trycloudflare.com.evil.test',
                      'https://good.trycloudflare.com/path', 'https://good.trycloudflare.com?x=1',
                      'https://good.trycloudflare.com#frag', 'https://good.trycloudflare.com:443',
                      'https://user@good.trycloudflare.com', 'https://-bad.trycloudflare.com',
                      'https://bad-.trycloudflare.com', 'https://a.b.trycloudflare.com']:
            self.assertEqual(connectivity.reported_origin('visit ' + value + ' now'), '')
        self.assertEqual(connectivity.reported_origin('| ' + ORIGIN + ' |'), ORIGIN)
        self.assertEqual(connectivity.reported_origin('"' + ORIGIN + '"'), ORIGIN)

    def test_bounded_long_log_line_discard_and_split_url(self):
        self.tunnel.start()
        self.connector.stdout.write_log('x' * 20000 + ORIGIN + '\n')
        self.connector.stdout.write_log('| https://fixture-only-')
        self.connector.stdout.write_log('address.trycloudflare.com |\n')
        self.connector.stdout.write_log('Registered tunnel connection\n')
        self.until(lambda: self.tunnel.status()['state'] == 'ready')
        self.assertEqual(self.origins, [ORIGIN])

    def test_callback_failure_revokes_and_terminates(self):
        def callback(origin):
            self.origins.append(origin)
            if origin:
                raise ValueError('fixture private callback failure')
        self.tunnel.on_origin = callback
        self.tunnel.start()
        self.connector.stdout.write_log('| ' + ORIGIN + ' |\nRegistered tunnel connection\n')
        self.until(lambda: self.tunnel.status()['state'] == 'failed')
        self.until(lambda: self.connector.poll() is not None)
        self.assertEqual(self.origins, [ORIGIN, ''])
        self.assertNotIn('private', self.tunnel.status()['message'])

    def test_process_launch_failure_is_sanitized(self):
        self.mocks[2].side_effect = OSError('fixture PRIVATE_TOKEN=must-not-appear')
        status = self.tunnel.start()
        self.assertEqual(status['state'], 'failed')
        self.assertNotIn('PRIVATE_TOKEN', json.dumps(status))

    def test_windows_uses_owned_popen_without_shell_or_pid_commands(self):
        windows_os = SimpleNamespace(name='nt', environ=os.environ)
        with patch.object(connectivity, 'os', windows_os), patch.object(connectivity.subprocess, 'CREATE_NO_WINDOW', 134217728, create=True):
            self.ready()
        kwargs = self.mocks[2].call_args.kwargs
        self.assertEqual(kwargs['creationflags'], 134217728)
        self.assertNotIn('start_new_session', kwargs)
        self.assertFalse(kwargs['shell'])

    @unittest.skipIf(os.name == 'nt', 'Executable-script fixture is POSIX; Windows Popen contract has a separate fixture')
    def test_real_owned_child_lifecycle_without_network(self):
        self.patches[2].stop()
        self.tunnel.startup_timeout = 5
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'cloudflared-fixture'
            script.write_text('#!' + sys.executable + '\nimport sys,time\nprint("| ' + ORIGIN + ' |",file=sys.stderr,flush=True)\nprint("Registered tunnel connection",file=sys.stderr,flush=True)\ntime.sleep(60)\n')
            script.chmod(0o700)
            self.mocks[0].return_value = str(script)
            self.tunnel.start()
            self.until(lambda: self.tunnel.status()['state'] == 'ready')
            child = self.tunnel._process
            self.assertIsNone(child.poll())
            self.assertEqual(self.tunnel.stop()['state'], 'stopped')
            self.assertIsNotNone(child.poll())
            self.assertEqual(self.origins, [ORIGIN, ''])

    def test_invalid_ports_cannot_redirect_upstream(self):
        for port in (0, 65536, True, 'http://evil.test'):
            with self.assertRaises(ValueError):
                connectivity.QuickTunnel(port, self.origins.append)


if __name__ == '__main__':
    unittest.main()
