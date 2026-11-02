"""Build a desktop host distribution from an explicit, credential-free allowlist."""
import argparse
from pathlib import Path
import zipfile

FILES = ('aterus.py','agents.py','pty_worker.py','windows_worker.py','terminal_view.py',
         'live_attach.py','lifecycle.py','connectivity.py','pairing.py','desktop.py','startup.py',
         'vendor/qrcodegen.py','vendor/NOTICE.md','download_connector.py','build-desktop.py','desktop.spec','requirements-build.txt','requirements-windows.txt','Start-Aterus.command',
         'Start-Aterus.cmd','Setup-Mac.command','Setup-Windows.ps1','CONNECT.md','Caddyfile.example')


def build(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    selected = [source/name for name in FILES]
    for name in ('vendor/qrcodegen.py','vendor/NOTICE.md','vendor/bin/cloudflared-LICENSE','vendor/bin/NOTICE.md','vendor/PyInstaller-COPYING.txt','vendor/Python-LICENSE.txt'):
        path=source/name
        if path.is_file():selected.append(path)
    selected += [p for p in (source/'public').rglob('*') if p.is_file() and not p.is_symlink()
                 and not any(part.startswith('.') for part in p.relative_to(source/'public').parts)]
    selected = sorted(set(selected))
    for path in selected:
        if not path.is_file() or path.is_symlink():
            raise ValueError('Required release source missing or linked: '+path.name)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(selected):
            archive.write(path,Path('Aterus')/path.relative_to(source))
    return len(selected)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination')
    args=parser.parse_args()
    print(str(build(Path(__file__).parent,args.destination))+' source files packaged; runtime data excluded')
