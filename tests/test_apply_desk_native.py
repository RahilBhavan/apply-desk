"""The live member bridge uses the real native packet/journal interface."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from apply_desk.native_host import MemberHost
from apply_desk.workspace import Workspace

ORIGIN = 'chrome-extension://' + 'a' * 32 + '/'


class MemberNativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        pdf = self.root / 'resume.pdf'
        pdf.write_bytes(b'%PDF-1.4\nfictional')
        self.workspace = Workspace.create(self.root / 'member', {'first_name': 'Alex', 'last_name': 'Student'}, pdf)
        self.workspace.import_jobs('company,title,apply_url\nExample,Intern,https://jobs.example.com/1\n')
        self.role = self.workspace.list_jobs()['jobs'][0]['id']
        self.config = {'workspace': str(self.workspace.root), 'allowed_origin': ORIGIN, 'state': str(self.root / 'state')}
        self.host = MemberHost(self.config, ORIGIN)

    def packet(self):
        return self.host.handle({'id': 'packet', 'op': 'packet', 'role_id': self.role, 'standing': True})

    def record(self, packet):
        return {**{key: packet[key] for key in ('role_version', 'packet_digest')},
                'url': 'https://jobs.example.com/1', 'document_id': 'doc', 'form_digest': 'form',
                'status': 'scanned', 'updated_at': '2026-11-11T00:00:00Z', 'issues': [],
                'fields': [{'key': 'text|why this role|1', 'label': 'Why this role?', 'kind': 'text',
                            'required': True, 'value': '', 'options': [], 'valid': True, 'files': []}]}

    def test_scanned_questions_reach_mcp_and_new_answers_reach_native_without_export(self):
        before = self.packet()
        self.host.handle({'id': 'scan', 'op': 'save', 'role_id': self.role, 'record': self.record(before)})
        self.assertEqual(self.workspace.context(self.role)['fields'][0]['label'], 'Why this role?')
        self.assertEqual(self.packet()['packet_digest'], before['packet_digest'])
        revision = self.workspace.context(self.role)['revision']
        proposal = self.workspace.propose(self.role, 'Why this role?', 'I want to learn.', ['profile:first_name'], revision)
        self.assertFalse(any(field['label'] == 'Why this role?' for field in self.packet()['fields']))
        self.workspace.accept(proposal['proposal_id'])
        after = self.packet()
        self.assertNotEqual(after['packet_digest'], before['packet_digest'])
        answer = next(field for field in after['fields'] if field['label'] == 'Why this role?')
        self.assertEqual(answer['answer'], 'I want to learn.')
        self.assertTrue(answer['verified'])
        self.assertFalse(after['data_consent'])
        self.assertFalse(after['truth_attestation'])
        from internship_applier.extension.host import Rejected
        with self.assertRaises(Rejected):
            self.host.handle({'id': 'old-scan', 'op': 'save', 'role_id': self.role, 'record': self.record(before)})

    def test_native_subprocess_restart_and_foreign_origin(self):
        config = self.root / 'config.json'
        config.write_text(json.dumps(self.config))
        request = json.dumps({'id': 'roles', 'op': 'list'}).encode()
        frame = struct.pack('@I', len(request)) + request
        command = [sys.executable, '-m', 'apply_desk.desktop_entry', 'native-host', '--config', str(config)]
        for _ in range(2):
            process = subprocess.run(command + [ORIGIN], input=frame, capture_output=True, check=True)
            size = struct.unpack('@I', process.stdout[:4])[0]
            reply = json.loads(process.stdout[4:4 + size])
            self.assertEqual(reply['result']['roles'][0]['role_id'], self.role)
        process = subprocess.run(command + ['chrome-extension://' + 'b' * 32 + '/'], input=frame, capture_output=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse(json.loads(process.stdout[4:])['ok'])

    def test_direct_answers_and_public_list_do_not_leak_member_data(self):
        packet = self.packet()
        self.host.handle({'id': 'capture', 'op': 'save', 'role_id': self.role, 'record': self.record(packet)})
        current = self.workspace.context(self.role)['revision']
        self.workspace.confirm_answer(self.role, 'Why this role?', 'My own answer.', current)
        self.assertEqual(self.workspace.context(self.role)['fields'][0]['answer'], 'My own answer.')
        shared = self.workspace.export_jobs()
        self.assertNotIn('Alex', shared)
        self.assertNotIn('My own answer', shared)
        self.assertEqual(len(shared.splitlines()), 2)


if __name__ == '__main__':
    unittest.main()

class ReleaseRegressionTests(unittest.TestCase):
    def test_member_school_does_not_inherit_a_personal_campus_alias(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            member = Workspace.create_pdf(root / 'member', {'school': 'University of Michigan'}, b'%PDF-1.4\nfictional')
            member.import_jobs('company,title,apply_url\nPublic,Intern,https://jobs.example.com/job/123\n')
            job = member.list_jobs()['jobs'][0]['id']
            host = MemberHost({'workspace': str(member.root), 'allowed_origin': ORIGIN, 'state': str(root / 'state')}, ORIGIN)
            packet = host.handle({'id': 'campus', 'op': 'packet', 'role_id': job, 'standing': True})
            self.assertEqual(next(field['answer'] for field in packet['fields'] if field['label'] == 'School'), 'University of Michigan')
            self.assertTrue(all('aliases' not in field for field in packet['fields']))

    def test_personalized_urls_never_enter_public_export_and_review_is_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); pdf=root/'resume.pdf';pdf.write_bytes(b'%PDF-1.4\nfictional')
            member=Workspace.create(root/'member',{'first_name':'Alex'},pdf)
            member.import_jobs('company,title,apply_url\nPrivate,Invite,https://jobs.example.com/apply?email=alex%40school.edu&token=private-invite\nPublic,Intern,https://jobs.example.com/job/123?gh_jid=123\n')
            preview=member.share_preview()
            self.assertEqual(preview['excluded'],1)
            exported=member.export_jobs(preview['share_id'])
            self.assertNotIn('private-invite',exported);self.assertNotIn('alex',exported)
            member.import_jobs('company,title,apply_url\nAnother,Intern,https://jobs.example.com/job/456\n')
            with self.assertRaises(ValueError):member.export_jobs(preview['share_id'])

    def test_multiple_independent_drafts_can_be_confirmed_then_profile_update_invalidates_packets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);pdf=root/'resume.pdf';pdf.write_bytes(b'%PDF-1.4\nfictional')
            member=Workspace.create(root/'member',{'major':'Computer Science'},pdf)
            member.import_jobs('company,title,apply_url\nPublic,Intern,https://jobs.example.com/job/123\n')
            job=member.list_jobs()['jobs'][0]['id']
            qs=[{'label':label,'type':'text','options':[],'required':True} for label in ('Why this role?','What interests you?')]
            member.capture(job,qs,member.list_jobs()['revision'])
            current=member.context(job)['revision']
            drafts=[member.propose(job,q['label'],'To use my Computer Science studies.',['profile:major'],current) for q in qs]
            for draft in drafts:member.accept(draft['proposal_id'])
            self.assertTrue(all(field['answer'] for field in member.context(job)['fields']))
            snapshot=member.engine_snapshot()
            member.update_profile({'major':'Mathematics'},b'%PDF-1.4\nnew fictional resume',member.context(job)['revision'])
            self.assertNotEqual(member.engine_snapshot(),snapshot)
            self.assertTrue(all(not field['answer'] for field in member.context(job)['fields']))
            self.assertTrue((snapshot/'resume.pdf').read_bytes().endswith(b'fictional'))

class ResumeEvidenceTests(unittest.TestCase):
    def test_real_pdf_text_is_source_evidence_and_never_a_profile_fact(self):
        stream=b'BT /F1 12 Tf 72 720 Td (Built a scheduling app with Python.) Tj ET'
        objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
          b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
          b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream',
          b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
        pdf=b'%PDF-1.4\n';offsets=[]
        for number,obj in enumerate(objects,1):
            offsets.append(len(pdf));pdf+=str(number).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
        xref=len(pdf);pdf+=b'xref\n0 6\n0000000000 65535 f \n'
        for offset in offsets:pdf+=f'{offset:010d} 00000 n \n'.encode()
        pdf+=b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(xref).encode()+b'\n%%EOF\n'
        with tempfile.TemporaryDirectory() as temporary:
            member=Workspace.create_pdf(Path(temporary)/'member',{'major':'Computer Science'},pdf)
            member.import_jobs('company,title,apply_url\nPublic,Intern,https://jobs.example.com/job/123\n')
            job=member.list_jobs()['jobs'][0]['id']
            context=member.context(job)
            self.assertTrue(any(key.startswith('resume:') and 'scheduling app with Python' in value for key,value in context['evidence'].items()))
            with member.state() as state:self.assertEqual(state['profile'],{'major':'Computer Science'})
