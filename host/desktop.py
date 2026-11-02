"""Aterus desktop host. Importing this module starts no GUI or network service."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import webbrowser


def data_directory(platform=None, home=None, environment=None):
    platform = sys.platform if platform is None else platform
    home = Path.home() if home is None else Path(home)
    environment = os.environ if environment is None else environment
    if platform == 'darwin':
        return home / 'Library' / 'Application Support' / 'Aterus'
    if platform == 'win32':
        base = Path(environment.get('LOCALAPPDATA') or home / 'AppData' / 'Local')
        return base / 'Aterus'
    return Path(environment.get('XDG_DATA_HOME') or home / '.local' / 'share') / 'aterus'


def workspace_path(value):
    if not isinstance(value, str) or not value or '\0' in value:
        raise ValueError('Choose an existing project folder.')
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.is_dir():
        raise ValueError('Choose an existing project folder with an absolute path.')
    path = path.resolve()
    if path == Path(path.anchor):
        raise ValueError('Choose a project folder instead of the entire filesystem.')
    return path


def load_workspace(directory):
    config = Path(directory) / 'desktop.json'
    try:
        if config.is_symlink() or config.stat().st_size > 32768:
            return None
        data = json.loads(config.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or set(data) != {'workspace'}:
            return None
        return workspace_path(data['workspace'])
    except (OSError, ValueError, TypeError):
        return None


def save_workspace(directory, workspace):
    workspace = workspace_path(str(workspace))
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink():
        raise ValueError('Aterus data folder must not be a symbolic link.')
    os.chmod(directory, 0o700)
    descriptor, temporary = tempfile.mkstemp(prefix='.desktop-', suffix='.json', dir=directory)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump({'workspace': str(workspace)}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, directory / 'desktop.json')
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def discover_cli_path(environment=None, home=None, platform=None):
    """Append standard CLI install locations, preserving the user's existing PATH."""
    environment = os.environ if environment is None else environment
    home = Path.home() if home is None else Path(home)
    platform = sys.platform if platform is None else platform
    paths = [p for p in environment.get('PATH', '').split(os.pathsep) if p and Path(p).is_absolute()]
    if platform == 'win32':
        candidates = [home / '.local' / 'bin', home / 'scoop' / 'shims',
                      Path(environment.get('APPDATA') or home / 'AppData' / 'Roaming') / 'npm']
    else:
        candidates = [home / '.local' / 'bin', home / '.opencode' / 'bin', home / '.kiro' / 'bin', home / '.bun' / 'bin', home / '.cargo' / 'bin', home / '.npm-global' / 'bin',
                      Path('/opt/homebrew/bin'), Path('/usr/local/bin'), Path('/usr/bin'), Path('/bin')]
    for candidate in candidates:
        value = str(candidate)
        if candidate.is_dir() and value not in paths:
            paths.append(value)
    environment['PATH'] = os.pathsep.join(paths)
    return environment['PATH']


def select_agent_binaries(home=None):
    """Prefer a detected modern per-user OpenCode over the unrelated legacy CLI."""
    import agents
    home=Path.home() if home is None else Path(home)
    candidate=home/'.opencode'/'bin'/('opencode.exe' if os.name=='nt' else 'opencode')
    if not candidate.is_file() or not os.access(candidate,os.X_OK):return
    current=agents.EXECUTABLES['opencode']
    if agents.controls('opencode')['variant']=='modern':return
    agents.EXECUTABLES['opencode']=str(candidate)
    if agents.controls('opencode')['variant']!='modern':agents.EXECUTABLES['opencode']=current


class DesktopHost:
    def __init__(self, data, workspace, hub_factory=None, server_factory=None, opener=None):
        self.data = Path(data)
        self.workspace = workspace_path(str(workspace))
        self.hub_factory = hub_factory
        self.server_factory = server_factory
        self.opener = opener or webbrowser.open
        self.hub = self.server = self.thread = None
        self.url = ''
        self.bootstrap_opened = False

    def start(self):
        if self.server is not None:
            raise RuntimeError('Aterus is already running.')
        if self.hub_factory is None or self.server_factory is None:
            import aterus
            self.hub_factory = self.hub_factory or aterus.Hub
            self.server_factory = self.server_factory or aterus.create_server
        hub = self.hub_factory(self.data, self.workspace)
        try:
            server = self.server_factory(hub, 0)
            self.hub, self.server = hub, server
            self.url = 'http://127.0.0.1:%d/' % server.server_address[1]
            self.thread = threading.Thread(target=server.serve_forever, name='Aterus HTTP', daemon=True)
            self.thread.start()
        except BaseException:
            if self.server is not None:
                self.server.server_close()
            hub.close()
            self.hub = self.server = self.thread = None
            raise
        return self.url

    def open_dashboard(self):
        if self.hub is None:
            raise RuntimeError('Aterus is not running.')
        url = self.url if self.bootstrap_opened else self.url + '#owner=' + self.hub.bootstrap
        opened = self.opener(url, new=2)
        if opened:
            self.bootstrap_opened = True
        return bool(opened)

    def stop(self):
        server, hub, thread = self.server, self.hub, self.thread
        self.server = self.hub = self.thread = None
        try:
            if server is not None:
                try:
                    if thread is not None and thread.is_alive():
                        server.shutdown()
                        thread.join(timeout=5)
                finally:
                    server.server_close()
        finally:
            if hub is not None:
                hub.close()


