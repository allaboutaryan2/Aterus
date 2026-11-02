"""Optional native Windows ConPTY worker; JSON protocol matches pty_worker.py.

Contract: https://github.com/andfoy/pywinpty/blob/main/winpty/ptyprocess.py
Pass argv as a list: pywinpty applies subprocess.list2cmdline internally.
No command interpreter or shell fallback is started. Native Windows verification
is required; fixtures on other systems only verify this adapter's contract.
"""
import base64
import binascii
import codecs
import json
import ntpath
import os
import queue
import signal
import sys
import threading
import time


MAX_INPUT = 16384
MAX_LINE = 65536


def validate_config(config):
    argv = config.get('argv')
    if not isinstance(argv, list) or not argv or any(not isinstance(a, str) or '\0' in a for a in argv):
        raise ValueError('Expected executable and argument list')
    if not argv[0] or ntpath.splitext(argv[0])[1].lower() in ('.cmd', '.bat', '.ps1'):
        raise ValueError('Windows agents require a native executable; shell wrappers are unsupported')
    cwd = config.get('cwd')
    if not isinstance(cwd, str) or not cwd or '\0' in cwd:
        raise ValueError('Expected workspace path')
    return argv, cwd


def run(config, spawn, backend, source, sink, external_stop=None, stop_grace=2):
    """Run the verified pywinpty public contract (injectable for platform fixtures)."""
    argv, cwd = validate_config(config)
    supplied_env = config.get('environment', {})
    if not isinstance(supplied_env, dict) or any(
            key not in ('OPENCODE_SERVER_USERNAME', 'OPENCODE_SERVER_PASSWORD')
            or not isinstance(value, str) or '\0' in value or len(value) > 16384
            for key, value in supplied_env.items()):
        raise ValueError('Unsupported agent environment')
    environment = os.environ.copy()
    environment.update(supplied_env)
    environment.update(TERM='xterm-256color', COLUMNS='100', LINES='30', PYWINPTY_BACKEND=str(int(backend)))
    # Passing a prequoted string triggers pywinpty's shlex parsing a second time.
    child = spawn(list(argv), cwd=cwd, env=environment, dimensions=(30, 100), backend=backend)
    controls = queue.Queue(maxsize=4)
    output = queue.Queue(maxsize=32)
    writes = queue.Queue(maxsize=4)
    finished = threading.Event()
    stopping = threading.Event()
    reader_done = threading.Event()
    decoder = codecs.getincrementaldecoder('utf-8')('strict')
    exit_code = -1
    deadline = None
    drain_deadline = None

    def enqueue(target, value):
        while not finished.is_set():
            try:
                target.put(value, timeout=.05)
                return
            except queue.Full:
                pass

    def read_controls():
        try:
            while not finished.is_set():
                line = source.readline(MAX_LINE + 1)
                if not line:
                    break
                if len(line) > MAX_LINE:
                    enqueue(controls, {'stop': True})
                    return
                try:
                    event = json.loads(line)
                    if isinstance(event, dict):
                        enqueue(controls, event)
                except (ValueError, TypeError):
                    continue
        finally:
            enqueue(controls, {'stop': True})

    def read_output():
        try:
            while not finished.is_set():
                text = child.read(16384)
                if text:
                    # pywinpty returns Unicode; retain complete UTF-8 characters.
                    enqueue(output, text.encode('utf-8'))
                else:
                    time.sleep(.01)
        except (EOFError, OSError):
            stopping.set()
        finally:
            reader_done.set()

    def write_input():
        while not finished.is_set():
            try:
                text = writes.get(timeout=.05)
            except queue.Empty:
                continue
            if stopping.is_set() or not child.isalive():
                continue
            try:
                child.write(text)
            except (EOFError, OSError):
                stopping.set()

    threads = [threading.Thread(target=fn, daemon=True) for fn in (read_controls, read_output, write_input)]
    for thread in threads:
        thread.start()

    def emit(event):
        sink.write(json.dumps(event) + '\n')
        sink.flush()

    def begin_stop():
        nonlocal deadline
        if deadline is None:
            stopping.set()
            deadline = time.monotonic() + stop_grace
            if child.isalive():
                try:
                    child.sendintr()
                except (EOFError, OSError):
                    pass

    try:
        while True:
            now = time.monotonic()
            alive = child.isalive()
            if not alive:
                stopping.set()
                if drain_deadline is None:
                    drain_deadline = now + 1
            if stopping.is_set() and alive and deadline is None:
                begin_stop()
            if external_stop is not None and external_stop.is_set():
                begin_stop()
            # Bound work per iteration so output floods cannot starve stop events.
            for _ in range(4):
                try:
                    data = output.get_nowait()
                except queue.Empty:
                    break
                emit({'output': base64.b64encode(data).decode('ascii')})
            if not alive and output.empty() and (reader_done.is_set() or now >= drain_deadline):
                exit_code = child.exitstatus
                if not isinstance(exit_code, int):
                    exit_code = -1
                break
            if deadline is not None and now >= deadline:
                child.terminate(force=True)
                deadline = None
                if child.isalive():
                    raise OSError('Windows terminal did not terminate')
            try:
                event = controls.get(timeout=.02)
            except queue.Empty:
                continue
            if event.get('stop'):
                begin_stop()
                continue
            # Recheck identity/liveness before delivering queued input or resize.
            if stopping.is_set() or not child.isalive():
                continue
            try:
                if 'input' in event:
                    raw = base64.b64decode(event['input'], validate=True)
                    if len(raw) > MAX_INPUT:
                        begin_stop()
                        continue
                    text = decoder.decode(raw)
                    if text:
                        writes.put_nowait(text)
                elif 'resize' in event:
                    rows, cols = event['resize']
                    if type(rows) is int and type(cols) is int and 10 <= rows <= 150 and 30 <= cols <= 300:
                        child.setwinsize(rows, cols)
            except queue.Full:
                begin_stop()  # Refuse an input flood instead of silently dropping keys.
            except (ValueError, TypeError, KeyError, binascii.Error):
                decoder.reset()
    finally:
        stopping.set()
        finished.set()
        try:
            child.close(force=True)
        finally:
            # Native reads may remain blocked after ConPTY closes; daemon threads
            # cannot keep this dedicated worker alive. Never wait indefinitely.
            for thread in threads:
                thread.join(timeout=.1)
    emit({'exit': exit_code})
    return exit_code


