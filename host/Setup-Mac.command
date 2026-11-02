#!/bin/zsh
set -eu
cd "$(dirname "$0")"
python3 download_connector.py --install
exec python3 desktop.py
