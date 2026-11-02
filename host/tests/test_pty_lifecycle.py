"""Real PTY fixture checks; no agent accounts or network required."""
import base64
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest

WORKER = Path(__file__).resolve().parents[1] / 'pty_worker.py'


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.worker = None
        self.output = b''

    def tearDown(self):
        if self.worker:
            if self.worker.poll() is None:
                self.worker.kill()
                self.worker.wait()
            for stream in (self.worker.stdin, self.worker.stdout, self.worker.stderr):
                if stream and not stream.closed:
                    stream.close()
        self.temp.cleanup()

    def start(self, source):
        script = Path(self.temp.name) / 'agent.py'
        script.write_text(source)
        self.worker = subprocess.Popen([sys.executable, str(WORKER), json.dumps({
            'cwd': self.temp.name, 'argv': [sys.executable, str(script)]})],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)

    def send(self, event):
        self.worker.stdin.write(json.dumps(event).encode() + b'\n')
        self.worker.stdin.flush()

    def until(self, text, timeout=6):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if text in self.output:
                return
            if select.select([self.worker.stdout], [], [], .1)[0]:
                line = self.worker.stdout.readline()
                if not line:
                    break
                event = json.loads(line)
                if 'output' in event:
                    self.output += base64.b64decode(event['output'])
        self.assertIn(text, self.output)

    def test_resize_keyboard_interrupt_and_natural_exit(self):
        self.start('import os, signal\nsignal.signal(signal.SIGINT, lambda *_: print("INTERRUPTED", flush=True))\nprint("READY", flush=True)\nwhile True:\n x=input()\n print("SIZE="+str(os.get_terminal_size()), flush=True)\n if x == "quit": break\n')
        self.until(b'READY')
        self.send({'resize': [41, 123]})
        self.send({'input': base64.b64encode(b'size\r').decode()})
        self.until(b'columns=123, lines=41')
        self.send({'input': base64.b64encode(b'\x03').decode()})
        self.until(b'INTERRUPTED')
        self.send({'input': base64.b64encode(b'quit\r').decode()})
        self.assertEqual(self.worker.wait(timeout=6), 0)
        events = [json.loads(line) for line in self.worker.stdout.read().splitlines()]
        self.assertEqual(events[-1], {'exit': 0})

    def test_stdin_eof_escalates_for_sigterm_ignoring_agent(self):
        self.start('import signal,time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nprint("READY",flush=True)\ntime.sleep(60)\n')
        self.until(b'READY')
        self.worker.stdin.close()
        self.assertEqual(self.worker.wait(timeout=6), 0)
        events = [json.loads(line) for line in self.worker.stdout.read().splitlines()]
        self.assertEqual(events[-1], {'exit': -signal.SIGKILL})

    def test_agent_exit_cleans_descendant_holding_terminal(self):
        marker = Path(self.temp.name) / 'survived'
        self.start('import os,time,signal\npid=os.fork()\nif pid == 0:\n signal.signal(signal.SIGTERM,signal.SIG_IGN)\n signal.signal(signal.SIGHUP,signal.SIG_IGN)\n time.sleep(3)\n open("survived","w").write("leaked")\nelse:\n print("CHILD="+str(pid),flush=True)\n time.sleep(.2)\n')
        self.until(b'CHILD=')
        self.assertEqual(self.worker.wait(timeout=6), 0)
        time.sleep(1.1)
        self.assertFalse(marker.exists(), 'Descendant survived agent exit')

    def test_sigterm_stops_worker_even_with_ignoring_agent(self):
        self.start('import signal,time\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\nprint("READY",flush=True)\ntime.sleep(60)\n')
        self.until(b'READY')
        self.worker.terminate()
        self.assertEqual(self.worker.wait(timeout=6), 0)


if __name__ == '__main__':
    unittest.main()
