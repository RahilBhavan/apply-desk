/* design-owner: Orbit because this is private application preparation. */
'use strict';
(() => {
  const W=globalThis.OrbitWorker={};
  W.epoch=crypto.randomUUID();
  const ready=chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'});
  W.fail=(code,message)=>{throw Object.assign(new Error(message),{code});};
  W.exact=(a,b)=>{try{const x=new URL(a),y=new URL(b);x.hash='';y.hash='';return x.href===y.href;}catch{return false;}};
  W.native=async(op,data={})=>{
    const id=crypto.randomUUID();let reply;
    try{reply=await chrome.runtime.sendNativeMessage('com.applydesk.host',{id,op,...data,...(data.role_id?{standing:true}:{})});}
    catch{W.fail('host_disconnected','Orbit local host is unavailable. Check its installation and batch configuration, then retry.');}
    if(!reply||reply.id!==id||typeof reply.ok!=='boolean')W.fail('host_protocol','The local host returned an invalid response. Check host and extension versions.');
    if(!reply.ok)W.fail(reply.error?.code||'host_error',reply.error?.message||'The local host could not complete this action.');
    return reply.result;
  };
  W.binding=async role=>{await ready;return(await chrome.storage.local.get('binding:'+role))['binding:'+role]||null;};
  W.store=async(role,value)=>{await ready;await chrome.storage.local.set({['binding:'+role]:value});};
  W.packet=async role=>{
    const p=await W.native('packet',{role_id:role});
    if(!p||p.role_id!==role||!Array.isArray(p.fields)||!p.packet_digest||!p.role_version||!/^https?:/.test(p.apply_url))W.fail('invalid_packet','The configured application packet is invalid.');
    return p;
  };
  W.target=async(b,p)=>{
    if(!b)W.fail('no_target','Choose the employer tab before scanning.');
    let tab;try{tab=await chrome.tabs.get(b.tab_id);}catch{W.fail('tab_closed','The chosen tab closed. Choose it again.');}
    if(!(p.allowed_urls||[p.apply_url]).some(u=>W.exact(u,tab.url)))W.fail('wrong_tab','This tab is outside the exact application steps configured for the role.');
    return tab;
  };
  W.inject=async tab=>{
    const frames=await chrome.scripting.executeScript({target:{tabId:tab.id},world:'ISOLATED',files:['scanner.js','controls.js','page.js']});
    const document_id=frames[0]?.documentId;
    if(!document_id)W.fail('document_unavailable','Chrome did not identify the current document. Scan again.');
    return {tabId:tab.id,documentIds:[document_id]};
  };
  W.page=async(target,method,args=[])=>{
    const r=await chrome.scripting.executeScript({target,world:'ISOLATED',func:async(m,a)=>{
      if(!['run','status','cancel','focus'].includes(m))throw new Error('Unknown page operation.');
      return await globalThis.OrbitApply[m](...a);
    },args:[method,args]});
    return r[0]?.result;
  };
  W.read=async(target,request,p)=>{
    const s=await W.page(target,'run',[request]);
    if(!s||!(p.allowed_urls||[p.apply_url]).some(u=>W.exact(u,s.url))||!s.document_id||!s.form_digest||!Array.isArray(s.fields)||!Array.isArray(s.issues)||!['scanned','needs_input','access_hold','conflict','verified_fields','error'].includes(s.status))W.fail('invalid_snapshot','The current application could not be read safely.');
    return s;
  };
  W.record=(p,s)=>{
    const r={role_version:p.role_version,packet_digest:p.packet_digest,url:s.url,document_id:s.document_id,form_digest:s.form_digest,status:s.status,fields:s.fields,issues:s.issues,updated_at:new Date().toISOString()};
    for(const k of ['step_id','observed_at','settled','revision','owner'])if(s[k]!==undefined)r[k]=s[k];
    return r;
  };
  W.digest=async value=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value))))].map(x=>x.toString(16).padStart(2,'0')).join('');
  W.fingerprint=s=>W.digest({document_id:s.document_id,form_digest:s.form_digest,revision:s.revision,fields:s.fields,issues:s.issues,status:s.status==='scanned'?'verified_fields':s.status});
  W.remember=async(role,p,tab,target,s)=>W.store(role,{tab_id:tab.id,worker_epoch:W.epoch,chrome_document_id:target.documentIds[0],packet_digest:p.packet_digest,role_version:p.role_version,observed_digest:await W.fingerprint(s),settled:s.settled===true,expected:{document_id:s.document_id,form_digest:s.form_digest,url:s.url,revision:s.revision,owner:s.owner}});
  W.context=(p,tab,target)=>({tab_id:tab.id,document_id:target.documentIds[0],url:tab.url,packet_digest:p.packet_digest,role_version:p.role_version});
})();
