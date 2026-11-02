#!/usr/bin/env python3
"""Prepare user-scoped launchd configuration; never installs or starts it implicitly."""
import argparse
import os
from pathlib import Path
import plistlib
import shlex
import sys

LABEL = 'app.aterus.agent-hub'


def launchd_config(project, workspace, data_dir, python=sys.executable, port=4380):
    project, workspace, data_dir = (Path(p).expanduser().resolve() for p in (project, workspace, data_dir))
    python = Path(python).expanduser().resolve()
    if not (project / 'aterus.py').is_file():
        raise ValueError('Project must contain aterus.py')
    if not workspace.is_dir():
        raise ValueError('Workspace must exist')
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError('Python executable must exist and be executable')
    if not 1024 <= port <= 65535:
        raise ValueError('Port must be between 1024 and 65535')
    return {
        'Label': LABEL,
        'ProgramArguments': [str(python), str(project / 'aterus.py'), '--workspace', str(workspace), '--data-dir', str(data_dir), '--port', str(port)],
        'WorkingDirectory': str(project),
        'RunAtLoad': True,
        'KeepAlive': False,
        'ProcessType': 'Background',
        'EnvironmentVariables': {'PATH': os.environ.get('PATH', '/usr/bin:/bin:/usr/sbin:/sbin')},
        # Startup URLs contain one-use owner credentials; never send them to log files.
        'StandardOutPath': '/dev/null',
        'StandardErrorPath': '/dev/null',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-plist', required=True, help='Output file; existing files are never overwritten')
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--data-dir', default=str(Path.home() / '.aterus'))
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--port', type=int, default=4380)
    args = parser.parse_args()
    try:
        config = launchd_config(Path(__file__).parent, args.workspace, args.data_dir, args.python, args.port)
        output = Path(args.write_plist).expanduser().absolute()
        with output.open('xb') as stream:
            os.chmod(output, 0o600)
            plistlib.dump(config, stream)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    q = shlex.quote
    print('Created ' + str(output))
    print('First run Aterus manually and pair your owner browser using the same data directory.')
    print('Then stop the manual service. To enable startup on macOS, run:')
    print('mkdir -p "$HOME/Library/LaunchAgents"')
    print('cp ' + q(str(output)) + ' "$HOME/Library/LaunchAgents/' + LABEL + '.plist"')
    print('launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/' + LABEL + '.plist"')
    print('To disable startup (session history is preserved):')
    print('launchctl bootout "gui/$(id -u)/' + LABEL + '"')
    print('rm "$HOME/Library/LaunchAgents/' + LABEL + '.plist"')
    print('Updates: stop the service, back up its data directory, replace application files, run tests, then start again. No automatic update source is configured.')


if __name__ == '__main__':
    main()
