"""Standalone engine -> native host -> desk -> MCP -> confirmation -> form, on fictional HTTPS."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from apply_desk.release import assemble
from apply_desk.integration import install_browser
from apply_desk.web_server import make_server
from apply_desk.workspace import Workspace

FORM = '''<!doctype html><html><head><title>Fictional employer</title></head><body><h1>Intern application</h1>
<form id="application"><label>Full name<input id="name" required></label><label>Email<input id="email" type="email" required></label>
<label>Why this role?<textarea id="why" required></textarea></label><label>Resume<input id="resume" type="file" required></label>
<label><input id="terms" type="checkbox" required>I agree to the terms</label><button type="submit">Submit application</button></form>
<script>window.submits=0;document.querySelector('form').onsubmit=e=>{e.preventDefault();window.submits++;}</script></body></html>'''
MCP_PROPOSAL = '''
import asyncio,sys
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
async def run():
 p=StdioServerParameters(command=sys.executable,args=['-m','apply_desk','--workspace',sys.argv[1],'mcp'])
 async with stdio_client(p) as (r,w):
  async with ClientSession(r,w) as c:
   await c.initialize()
   jobs=await c.call_tool('list_apply_jobs',{})
   context=await c.call_tool('get_application_context',{'role_id':sys.argv[2]})
   import json
   data=json.loads(context.content[0].text)
   result=await c.call_tool('propose_application_answer',{'role_id':sys.argv[2],'label':'Why this role?',
    'answer':'I want to apply my Computer Science studies.','evidence_keys':['profile:major'],'expected_revision':data['revision']})
   assert not result.isError
asyncio.run(run())
'''


class EngineBrowserTests(unittest.TestCase):
    def test_standalone_live_preparation_and_member_confirmation(self):
        from playwright.sync_api import sync_playwright
        parent = Path.home() / 'scratch/main/apply-desk-release-tests'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            root = Path(temporary)
            release = assemble(root / 'source')
            browser_files = release / 'apply_desk/browser'
            profile = root / 'config/chromium'
            pdf = root / 'resume.pdf'
            pdf.write_bytes(b'%PDF-1.4\nfictional')
            workspace = Workspace.create(root / 'member', {'first_name': 'Alex', 'last_name': 'Student',
                'email': 'alex@example.com', 'major': 'Computer Science'}, pdf)
            workspace.import_jobs('company,title,apply_url\nFictional Employer,Intern,https://jobs.example.test/apply\n')
            role = workspace.list_jobs()['jobs'][0]['id']
            with patch('apply_desk.integration.browser_source', return_value=browser_files):
                installed = install_browser(workspace.root, root / 'support', profile / 'NativeMessagingHosts')
            server = make_server(workspace.root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with sync_playwright() as p:
                    env = {k:v for k,v in os.environ.items() if k not in {'DISPLAY','WAYLAND_DISPLAY'}}
                    env.update(XDG_CONFIG_HOME=str(root / 'config'), VK_ICD_FILENAMES='/dev/null',
                               DBUS_SYSTEM_BUS_ADDRESS='unix:path=/dev/null', DBUS_SESSION_BUS_ADDRESS='unix:path=/dev/null')
                    context = p.chromium.launch_persistent_context(str(profile),channel='chromium',headless=True,env=env,
                        args=['--ozone-platform=headless','--use-gl=angle','--use-angle=swiftshader','--disable-vulkan',
                              '--disable-extensions-except='+str(browser_files),'--load-extension='+str(browser_files)])
                    context.route('https://jobs.example.test/**', lambda route: route.fulfill(status=200,content_type='text/html',body=FORM))
                    page = context.new_page(); page.goto('https://jobs.example.test/apply')
                    cdp = context.browser.new_browser_cdp_session()
                    targets = cdp.send('Target.getTargets', {'filter':[{'type':'tab','exclude':False}]})['targetInfos']
                    target = next(t for t in targets if t['url']==page.url)
                    cdp.send('Extensions.triggerAction',{'id':installed['extension_id'],'targetId':target['targetId']})
                    for popup in context.pages:
                        if popup.url.endswith('/popup.html'): popup.close()
                    ui = context.new_page()
                    ui.goto('chrome-extension://'+installed['extension_id']+'/review.html')
                    ui.locator('#role option[value="'+role+'"]').wait_for(state='attached')
                    ui.locator('#role').select_option(role)
                    tabs = ui.evaluate("() => chrome.runtime.sendMessage({type:'orbit:tabs'})")['result']['tabs']
                    tab = next(tab for tab in tabs if tab['url']==page.url)
                    ui.locator('#target').select_option(str(tab['id']))
                    ui.locator('#prepare').click()
                    ui.locator('#notice').filter(has_text='Scan, Fill and Verify done').wait_for(timeout=20000)
                    self.assertEqual(page.locator('#name').input_value(),'Alex Student')
                    self.assertEqual(page.locator('#email').input_value(),'alex@example.com')
                    self.assertEqual(page.locator('#why').input_value(),'')
                    self.assertFalse(page.locator('#terms').is_checked())
                    self.assertEqual(page.evaluate('window.submits'),0)
                    self.assertIn('Why this role?', [q['label'] for q in workspace.context(role)['fields']])
                    subprocess.run([sys.executable,'-c',MCP_PROPOSAL,str(workspace.root),role],check=True,capture_output=True,timeout=20)
                    self.assertEqual(page.locator('#why').input_value(),'')
                    desk = context.new_page(); desk.goto(f'http://127.0.0.1:{server.server_port}')
                    desk.get_by_role('button',name='Confirm this answer',exact=True).click()
                    desk.get_by_text('Answer confirmed.',exact=False).wait_for()
                    ui.locator('#prepare').click()
                    ui.locator('#notice').filter(has_text='Scan, Fill and Verify done').wait_for(timeout=20000)
                    self.assertEqual(page.locator('#why').input_value(),'I want to apply my Computer Science studies.')
                    self.assertFalse(page.locator('#terms').is_checked())
                    self.assertEqual(page.evaluate('window.submits'),0)
                    page.locator('#terms').check(); page.get_by_role('button',name='Submit application').click()
                    self.assertEqual(page.evaluate('window.submits'),1)
                    desk.once('dialog',lambda dialog:dialog.accept())
                    desk.get_by_role('button',name='Record as submitted').click()
                    desk.get_by_text('Submitted · recorded by you').wait_for()
                    self.assertEqual(workspace.engine_snapshot().joinpath('batch.json').read_text().count('Fictional Employer'),0)
                    context.close()
            finally:
                server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
