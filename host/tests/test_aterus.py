import agents
import base64
import http.client
import importlib.util
import io
from types import SimpleNamespace
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('aterus', ROOT / 'aterus.py')
aterus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aterus)


class HubTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        self.hub = aterus.Hub(self.root / 'data', self.project)

    def tearDown(self):
        self.hub.close()
        self.temp.cleanup()

    def test_commands_and_no_permission_bypass(self):
        with patch.object(aterus.shutil, 'which', side_effect=lambda x:'/bin/'+x), patch.object(agents, 'help_text', return_value='SESSION_ID --resume-id --resume --model --no-alt-screen'):
            self.assertEqual(aterus.agent_command('kiro', 'custom', 'abc'), ['/bin/kiro-cli','chat','--resume-id','abc','--model','custom'])
            self.assertEqual(aterus.agent_command('codex', '', 'abc'), ['/bin/codex','resume','abc','--no-alt-screen'])
            for name in aterus.AGENTS:
                self.assertFalse(any('trust-all' in a or 'dangerously' in a for a in aterus.agent_command(name)))
            with self.assertRaises(ValueError):
                aterus.agent_command('opencode', '', 'abc')
        with self.assertRaises(ValueError):
            aterus.agent_command('shell')

    def test_control_and_collection_reuse_locked_session_reads(self):
        for index, (state, kind, code, expected) in enumerate((
                ('running', '', 0, 'exited'), ('running', '', 7, 'failed'),
                ('stopping', '', 0, 'stopped'), ('stopping', 'opencode-live', 7, 'detached'))):
            sid = 'read-' + str(index)
            self.hub.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?)',
                             (sid, 'opencode', 'Fixture', str(self.project), time.time(), state, None, '', ''))
            if kind:
                self.hub.execute('INSERT INTO attachments VALUES(?,?,?)', (sid, kind, 'fixture'))
            worker = SimpleNamespace(stdin=io.BytesIO(), stdout=io.BytesIO((json.dumps({'exit':code})+'\n').encode()),
                                     poll=lambda:None, wait=lambda:code)
            self.hub.live[sid] = worker
            with patch.object(self.hub, 'rows', wraps=self.hub.rows) as read:
                if state == 'running':
                    self.hub.control(sid, {'input':'aGVsbG8='})
                    self.assertEqual(worker.stdin.getvalue(), b'{"input": "aGVsbG8="}\n')
                else:
                    with self.assertRaisesRegex(ValueError, 'This terminal is stopping'):
                        self.hub.control(sid, {'input':'aGVsbG8='})
                    self.assertEqual(worker.stdin.getvalue(), b'')
                self.assertEqual(read.call_count, 1)
            with patch.object(self.hub, 'rows', wraps=self.hub.rows) as read:
                self.hub.collect(sid, worker)
                self.assertEqual(read.call_count, 1)
            self.assertEqual(self.hub.session(sid)['state'], expected)
            self.assertEqual(self.hub.session(sid)['exit_code'], code)

    def test_file_selection_matches_stable_sort_with_tied_timestamps(self):
        self.hub.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?)',
                         ('files', 'kiro', 'Files', str(self.project), time.time(), 'exited', 0, '', ''))
        for index in range(140):
            file = self.project / ('file-' + str(index))
            file.write_bytes(bytes(index % 32))
            os.utime(file, (100 + index % 9, 100 + index % 9))
        files = []
        for directory, _, names in os.walk(self.project):
            for name in names:
                item = Path(directory) / name
                stat = item.stat()
                files.append({'path': str(item.relative_to(self.project)), 'size': stat.st_size, 'modified': stat.st_mtime})
        handler = aterus.Handler.__new__(aterus.Handler)
        handler.server = SimpleNamespace(hub=self.hub)
        handler.path = '/api/files?id=files'
        handler.reply = lambda status, data:(status, data)
        status, result = handler.get_api('/api/files', {'owner':True})
        self.assertEqual(status, 200)
        self.assertEqual(result, sorted(files, key=lambda f:f['modified'], reverse=True)[:60])

    def test_workspace_boundary_hidden_files_and_symlinks(self):
        (self.project / 'ok.txt').write_text('ok')
        (self.root / 'secret.txt').write_text('secret')
        (self.project / 'escape').symlink_to(self.root / 'secret.txt')
        (self.project / '.env').write_text('private')
        self.assertEqual(aterus.project_file(self.project, 'ok.txt').read_text(), 'ok')
        for path in ('../secret.txt', '.env', 'escape', str(self.root / 'secret.txt')):
            with self.assertRaises(ValueError):
                aterus.project_file(self.project, path)

    def test_real_pty_interactive_input_exit_and_no_shell_fallback(self):
        fake = self.root / 'fake-agent'
        fake.write_text('#!/usr/bin/env python3\nimport os\nprint("TTY="+str(os.isatty(0)), flush=True)\nprint("REPLY="+input(), flush=True)\n')
        fake.chmod(0o700)
        with patch.object(aterus.shutil, 'which', return_value=str(fake)):
            session = self.hub.start({'agent':'kiro','cwd':str(self.project)})
        sid = session['id']
        deadline = time.time() + 6
        log = self.root / 'data' / (sid + '.log')
        while time.time() < deadline:
            if log.exists() and b'TTY=True' in log.read_bytes():
                break
            time.sleep(.03)
        self.assertIn(b'TTY=True', log.read_bytes())
        self.hub.control(sid, {'input':base64.b64encode(b'hello\r').decode()})
        while time.time() < deadline and sid in self.hub.live:
            time.sleep(.03)
        self.assertIn(b'REPLY=hello', log.read_bytes())
        self.assertEqual(self.hub.session(sid)['exit_code'], 0)
        with self.assertRaises(ValueError):
            self.hub.control(sid, {'input':base64.b64encode(b'touch should-not-exist\r').decode()})
        self.assertFalse((self.project / 'should-not-exist').exists())

    def test_stop_kills_running_terminal(self):
        fake = self.root / 'fake-agent'
        fake.write_text('#!/usr/bin/env python3\nimport time\nprint("ready",flush=True)\ntime.sleep(100)\n')
        fake.chmod(0o700)
        with patch.object(aterus.shutil, 'which', return_value=str(fake)):
            session = self.hub.start({'agent':'kiro','cwd':str(self.project)})
        time.sleep(.2)
        self.hub.control(session['id'], {'stop':True})
        with self.assertRaisesRegex(ValueError, 'stopping|no longer running'):
            self.hub.control(session['id'], {'input':base64.b64encode(b'no input\r').decode()})
        deadline = time.time() + 6
        while time.time() < deadline and session['id'] in self.hub.live:
            time.sleep(.03)
        self.assertNotIn(session['id'], self.hub.live)
        self.assertEqual(self.hub.session(session['id'])['state'], 'stopped')

    def test_unrequested_agent_failure_stays_failed(self):
        with patch.object(aterus, 'agent_command', return_value=['/usr/bin/false']):
            session = self.hub.start({'agent': 'kiro'})
        deadline = time.time() + 5
        while session['id'] in self.hub.live and time.time() < deadline:
            time.sleep(.03)
        self.assertEqual(self.hub.session(session['id'])['state'], 'failed')
        self.assertNotEqual(self.hub.session(session['id'])['exit_code'], 0)

    def test_http_auth_origin_pairing_and_revocation(self):
        # Exercise the real HTTP parser/handler over byte streams without needing a socket.
        origin = 'http://127.0.0.1:4380'
        server = SimpleNamespace(hub=self.hub, public_host='',
            hosts={'127.0.0.1:4380'}, origins={origin})
        def request(path, body=None, cookie='', extra=None):
            headers = {'Origin':origin,'Cookie':cookie,'Content-Type':'application/json','Host':'127.0.0.1:4380'}
            headers.update(extra or {})
            payload = b'' if body is None else json.dumps(body).encode()
            headers['Content-Length'] = str(len(payload))
            method = 'GET' if body is None else 'POST'
            wire = ('%s %s HTTP/1.0\r\n' % (method,path) + ''.join(k+': '+v+'\r\n' for k,v in headers.items()) + '\r\n').encode() + payload
            class Connection:
                def __init__(self):
                    self.output = bytearray()
                def makefile(self, *_):
                    return io.BytesIO(wire)
                def sendall(self, data):
                    self.output.extend(data)
            connection = Connection()
            aterus.Handler(connection, ('127.0.0.1', 1234), server)
            head, data = bytes(connection.output).split(b'\r\n\r\n',1)
            status = int(head.split(b' ')[1])
            cookie = next((line.split(b': ',1)[1].decode().split(';')[0] for line in head.split(b'\r\n') if line.startswith(b'Set-Cookie:')), '')
            try:
                parsed = json.loads(data)
            except ValueError:
                parsed = data
            return status,parsed,cookie
        try:
            self.hub.status_cache = (time.monotonic(), [])
            self.assertEqual(request('/api/state')[0],401)
            self.assertEqual(request('/api/bootstrap',{'token':self.hub.bootstrap},extra={'Origin':'https://evil.test'})[0],403)
            self.assertEqual(request('/api/state',extra={'Host':'evil.test'})[0],403)
            self.assertEqual(request('/api/state',extra={'Host':'127.0.0.1:4380\r\nHost: evil.test'})[0],400)
            self.assertEqual(request('/api/state',extra={'Sec-Fetch-Site':'cross-site'})[0],403)
            self.assertEqual(request('/api/bootstrap',{'token':self.hub.bootstrap},extra={'Content-Type':'text/plain'})[0],400)
            self.assertEqual(request('/api/bootstrap',{'token':self.hub.bootstrap},extra={'Transfer-Encoding':'chunked'})[0],400)
            status,_,owner = request('/api/bootstrap',{'token':self.hub.bootstrap})
            self.assertEqual(status,200)
            self.assertTrue(owner.startswith('aterus='))
            with patch.object(agents, 'help_text', return_value='--cwd --output-format'):
                status, protocol, _ = request('/api/agent-controls?agent=opencode', cookie=owner)
                self.assertEqual(status, 200)
                self.assertEqual(protocol['submit'], '\x13')
                self.assertFalse(protocol['login'])
            self.assertEqual(request('/api/agent-controls?agent=shell', cookie=owner)[0], 400)
            self.assertEqual(request('/',extra={'Sec-Fetch-Site':'cross-site'})[0],200)
            for asset in ('/', '/app.js', '/vendor/xterm.js', '/vendor/xterm.css', '/sw.js', '/manifest.webmanifest', '/icon-180.png', '/icon-192.png', '/icon-512.png'):
                self.assertEqual(request(asset)[0], 200, asset)
            self.hub.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?)',
                             ('source', 'kiro', 'Source', str(self.project), time.time(), 'exited', 0, '', ''))
            (self.hub.data / 'source.log').write_bytes(b'hello\x1b[31m\rmalicious control')
            with patch.object(self.hub, 'start', return_value={'id':'target'}), patch.object(self.hub, 'control') as control:
                status, draft, _ = request('/api/handoff', {'id':'source','agent':'codex','context':'Continue safely'}, owner)
                self.assertEqual(status, 201)
                self.assertIn('Continue safely', draft['handoff_prompt'])
                self.assertFalse(any(ord(c) < 32 for c in draft['handoff_prompt']))
                control.assert_not_called()
            self.assertEqual(request('/api/bootstrap',{'token':''})[0],403)
            status,code,_ = request('/api/pairing',{},owner)
            self.assertEqual(status,200)
            status,pending,phone = request('/api/pair',{'code':code['code'],'name':'iPhone'})
            self.assertEqual(status,202)
            self.assertEqual(phone,'')
            self.assertEqual(request('/api/state')[0],401)
            self.assertEqual(request('/api/pair-status',{'id':pending['id'],'secret':pending['secret']})[1]['state'],'pending')
            self.assertEqual(request('/api/pair-approve',{'id':pending['id']})[0],401)
            self.assertEqual(request('/api/pair-approve',{'id':pending['id']},owner)[0],200)
            status,approved,phone=request('/api/pair-status',{'id':pending['id'],'secret':pending['secret']})
            self.assertEqual(status,200)
            self.assertEqual(approved['state'],'approved')
            self.assertTrue(phone.startswith('aterus='))
            self.assertEqual(request('/api/pair-approve',{'id':pending['id']},phone)[0],403)
            self.assertEqual(request('/api/connect/start',{},phone)[0],403)
            self.assertEqual(request('/api/pairing',{},phone)[0],403)
            self.assertEqual(request('/api/external/candidates',cookie=phone)[0],403)
            self.assertEqual(request('/api/external/terminals',cookie=phone)[0],403)
            self.assertEqual(request('/api/external/discover',{'origin':'http://127.0.0.1:4096'},phone)[0],403)
            self.assertEqual(request('/api/external/attach',{'source':'unknown','native':'bad'},phone)[0],403)
            self.assertEqual(request('/api/state',cookie=phone)[0],200)
            devices = request('/api/devices',cookie=owner)[1]
            phone_hash = next(d['hash'] for d in devices if d['name']=='iPhone')
            self.assertEqual(request('/api/revoke',{'hash':phone_hash},owner)[0],200)
            self.assertEqual(request('/api/state',cookie=phone)[0],401)
        finally:
            pass

    def test_workspace_upload_and_single_instance_boundaries(self):
        with patch.object(aterus, 'agent_command', return_value=['/bin/echo']):
            with self.assertRaisesRegex(ValueError, 'inside the root'):
                self.hub.start({'agent': 'kiro', 'cwd': str(self.root)})
        with self.assertRaisesRegex(ValueError, 'Another Aterus'):
            aterus.Hub(self.root / 'data', self.project)
        self.hub.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?)',
                         ('fixture', 'kiro', 'Fixture', str(self.project), time.time(), 'exited', 0, '', ''))
        result = self.hub.upload('fixture', 'note.txt', base64.b64encode(b'hello').decode())
        self.assertEqual(result['path'], 'uploads/note.txt')
        with aterus.open_project_file(self.project, result['path']) as stream:
            self.assertEqual(stream.read(), b'hello')
        for name in ('../outside', '.env', '/tmp/outside', 'bad\nname'):
            with self.assertRaises(ValueError):
                self.hub.upload('fixture', name, 'eA==')
        with self.assertRaises(FileExistsError):
            self.hub.upload('fixture', 'note.txt', 'eA==')
        (self.project / 'uploads' / 'escape').symlink_to(self.root / 'private')
        with self.assertRaises(OSError):
            self.hub.upload('fixture', 'escape', 'eA==')

    def test_device_expiry_and_restart_history(self):
        token = self.hub.issue_device('Phone')
        self.hub.execute('UPDATE devices SET seen=?', (time.time() - 31 * 86400,))
        self.assertIsNone(self.hub.device(token))
        self.hub.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?)',
                         ('old', 'kiro', 'Old', str(self.project), time.time(), 'running', None, '', 'native'))
        self.hub.close()
        self.hub = aterus.Hub(self.root / 'data', self.project)
        self.assertEqual(self.hub.session('old')['state'], 'interrupted')
        self.assertEqual(self.hub.session('old')['native_id'], 'native')

    def test_live_frontend_detach_is_distinct_from_stopping_original(self):
        import sys
        server = SimpleNamespace(attach=lambda native: (
            {'id':native,'cwd':str(self.project),'title':'Original'},
            [sys.executable,'-c','import time;time.sleep(60)'],
            {'OPENCODE_SERVER_PASSWORD':'fixture-private'}), origin='http://127.0.0.1:4096')
        self.hub.external_sources['source']=(server,time.monotonic())
        session=self.hub.attach_live('source','ses_exact')
        self.assertEqual(session['attachment_kind'],'opencode-live')
        self.assertEqual(session['native_id'],'ses_exact')
        time.sleep(.1)
        self.hub.control(session['id'],{'stop':True})
        self.hub.stop_all()
        self.assertEqual(self.hub.session(session['id'])['state'],'detached')
        with self.assertRaises(ValueError):self.hub.attach_live('unknown','ses_exact')

    def test_external_terminal_view_never_injects_or_stops_original(self):
        record={'id':'opaque','agent':'claude','cwd':str(self.project)}
        self.hub.external_records['opaque']=record
        with patch.object(self.hub.terminal_view, 'read', return_value='Existing output'):
            session=self.hub.attach_terminal_view('opaque')
        self.assertEqual(session['attachment_kind'],'terminal-view')
        self.assertEqual(session['state'],'viewing')
        with self.assertRaisesRegex(ValueError,'read-only'):
            self.hub.control(session['id'],{'input':'eA=='})
        self.hub.control(session['id'],{'stop':True})
        self.assertEqual(self.hub.session(session['id'])['state'],'detached')
        self.assertEqual(self.hub.live,{})

    def test_local_socket_transport(self):
        try:
            server = aterus.create_server(self.hub, 0)
        except PermissionError:
            self.skipTest('Execution sandbox prohibits binding a local socket')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection('127.0.0.1', server.server_address[1])
            connection.request('GET', '/api/state')
            response = connection.getresponse()
            self.assertEqual(response.status, 401)
            response.read()
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
