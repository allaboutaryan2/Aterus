"""Attach a second frontend to a locally owned OpenCode server, never a shell.

The documented /global/health and /session endpoints identify the server and
workspace. opencode attach --session supplies the native live frontend.
"""
import base64
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit
import agents


class AttachError(ValueError):
    pass


def parse_origin(value):
    try:
        url = urlsplit(value)
        if (url.scheme != 'http' or url.hostname not in ('127.0.0.1', '::1') or
                url.username or url.password or url.path not in ('', '/') or url.query or url.fragment or
                url.port is None or not 1024 <= url.port <= 65535):
            raise ValueError()
        host = '[::1]' if url.hostname == '::1' else '127.0.0.1'
        return 'http://' + host + ':' + str(url.port), url.hostname, url.port
    except (ValueError, TypeError):
        raise AttachError('Use an explicit loopback URL such as http://127.0.0.1:4096; remote URLs are not accepted')


def listeners():
    """No argv or environment inspection: only owned process and socket metadata."""
    if sys.platform == 'win32':
        # PowerShell process ownership is checked by SID; no elevated access needed.
        script = r'''$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value; Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object {$_.LocalAddress -eq '127.0.0.1' -or $_.LocalAddress -eq '::1'} | ForEach-Object { $c=$_; $p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$c.OwningProcess); $o=Invoke-CimMethod -InputObject $p -MethodName GetOwnerSid; if($o.Sid -eq $sid -and $p.Name -eq 'opencode.exe') { [pscustomobject]@{pid=[int]$c.OwningProcess;port=[int]$c.LocalPort;host=$c.LocalAddress;started=[string]$p.CreationDate} } } | ConvertTo-Json -Compress'''
        argv = ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script]
    else:
        executable = shutil.which('lsof') or '/usr/sbin/lsof'
        argv = [executable, '-nP', '-a', '-u', str(os.getuid()), '-iTCP', '-sTCP:LISTEN', '-Fpcun']
    code, output, error = agents.probe(argv, timeout=5)
    if error or code not in (0, 1):
        raise AttachError('Cannot inspect owned listening processes. Run Aterus from your normal desktop terminal.')
    if sys.platform == 'win32':
        if code != 0:
            raise AttachError('Cannot inspect Windows listeners for the current user')
        try:
            data = json.loads(output or '[]')
            data = data if isinstance(data, list) else [data]
            return [dict(pid=int(r['pid']), host=r['host'], port=int(r['port']), started=r.get('started','')) for r in data]
        except (ValueError, TypeError, KeyError):
            raise AttachError('Unsupported Windows listener output')
    results, current = [], {}
    for line in output.splitlines():
        if not line:
            continue
        if line[0] == 'p':
            current = {'pid': line[1:]}
        elif line[0] in ('c', 'u'):
            current[line[0]] = line[1:]
        elif line[0] == 'n' and current.get('c') == 'opencode' and current.get('u') == str(os.getuid()):
            match = re.fullmatch(r'(127\.0\.0\.1|\[::1\]):(\d+)', line[1:])
            if match:
                results.append({'pid': int(current['pid']), 'host': match[1].strip('[]'), 'port': int(match[2])})
    return results


def candidate_origins():
    return list(dict.fromkeys(('http://[' + row['host'] + ']' if row['host'] == '::1' else 'http://' + row['host']) + ':' + str(row['port']) for row in listeners()))


class OpenCodeServer:
    def __init__(self, origin, workspace, password='', username='opencode'):
        self.origin, self.host, self.port = parse_origin(origin)
        self.workspace = Path(workspace).resolve()
        if not isinstance(password, str) or len(password) > 2048 or not isinstance(username, str) or len(username) > 120 or ':' in username or any(ord(c)<32 for c in username+password):
            raise AttachError('Invalid server credentials')
        self.password, self.username = password, username
        self.pin = None
        self.verify_owner()
        health = self.request('/global/health')
        if not isinstance(health, dict) or health.get('healthy') is not True or not isinstance(health.get('version'), str):
            raise AttachError('This listener is not a verified OpenCode server')
        self.version = health['version'][:80]

    def verify_owner(self):
        matches = [row for row in listeners() if row['host'] == self.host and row['port'] == self.port]
        if len(matches) != 1:
            raise AttachError('No unique, owned OpenCode process is listening on this loopback endpoint')
        identity = (matches[0]['pid'], matches[0].get('started', ''))
        if self.pin is not None and self.pin != identity:
            raise AttachError('The external server process changed; discover it again')
        self.pin = identity

    def request(self, path):
        # Direct literal-IP connection: no DNS, proxy, redirects or arbitrary URL fetch.
        connection = http.client.HTTPConnection(self.host, self.port, timeout=4)
        headers = {'Accept': 'application/json'}
        if self.password:
            headers['Authorization'] = 'Basic ' + base64.b64encode((self.username+':'+self.password).encode()).decode()
        try:
            connection.request('GET', path, headers=headers)
            response = connection.getresponse()
            raw = response.read(2 * 1024 * 1024 + 1)
            if response.status == 401:
                raise AttachError('OpenCode requires its server password; enter it on the owner Mac')
            if response.status != 200 or len(raw) > 2 * 1024 * 1024:
                raise AttachError('OpenCode returned an unsupported response')
            return json.loads(raw)
        except AttachError:
            raise
        except (OSError, ValueError, http.client.HTTPException):
            raise AttachError('Could not read this OpenCode server; check the endpoint, password and running process')
        finally:
            connection.close()

    def sessions(self):
        self.verify_owner()
        rows = self.request('/session')
        if not isinstance(rows, list):
            raise AttachError('Unsupported OpenCode session schema')
        result = []
        for row in rows[:500]:
            if not isinstance(row, dict):
                continue
            sid, directory = row.get('id'), row.get('directory')
            if not isinstance(sid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', sid) or not isinstance(directory, str) or not Path(directory).is_absolute():
                continue
            cwd = Path(directory).resolve()
            try:
                cwd.relative_to(self.workspace)
            except ValueError:
                continue
            if cwd.is_dir():
                result.append({'id': sid, 'title': str(row.get('title') or sid)[:160], 'cwd': str(cwd)})
        return result

    def attach(self, sid):
        found = [row for row in self.sessions() if row['id'] == sid]
        if len(found) != 1:
            raise AttachError('The native session is absent, ambiguous or outside the authorized workspace')
        help_output = agents.help_text('opencode', ('attach',))
        if not agents._flag(help_output, '--session') or not agents._flag(help_output, '--dir'):
            raise AttachError('Select a modern OpenCode executable with attach --session and --dir support')
        executable = shutil.which(agents.EXECUTABLES['opencode'])
        if not executable:
            raise AttachError('OpenCode executable not found')
        environment = {'OPENCODE_SERVER_USERNAME': self.username, 'OPENCODE_SERVER_PASSWORD': self.password}
        return found[0], [executable, 'attach', self.origin, '--session', sid, '--dir', found[0]['cwd']], environment
