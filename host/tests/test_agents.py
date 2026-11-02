import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('aterus_agents',Path(__file__).resolve().parents[1]/'agents.py')
agents = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agents)


class AgentTests(unittest.TestCase):
    def test_version_aware_commands_and_argument_values(self):
        with patch.object(agents.shutil,'which',return_value='/bin/agent'), patch.object(agents,'help_text',return_value='SESSION_ID --model --resume-id --resume --no-alt-screen'):
            self.assertEqual(agents.command('kiro','model','native-id'), ['/bin/agent','chat','--resume-id','native-id','--model','model'])
            self.assertEqual(agents.command('codex','','native-id'), ['/bin/agent','resume','native-id','--no-alt-screen'])
            for value in ('--trust-all-tools','bad\nvalue'):
                with self.assertRaises(ValueError): agents.command('kiro',value)
        with patch.object(agents.shutil,'which',return_value='/bin/agent'), patch.object(agents,'help_text',return_value=''):
            self.assertEqual(agents.command('codex'), ['/bin/agent'])
            with self.assertRaises(ValueError): agents.command('kiro','','id')
            with self.assertRaises(ValueError): agents.command('opencode','model')

    def test_auth_no_identity_leak_and_unknown_not_ready(self):
        cases = [('kiro',(1,'{"account":null}',''),'signed_out'),
                 ('claude',(0,'{"loggedIn":true,"email":"private@example.test"}',''),'signed_in'),
                 ('codex',(1,'Operation not permitted',''),'unknown')]
        with patch.object(agents.shutil,'which',return_value='/bin/agent'):
            for agent,response,expected in cases:
                with patch.object(agents,'probe',side_effect=[(0,'agent 2.36.0',''),response]):
                    result=agents.agent_status(agent)
                    self.assertEqual(result['auth'],expected)
                    self.assertNotIn('private',str(result))
        with patch.object(agents.shutil,'which',return_value=None):
            self.assertEqual(agents.agent_status('kiro')['readiness'],'not_installed')

    def test_native_identity_and_schema_fail_closed(self):
        with patch.object(agents,'_kiro_list',return_value=({'sessions':[{'session_id':'exact-id','title':'native'}]},'')):
            self.assertEqual(agents.native_sessions('kiro','/tmp')['items'][0]['id'],'exact-id')
            agents.validate_resume('kiro','/tmp','exact-id')
            with self.assertRaises(ValueError): agents.validate_resume('kiro','/tmp','exact')
        with patch.object(agents,'_kiro_list',return_value=([{'id':'same'},{'id':'same'}],'')):
            with self.assertRaises(ValueError): agents.validate_resume('kiro','/tmp','same')
        with patch.object(agents,'_kiro_list',return_value=({'surprise':[]},'')):
            self.assertTrue(agents.native_sessions('kiro','/tmp')['error'])

    def test_models_and_blocked_errors(self):
        with patch.object(agents,'_kiro_list',return_value=({'models':[{'id':'real-id','name':'Real'}]},'')):
            self.assertEqual(agents.available_models('kiro','/tmp')['items'],[{'id':'real-id','name':'Real'}])
        with patch.object(agents.shutil,'which',return_value='/bin/agent'), patch.object(agents,'help_text',return_value='--list-sessions'), patch.object(agents,'probe',return_value=(1,'secret identity Operation not permitted','')):
            result=agents.native_sessions('kiro','/tmp')
            self.assertIn('blocked',result['error'])
            self.assertNotIn('secret',str(result))

    def test_probe_output_and_time_bounds(self):
        code,text,error=agents.probe([sys.executable,'-c','print("ok")'])
        self.assertEqual((code,text,error),(0,'ok\n',''))
        _,_,error=agents.probe([sys.executable,'-c','import time;time.sleep(2)'],timeout=.05)
        self.assertIn('timed out',error)
        with patch.object(agents,'MAX_OUTPUT',100):
            _,_,error=agents.probe([sys.executable,'-c','print("x"*1000)'])
            self.assertIn('output limit',error)

if __name__=='__main__': unittest.main()