def _restore_worker_streams():
    """Windowed frozen executables still need inherited anonymous worker pipes."""
    import io
    for name, descriptor, mode in (('stdin', 0, 'rb'), ('stdout', 1, 'wb'), ('stderr', 2, 'wb')):
        if getattr(sys, name) is not None:
            continue
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            import msvcrt
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetStdHandle.argtypes = [wintypes.DWORD]
            kernel.GetStdHandle.restype = wintypes.HANDLE
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            kernel.DuplicateHandle.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
                                              ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD,
                                              wintypes.BOOL, wintypes.DWORD]
            kernel.DuplicateHandle.restype = wintypes.BOOL
            handle = kernel.GetStdHandle((-10 - descriptor) & 0xffffffff)
            duplicate = wintypes.HANDLE()
            process = kernel.GetCurrentProcess()
            if not handle or handle == wintypes.HANDLE(-1).value or not kernel.DuplicateHandle(process, handle, process, ctypes.byref(duplicate), 0, False, 2):
                raise RuntimeError('Aterus worker requires inherited private pipes.')
            descriptor_copy = msvcrt.open_osfhandle(duplicate.value, os.O_BINARY | (os.O_RDONLY if descriptor == 0 else os.O_WRONLY))
        else:
            descriptor_copy = os.dup(descriptor)
        binary = os.fdopen(descriptor_copy, mode, buffering=0)
        setattr(sys, name, io.TextIOWrapper(binary, encoding='utf-8', errors='strict', write_through=True))


def dispatch_worker(argv=None):
    argv = sys.argv if argv is None else argv
    if len(argv) < 2 or argv[1] != '--aterus-worker':
        return False
    expected = 'windows' if os.name == 'nt' else 'posix'
    if len(argv) != 3 or argv[2] != expected:
        raise ValueError('Invalid Aterus worker platform.')
    _restore_worker_streams()
    import importlib
    worker = importlib.import_module('windows_worker' if expected == 'windows' else 'pty_worker')
    previous = sys.argv
    try:
        sys.argv = [previous[0]]  # Configuration arrives through stdin, never process arguments.
        worker.main()
    finally:
        sys.argv = previous
    return True


def self_test():
    """Headless packaged-runtime check; no GUI, owner token or tunnel activation."""
    _restore_worker_streams()
    import http.client
    import pairing
    import connectivity
    with tempfile.TemporaryDirectory(prefix='aterus-desktop-check-') as directory:
        root=Path(directory);workspace=root/'workspace';workspace.mkdir()
        host=DesktopHost(root/'data',workspace)
        try:
            host.start()
            connection=http.client.HTTPConnection('127.0.0.1',host.server.server_address[1],timeout=4)
            connection.request('GET','/');response=connection.getresponse();response.read();shell_status=response.status
            connection.request('GET','/api/state');response=connection.getresponse();response.read();auth_status=response.status;connection.close()
            print(json.dumps({'public_shell_status':shell_status,'unpaired_api_status':auth_status,
                'qr_svg_bytes':len(pairing.qr_svg('https://test.example/#pair=ABCDEF123456')),
                'connector_available':bool(connectivity.connector_executable()),'tunnel_started':False}))
        finally:host.stop()
    return 0


