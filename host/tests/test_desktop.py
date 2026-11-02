"""Desktop host fixtures: no GUI, sockets, browser or real agents are started."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import desktop


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        self.data = self.root / 'data'

    def tearDown(self):
        self.temp.cleanup()

    def test_import_does_not_require_gui_or_start_service(self):
        code = "import sys; import desktop; assert 'tkinter' not in sys.modules; assert 'aterus' not in sys.modules; assert 'pty_worker' not in sys.modules"
        result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout, b'')

    def test_config_contains_only_authorized_existing_workspace(self):
        desktop.save_workspace(self.data, self.project)
        self.assertEqual(desktop.load_workspace(self.data), self.project.resolve())
        config = json.loads((self.data / 'desktop.json').read_text())
        self.assertEqual(config, {'workspace': str(self.project.resolve())})
        with self.assertRaises(ValueError):
            desktop.save_workspace(self.data, Path(self.project.anchor))
        for invalid in ('relative/project', str(self.root / 'missing'), '\0'):
            with self.assertRaises(ValueError):
                desktop.workspace_path(invalid)
        (self.data / 'desktop.json').write_text(json.dumps({'workspace': str(self.project), 'token':'not-accepted'}))
        self.assertIsNone(desktop.load_workspace(self.data))
        (self.data / 'desktop.json').write_text('invalid json')
        self.assertIsNone(desktop.load_workspace(self.data))

    @unittest.skipIf(os.name == 'nt', 'POSIX filesystem mode/symlink fixture')
    def test_private_modes_and_no_linked_config(self):
        desktop.save_workspace(self.data, self.project)
        self.assertEqual(self.data.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.data / 'desktop.json').stat().st_mode & 0o777, 0o600)
        (self.data / 'desktop.json').unlink()
        outside = self.root / 'outside.json'
        outside.write_text(json.dumps({'workspace': str(self.project)}))
        (self.data / 'desktop.json').symlink_to(outside)
        self.assertIsNone(desktop.load_workspace(self.data))
        desktop.save_workspace(self.data, self.project)
        self.assertFalse((self.data / 'desktop.json').is_symlink())
        self.assertEqual(outside.read_text(), json.dumps({'workspace': str(self.project)}))

    def test_modern_per_user_opencode_is_selected_without_changing_global_path(self):
        import agents
        candidate=self.root/'.opencode'/'bin'/('opencode.exe' if os.name=='nt' else 'opencode')
        candidate.parent.mkdir(parents=True);candidate.write_text('fixture');candidate.chmod(0o700)
        original=agents.EXECUTABLES['opencode']
        try:
            with patch.object(agents,'controls',side_effect=[{'variant':'legacy-go'},{'variant':'modern'}]):
                desktop.select_agent_binaries(self.root)
            self.assertEqual(agents.EXECUTABLES['opencode'],str(candidate))
        finally:agents.EXECUTABLES['opencode']=original

    def test_platform_data_paths_and_cli_path_are_explicit(self):
        self.assertEqual(desktop.data_directory('darwin', self.root, {}), self.root / 'Library/Application Support/Aterus')
        self.assertEqual(desktop.data_directory('win32', self.root, {'LOCALAPPDATA':str(self.root / 'local')}), self.root / 'local/Aterus')
        self.assertEqual(desktop.data_directory('linux', self.root, {}), self.root / '.local/share/aterus')
        local = self.root / '.local/bin'
        local.mkdir(parents=True)
        environment = {'PATH':str(self.project) + os.pathsep + '.'}
        result = desktop.discover_cli_path(environment, self.root, 'darwin').split(os.pathsep)
        self.assertEqual(result[0], str(self.project))
        self.assertIn(str(local), result)
        self.assertNotIn('.', result)
        self.assertEqual(len(result), len(set(result)))

    def test_service_lifecycle_loopback_and_one_time_browser_secret(self):
        hub = Mock(bootstrap='private-fixture-secret')
        server = Mock(server_address=('127.0.0.1', 4321))
        thread = Mock()
        opener = Mock(return_value=True)
        with patch.object(desktop.threading, 'Thread', return_value=thread):
            factory, server_factory = Mock(return_value=hub), Mock(return_value=server)
            host = desktop.DesktopHost(self.data, self.project, factory, server_factory, opener)
            self.assertEqual(host.start(), 'http://127.0.0.1:4321/')
            server_factory.assert_called_once_with(hub, 0)
            thread.start.assert_called_once_with()
            self.assertTrue(host.open_dashboard())
            self.assertTrue(host.open_dashboard())
            self.assertEqual(opener.call_args_list[0].args[0], 'http://127.0.0.1:4321/#owner=private-fixture-secret')
            self.assertEqual(opener.call_args_list[1].args[0], 'http://127.0.0.1:4321/')
            self.assertFalse((self.data / 'desktop.json').exists(), 'host must not persist any tokens')
            host.stop()
            host.stop()
            server.shutdown.assert_called_once_with()
            server.server_close.assert_called_once_with()
            hub.close.assert_called_once_with()

    def test_failed_browser_can_retry_bootstrap_and_failed_start_closes_hub(self):
        hub = Mock(bootstrap='fixture')
        server = Mock(server_address=('127.0.0.1', 4321))
        with patch.object(desktop.threading, 'Thread'):
            host = desktop.DesktopHost(self.data, self.project, Mock(return_value=hub), Mock(return_value=server), Mock(side_effect=[False, True]))
            host.start()
            self.assertFalse(host.open_dashboard())
            self.assertTrue(host.open_dashboard())
            self.assertTrue(all('#owner=fixture' in call.args[0] for call in host.opener.call_args_list))
            host.stop()
        hub = Mock()
        host = desktop.DesktopHost(self.data, self.project, Mock(return_value=hub), Mock(side_effect=OSError('blocked')))
        with self.assertRaises(OSError):
            host.start()
        hub.close.assert_called_once_with()
        self.assertIsNone(host.server)

    def test_frozen_worker_dispatch_uses_stdin_and_no_gui(self):
        expected = 'windows' if os.name == 'nt' else 'posix'
        worker = Mock()
        observed = []
        worker.main.side_effect = lambda: observed.append(list(sys.argv))
        with patch.object(desktop, '_restore_worker_streams') as restore, patch('importlib.import_module', return_value=worker) as load:
            old = list(sys.argv)
            self.assertTrue(desktop.dispatch_worker(['Aterus', '--aterus-worker', expected]))
            self.assertEqual(observed, [[old[0]]])
            self.assertEqual(sys.argv, old)
            restore.assert_called_once_with()
            load.assert_called_once_with('windows_worker' if os.name == 'nt' else 'pty_worker')
        self.assertFalse(desktop.dispatch_worker(['Aterus']))
        with self.assertRaises(ValueError):
            desktop.dispatch_worker(['Aterus','--aterus-worker','wrong'])

    @unittest.skipIf(os.name == 'nt', 'POSIX inherited descriptor fixture; Windows needs native packaged verification')
    def test_windowed_worker_restores_private_inherited_pipes(self):
        code = ("import sys, desktop; sys.stdin=None; sys.stdout=None; sys.stderr=None; "
                "desktop._restore_worker_streams(); "
                "print('reply='+sys.stdin.buffer.readline().decode().strip(), flush=True)")
        result = subprocess.run([sys.executable, '-c', code], input=b'fixture-input\n', cwd=ROOT,
                                capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout, b'reply=fixture-input\n')

    def test_build_script_never_installs_dependencies(self):
        spec = importlib.util.spec_from_file_location('build_desktop', ROOT / 'build-desktop.py')
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        with patch.object(build.importlib.util, 'find_spec', return_value=None), patch.object(sys, 'argv', ['build-desktop.py']), patch.object(build.subprocess, 'call') as call:
            with patch('sys.stderr'), self.assertRaises(SystemExit) as error:
                build.main()
            self.assertEqual(error.exception.code, 2)
            call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
