import hashlib,io,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import download_connector as installer

class DownloadTests(unittest.TestCase):
    def test_pinned_digest_and_archive_exact_regular_file(self):
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w:gz') as tar:
            data=b'known-executable';item=tarfile.TarInfo('cloudflared');item.size=len(data);tar.addfile(item,io.BytesIO(data))
            data2=b'never-extract';item=tarfile.TarInfo('../outside');item.size=len(data2);tar.addfile(item,io.BytesIO(data2))
        raw=archive.getvalue()
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(installer.ASSETS,{('Darwin','arm64'):('cloudflared-darwin-arm64.tgz',hashlib.sha256(raw).hexdigest())}),patch.object(installer.urllib.request,'urlopen',return_value=io.BytesIO(raw)):
                target=installer.install(directory,'Darwin','arm64')
            self.assertEqual(target.read_bytes(),b'known-executable')
            self.assertFalse((Path(directory)/'outside').exists())
            with patch.dict(installer.ASSETS,{('Windows','AMD64'):('cloudflared-windows-amd64.exe','0'*64)}),patch.object(installer.urllib.request,'urlopen',return_value=io.BytesIO(b'wrong')):
                with self.assertRaisesRegex(ValueError,'digest'):installer.install(directory,'Windows','AMD64')
            self.assertFalse((Path(directory)/'vendor/bin/cloudflared.exe').exists())

    def test_unsupported_architecture_or_linked_target_never_downloads(self):
        with patch.object(installer.urllib.request,'urlopen') as fetch:
            with self.assertRaises(ValueError):installer.install('/tmp','Windows','unknown')
            fetch.assert_not_called()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'vendor/bin';path.mkdir(parents=True)
            (path/'cloudflared').symlink_to(Path(directory)/'outside')
            with patch.object(installer.urllib.request,'urlopen') as fetch:
                with self.assertRaisesRegex(ValueError,'linked'):installer.install(directory,'Darwin','arm64')
                fetch.assert_not_called()
