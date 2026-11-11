"""Exercise the member seam, persistence and existing browser-host packet interface."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from apply_desk.workspace import Workspace

CSV = 'company,title,apply_url\nExample,Intern,https://jobs.example.com/role/1\n'
QUESTIONS = [
    {'label': 'First name', 'type': 'text', 'options': [], 'required': True},
    {'label': 'Why this role?', 'type': 'textarea', 'options': [], 'required': True},
    {'label': 'I agree to the terms', 'type': 'text', 'options': [], 'required': True}]


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdf = self.root / 'original.pdf'
        self.pdf.write_bytes(b'%PDF-1.4\nfictional resume')
        self.workspace = Workspace.create(self.root / 'member', {'first_name': 'Alex', 'major': 'Computer Science'}, self.pdf)
        self.workspace.import_jobs(CSV)
        self.role = self.workspace.list_jobs()['jobs'][0]['id']
        self.capture()

    def capture(self, questions=QUESTIONS):
        return self.workspace.capture(self.role, questions, self.workspace.list_jobs()['revision'])

    def propose(self, answer='I want to apply my Computer Science studies.'):
        return self.workspace.propose(self.role, 'Why this role?', answer, ['profile:major'],
                                      self.workspace.context(self.role)['revision'])

    def test_profile_prepares_but_draft_stays_pending_then_member_confirms(self):
        context = self.workspace.context(self.role)
        self.assertEqual(context['fields'][0]['answer'], 'Alex')
        proposal = self.propose()
        self.assertEqual(self.workspace.context(self.role)['fields'][1]['answer'], '')
        self.assertEqual(self.propose(), proposal)
        self.workspace.accept(proposal['proposal_id'])
        self.assertEqual(Workspace(self.workspace.root).context(self.role)['fields'][1]['who'], 'fact')
        self.assertTrue(self.workspace.accept(proposal['proposal_id'])['already_accepted'])
        self.assertEqual(self.workspace.context(self.role)['fields'][2]['answer'], '')

    def test_duplicate_import_restart_isolation_and_no_private_csv_columns(self):
        self.assertEqual(self.workspace.import_jobs(CSV), {'added': 0, 'total': 1})
        other = Workspace.create(self.root / 'other', {'first_name': 'Sam'}, self.pdf)
        other.import_jobs(CSV)
        self.assertNotEqual(other.list_jobs()['jobs'][0]['id'], self.role)
        with self.assertRaises(ValueError):
            other.context(self.role)
        with self.assertRaises(ValueError):
            other.accept(self.propose()['proposal_id'])
        with self.assertRaises(ValueError):
            self.workspace.import_jobs('company,title,apply_url,email\na,b,https://example.com,private@example.com\n')
        self.assertEqual(len(Workspace(self.workspace.root).list_jobs()['jobs']), 1)

    def test_stale_questions_choices_and_proposals_refused(self):
        proposal = self.propose()
        old = self.workspace.context(self.role)['revision']
        choices = [{'label': 'Preferred office', 'type': 'select', 'options': ['Detroit', 'Chicago'], 'required': True}]
        self.capture(choices)
        with self.assertRaises(ValueError):
            self.workspace.accept(proposal['proposal_id'])
        with self.assertRaises(ValueError):
            self.workspace.capture(self.role, QUESTIONS, old)
        with self.assertRaises(ValueError):
            self.workspace.propose(self.role, 'Preferred office', 'New York', ['profile:major'], self.workspace.context(self.role)['revision'])
        self.capture()
        p = self.propose()
        self.workspace.accept(p['proposal_id'])
        self.capture(QUESTIONS[:1])
        self.assertNotIn('I want to', json.dumps(self.workspace.context(self.role)))

    def test_manual_questions_and_unknown_evidence_stay_blocked(self):
        revision = self.workspace.context(self.role)['revision']
        for label, keys in [('I agree to the terms', ['profile:major']), ('Why this role?', ['profile:invented'])]:
            with self.assertRaises(ValueError):
                self.workspace.propose(self.role, label, 'yes', keys, revision)

    def test_native_host_consumes_confirmed_export_without_hub_or_t3(self):
        from apply_desk.engine import load
        Host = load()[0]
        origin = 'chrome-extension://' + 'a' * 32 + '/'
        self.workspace.accept(self.propose()['proposal_id'])
        batch = self.root / 'batch'
        self.workspace.export_batch(batch)
        host = Host({'batch': str(batch), 'state': str(self.root / 'extension-state'), 'allowed_origin': origin}, origin)
        packet = host.handle({'id': 'packet', 'op': 'packet', 'role_id': self.role})
        fields = {field['label']: field for field in packet['fields']}
        self.assertTrue(fields['First name']['verified'])
        self.assertTrue(fields['Why this role?']['verified'])
        self.assertNotIn('I agree to the terms', fields)  # Unanswered/manual questions are never trusted answers.
        self.assertTrue(packet['resume']['base64'])
        self.assertFalse(packet['data_consent'])
        self.assertFalse(packet['truth_attestation'])
        standing = host.handle({'id': 'standing', 'op': 'packet', 'role_id': self.role, 'standing': True})
        self.assertEqual(standing['packet_digest'], packet['packet_digest'])
        with self.assertRaises(FileExistsError):
            self.workspace.export_batch(batch)
        (self.workspace.root / 'resume.pdf').write_bytes(b'%PDF-changed')
        with self.assertRaises(ValueError):
            self.workspace.export_batch(self.root / 'changed-batch')

    def test_cli_restart_reads_real_persisted_values(self):
        result = subprocess.run([sys.executable, '-m', 'apply_desk', '--workspace', str(self.workspace.root),
                                 'context', self.role], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)['fields'][0]['answer'], 'Alex')


if __name__ == '__main__':
    unittest.main()
