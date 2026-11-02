import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import live_attach


class Response:
    status = 200
    def __init__(self, payload): self.payload = payload
    def read(self, limit): return json.dumps(self.payload).encode()


class Connection:
    requests = []
    responses = []
    def __init__(self, host, port, timeout):
        self.host, self.port = host, port
    def request(self, method, path, headers): self.requests.append((method,path,headers))
    def getresponse(self): return self.responses.pop(0)
    def close(self): pass


class LiveAttachTests(unittest.TestCase):
    def test_only_literal_loopback_origins_without_secrets_or_redirects(self):
        self.assertEqual(live_attach.parse_origin('http://127.0.0.1:4096/')[0], 'http://127.0.0.1:4096')
        self.assertEqual(live_attach.parse_origin('http://[::1]:4096')[1], '::1')
        for value in ('https://remote.test:4096', 'http://localhost:4096','http://127.0.0.1:80','http://127.0.0.1:4096/path','http://user:secret@127.0.0.1:4096','http://127.0.0.1:4096?q=secret','http://127.0.0.1:4096/#x','file:///tmp/file','http://2130706433:4096'):
            with self.assertRaises(live_attach.AttachError): live_attach.parse_origin(value)

    def test_process_discovery_filters_user_command_and_bind_address(self):
        uid = os.getuid()
        text = f'p123\ncopencode\nu{uid}\nn127.0.0.1:4096\np124\ncopencode\nu{uid+1}\nn127.0.0.1:4097\np125\ncpython\nu{uid}\nn127.0.0.1:4098\np126\ncopencode\nu{uid}\nn*:4099\n'
        with patch.object(live_attach.agents, 'probe', return_value=(0,text,'')):
            self.assertEqual(live_attach.listeners(), [{'pid':123,'host':'127.0.0.1','port':4096}])

    def test_identity_workspace_and_credentials_stay_out_of_argv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); workspace = root/'project'; workspace.mkdir(); outside=root/'other';outside.mkdir()
            rows = [{'id':'ses_exact','directory':str(workspace),'title':'Existing'}, {'id':'ses_outside','directory':str(outside)}, {'id':'ses_unknown'}, {'id':'ses_relative','directory':'.'}]
            owner = [{'pid':123,'host':'127.0.0.1','port':4096}]
            Connection.requests=[];Connection.responses=[Response({'healthy':True,'version':'1.18.35'}),Response(rows),Response(rows)]
            with patch.object(live_attach,'listeners',return_value=owner), patch.object(live_attach.http.client,'HTTPConnection',Connection), patch.object(live_attach.agents,'help_text',return_value='opencode attach <url> --session --dir'), patch.object(live_attach.shutil,'which',return_value='/bin/opencode'):
                server=live_attach.OpenCodeServer('http://127.0.0.1:4096',workspace,'private-password')
                self.assertEqual([r['id'] for r in server.sessions()],['ses_exact'])
                record,argv,environment=server.attach('ses_exact')
                self.assertEqual(record['cwd'],str(workspace.resolve()))
                self.assertEqual(argv,['/bin/opencode','attach','http://127.0.0.1:4096','--session','ses_exact','--dir',str(workspace.resolve())])
                self.assertNotIn('private-password',repr(argv));self.assertEqual(environment['OPENCODE_SERVER_PASSWORD'],'private-password')
                self.assertTrue(Connection.requests[0][2]['Authorization'].startswith('Basic '))
                with patch.object(live_attach,'listeners',return_value=[{'pid':999,'host':'127.0.0.1','port':4096}]):
                    with self.assertRaisesRegex(ValueError,'changed'): server.sessions()

    def test_auth_and_redirect_errors_never_return_response_body(self):
        owner=[{'pid':123,'host':'127.0.0.1','port':4096}]
        for status in (401,302):
            response=Response({'secret':'do-not-return'});response.status=status;Connection.responses=[response]
            with patch.object(live_attach,'listeners',return_value=owner),patch.object(live_attach.http.client,'HTTPConnection',Connection):
                with self.assertRaises(live_attach.AttachError) as error:
                    live_attach.OpenCodeServer('http://127.0.0.1:4096','/tmp')
                self.assertNotIn('do-not-return',str(error.exception))

    def test_duplicate_or_missing_native_session_fails_closed(self):
        server=object.__new__(live_attach.OpenCodeServer)
        with patch.object(server,'sessions',return_value=[{'id':'same'},{'id':'same'}]):
            with self.assertRaisesRegex(ValueError,'ambiguous'): server.attach('same')
        with patch.object(server,'sessions',return_value=[]):
            with self.assertRaises(ValueError): server.attach('unknown')


if __name__=='__main__': unittest.main()
