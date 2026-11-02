"""Login item fixtures only: temporary homes and an in-memory registry."""
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import startup


class Registry:
    HKEY_CURRENT_USER = 1
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1
    def __init__(self):
        self.values = {}
        self.keys = []
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass
    def OpenKey(self, root, path, _, access):
        self.keys.append((root,path))
        return self
    CreateKeyEx = OpenKey
    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError()
        return self.values[name]
    def SetValueEx(self, key, name, reserved, kind, value):
        self.values[name] = (value,kind)
    def DeleteValue(self, key, name):
        del self.values[name]


class StartupTests(unittest.TestCase):
    def test_source_and_frozen_commands_contain_no_owner_credentials(self):
        executable = str(Path(sys.executable).resolve())
        script = str((ROOT / 'desktop.py').resolve())
        self.assertEqual(startup.launch_command(executable, script, False), [executable,script,'--startup'])
        self.assertEqual(startup.launch_command(executable, script, True), [executable,'--startup'])

    def test_mac_enable_disable_only_own_private_login_item(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            command = startup.launch_command()
            self.assertFalse(startup.enabled(command,'darwin',home))
            startup.set_enabled(True,command,'darwin',home)
            path = home / 'Library/LaunchAgents/app.aterus.desktop.plist'
            data = plistlib.loads(path.read_bytes())
            self.assertTrue(startup.enabled(command,'darwin',home))
            self.assertEqual(data['ProgramArguments'],command)
            self.assertTrue(data['RunAtLoad'])
            self.assertFalse(data['KeepAlive'])
            self.assertNotIn('StandardOutPath',data)
            self.assertNotIn('StandardErrorPath',data)
            if os.name != 'nt':
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            unrelated = path.with_name('other.application.plist')
            unrelated.write_bytes(b'unrelated')
            startup.set_enabled(False,command,'darwin',home)
            self.assertFalse(path.exists())
            self.assertEqual(unrelated.read_bytes(),b'unrelated')
            startup.set_enabled(False,command,'darwin',home)
            path.write_bytes(plistlib.dumps({'Label':'unrelated'}))
            with self.assertRaises(ValueError):
                startup.set_enabled(True,command,'darwin',home)
            with self.assertRaises(ValueError):
                startup.set_enabled(False,command,'darwin',home)

    def test_registry_is_current_user_exact_value_and_preserves_unrelated(self):
        registry = Registry()
        command = startup.launch_command()
        registry.values['Other'] = ('unrelated',1)
        self.assertFalse(startup.enabled(command,'win32',registry=registry))
        startup.set_enabled(True,command,'win32',registry=registry)
        self.assertTrue(startup.enabled(command,'win32',registry=registry))
        self.assertEqual(registry.values['Aterus'][0], subprocess.list2cmdline(command))
        startup.set_enabled(False,command,'win32',registry=registry)
        self.assertNotIn('Aterus',registry.values)
        self.assertIn('Other',registry.values)
        self.assertTrue(all(key == (1,startup.RUN_KEY) for key in registry.keys))
        registry.values['Aterus'] = ('different program',1)
        with self.assertRaises(ValueError):
            startup.set_enabled(False,command,'win32',registry=registry)
        self.assertEqual(registry.values['Aterus'][0],'different program')

    def test_invalid_platform_and_command_rejected(self):
        with self.assertRaises(ValueError):
            startup.set_enabled(True,['relative','--startup'],'darwin')
        with self.assertRaises(ValueError):
            startup.set_enabled(True,startup.launch_command(),'linux')


if __name__ == '__main__':
    unittest.main()
