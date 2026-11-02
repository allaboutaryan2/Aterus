# Build on macOS for Aterus.app, Windows for Aterus.exe; no cross compilation.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

root = Path(SPECPATH)
data = [(str(root / 'public'), 'public'),(str(root/'vendor'), 'vendor')]
# Optional user-provided tunnel executable must retain its own third-party notices.
# vendor includes the verified connector, QR encoder and third-party notices.
imports = ['aterus', 'agents', 'terminal_view', 'live_attach', 'connectivity', 'lifecycle', 'startup']
imports += ['windows_worker'] if sys.platform == 'win32' else ['pty_worker']
imports += [p.stem for p in root.glob('*pair*.py')]
binaries = []
if sys.platform == 'win32':
    imports += collect_submodules('winpty')
    binaries += collect_dynamic_libs('winpty')
a = Analysis([str(root / 'desktop.py')], pathex=[str(root)], binaries=binaries,
             datas=data, hiddenimports=imports, hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Aterus', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          disable_windowed_traceback=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Aterus')
if sys.platform == 'darwin':
    app = BUNDLE(collection, name='Aterus.app', icon=str(root/'public'/'Aterus.icns'),
                 bundle_identifier='app.aterus.desktop',
                 info_plist={'CFBundleName':'Aterus', 'CFBundleDisplayName':'Aterus',
                             'CFBundleShortVersionString':'0.1.0', 'CFBundleVersion':'1',
                             'NSHighResolutionCapable':True})
