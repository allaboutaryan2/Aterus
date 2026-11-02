#!/usr/bin/env python3
"""Build the desktop app using explicitly installed build requirements; no downloads."""
import argparse
import os
import importlib.util
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist-dir', type=Path, default=Path(__file__).resolve().parent / 'dist')
    args = parser.parse_args()
    if importlib.util.find_spec('PyInstaller') is None:
        parser.error('PyInstaller is not installed. In your chosen build environment, install requirements-build.txt first.')
    if sys.platform == 'win32' and importlib.util.find_spec('winpty') is None:
        parser.error('Windows builds require pywinpty from requirements-build.txt.')
    root = Path(__file__).resolve().parent
    command = [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
               '--distpath', str(args.dist_dir.resolve()), '--workpath', str(root / 'build' / 'desktop'),
               str(root / 'desktop.spec')]
    environment=os.environ.copy()
    environment['PYINSTALLER_CONFIG_DIR']=str(root/'build'/'pyinstaller-cache')
    return subprocess.call(command, cwd=root, env=environment)


if __name__ == '__main__':
    raise SystemExit(main())
