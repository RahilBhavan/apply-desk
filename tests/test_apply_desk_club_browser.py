"""Exercise the real member UI with fictional files on an isolated loopback server."""
import os
from pathlib import Path
import tempfile
import threading
import unittest
from apply_desk.web_server import make_server
from apply_desk.workspace import Workspace


class BrowserTests(unittest.TestCase):
    def test_onboarding_jobs_and_local_proposal_confirmation(self):
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            root = folder / 'member'
            pdf = folder / 'resume.pdf'
            pdf.write_bytes(b'%PDF-1.4\nfictional')
            csv = folder / 'club.csv'
            csv.write_text('company,title,apply_url\nExample,Software engineering intern,https://jobs.example.com/1\n')
            server = make_server(root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(f'http://127.0.0.1:{server.server_port}')
                    page.get_by_label('First name').fill('Alex')
                    page.get_by_label('Last name').fill('Student')
                    page.get_by_label('Email', exact=True).fill('alex@example.com')
                    page.get_by_label('Major optional').fill('Computer Science')
                    page.locator('#resume').set_input_files(str(pdf))
                    page.locator('#confirmed').check()
                    page.get_by_role('button', name='Create my workspace').click()
                    page.get_by_role('heading', name='Alex’s applications').wait_for()
                    page.get_by_text('Import or share a club job list', exact=True).click()
                    page.locator('#csv').set_input_files(str(csv))
                    page.get_by_role('button', name='Import jobs').click()
                    page.get_by_role('heading', name='Software engineering intern').wait_for()
                    workspace = Workspace(root)
                    role = workspace.list_jobs()['jobs'][0]['id']
                    workspace.capture(role, [{'label': 'Why this role?', 'type': 'textarea', 'options': [], 'required': True}], workspace.list_jobs()['revision'])
                    workspace.propose(role, 'Why this role?', 'To use my Computer Science studies.', ['profile:major'], workspace.context(role)['revision'])
                    page.get_by_role('button', name='Check for new questions and answers').click()
                    page.get_by_role('button', name='Confirm this answer').click()
                    page.get_by_text('Answer confirmed.', exact=False).wait_for()
                    self.assertEqual(workspace.context(role)['fields'][0]['who'], 'fact')
                    page.reload()
                    page.get_by_text('Previously confirmed.', exact=False).wait_for()
                    page.get_by_text('Advanced connection details', exact=True).click()
                    page.get_by_role('button', name='Export a preparation snapshot').click()
                    page.get_by_text('Private batch saved:', exact=False).wait_for()
                    page.get_by_role('button', name='Show local connection settings').click()
                    page.locator('#connection-result').filter(has_text='apply_desk').wait_for()
                    evidence = Path(os.environ.get('APPLY_DESK_EVIDENCE', str(folder)))
                    evidence.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(evidence / 'desktop.png'), full_page=True)
                    page.set_viewport_size({'width': 390, 'height': 844})
                    self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                    page.screenshot(path=str(evidence / 'phone.png'), full_page=True)
                    self.assertEqual(errors, [])
                    browser.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