def read_config(argv, source):
    if len(argv) > 1:
        return json.loads(argv[1])  # Legacy direct-worker fixtures.
    line = source.readline(MAX_LINE + 1)
    if len(line) > MAX_LINE or not line.endswith(b'\n'):
        raise ValueError('Missing or oversized worker configuration')
    return json.loads(line)


def main():
    def report_failure(message):
        print(json.dumps({'output': base64.b64encode((message + '\r\n').encode()).decode()}), flush=True)
        print(json.dumps({'exit': -1}), flush=True)

    if os.name != 'nt':
        report_failure('Windows ConPTY worker requires Windows 10/11.')
        return
    if sys.version_info < (3, 10):
        report_failure('Windows terminal support requires Python 3.10 or newer.')
        return
    try:
        from winpty import PtyProcess, Backend
    except ImportError:
        report_failure('Install Windows terminal support: py -m pip install -r requirements-windows.txt')
        return
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    try:
        config = read_config(sys.argv, sys.stdin.buffer)
        run(config, PtyProcess.spawn, Backend.ConPTY, sys.stdin.buffer, sys.stdout, stop)
    except Exception:
        # Native errors can contain command arguments or account paths.
        report_failure('Windows terminal could not start or closed unexpectedly.')


if __name__ == '__main__':
    main()
