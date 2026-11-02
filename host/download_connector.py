"""Explicit local setup of a pinned official connector; never starts a tunnel."""
import argparse
import hashlib
import io
import os
from pathlib import Path
import platform
import tarfile
import tempfile
import urllib.request

VERSION='2026.10.7'
ASSETS={
 ('Darwin','arm64'):('cloudflared-darwin-arm64.tgz','3586ccf397e98e5f437e60e7c307ca6ac463e110580503af8bb8e6f9ebf831bd'),
 ('Darwin','x86_64'):('cloudflared-darwin-amd64.tgz','02f3edfd87684dd5b705607688e4eb4b323f6e777b81e7b3a85af556aa356848'),
 ('Windows','AMD64'):('cloudflared-windows-amd64.exe','2493dbc168923bb3e59e5e7716f71deced92992eea9acd6e9d74f84ac7751343'),
}


def install(root=None, system=None, machine=None):
    system=system or platform.system();machine=machine or platform.machine()
    if (system,machine) not in ASSETS:raise ValueError('Automatic connector setup supports Mac arm64/x86_64 and Windows x64; install cloudflared separately on this architecture')
    asset,digest=ASSETS[system,machine]
    destination=Path(root or Path(__file__).parent)/'vendor'/'bin'
    if destination.is_symlink():raise ValueError('Refusing linked connector directory')
    destination.mkdir(parents=True,exist_ok=True)
    target=destination/('cloudflared.exe' if system=='Windows' else 'cloudflared')
    if target.is_symlink():raise ValueError('Refusing linked connector executable')
    url='https://github.com/cloudflare/cloudflared/releases/download/'+VERSION+'/'+asset
    # Bounded download and atomic replacement; no install scripts or extraction paths.
    with urllib.request.urlopen(url,timeout=60) as response:
        raw=response.read(80*1024*1024+1)
    if len(raw)>80*1024*1024 or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Official connector download failed digest validation')
    if asset.endswith('.tgz'):
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            entries=[m for m in archive.getmembers() if m.name in ('cloudflared','./cloudflared') and m.isfile()]
            if len(entries)!=1:raise ValueError('Unsupported connector archive')
            content=archive.extractfile(entries[0]).read(150*1024*1024+1)
    else:content=raw
    if len(content)>150*1024*1024:raise ValueError('Connector executable is too large')
    fd,temporary=tempfile.mkstemp(prefix='connector-',dir=destination)
    try:
        with os.fdopen(fd,'wb') as output:output.write(content)
        os.chmod(temporary,0o755);os.replace(temporary,target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--install',action='store_true',help='Download and verify the official connector into this project')
    args=parser.parse_args()
    if not args.install:parser.error('Pass --install to explicitly download the connector; no network connection is started')
    try:print('Verified connector installed at '+str(install())+'; no tunnel was started.')
    except (ValueError,OSError) as error:parser.exit(1,'Connector setup failed: '+str(error)+'\n')
