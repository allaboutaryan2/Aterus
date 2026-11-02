"""Windows adapter contract fixtures; only NativeWindowsTests use real ConPTY."""
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('windows_worker', ROOT / 'windows_worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class Controls:
    def __init__(self):
        self.lines = queue.Queue()

    def readline(self, size):
        return self.lines.get()

    def send(self, event):
        self.lines.put(json.dumps(event).encode() + b'\n')

    def close(self):
        self.lines.put(b'')


class FakeConPTY:
    def __init__(self):
        self.alive = True
        self.exitstatus = None
        self.reads = queue.Queue()
        self.writes = []
        self.sizes = []
        self.interrupts = 0
        self.terminated = []
        self.closed = []

    def read(self, size):
        item = self.reads.get()
        if item is None:
            raise EOFError()
        return item

    def write(self, text):
        if not self.alive:
            raise AssertionError('Input after native process exit')
        self.writes.append(text)
        return len(text.encode('utf-8'))

    def setwinsize(self, rows, cols):
        self.sizes.append((rows, cols))

    def sendintr(self):
        self.interrupts += 1

    def isalive(self):
        return self.alive

    def finish(self, code=0):
        self.exitstatus = code
        self.alive = False
        self.reads.put(None)

    def terminate(self, force=False):
        self.terminated.append(force)
        self.finish(1)
        return True

    def close(self, force=False):
        self.closed.append(force)
        if self.alive:
            self.finish(1)


class WindowsContractTests(unittest.TestCase):
    def setUp(self):
        self.child = FakeConPTY()
        self.source = Controls()
        self.sink = io.StringIO()
        self.spawned = []
        self.errors = []
        self.config = {'environment': {'OPENCODE_SERVER_USERNAME': 'aterus', 'OPENCODE_SERVER_PASSWORD': 'fixture-only-value'}, 'argv': [r'C:\Program Files\Agent\agent.exe', '--model', 'model with spaces', 'a"b'],
                       'cwd': r'C:\Projects\My Project'}

    def tearDown(self):
        self.child.finish()
        self.source.close()
        if hasattr(self, 'thread'):
            self.thread.join(timeout=2)
            self.assertFalse(self.thread.is_alive())
        self.assertEqual(self.errors, [])

    def start(self):
        def spawn(*args, **kwargs):
            self.spawned.append((args, kwargs))
            return self.child
        def target():
            try:
                worker.run(self.config, spawn, 0, self.source, self.sink, stop_grace=.05)
            except Exception as error:
                self.errors.append(error)
        self.thread = threading.Thread(target=target, daemon=True)
        self.thread.start()
        self.until(lambda: self.spawned)

    def until(self, check):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not check():
            time.sleep(.01)
        self.assertTrue(check())

    def send_input(self, data):
        self.source.send({'input': base64.b64encode(data).decode()})

    def events(self):
        return [json.loads(line) for line in self.sink.getvalue().splitlines()]

    def test_argv_env_resize_unicode_and_natural_exit(self):
        self.start()
        args, kwargs = self.spawned[0]
        self.assertEqual(args, (self.config['argv'],))
        self.assertEqual(kwargs['cwd'], self.config['cwd'])
        self.assertEqual(kwargs['dimensions'], (30, 100))
        self.assertEqual(kwargs['backend'], 0)
        self.assertEqual(kwargs['env']['PYWINPTY_BACKEND'], '0')
        self.assertEqual(kwargs['env']['OPENCODE_SERVER_USERNAME'], 'aterus')
        self.assertEqual(kwargs['env']['OPENCODE_SERVER_PASSWORD'], 'fixture-only-value')
        self.source.send({'resize': [44, 120]})
        raw = 'héllo 😀\r'.encode()
        self.send_input(raw[:2])
        self.send_input(raw[2:])
        self.until(lambda: ''.join(self.child.writes) == 'héllo 😀\r')
        self.until(lambda: self.child.sizes == [(44, 120)])
        self.child.reads.put('\x1b[32mRéponse 😀\x1b[0m')
        self.until(lambda: 'output' in self.sink.getvalue())
        self.child.finish(7)
        self.thread.join(timeout=3)
        events = self.events()
        output = b''.join(base64.b64decode(e['output']) for e in events if 'output' in e)
        self.assertEqual(output.decode(), '\x1b[32mRéponse 😀\x1b[0m')
        self.assertEqual(events[-1], {'exit': 7})
        self.assertEqual(self.child.closed, [True])

    def test_stop_escalates_and_discards_later_input(self):
        self.start()
        self.source.send({'stop': True})
        self.send_input(b'never delivered\r')
        self.thread.join(timeout=3)
        self.assertFalse(self.thread.is_alive())
        self.assertEqual(self.child.interrupts, 1)
        self.assertEqual(self.child.terminated, [True])
        self.assertEqual(self.child.writes, [])

    def test_control_pipe_eof_stops_child(self):
        self.start()
        self.source.close()
        self.thread.join(timeout=3)
        self.assertEqual(self.child.terminated, [True])
        self.assertFalse(self.thread.is_alive())

    def test_invalid_payloads_and_dimensions_never_reach_native_api(self):
        self.start()
        self.source.send({'input': 'not base64!'})
        self.source.send({'resize': [True, 100]})
        self.source.send({'resize': [5, 100]})
        self.source.send({'resize': [30]})
        self.send_input(b'valid\r')
        self.until(lambda: self.child.writes == ['valid\r'])
        self.assertEqual(self.child.sizes, [])
        self.source.send({'stop': True})
        self.thread.join(timeout=3)

    def test_exited_process_never_receives_input(self):
        self.child.finish(0)
        self.send_input(b'never delivered\r')
        self.start()
        self.thread.join(timeout=3)
        self.assertEqual(self.child.writes, [])
        self.assertEqual(self.events()[-1], {'exit': 0})

    def test_closed_terminal_stops_agent_that_stays_alive(self):
        self.start()
        self.child.reads.put(None)
        self.thread.join(timeout=3)
        self.assertFalse(self.thread.is_alive())
        self.assertEqual(self.child.terminated, [True])

    def test_oversized_input_stops_instead_of_truncating(self):
        self.start()
        self.send_input(b'x' * (worker.MAX_INPUT + 1))
        self.thread.join(timeout=3)
        self.assertFalse(self.thread.is_alive())
        self.assertEqual(self.child.writes, [])
        self.assertEqual(self.child.terminated, [True])

    def test_config_line_preserves_following_protocol_and_secrets_not_in_argv(self):
        following = b'{"stop":true}\n'
        stream = io.BytesIO(json.dumps(self.config).encode() + b'\n' + following)
        self.assertEqual(worker.read_config(['windows_worker.py'], stream), self.config)
        self.assertEqual(stream.readline(), following)
        with self.assertRaises(ValueError):
            worker.read_config(['windows_worker.py'], io.BytesIO(b'x' * (worker.MAX_LINE + 1)))

    def test_environment_allowlist(self):
        self.config['environment']['PATH'] = 'untrusted'
        with self.assertRaisesRegex(ValueError, 'Unsupported agent environment'):
            worker.run(self.config, lambda *a, **kw: self.fail('must not spawn'), 0, self.source, self.sink)

    def test_no_shell_wrapper_fallback(self):
        for executable in ('agent.cmd', 'agent.bat', 'agent.ps1'):
            with self.assertRaisesRegex(ValueError, 'shell wrappers'):
                worker.validate_config({'argv': [executable], 'cwd': 'C:\\project'})
        with self.assertRaises(ValueError):
            worker.validate_config({'argv': 'agent.exe', 'cwd': 'C:\\project'})


@unittest.skipUnless(os.name == 'nt', 'Native ConPTY requires a Windows host; contract fixtures run elsewhere')
class NativeWindowsTests(unittest.TestCase):
    def test_native_python_exchange_and_exit(self):
        try:
            from winpty import PtyProcess, Backend
        except ImportError:
            self.skipTest('Install requirements-windows.txt before native ConPTY checks')
        source = Controls()
        sink = io.StringIO()
        errors = []
        script = 'import sys; print("READY",flush=True); print("REPLY="+input(),flush=True)'
        def target():
            try:
                worker.run({'argv': [sys.executable, '-c', script], 'cwd': str(ROOT)},
                           PtyProcess.spawn, Backend.ConPTY, source, sink)
            except Exception as error:
                errors.append(error)
        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                events = [json.loads(line) for line in sink.getvalue().splitlines()]
                output = b''.join(base64.b64decode(e['output']) for e in events if 'output' in e)
                if b'READY' in output:
                    break
                time.sleep(.05)
            self.assertIn(b'READY', output)
            source.send({'input': base64.b64encode('hello 😀\r'.encode()).decode()})
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            events = [json.loads(line) for line in sink.getvalue().splitlines()]
            output = b''.join(base64.b64decode(e['output']) for e in events if 'output' in e)
            self.assertIn('REPLY=hello 😀'.encode(), output)
            self.assertEqual(events[-1], {'exit': 0})
        finally:
            source.close()
            thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
