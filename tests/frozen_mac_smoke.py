"""Exercise the frozen app from an empty cwd, with fictional member data only."""
import asyncio,base64,json,os,re,select,struct,subprocess,sys,tempfile
from pathlib import Path
from urllib.request import Request,urlopen

def fictional_pdf():
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
 return pdf+b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(xref).encode()+b'\n%%EOF\n'

binary=sys.argv[1]
parent=Path.home()/'scratch/apply-desk/frozen-smoke'
parent.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=parent) as temporary:
 root=Path(temporary); member=root/'member'
 environment={k:v for k,v in os.environ.items() if k not in {'PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'}}
 environment['PATH']='/usr/bin:/bin:/usr/sbin:/sbin'
 server=subprocess.Popen([binary,'--workspace',str(member),'serve','--no-open'],cwd='/var/empty',env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 try:
  assert select.select([server.stdout],[],[],20)[0], 'app did not start'
  line=server.stdout.readline().strip();assert line.startswith('Apply Desk: '),line
  url=line.split(': ',1)[1]
  with urlopen(url) as response:html=response.read().decode()
  token=re.search('name="apply-desk-token" content="([^"]+)"',html).group(1)
  def api(path,body=None):
   request=Request(url+'/api/'+path,data=json.dumps(body).encode() if body is not None else None,
    headers={'Content-Type':'application/json','X-Apply-Desk':token})
   with urlopen(request,timeout=15) as response:return json.load(response)
  api('init',{'profile':{'first_name':'Alex','last_name':'Student','major':'Computer Science','school':'University of Michigan'},'resume':base64.b64encode(fictional_pdf()).decode()})
  api('jobs',{'csv':'company,title,apply_url\nFictional Employer,Intern,https://jobs.example.com/apply\n'})
  state=api('state');role=state['jobs'][0]['id']
  assert 'scheduling app with Python' in state['resume_text']
  configuration=root/'native.json';origin='chrome-extension://'+'a'*32+'/'
  configuration.write_text(json.dumps({'workspace':str(member),'state':str(root/'native-state'),'allowed_origin':origin}))
  def native(operation):
   raw=json.dumps({'id':'test',**operation}).encode()
   result=subprocess.run([binary,'native-host','--config',str(configuration),origin],input=struct.pack('@I',len(raw))+raw,capture_output=True,check=True,cwd='/var/empty',env=environment,timeout=15)
   reply=json.loads(result.stdout[4:]);assert reply['ok'],reply
   return reply['result']
  before=native({'op':'packet','role_id':role,'standing':True})
  assert not before['data_consent'] and not before['truth_attestation']
  assert all('aliases' not in field for field in before['fields'])
  connection=api('connection',{});assert '-m' not in connection['args']
  async def mcp():
   from mcp import ClientSession,StdioServerParameters
   from mcp.client.stdio import stdio_client
   params=StdioServerParameters(command=connection['command'],args=connection['args'],cwd='/var/empty',env=environment)
   async with stdio_client(params) as (r,w):
    async with ClientSession(r,w) as c:
     await c.initialize();tools=await c.list_tools();assert len(tools.tools)==5
     jobs=await c.call_tool('list_apply_jobs',{});assert not jobs.isError
     context=await c.call_tool('get_application_context',{'role_id':role});data=json.loads(context.content[0].text)
     captured=await c.call_tool('capture_application_questions',{'role_id':role,'expected_revision':data['revision'],
       'questions':[{'label':'Why this role?','type':'textarea','options':[],'required':True}]});assert not captured.isError
     context=await c.call_tool('get_application_context',{'role_id':role});data=json.loads(context.content[0].text)
     proposed=await c.call_tool('propose_application_answer',{'role_id':role,'label':'Why this role?','answer':'I want to build on my scheduling app work.',
      'evidence_keys':[next(key for key in data['evidence'] if key.startswith('resume:'))],'expected_revision':data['revision']});assert not proposed.isError
  asyncio.run(mcp())
  assert not any(f['label']=='Why this role?' for f in native({'op':'packet','role_id':role,'standing':True})['fields'])
  proposals=api('state')['proposals'];assert len(proposals)==1
  api('accept',{'proposal_id':proposals[0]['id']})
  after=native({'op':'packet','role_id':role,'standing':True});assert after['packet_digest']!=before['packet_digest']
  assert next(f for f in after['fields'] if f['label']=='Why this role?')['verified']
  second=subprocess.run([binary,'--workspace',str(member),'serve','--no-open'],cwd='/var/empty',env=environment,capture_output=True,timeout=10)
  assert second.returncode==0
  preview=api('share-preview',{});shared=api('share-jobs',{'share_id':preview['share_id']})['csv'];assert 'Alex' not in shared and 'Computer Science' not in shared
  print(json.dumps({'frozen_ui':True,'native_messaging':True,'mcp_tools':5,'unconfirmed_draft_blocked':True,'confirmed_answer_live':True,'inherited_grants_disabled':True,'duplicate_launch_reused':True,'club_export_private':True}))
 finally:
  server.terminate()
  try:server.wait(10)
  except subprocess.TimeoutExpired:server.kill();server.wait()
  if server.returncode not in {-15,0}:print(server.stderr.read(),file=sys.stderr)
