import http.client
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from email.message import Message
from types import SimpleNamespace
from unittest.mock import Mock, patch

import aterus
from pairing import PairingGate


@unittest.skipUnless(Path('/.dockerenv').exists() or Path('/run/.containerenv').exists(),
                     'Security reproductions require an isolated Docker container')
class SecurityTests(unittest.TestCase):
    def handler(self, path, body, identity=None, server=None):
        handler = aterus.Handler.__new__(aterus.Handler)
        handler.command = 'POST'
        handler.path = path
        handler.request = object()
        handler.headers = Message()
        for name, value in {'Host':'127.0.0.1:4380', 'Origin':'http://127.0.0.1:4380',
                            'Content-Type':'application/json', 'Content-Length':str(len(body))}.items():
            handler.headers[name] = value
        handler.rfile = io.BytesIO(body)
        handler.server = server or SimpleNamespace(hosts={'127.0.0.1:4380'}, origins={'http://127.0.0.1:4380'},
                                                    upload_slot=threading.BoundedSemaphore(1))
        handler.identity = lambda:identity
        handler.reply = lambda status, data, **kwargs:(status, data)
        return handler

    def test_protected_requests_reject_before_reading_body(self):
        for path in ('/api/upload', '/api/input', '/api/handoff', '/api/sessions'):
            handler = self.handler(path, b'{}')
            handler.rfile = Mock()
            self.assertEqual(handler.dispatch()[0], 401)
            handler.rfile.read.assert_not_called()
        for path in ('/', '/unknown', '/style.css'):
            handler = self.handler(path, b'{}')
            handler.rfile = Mock()
            self.assertEqual(handler.dispatch()[0], 404)
            handler.rfile.read.assert_not_called()

    def test_upload_budget_releases_on_invalid_body_and_allows_normal_body(self):
        handler = self.handler('/api/upload', b'x' * 40000, {'owner':True})
        self.assertEqual(handler.dispatch()[0], 400)
        slot = handler.server.upload_slot
        self.assertTrue(slot.acquire(blocking=False))
        handler.rfile = Mock()
        self.assertEqual(handler.dispatch()[0], 503)
        handler.rfile.read.assert_not_called()
        slot.release()
        data = {'data':'x' * 40000}
        handler = self.handler('/api/upload', json.dumps(data).encode(), {'owner':True})
        handler.post_api = lambda path, body, device:(201, body)
        self.assertEqual(handler.dispatch(), (201, data))
        self.assertTrue(handler.server.upload_slot.acquire(blocking=False))
        handler.server.upload_slot.release()

    def test_invalid_pairing_flood_cannot_block_a_valid_code(self):
        issue = Mock()
        gate = PairingGate(issue, clock=lambda:1000)
        for _ in range(40):
            with self.assertRaises(ValueError):gate.request('invalid', 'Attacker')
        self.assertEqual(len(gate.attempts), 20)
        code = gate.create()['code']
        pending = gate.request(' ' + code.lower() + ' ', 'Phone')
        self.assertEqual(gate.status(pending['id'], pending['secret']), ({'state':'pending'}, None))
        with self.assertRaises(ValueError):gate.request(code, 'Replay')
        issue.assert_not_called()
        gate.pending = {str(i):{'expires_at':2000} for i in range(32)}
        code = gate.create()['code']
        with self.assertRaisesRegex(ValueError, 'pending'):gate.request(code, 'Phone')
        self.assertIn(code, gate.codes)

    def test_pairing_aliases_work_after_invalid_attempts(self):
        for path in ('/api/pair', '/api/pair-request'):
            gate = PairingGate(Mock(), clock=lambda:1000)
            for _ in range(20):
                with self.assertRaises(ValueError):gate.request('wrong', 'Attacker')
            code = gate.create()['code']
            server = SimpleNamespace(hosts={'127.0.0.1:4380'}, origins={'http://127.0.0.1:4380'},
                                     hub=SimpleNamespace(pair_gate=gate))
            handler = self.handler(path, json.dumps({'code':code,'name':'Phone'}).encode(), server=server)
            self.assertEqual(handler.dispatch()[0], 202)

    def test_workspace_switch_blocks_old_sessions_and_preserves_in_scope_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, current = root/'old', root/'current'
            old.mkdir();current.mkdir()
            hub = aterus.Hub(root/'data', old)
            token = hub.issue_device('Phone')
            hub.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?)',
                        ('old','kiro','Old',str(old),time.time(),'exited',0,'',''))
            (hub.data/'old.log').write_bytes(b'private old transcript')
            hub.close()
            hub = aterus.Hub(root/'data', current)
            try:
                self.assertIsNotNone(hub.device(token))
                with self.assertRaisesRegex(ValueError, 'outside'):hub.session('old')
                handler = aterus.Handler.__new__(aterus.Handler)
                handler.server = SimpleNamespace(hub=hub)
                handler.reply = lambda status, data:(status, data)
                for path in ('/api/files','/api/preview','/api/file','/api/output'):
                    handler.path = path + '?id=old&path=note.txt'
                    with patch('builtins.open', side_effect=AssertionError('Read outside current workspace')):
                        with self.assertRaisesRegex(ValueError, 'outside'):handler.get_api(path, {'owner':True})
                with self.assertRaisesRegex(ValueError, 'outside'):hub.upload('old', 'file.txt', 'eA==')
                with self.assertRaisesRegex(ValueError, 'outside'):hub.control('old', {'stop':True})
                with self.assertRaisesRegex(ValueError, 'outside'):
                    handler.post_api('/api/handoff', {'id':'old','context':'Continue','agent':'codex'}, {'owner':True})
                hub.status_cache = (time.monotonic(), [])
                handler.path = '/api/state'
                self.assertEqual(handler.get_api('/api/state', {'owner':True,'name':'Phone'})[1]['sessions'], [])
                hub.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?)',
                            ('deleted','kiro','Deleted',str(current/'deleted'),time.time(),'exited',0,'',''))
                self.assertEqual(hub.session('deleted')['id'], 'deleted')
                (current/'link').symlink_to(old, target_is_directory=True)
                self.assertFalse(hub.session_allowed({'cwd':str(current/'link')}))
                self.assertFalse(hub.session_allowed({'cwd':str(root/'current-extra')}))
                self.assertTrue(hub.session_allowed({'cwd':str(current)}))
            finally:hub.close()

    def test_directory_swap_cannot_redirect_files_or_uploads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project, outside = root/'project', root/'outside'
            project.mkdir();outside.mkdir()
            nested = project/'nested'
            nested.mkdir()
            (outside/'secret.txt').write_bytes(b'outside')
            hub = aterus.Hub(root/'data', project)
            try:
                hub.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?)',
                            ('swap','kiro','Swap',str(nested),time.time(),'exited',0,'',''))
                session = hub.session('swap')
                nested.rename(project/'original')
                nested.symlink_to(outside, target_is_directory=True)
                with self.assertRaises(ValueError):hub.open_file(session, 'secret.txt')
                # Force the swap immediately after the containment check succeeds.
                nested.unlink();(project/'original').rename(nested)
                allowed = hub.session_allowed
                def swap(record):
                    result = allowed(record)
                    nested.rename(project/'original')
                    nested.symlink_to(outside, target_is_directory=True)
                    return result
                with patch.object(hub, 'session_allowed', side_effect=swap):
                    with self.assertRaises(OSError):hub.open_file(session, 'secret.txt')
                self.assertFalse((outside/'uploads').exists())
                with self.assertRaises(ValueError):hub.upload('swap','file.txt','eA==')
            finally:hub.close()

    def test_global_admission_covers_distinct_clients(self):
        server = aterus.Server(('127.0.0.1',0), aterus.Handler)
        server.max_workers = 1
        first, second = object(), object()
        try:
            with patch.object(aterus.ThreadingHTTPServer, 'process_request'), patch.object(server, 'shutdown_request') as rejected:
                server.process_request(first, ('10.0.0.1',1))
                server.process_request(second, ('10.0.0.2',2))
                self.assertEqual(server.workers,1)
                rejected.assert_called_once_with(second)
                server.release_request(first,'10.0.0.1')
                self.assertEqual(server.workers,0)
                self.assertEqual(server.deadlines,{})
        finally:server.server_close()

    def test_deadline_stops_trickled_headers_and_releases_admission(self):
        server = aterus.Server(('127.0.0.1',0), aterus.Handler)
        server.max_workers = 3
        server.max_client_workers = 2
        server.request_timeout = .3
        server.hosts = {'127.0.0.1:' + str(server.server_address[1])}
        server.origins = {'http://' + next(iter(server.hosts))}
        server.handle_error = lambda *args:None
        sockets = []
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for _ in range(2):sockets.append(socket.create_connection(server.server_address, timeout=1))
            deadline = time.monotonic()+2
            while server.workers<2 and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(server.workers,2)
            rejected = socket.create_connection(server.server_address, timeout=1)
            self.assertEqual(rejected.recv(1),b'')
            rejected.close()
            for _ in range(10):
                for connection in sockets:
                    try:connection.sendall(b'G')
                    except OSError:pass
                time.sleep(.05)
            deadline = time.monotonic()+2
            while server.workers and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(server.workers,0)
            self.assertEqual(server.client_workers,{})
            self.assertEqual(server.deadlines,{})
            connection = http.client.HTTPConnection(*server.server_address, timeout=2)
            connection.request('GET','/')
            response = connection.getresponse()
            self.assertEqual(response.status,200)
            response.read();connection.close()
            slow = socket.create_connection(server.server_address,timeout=1)
            sockets.append(slow)
            host = next(iter(server.hosts))
            headers = ('POST /api/pair-status HTTP/1.0\r\nHost: '+host+'\r\nOrigin: http://'+host+
                       '\r\nContent-Type: application/json\r\nContent-Length: 1000\r\n\r\n{').encode()
            slow.sendall(headers)
            for _ in range(10):
                try:slow.sendall(b' ')
                except OSError:pass
                time.sleep(.05)
            deadline = time.monotonic()+2
            while server.workers and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(server.workers,0)
        finally:
            for connection in sockets:connection.close()
            server.shutdown();server.server_close();thread.join(timeout=2)


if __name__ == '__main__':unittest.main()
