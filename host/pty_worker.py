"""One terminal per process; no shell is launched between Aterus and the agent."""
import base64
import binascii
import fcntl
import json
import os
import pty
import select
import signal
import struct
import sys
import termios
import time


def main():
    if len(sys.argv) > 1:
        config = json.loads(sys.argv[1])
    else:
        first = bytearray()
        while len(first) <= 65536:
            char = os.read(sys.stdin.fileno(), 1)
            if char in (b'', b'\n'):
                break
            first.extend(char)
        config = json.loads(first)
    pid, master = pty.fork()
    if pid == 0:
        os.chdir(config['cwd'])
        os.environ.update(TERM='xterm-256color', COLUMNS='100', LINES='30')
        for key, value in config.get('environment', {}).items():
            if key in ('OPENCODE_SERVER_USERNAME', 'OPENCODE_SERVER_PASSWORD') and isinstance(value, str):
                os.environ[key] = value
        os.execv(config['argv'][0], config['argv'])
    fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 100, 0, 0))
    os.set_blocking(master, False)
    outgoing = bytearray()
    deadline = None
    status = None
    stdin_open = True
    terminal_open = True

    def signal_child(sig):
        try:
            os.killpg(pid, sig)
        except PermissionError:
            # Restricted hosts may permit our child but deny group signals.
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        except ProcessLookupError:
            pass

    def stop(*_):
        nonlocal deadline
        if deadline is None:
            deadline = time.monotonic() + 2
            signal_child(signal.SIGTERM)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)
    pending = b''
    try:
        while True:
            if status is None:
                done, child_status = os.waitpid(pid, os.WNOHANG)
                if done:
                    status = child_status
                    # A descendant can hold the PTY after its agent exits.
                    stop()
            if deadline is not None and time.monotonic() >= deadline:
                signal_child(signal.SIGKILL)
                break
            if not terminal_open and status is not None:
                # Also terminate descendants that closed their inherited PTY.
                signal_child(signal.SIGKILL)
                break
            readers = ([master] if terminal_open else []) + ([sys.stdin.fileno()] if stdin_open else [])
            ready, writable, _ = select.select(readers, [master] if outgoing and terminal_open and deadline is None else [], [], .05)
            if master in writable:
                try:
                    written = os.write(master, outgoing)
                    del outgoing[:written]
                except BlockingIOError:
                    pass
                except OSError:
                    stop()
            if master in ready:
                try:
                    data = os.read(master, 16384)
                except OSError:
                    data = b''
                if data:
                    print(json.dumps({'output': base64.b64encode(data).decode()}), flush=True)
                else:
                    terminal_open = False
                    stop()
            if stdin_open and sys.stdin.fileno() in ready:
                block = os.read(sys.stdin.fileno(), 16384)
                if not block:
                    stdin_open = False
                    pending = b''
                    stop()
                pending += block
                if len(pending) > 65536:
                    pending = b''
                    stop()
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    try:
                        event = json.loads(line)
                        if not isinstance(event, dict):
                            continue
                        if event.get('stop'):
                            stop()
                        elif deadline is None and terminal_open:
                            if 'input' in event:
                                data = base64.b64decode(event['input'], validate=True)
                                if len(data) <= 16384 and len(outgoing) + len(data) <= 65536:
                                    outgoing.extend(data)
                            elif 'resize' in event:
                                rows, cols = event['resize']
                                if type(rows) is int and type(cols) is int and 10 <= rows <= 150 and 30 <= cols <= 300:
                                    fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
                    except (ValueError, TypeError, OSError, KeyError, binascii.Error):
                        pass
    except (BrokenPipeError, KeyboardInterrupt):
        stop()
    finally:
        # Always clean the agent's process group, even when output consumers vanish.
        signal_child(signal.SIGKILL)
        if status is None:
            _, status = os.waitpid(pid, 0)
        os.close(master)
    try:
        print(json.dumps({'exit': os.waitstatus_to_exitcode(status)}), flush=True)
    except BrokenPipeError:
        pass


if __name__ == '__main__':
    main()
