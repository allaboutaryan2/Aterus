"""Explicit, optional Quick Tunnel lifecycle; never installs or changes accounts.

Official command/limits: https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/
Flags: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/run-parameters/
The callback manages ONLY Aterus's temporary origin, never manual origins.
"""
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time


CONNECTOR_ROOT = Path(__file__).resolve().parent
INSTALL_URL = 'https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/'
QUICK_ORIGIN = re.compile(r'https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.trycloudflare\.com\Z')
URL_TOKEN = re.compile(r'https://[^\s"<>|]+')


def connector_executable():
    """Prefer an installed native connector, then Aterus's private bundled binary."""
    installed = shutil.which('cloudflared')
    if installed and Path(installed).suffix.lower() not in ('.cmd', '.bat', '.ps1'):
        return installed
    filename = 'cloudflared.exe' if os.name == 'nt' else 'cloudflared'
    bundled = CONNECTOR_ROOT / 'vendor' / 'bin' / filename
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return str(bundled)
    return None


def reported_origin(line):
    """Accept an exact HTTPS DNS origin, never URL prefixes, paths or credentials."""
    for token in URL_TOKEN.findall(line):
        if QUICK_ORIGIN.fullmatch(token):
            return token
    return ''


class QuickTunnel:
    def __init__(self, port, on_origin, *, startup_timeout=45, stop_timeout=3):
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('Expected the active loopback server port')
        if not callable(on_origin):
            raise ValueError('Expected an origin callback')
        self.port = port
        self.on_origin = on_origin
        self.startup_timeout = max(.05, float(startup_timeout))
        self.stop_timeout = max(.05, float(stop_timeout))
        self._lock = threading.RLock()
        self._lifecycle = threading.RLock()
        self._process = None
        self._generation = 0
        self._cancel = None
        self._origin = ''
        self._state = 'stopped'
        self._message = 'Secure phone connection is stopped.'

    @property
    def enabled(self):
        with self._lock:
            return self._state in ('starting', 'ready')

    def status(self):
        with self._lock:
            return {'state': self._state, 'origin': self._origin, 'enabled': self.enabled,
                    'installed': bool(connector_executable()), 'message': self._message,
                    'install_url': INSTALL_URL, 'temporary': True,
                    'phone_verified': False}

    def _clear_origin(self):
        # Called under _lock. A stopped unused manager must not clear manual config.
        if self._origin:
            self._origin = ''
            try:
                self.on_origin('')
            except Exception:
                return False
        return True

    def start(self):
        """Caller must obtain explicit user intent before exposing the service."""
        with self._lifecycle, self._lock:
            if self._state in ('starting', 'ready'):
                return self.status()
            if self._process is not None and self._process.poll() is None:
                self._state = 'failed'
                self._message = 'The previous connector is still running. Stop it before retrying.'
                return self.status()
            executable = connector_executable()
            if not executable:
                self._state = 'failed'
                self._message = 'The bundled connector is missing or not executable. Reinstall the complete Aterus package, or install cloudflared from the official download page and retry.'
                return self.status()
            # Quick Tunnels do not require account config. Preserve existing files
            # rather than renaming/deleting a user's configured tunnels.
            config_roots = [Path.home() / '.cloudflared', Path('/etc/cloudflared'), Path('/usr/local/etc/cloudflared')]
            if any((root / name).is_file() for root in config_roots for name in ('config.yml', 'config.yaml')):
                self._state = 'failed'
                self._message = 'Existing cloudflared configuration detected. Use a separately configured tunnel; Aterus will not modify your configuration.'
                return self.status()
            if not self._clear_origin():
                self._state = 'failed'
                self._message = 'Could not revoke the previous origin. Restart Aterus before retrying.'
                return self.status()
            self._generation += 1
            generation = self._generation
            self._cancel = threading.Event()
            cancel = self._cancel
            self._state = 'starting'
            self._message = 'Requesting a temporary HTTPS address and waiting for Cloudflare to connect.'
            environment = {key: value for key, value in os.environ.items()
                           if not key.startswith(('TUNNEL_', 'CLOUDFLARE_', 'CF_TUNNEL_'))}
            environment['NO_AUTOUPDATE'] = 'true'
            options = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.PIPE,
                       'stderr': subprocess.STDOUT, 'env': environment, 'shell': False}
            if os.name == 'nt':
                options['creationflags'] = subprocess.CREATE_NO_WINDOW
            else:
                options['start_new_session'] = True
            try:
                process = subprocess.Popen([executable, 'tunnel', '--no-autoupdate', '--url',
                                            'http://127.0.0.1:' + str(self.port)], **options)
            except OSError:
                self._state = 'failed'
                self._message = 'Could not start cloudflared. Check the installed executable and retry.'
                return self.status()
            self._process = process
            threading.Thread(target=self._monitor, args=(process, generation, cancel), daemon=True).start()
            return self.status()

    def _terminate(self, process):
        """Only signal the owned Popen handle; never kill by discovered PID/name."""
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=self.stop_timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=self.stop_timeout)
            return process.poll() is not None
        except (OSError, subprocess.TimeoutExpired):
            return process.poll() is not None

    def _fail(self, process, generation, cancel, message):
        with self._lock:
            if generation != self._generation:
                return
            cancel.set()
            revoked = self._clear_origin()
            self._state = 'failed'
            self._message = message if revoked else 'Could not revoke the temporary origin safely. Restart Aterus before retrying.'
        self._terminate(process)

    def _monitor(self, process, generation, cancel):
        events = queue.Queue(maxsize=32)
        reader_done = threading.Event()

        def send(event):
            while not cancel.is_set():
                try:
                    events.put(event, timeout=.05)
                    return
                except queue.Full:
                    continue

        def drain():
            pending = b''
            dropping = False
            try:
                stream = process.stdout
                read = getattr(stream, 'read1', stream.read)
                while not cancel.is_set():
                    block = read(4096)
                    if not block:
                        break
                    for piece in block.splitlines(keepends=True):
                        if not dropping:
                            pending += piece
                            if len(pending) > 8192:
                                pending = b''
                                dropping = True
                        if piece.endswith((b'\n', b'\r')):
                            if not dropping:
                                line = pending.decode('utf-8', errors='replace')
                                origin = reported_origin(line)
                                if origin:
                                    send(('origin', origin))
                                if 'Registered tunnel connection' in line:
                                    send(('connected', ''))
                            pending = b''
                            dropping = False
                # A final short line without a newline may contain the banner URL.
                if pending and not dropping:
                    origin = reported_origin(pending.decode('utf-8', errors='replace'))
                    if origin:
                        send(('origin', origin))
            except (OSError, ValueError):
                pass
            finally:
                reader_done.set()
                try:
                    process.stdout.close()
                except OSError:
                    pass

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        candidate = ''
        connected = False
        deadline = time.monotonic() + self.startup_timeout
        try:
            while not cancel.is_set():
                if process.poll() is not None:
                    self._fail(process, generation, cancel, 'Cloudflare connection ended. Start a new connection to get a new address.')
                    return
                if time.monotonic() >= deadline and not (candidate and connected):
                    self._fail(process, generation, cancel, 'Cloudflare did not connect before the timeout. Check network access and retry.')
                    return
                try:
                    kind, value = events.get(timeout=.05)
                except queue.Empty:
                    if reader_done.is_set():
                        self._fail(process, generation, cancel, 'Cloudflare stopped reporting its connection. Retry after checking the installed CLI and network.')
                        return
                    continue
                if kind == 'origin':
                    if candidate and candidate != value:
                        self._fail(process, generation, cancel, 'Cloudflare reported conflicting addresses. Connection stopped; retry.')
                        return
                    candidate = value
                elif kind == 'connected':
                    connected = True
                if candidate and connected:
                    with self._lock:
                        if generation != self._generation or cancel.is_set():
                            return
                        if not self._origin:
                            self._origin = candidate
                            self.on_origin(candidate)
                        self._state = 'ready'
                        self._message = 'Cloudflare is connected. Open this address on your phone and pair it. Phone access has not been verified.'
        except Exception:
            self._fail(process, generation, cancel, 'Could not enable the temporary origin safely. Connection stopped.')
        finally:
            reader.join(timeout=.2)

    def stop(self):
        with self._lifecycle:
            with self._lock:
                self._generation += 1
                if self._cancel is not None:
                    self._cancel.set()
                revoked = self._clear_origin()
                process = self._process
                self._state = 'stopped' if revoked else 'failed'
                self._message = ('Secure phone connection is stopped. Its previous address is no longer trusted.' if revoked
                                 else 'Could not revoke the temporary origin safely. Restart Aterus before retrying.')
            if process is not None and not self._terminate(process):
                with self._lock:
                    self._state = 'failed'
                    self._message = 'The temporary origin was revoked, but the connector did not stop. Close this Aterus process before retrying.'
            return self.status()
