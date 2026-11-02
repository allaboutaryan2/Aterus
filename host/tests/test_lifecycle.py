import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('lifecycle', ROOT / 'lifecycle.py')
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


class LifecycleTests(unittest.TestCase):
    def test_generated_job_is_scoped_and_does_not_log_owner_url(self):
        with tempfile.TemporaryDirectory() as folder:
            config = lifecycle.launchd_config(ROOT, folder, Path(folder) / 'data')
            self.assertEqual(plistlib.loads(plistlib.dumps(config)), config)
            self.assertEqual(config['Label'], 'app.aterus.agent-hub')
            self.assertEqual(config['StandardOutPath'], '/dev/null')
            self.assertFalse(config['KeepAlive'])
            self.assertNotIn('shell', config)
            self.assertEqual(config['ProgramArguments'][2:4], ['--workspace', str(Path(folder).resolve())])

    def test_invalid_configuration_rejected(self):
        with self.assertRaises(ValueError):
            lifecycle.launchd_config(ROOT, ROOT, ROOT / 'data', port=0)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                lifecycle.launchd_config(folder, ROOT, ROOT / 'data')
