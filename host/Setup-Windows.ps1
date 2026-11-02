$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
py -3 -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'"
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.10+ and its py launcher first.' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the local Python environment.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-windows.txt
if ($LASTEXITCODE -ne 0) { throw 'Windows terminal dependency installation failed.' }
& '.\.venv\Scripts\python.exe' download_connector.py --install
if ($LASTEXITCODE -ne 0) { throw 'Connector setup failed; you can still use Aterus locally.' }
Write-Host 'Ready. Run Start-Aterus.cmd. Use native agent executables; shell shims are not supported.'
