from pathlib import Path
import tempfile
import unittest
import zipfile
import release


class ReleaseTests(unittest.TestCase):
    def test_runtime_secrets_are_excluded_and_required_sources_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';source.mkdir()
            for name in release.FILES:
                (source/name).parent.mkdir(parents=True,exist_ok=True)
                (source/name).write_text('source')
            (source/'public').mkdir();(source/'public'/'app.js').write_text('public code')
            (source/'public'/'.secret').write_text('private')
            (source/'.aterus-data').mkdir();(source/'.aterus-data'/'aterus.db').write_text('private')
            (source/'.env').write_text('private')
            output=root/'release.zip';release.build(source,output)
            with zipfile.ZipFile(output) as archive:
                self.assertIn('Aterus/aterus.py',archive.namelist())
                self.assertFalse(any('secret' in name or '.env' in name or '.aterus-data' in name for name in archive.namelist()))
            (source/'aterus.py').unlink()
            with self.assertRaises(ValueError):release.build(source,output)
