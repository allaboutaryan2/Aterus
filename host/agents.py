"""Version-aware CLI adapters. Probe output stays private; no account details leave here.

Kiro commands: https://kiro.dev/docs/cli/reference/cli-commands/
Session semantics: https://kiro.dev/docs/cli/chat/session-management/
Installed help remains authoritative for optional flags.
"""
import functools
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import time

EXECUTABLES = {'kiro':'kiro-cli', 'claude':'claude', 'codex':'codex',
               'gemini':'gemini', 'opencode':'opencode', 'pi':'pi'}
MAX_OUTPUT = 1024 * 1024


def probe(argv, cwd=None, timeout=6):
    """Read-only subprocess with a deadline and output cap; never invoke a shell."""
    try:
        process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError:
        return None, '', 'CLI could not be executed'
    chunks, size = [], 0
    deadline = time.monotonic() + timeout
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    error = ''
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                error = 'CLI probe timed out'
                break
            for key, _ in selector.select(min(remaining, .2)):
                block = os.read(key.fileobj.fileno(), 65536)
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                size += len(block)
                if size > MAX_OUTPUT:
                    error = 'CLI probe exceeded output limit'
                    break
                chunks.append(block)
            if error:
                break
        if not error:
            try:
                process.wait(timeout=max(.01, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                error = 'CLI probe timed out'
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
    return process.returncode, b''.join(chunks).decode('utf-8', 'replace'), error


@functools.lru_cache(maxsize=32)
def _help(executable, stamp, subcommand):
    code, text, error = probe([executable, *subcommand, '--help'])
    return text if code == 0 and not error else ''


def help_text(agent, subcommand=()):
    executable = shutil.which(EXECUTABLES[agent])
    if not executable:
        return ''
    try:
        stamp = Path(executable).stat().st_mtime_ns
    except OSError:
        return ''
    return _help(executable, stamp, tuple(subcommand))


def _flag(text, flag):
    return re.search(r'(?<![\w-])' + re.escape(flag) + r'(?![\w-])', text) is not None


def command(agent, model='', resume=''):
    if agent not in EXECUTABLES:
        raise ValueError('Unknown agent')
    executable = shutil.which(EXECUTABLES[agent])
    if not executable:
        raise ValueError('This CLI is not installed or is missing from PATH')
    for value in (model, resume):
        if not isinstance(value, str) or len(value) > 200 or any(ord(c) < 32 for c in value) or value.startswith('-'):
            raise ValueError('Invalid model or session ID')
    sub = ('chat',) if agent == 'kiro' else ()
    help_output = help_text(agent, sub)
    args = list(sub)
    if agent == 'codex' and resume:
        resume_help = help_text(agent, ('resume',))
        if 'SESSION_ID' not in resume_help:
            raise ValueError('Native resume is not verified for this CLI version')
        help_output = resume_help
        args = ['resume', resume]
    elif resume:
        flag = {'kiro':'--resume-id', 'claude':'--resume', 'opencode':'--session'}.get(agent)
        if not flag or not _flag(help_output, flag):
            raise ValueError('Native resume is not verified for this CLI version')
        args += [flag, resume]
    if agent == 'codex' and _flag(help_output, '--no-alt-screen'):
        args += ['--no-alt-screen']
    if model:
        if not _flag(help_output, '--model'):
            raise ValueError('Model selection is not verified for this CLI version')
        args += ['--model', model]
    return [executable, *args]


def agent_status(agent):
    executable = shutil.which(EXECUTABLES[agent])
    result = {'installed':bool(executable), 'version':None, 'auth':'unknown',
              'readiness':'not_installed' if not executable else 'unverified'}
    if not executable:
        return result
    code, output, error = probe([executable, '--version'])
    match = re.search(r'\b\d+\.\d+(?:\.\d+)?(?:[-+][\w.]+)?\b', output)
    if code == 0 and match:
        result['version'] = match.group()
    checks = {'kiro':['whoami','--format','json'],
              'claude':['auth','status','--json'], 'codex':['login','status']}
    if agent == 'opencode':
        result['controls'] = controls(agent)
        result['readiness'] = 'provider_unverified'
        return result
    if agent not in checks:
        return result
    code, output, error = probe([executable, *checks[agent]])
    if error:
        result['readiness'] = 'probe_failed'
        return result
    try:
        data = json.loads(output)
    except ValueError:
        data = None
    if agent == 'kiro' and isinstance(data, dict) and 'account' in data:
        result['auth'] = 'signed_in' if code == 0 and data['account'] else 'signed_out'
    elif agent == 'claude' and isinstance(data, dict) and isinstance(data.get('loggedIn'), bool):
        result['auth'] = 'signed_in' if data['loggedIn'] else 'signed_out'
    elif agent == 'codex' and code == 0 and 'logged in' in output.lower():
        result['auth'] = 'signed_in'
    elif 'not logged in' in output.lower():
        result['auth'] = 'signed_out'
    if 'operation not permitted' in output.lower() or 'permission denied' in output.lower():
        result['readiness'] = 'access_blocked'
    elif result['auth'] != 'unknown':
        result['readiness'] = 'authentication_reported' if result['auth'] == 'signed_in' else 'login_required'
    return result


def _kiro_list(flag, cwd):
    executable = shutil.which(EXECUTABLES['kiro'])
    if not executable or not _flag(help_text('kiro', ('chat',)), flag):
        return None, 'This CLI version does not support this discovery command'
    code, output, error = probe([executable, 'chat', flag, '--format', 'json'], cwd=cwd)
    if error:
        return None, error
    if code != 0:
        if 'operation not permitted' in output.lower() or 'permission denied' in output.lower():
            return None, 'CLI account or session access is blocked by the execution environment'
        return None, 'CLI discovery failed; check login on the Mac'
    try:
        return json.loads(output), ''
    except ValueError:
        return None, 'CLI returned an unsupported JSON format'


def native_sessions(agent, cwd):
    """Only return exact IDs from CLI discovery in the selected workspace."""
    if agent == 'opencode':
        return opencode_sessions(cwd)
    if agent != 'kiro':
        return {'supported':False, 'items':[], 'error':'Native discovery is not implemented for this agent'}
    data, error = _kiro_list('--list-sessions', cwd)
    if error:
        return {'supported':True, 'items':[], 'error':error}
    if isinstance(data, dict) and isinstance(data.get('sessions'), list):
        data = data['sessions']
    if not isinstance(data, list):
        return {'supported':True, 'items':[], 'error':'CLI returned an unsupported session schema'}
    items = []
    for entry in data[:500]:
        if not isinstance(entry, dict):
            return {'supported':True, 'items':[], 'error':'CLI returned an unsupported session schema'}
        sid = entry.get('session_id', entry.get('id'))
        if not isinstance(sid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', sid):
            return {'supported':True, 'items':[], 'error':'CLI returned an unsupported session identity'}
        items.append({'id':sid, 'title':str(entry.get('title') or entry.get('name') or sid)[:160],
                      'cwd':str(Path(cwd).resolve())})
    return {'supported':True, 'items':items, 'error':''}


def validate_resume(agent, cwd, resume):
    if not resume or agent not in ('kiro', 'opencode'):
        return
    result = native_sessions(agent, cwd)
    if result['error']:
        raise ValueError(result['error'])
    if sum(item['id'] == resume for item in result['items']) != 1:
        raise ValueError('Native session ID is absent or ambiguous in this workspace')


def available_models(agent, cwd):
    if agent == 'opencode':
        return opencode_models(cwd)
    if agent != 'kiro':
        return {'supported':False, 'items':[], 'error':'Use a model ID supported by the installed agent'}
    data, error = _kiro_list('--list-models', cwd)
    if error:
        return {'supported':True, 'items':[], 'error':error}
    if isinstance(data, dict):
        data = data.get('models')
    if not isinstance(data, list):
        return {'supported':True, 'items':[], 'error':'CLI returned an unsupported model schema'}
    items = []
    for entry in data[:200]:
        model = entry if isinstance(entry, str) else entry.get('id', entry.get('model_id')) if isinstance(entry, dict) else None
        if not isinstance(model, str) or not model or len(model)>200 or model.startswith('-') or any(ord(c)<32 for c in model):
            return {'supported':True, 'items':[], 'error':'CLI returned an unsupported model identity'}
        items.append({'id':model, 'name':str(entry.get('name') or model)[:160] if isinstance(entry,dict) else model})
    return {'supported':True, 'items':items, 'error':''}


def controls(agent):
    """Terminal protocol, established from the installed CLI's root help."""
    if agent != 'opencode':
        return {'variant': 'standard', 'submit': '\r', 'login': agent in ('kiro', 'claude', 'codex')}
    root = help_text('opencode')
    if _flag(root, '--session'):
        return {'variant': 'modern', 'submit': '\r', 'login': bool(help_text('opencode', ('auth', 'login')))}
    if _flag(root, '--cwd') and _flag(root, '--output-format'):
        return {'variant': 'legacy-go', 'submit': '\x13', 'login': False,
                'notice': 'Legacy Go OpenCode: focus its editor before sending. Ctrl+S submits, Ctrl+O selects models, Ctrl+A opens sessions. Configure a provider in OpenCode; Claude CLI login is separate.'}
    return {'variant': 'unknown', 'submit': '\r', 'login': False,
            'notice': 'OpenCode version not recognized. Use the terminal directly; automatic prompt submission is unavailable.'}


def login_command(agent):
    if agent not in EXECUTABLES:
        raise ValueError('Unknown agent')
    executable = shutil.which(EXECUTABLES[agent])
    if not executable:
        raise ValueError('Agent is not installed')
    if agent == 'opencode':
        if not controls(agent)['login']:
            raise ValueError('This OpenCode version has no CLI login command. Configure its provider in the OpenCode terminal or its own configuration.')
        return [executable, 'auth', 'login']
    if agent not in ('kiro', 'claude', 'codex'):
        raise ValueError('Use the CLI directly to sign in to this agent')
    return [executable, *(['auth', 'login'] if agent == 'claude' else ['login'])]


def _opencode_query(arguments, cwd):
    code, output, error = probe([shutil.which(EXECUTABLES['opencode']), *arguments], cwd=cwd)
    if error:
        return None, error
    if code != 0:
        return None, 'OpenCode discovery failed; check its provider configuration and terminal on the Mac'
    return output, ''


def opencode_sessions(cwd):
    help_output = help_text('opencode', ('session', 'list')) if controls('opencode')['variant'] == 'modern' else ''
    if not _flag(help_output, '--format') or 'json' not in help_output.lower():
        return {'supported': False, 'items': [], 'error': 'This OpenCode version has no verified JSON session-list command. Open its session picker in the terminal (legacy: Ctrl+A).'}
    raw, error = _opencode_query(['session', 'list', '--format', 'json'], cwd)
    if error:
        return {'supported': True, 'items': [], 'error': error}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            data = data.get('sessions')
        if not isinstance(data, list):
            raise ValueError()
        items = []
        for entry in data[:500]:
            if not isinstance(entry, dict):
                raise ValueError()
            sid = entry.get('id', entry.get('sessionId'))
            directory = entry.get('directory', entry.get('cwd'))
            if not isinstance(sid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', sid):
                raise ValueError()
            # Missing/relative project identity cannot authorize resume in a workspace.
            if not isinstance(directory, str) or not Path(directory).is_absolute():
                continue
            if Path(directory).resolve() != Path(cwd).resolve():
                continue
            items.append({'id': sid, 'title': str(entry.get('title') or entry.get('name') or sid)[:160], 'cwd': str(Path(directory).resolve())})
        return {'supported': True, 'items': items, 'error': ''}
    except (ValueError, TypeError, OSError):
        return {'supported': True, 'items': [], 'error': 'OpenCode returned an unsupported session schema'}


def opencode_models(cwd):
    root = help_text('opencode')
    if controls('opencode')['variant'] != 'modern' or not re.search(r'(?m)^\s*(?:opencode\s+)?models(?:\s|$)', root):
        return {'supported': False, 'items': [], 'error': 'Select a model inside this OpenCode terminal (legacy: Ctrl+O); CLI model discovery is unavailable.'}
    raw, error = _opencode_query(['models'], cwd)
    if error:
        return {'supported': True, 'items': [], 'error': error}
    # Do not pass warnings, config dumps or arbitrary log lines through as models.
    ids = list(dict.fromkeys(line.strip() for line in raw.splitlines() if re.fullmatch(r'[A-Za-z0-9_.:-]+/[A-Za-z0-9_./:-]+', line.strip())))[:200]
    return {'supported': True, 'items': [{'id': model, 'name': model} for model in ids],
            'error': '' if ids else 'No model IDs were returned; configure a provider in OpenCode'}


def startup_hint(agent, transcript):
    if agent == 'opencode' and b'agent coder not found' in transcript.lower():
        return 'OpenCode could not find its coder agent. Check OpenCode\'s provider and coder-model configuration on the Mac. Claude Code login does not configure this OpenCode installation.'
    return ''
