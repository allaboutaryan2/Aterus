"""Explicitly enabled, read-only views of owned foreground agents in Terminal.app.

No terminal input, process signaling, shell attachment or permission changes. Clients
must use IDs resolved by the service to retained discovery records, never supply pins.
"""
import hashlib
import os
from pathlib import Path
import sys

from agents import probe

AGENT_NAMES = frozenset(('claude', 'opencode', 'codex', 'kiro-cli', 'gemini', 'pi'))

# argv carries the tty as data: no string interpolation into AppleScript source.
READ_HISTORY = '''on run argv
    set targetTTY to item 1 of argv
    tell application "Terminal"
        repeat with w in windows
            repeat with t in tabs of w
                if tty of t is targetTTY then
                    set oldHistory to history of t
                    set oldLines to paragraphs of oldHistory
                    set firstLine to (count of oldLines) - 399
                    if firstLine < 1 then set firstLine to 1
                    set AppleScript's text item delimiters to linefeed
                    set resultText to (items firstLine thru -1 of oldLines) as text
                    set AppleScript's text item delimiters to ""
                    return resultText
                end if
            end repeat
        end repeat
    end tell
    error "ATERUS_TAB_NOT_FOUND" number 9101
end run
'''


class TerminalViewError(ValueError):
    pass


class TerminalView:
    def __init__(self, enabled=False):
        self.enabled = enabled

    def _check_enabled(self):
        if not self.enabled:
            raise TerminalViewError('External Terminal viewing is disabled; enable --external-terminal-view on the Mac')
        if sys.platform != 'darwin':
            raise TerminalViewError('External Terminal viewing requires macOS Terminal.app')

    def _processes(self, pid=None):
        argv = ['/bin/ps', '-axo', 'pid=,uid=,tty=,stat=,lstart=,comm=']
        if pid is not None:
            if not isinstance(pid, int) or pid <= 0:
                raise TerminalViewError('Invalid external process identity')
            argv = ['/bin/ps', '-p', str(pid), '-o', 'pid=,uid=,tty=,stat=,lstart=,comm=']
        code, output, error = probe(argv)
        if error or code not in (0, 1):
            raise TerminalViewError('Process inspection is blocked by the execution environment')
        if code == 1:
            if pid is not None and not output.strip():
                return []
            raise TerminalViewError('Process inspection is blocked by the execution environment')
        records = []
        for line in output.splitlines():
            parts = line.split(None, 9)
            if len(parts) != 10:
                continue
            try:
                found_pid, uid = int(parts[0]), int(parts[1])
            except ValueError:
                continue
            tty, stat, executable = parts[2], parts[3], parts[9]
            name = Path(executable).name
            if uid != os.getuid() or name not in AGENT_NAMES or '+' not in stat or any(c in stat for c in 'ZX'):
                continue
            # Terminal.app ttys on macOS; avoid console, ptys and unassociated tabs.
            if not tty.startswith('ttys') or not tty[4:].isdigit():
                continue
            records.append({'pid':found_pid, 'uid':uid, 'tty':'/dev/'+tty,
                            'started':' '.join(parts[4:9]), 'executable':executable,
                            'agent':name})
        return records

    def _cwd(self, pid, workspace):
        code, output, error = probe(['/usr/sbin/lsof', '-a', '-p', str(pid), '-d', 'cwd', '-Fn'])
        if error or code != 0:
            raise TerminalViewError('Working directory inspection is unavailable for this process')
        paths = [line[1:] for line in output.splitlines() if line.startswith('n')]
        if len(paths) != 1:
            raise TerminalViewError('Working directory could not be verified')
        try:
            root = Path(workspace).expanduser().resolve(strict=True)
            cwd = Path(paths[0]).resolve(strict=True)
            if not root.is_dir() or not cwd.is_dir():
                raise ValueError()
            cwd.relative_to(root)
        except (OSError, ValueError):
            raise TerminalViewError('External agent is outside the allowed workspace')
        return str(cwd), str(root)

    def discover(self, workspace):
        self._check_enabled()
        root = Path(workspace).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise TerminalViewError('Workspace directory does not exist')
        records = []
        for record in self._processes():
            try:
                record['cwd'], record['workspace'] = self._cwd(record['pid'], root)
            except TerminalViewError:
                continue
            identity = '\0'.join(str(record[k]) for k in ('pid','uid','tty','started','executable','cwd','workspace'))
            record['id'] = hashlib.sha256(identity.encode()).hexdigest()[:32]
            records.append(record)
        return records

    def _verify(self, record):
        fresh = self._processes(record.get('pid'))
        if len(fresh) != 1 or any(fresh[0][key] != record.get(key) for key in ('pid','uid','tty','started','executable')):
            raise TerminalViewError('External agent has exited or its process identity changed; rediscover it')
        cwd, root = self._cwd(record['pid'], record['workspace'])
        if cwd != record.get('cwd') or root != record.get('workspace'):
            raise TerminalViewError('External agent changed workspace; rediscover it')

    def read(self, record):
        self._check_enabled()
        self._verify(record)
        code, output, error = probe(['/usr/bin/osascript', '-e', READ_HISTORY, record['tty']], timeout=8)
        if error:
            raise TerminalViewError('Terminal.app history could not be read within the output or time limit')
        if code != 0:
            if '-1743' in output or 'not authorized' in output.lower() or 'not permitted' in output.lower():
                raise TerminalViewError('macOS denied Terminal.app Automation access; allow Aterus in System Settings > Privacy & Security > Automation to use this optional view')
            if 'ATERUS_TAB_NOT_FOUND' in output:
                raise TerminalViewError('No Terminal.app tab matches this foreground agent')
            raise TerminalViewError('Terminal.app history is unavailable')
        # Recheck after AppleScript too: avoid returning a tab after agent exit.
        self._verify(record)
        return '\n'.join(output.splitlines()[-400:])
