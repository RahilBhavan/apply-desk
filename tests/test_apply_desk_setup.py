"""Install only within scratch paths; no real browser/provider settings are touched."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from apply_desk.release import assemble
from apply_desk.integration import install_browser, write_project


class SetupTests(unittest.TestCase):
    def test_allowlisted_release_and_repeatable_isolated_browser_registration(self):
        root = Path.home() / 'scratch/main/apply-desk-release-tests'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            base = Path(temporary)
            source = assemble(base / 'source')
            browser = source / 'apply_desk/browser'
            self.assertEqual(json.loads((browser / 'manifest.json').read_text())['name'], 'Apply Desk')
            for path in browser.glob('*.js'):
                self.assertFalse(any('rahil' in line.casefold() for line in path.read_text().splitlines() if line.lstrip().startswith('//')))
            self.assertFalse(any('workspace.json' in str(path) or '.sqlite' in path.name for path in source.rglob('*')))
            registration = base / 'registration'
            registration.mkdir()
            other = registration / 'another-host.json'
            other.write_text('{"preserved": true}')
            with patch('apply_desk.integration.browser_source', return_value=browser):
                first = install_browser(base / 'member', base / 'support', registration)
                second = install_browser(base / 'member', base / 'support', registration)
            self.assertEqual(first, second)
            self.assertEqual(json.loads(other.read_text()), {'preserved': True})
            native = json.loads(Path(first['registration']).read_text())
            self.assertEqual(native['allowed_origins'], ['chrome-extension://' + first['extension_id'] + '/'])
            self.assertIn('com.applydesk.host', Path(first['registration']).name)

    def test_t3_project_is_member_scoped_and_preserves_foreign_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            member = root / 'member'
            project = root / 't3'
            first = write_project(member, project)
            second = write_project(member, project)
            self.assertEqual(first, second)
            self.assertTrue((project / '.codex/config.toml').is_file())
            self.assertTrue((project / '.mcp.json').is_file())
            self.assertIn('Never confirm answers or submit', (project / 'AGENTS.md').read_text())
            foreign = root / 'foreign'
            foreign.mkdir()
            (foreign / 'README').write_text('keep')
            with self.assertRaises(ValueError):
                write_project(member, foreign)
            with self.assertRaises(ValueError):
                write_project(root / 'other', project)
            self.assertEqual((foreign / 'README').read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()

class FrozenConfigurationTests(unittest.TestCase):
    def test_frozen_configuration_is_an_executable_command_not_a_python_module_invocation(self):
        import sys
        from apply_desk.integration import connection
        with patch.object(sys,'frozen',True,create=True), patch.object(sys,'executable','/Applications/Apply Desk.app/Contents/MacOS/ApplyDesk'):
            config=connection('/private/member')
        self.assertEqual(config['command'],'/Applications/Apply Desk.app/Contents/MacOS/ApplyDesk')
        self.assertEqual(config['args'],['--workspace','/private/member','mcp'])
        self.assertNotIn('-m',config['args'])
