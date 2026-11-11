"""Real old/new desktop processes hand over one persisted member workspace."""
import json
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
from urllib.request import urlopen
from apply_desk.release import assemble
from apply_desk.runtime import directory
from apply_desk.workspace import Workspace


class UpdateTests(unittest.TestCase):
    def test_updated_app_stops_old_server_and_reuses_private_data(self):
        parent=Path.home()/'scratch/main/apply-desk-release-tests';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            root=Path(temporary)
            old=assemble(root/'old');new=assemble(root/'new')
            (old/'apply_desk/build-id.txt').write_text('old-build')
            (new/'apply_desk/build-id.txt').write_text('new-build')
            pdf=root/'resume.pdf';pdf.write_bytes(b'%PDF-1.4\nfictional')
            member=Workspace.create(root/'member',{'first_name':'Alex'},pdf)
            processes=[]
            try:
                for source in (old,new):
                    process=subprocess.Popen([sys.executable,'-m','apply_desk','--workspace',str(member.root),'serve','--no-open'],
                        cwd=source,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                    processes.append(process)
                    self.assertTrue(select.select([process.stdout],[],[],15)[0])
                    line=process.stdout.readline().strip()
                    self.assertTrue(line.startswith('Apply Desk: '),(line,process.stderr.read() if process.poll() is not None else ''))
                    url=line.split(': ',1)[1]
                    with urlopen(url+'/health') as response:health=json.load(response)
                    self.assertEqual(health['build_id'],'old-build' if source==old else 'new-build')
                self.assertEqual(processes[0].wait(10),0)
                self.assertIsNone(processes[1].poll())
                self.assertEqual(Workspace(member.root).list_jobs()['jobs'],[])
                self.assertNotEqual(directory(root/'member'),directory(root/'other-member'))
            finally:
                for process in processes:
                    if process.poll() is None:process.terminate()
                    try:process.wait(5)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
                    process.stdout.close();process.stderr.close()


if __name__=='__main__':unittest.main()
