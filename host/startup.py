"""Opt-in per-user login startup. Called only after an explicit desktop toggle."""
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile

LABEL = 'app.aterus.desktop'
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME = 'Aterus'
MARKER = 'ATERUS_DESKTOP_STARTUP'


def launch_command(executable=None, script=None, frozen=None):
    executable = str(Path(executable or sys.executable).resolve())
    frozen = bool(getattr(sys, 'frozen', False)) if frozen is None else frozen
    command = [executable]
    if not frozen:
        command.append(str(Path(script or Path(__file__).with_name('desktop.py')).resolve()))
    return command + ['--startup']


def _mac_path(home):
    return Path(home) / 'Library' / 'LaunchAgents' / (LABEL + '.plist')


def _mac_read(path):
    if path.is_symlink():
        raise ValueError('Aterus login item must not be a symbolic link.')
    try:
        with path.open('rb') as stream:
            data = plistlib.load(stream)
    except FileNotFoundError:
        return None
    environment = data.get('EnvironmentVariables') if isinstance(data, dict) else None
    if not isinstance(data, dict) or data.get('Label') != LABEL or not isinstance(environment, dict) or environment.get(MARKER) != '1':
        raise ValueError('A different login item already uses the Aterus identifier.')
    return data


def enabled(command=None, platform=None, home=None, registry=None):
    platform = sys.platform if platform is None else platform
    command = launch_command() if command is None else command
    if platform == 'darwin':
        data = _mac_read(_mac_path(Path.home() if home is None else home))
        return data is not None and data.get('ProgramArguments') == command
    if platform == 'win32':
        if registry is None:
            import winreg as registry
        try:
            with registry.OpenKey(registry.HKEY_CURRENT_USER, RUN_KEY, 0, registry.KEY_READ) as key:
                value, kind = registry.QueryValueEx(key, RUN_NAME)
            return kind == registry.REG_SZ and value == subprocess.list2cmdline(command)
        except FileNotFoundError:
            return False
    return False


def set_enabled(value, command=None, platform=None, home=None, registry=None):
    command = launch_command() if command is None else command
    if not isinstance(command, list) or len(command) not in (2, 3) or command[-1] != '--startup' or any(not isinstance(a, str) or '\0' in a for a in command) or not Path(command[0]).is_absolute():
        raise ValueError('Invalid Aterus startup command.')
    platform = sys.platform if platform is None else platform
    if platform == 'darwin':
        path = _mac_path(Path.home() if home is None else home)
        if path.parent.is_symlink():
            raise ValueError('Login-item folder must not be a symbolic link.')
        existing = _mac_read(path)
        if not value:
            if existing is not None:
                path.unlink()
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {'Label': LABEL, 'ProgramArguments': command, 'RunAtLoad': True,
                'KeepAlive': False, 'EnvironmentVariables': {MARKER:'1'}}
        descriptor, temporary = tempfile.mkstemp(prefix='.aterus-', suffix='.plist', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                plistlib.dump(data, stream)
            os.replace(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
        return
    if platform == 'win32':
        if registry is None:
            import winreg as registry
        with registry.CreateKeyEx(registry.HKEY_CURRENT_USER, RUN_KEY, 0, registry.KEY_READ | registry.KEY_SET_VALUE) as key:
            try:
                previous, kind = registry.QueryValueEx(key, RUN_NAME)
            except FileNotFoundError:
                previous, kind = None, None
            expected = subprocess.list2cmdline(command)
            if previous is not None and (kind != registry.REG_SZ or previous != expected):
                raise ValueError('A different startup command already uses the Aterus entry.')
            if value:
                registry.SetValueEx(key, RUN_NAME, 0, registry.REG_SZ, expected)
            elif previous is not None:
                registry.DeleteValue(key, RUN_NAME)
        return
    raise ValueError('Login startup is supported on macOS and Windows.')
