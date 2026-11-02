import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import terminal_view as view


class TerminalViewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.workspace=Path(self.temp.name)
        self.service=view.TerminalView(enabled=True)
        self.ps='321 %s ttys001 S+ Sun Nov 1 01:33:18 2026 /Users/test/bin/kiro-cli\n' % view.os.getuid()
        self.platform=patch.object(view.sys,'platform','darwin')
        self.platform.start()

    def tearDown(self):
        self.platform.stop()
        self.temp.cleanup()

    def fake_probe(self, argv, **kwargs):
        if argv[0]=='/bin/ps': return 0,self.ps,''
        if argv[0]=='/usr/sbin/lsof': return 0,'p321\nn'+str(self.workspace)+'\n',''
        if argv[0]=='/usr/bin/osascript': return 0,'\n'.join(str(i) for i in range(450)),''
        raise AssertionError(argv)

    def test_opt_in_and_platform(self):
        with self.assertRaisesRegex(view.TerminalViewError,'disabled'): view.TerminalView().discover(self.workspace)
        with patch.object(view.sys,'platform','win32'):
            with self.assertRaisesRegex(view.TerminalViewError,'requires macOS'): self.service.discover(self.workspace)

    def test_discovery_identity_and_read_only_history(self):
        with patch.object(view,'probe',side_effect=self.fake_probe) as probe:
            record=self.service.discover(self.workspace)[0]
            history=self.service.read(record)
            self.assertEqual(len(history.splitlines()),400)
            self.assertEqual(history.splitlines()[0],'50')
            commands=[call.args[0] for call in probe.call_args_list]
            self.assertTrue(all(cmd[0] in ('/bin/ps','/usr/sbin/lsof','/usr/bin/osascript') for cmd in commands))
            script=next(cmd for cmd in commands if cmd[0]=='/usr/bin/osascript')
            self.assertEqual(script[-1],'/dev/ttys001')
            self.assertNotIn('do script',script[-2])
            self.assertNotIn('keystroke',script[-2])

    def test_shell_background_foreign_owner_and_node_skipped(self):
        uid=view.os.getuid()
        for line in [self.ps.replace('S+','S'),self.ps.replace(str(uid),str(uid+1),1),self.ps.replace('kiro-cli','zsh'),self.ps.replace('kiro-cli','node')]:
            with patch.object(view,'probe',return_value=(0,line,'')):
                self.assertEqual(self.service.discover(self.workspace),[])

    def test_pid_reuse_and_workspace_escape_fail_closed(self):
        with patch.object(view,'probe',side_effect=self.fake_probe): record=self.service.discover(self.workspace)[0]
        with patch.object(view,'probe',return_value=(0,self.ps.replace('01:33:18','01:33:19'),'')):
            with self.assertRaisesRegex(view.TerminalViewError,'identity changed'): self.service.read(record)
        with patch.object(view,'probe',side_effect=[(0,self.ps,''),(0,'n/\n','')]):
            with self.assertRaisesRegex(view.TerminalViewError,'outside'): self.service.read(record)

    def test_process_and_automation_denials_sanitized(self):
        with patch.object(view,'probe',return_value=(1,'ps: Operation not permitted PRIVATE','')):
            with self.assertRaisesRegex(view.TerminalViewError,'blocked'): self.service.discover(self.workspace)
        with patch.object(view,'probe',side_effect=self.fake_probe): record=self.service.discover(self.workspace)[0]
        def deny(argv,**kwargs):
            if argv[0]=='/usr/bin/osascript': return 1,'PRIVATE not authorized -1743',''
            return self.fake_probe(argv,**kwargs)
        with patch.object(view,'probe',side_effect=deny):
            with self.assertRaisesRegex(view.TerminalViewError,'Automation') as error: self.service.read(record)
            self.assertNotIn('PRIVATE',str(error.exception))

    def test_exit_during_read_discards_history(self):
        with patch.object(view,'probe',side_effect=self.fake_probe): record=self.service.discover(self.workspace)[0]
        calls=0
        def exited(argv,**kwargs):
            nonlocal calls
            if argv[0]=='/bin/ps':
                calls+=1
                if calls==2:return 1,'',''
            return self.fake_probe(argv,**kwargs)
        with patch.object(view,'probe',side_effect=exited):
            with self.assertRaisesRegex(view.TerminalViewError,'exited'):self.service.read(record)

if __name__=='__main__':unittest.main()
