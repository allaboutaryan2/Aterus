"""Version compatibility fixtures; these do not contact model providers."""
import unittest
from unittest.mock import patch
import agents

LEGACY = 'Usage: opencode [flags]\n--cwd string\n--output-format string\n--prompt string\n--version'
MODERN = 'opencode [project]\n--session string\n--model string\n  opencode models [provider]\n  opencode auth [command]\n  opencode session [command]'


class OpenCodeTests(unittest.TestCase):
    def test_legacy_launch_and_controls_never_send_noninteractive_flags(self):
        with patch.object(agents.shutil, 'which', return_value='/bin/opencode'), patch.object(agents, 'help_text', return_value=LEGACY):
            self.assertEqual(agents.command('opencode'), ['/bin/opencode'])
            self.assertEqual(agents.controls('opencode')['submit'], '\x13')
            for model, resume in (('provider/model', ''), ('', 'native-id')):
                with self.assertRaises(ValueError):
                    agents.command('opencode', model, resume)
            with self.assertRaisesRegex(ValueError, 'no CLI login'):
                agents.login_command('opencode')
            with patch.object(agents, 'probe') as probe:
                self.assertFalse(agents.native_sessions('opencode', '/tmp')['supported'])
                self.assertFalse(agents.available_models('opencode', '/tmp')['supported'])
                probe.assert_not_called()

    def test_modern_commands_and_login(self):
        with patch.object(agents.shutil, 'which', return_value='/bin/opencode'), patch.object(agents, 'help_text', return_value=MODERN):
            self.assertEqual(agents.command('opencode', 'provider/model', 'ses_123'), ['/bin/opencode', '--session', 'ses_123', '--model', 'provider/model'])
            self.assertEqual(agents.controls('opencode')['submit'], '\r')
            self.assertEqual(agents.login_command('opencode'), ['/bin/opencode', 'auth', 'login'])
            for bad in ('--auto', 'native\rpermission', '\x1bcommand'):
                with self.assertRaises(ValueError):
                    agents.command('opencode', resume=bad)

    def test_native_sessions_require_exact_workspace_and_unique_identity(self):
        def help_for(agent, sub=()):
            return '--format json' if sub == ('session', 'list') else MODERN
        raw = '[{"id":"ses_exact","directory":"/tmp","title":"Current"},{"id":"ses_other","directory":"/private/other"},{"id":"ses_unknown"},{"id":"ses_relative","directory":"."}]'
        with patch.object(agents, 'help_text', side_effect=help_for), patch.object(agents, '_opencode_query', return_value=(raw, '')):
            result = agents.native_sessions('opencode', '/tmp')
            self.assertEqual([s['id'] for s in result['items']], ['ses_exact'])
            agents.validate_resume('opencode', '/tmp', 'ses_exact')
            with self.assertRaises(ValueError):
                agents.validate_resume('opencode', '/tmp', 'ses_other')
        duplicate = '[{"id":"same","directory":"/tmp"},{"id":"same","directory":"/tmp"}]'
        with patch.object(agents, 'help_text', side_effect=help_for), patch.object(agents, '_opencode_query', return_value=(duplicate, '')):
            with self.assertRaisesRegex(ValueError, 'ambiguous'):
                agents.validate_resume('opencode', '/tmp', 'same')
        with patch.object(agents, 'help_text', side_effect=help_for), patch.object(agents, '_opencode_query', return_value=('{}', '')):
            self.assertTrue(agents.native_sessions('opencode', '/tmp')['error'])

    def test_models_filter_log_lines_and_deduplicate(self):
        raw = 'WARNING: private credentials not printed\nanthropic/claude-test\nopenai/test.model\nanthropic/claude-test\n'
        with patch.object(agents, 'help_text', return_value=MODERN), patch.object(agents, '_opencode_query', return_value=(raw, '')):
            result = agents.available_models('opencode', '/tmp')
            self.assertEqual([m['id'] for m in result['items']], ['anthropic/claude-test', 'openai/test.model'])
            self.assertNotIn('private', str(result))

    def test_status_does_not_equate_installed_with_authenticated(self):
        with patch.object(agents.shutil, 'which', return_value='/bin/opencode'), patch.object(agents, 'help_text', return_value=LEGACY), patch.object(agents, 'probe', return_value=(0, '0.0.55', '')):
            status = agents.agent_status('opencode')
            self.assertEqual(status['version'], '0.0.55')
            self.assertEqual(status['auth'], 'unknown')
            self.assertEqual(status['readiness'], 'provider_unverified')
        hint = agents.startup_hint('opencode', b'private-token Error: agent coder not found')
        self.assertIn('coder', hint)
        self.assertNotIn('private-token', hint)
        self.assertEqual(agents.startup_hint('claude', b'agent coder not found'), '')


if __name__ == '__main__':
    unittest.main()