def main():
    if dispatch_worker():
        return 0
    if '--self-test' in sys.argv[1:]:
        return self_test()
    # Import lazily: workers and tests must not require Tk or a display server.
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ImportError:
        raise RuntimeError('Aterus Desktop requires a Python build with Tk, or the packaged desktop app.') from None
    startup_launch = '--startup' in sys.argv[1:]
    discover_cli_path()
    select_agent_binaries()
    root = tk.Tk()
    root.withdraw()
    root.title('Aterus')
    directory = data_directory()
    workspace = load_workspace(directory)
    host = None
    status = tk.StringVar(value='Choose the project folder your agents may access.')
    workspace_text = tk.StringVar(value='No workspace selected')

    def choose_workspace():
        nonlocal workspace, host
        selected = filedialog.askdirectory(parent=root, title='Choose the workspace Aterus agents may access', mustexist=True,
                                           initialdir=str(workspace or Path.home()))
        if not selected:
            return False
        try:
            chosen = workspace_path(selected)
            save_workspace(directory, chosen)
            if host is not None:
                host.stop()
            workspace = chosen
            host = None
            start_host()
            return True
        except (OSError, ValueError, RuntimeError):
            status.set('Could not open this workspace. Select an accessible project folder.')
            messagebox.showerror('Aterus', 'Could not start Aterus for that folder. Check folder access and that no other Aterus host is running.', parent=root)
            return False

    def open_dashboard():
        try:
            if host is not None and host.open_dashboard():
                status.set('Running privately on this Mac.' if sys.platform == 'darwin' else 'Running privately on this computer.')
            else:
                status.set('Browser could not open. Check your default browser and try Open Aterus again.')
        except Exception:
            status.set('Browser could not open. Check your default browser and try again.')

    def start_host():
        nonlocal host
        status.set('Starting the private host…')
        candidate = DesktopHost(directory, workspace)
        candidate.start()
        host = candidate
        workspace_text.set(str(workspace))
        if startup_launch:
            status.set('Running privately. Select Open Aterus when you want to use the dashboard.')
        else:
            open_dashboard()

    def check_host():
        if host is not None and host.hub is not None and host.hub.pair_gate.requests():
            status.set('A phone is waiting for approval. Open Aterus → Devices and compare its verification code.')
        if host is not None and host.thread is not None and not host.thread.is_alive():
            status.set('The private host stopped unexpectedly. Quit and reopen Aterus to restart it.')
        root.after(2000, check_host)

    def quit_app():
        nonlocal host
        status.set('Stopping agents and the private host…')
        if host is not None:
            host.stop()
            host = None
        root.destroy()

    body = tk.Frame(root, padx=28, pady=24)
    body.pack(fill='both', expand=True)
    tk.Label(body, text='aterus ↗', font=('Helvetica', 30, 'bold'), anchor='w').pack(fill='x')
    tk.Label(body, text='Your agents, within reach.', anchor='w').pack(fill='x', pady=(0, 20))
    tk.Label(body, textvariable=status, wraplength=440, justify='left', anchor='w').pack(fill='x')
    tk.Label(body, textvariable=workspace_text, wraplength=440, justify='left', anchor='w', fg='#59654f').pack(fill='x', pady=16)
    tk.Button(body, text='Open Aterus', command=open_dashboard).pack(fill='x', pady=4)
    tk.Button(body, text='Choose workspace…', command=choose_workspace).pack(fill='x', pady=4)
    import startup
    try:
        startup_value = tk.BooleanVar(value=startup.enabled())
    except (OSError, ValueError):
        startup_value = tk.BooleanVar(value=False)
    def change_startup():
        requested = bool(startup_value.get())
        try:
            startup.set_enabled(requested)
            status.set('Aterus will start at your next sign-in.' if requested else 'Start at sign-in is disabled.')
        except (OSError, ValueError):
            startup_value.set(not requested)
            messagebox.showerror('Aterus', 'Could not change the Aterus login item. Existing unrelated entries were preserved.', parent=root)
    tk.Checkbutton(body, text='Start Aterus when I sign in', variable=startup_value,
                   command=change_startup, state='normal' if sys.platform in ('darwin','win32') else 'disabled').pack(anchor='w', pady=(12, 0))
    tk.Button(body, text='Help and updates ↗', command=lambda: webbrowser.open('https://aterus-connect.allaboutaryan2.chatgpt.site', new=2)).pack(fill='x', pady=4)
    tk.Button(body, text='Quit Aterus', command=quit_app).pack(fill='x', pady=(16, 0))
    tk.Label(body, text='Keep this host open to use your phone. Pair devices inside Aterus.\nRemote access and operating-system permissions stay under your control.',
             wraplength=440, justify='left', anchor='w').pack(fill='x', pady=(16, 0))
    root.protocol('WM_DELETE_WINDOW', quit_app)
    root.resizable(False, False)
    root.deiconify()
    if workspace is None:
        if startup_launch:
            status.set('Choose a workspace to start Aterus. No service was started automatically.')
        else:
            root.after(100, choose_workspace)
    else:
        try:
            start_host()
        except (OSError, ValueError, RuntimeError):
            status.set('Could not start the private host. Close any other Aterus instance, or choose another workspace.')
    root.after(2000, check_host)
    try:
        root.mainloop()
    finally:
        if host is not None:
            host.stop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
