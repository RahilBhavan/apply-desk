/* design-owner: Orbit because this is private application preparation. */
'use strict';
importScripts('worker-core.js','worker-actions.js');
const W=globalThis.OrbitWorker;
const shapes={list:['offset','limit'],review_start:['role_id','packet_digest','launch_id'],review_status:['role_id'],tabs:[],bind:['role_id','tab_id'],state:['role_id'],scan:['role_id'],fill:['role_id','operation_id'],verify:['role_id'],progress:['role_id'],observe:['role_id'],cancel:['role_id'],reconcile:['role_id'],focus:['role_id','field_key'],fact_preview:['role_id','label','value','source','scope','packet_digest'],fact_confirm:['role_id','preview_id','label','value','source','scope','packet_digest'],advice_prepare:['role_id','packet_digest','fact_keys'],advice_import:['role_id','packet_digest','response'],advice_list:['role_id'],review_event:['role_id','packet_digest','session_id','event'],review_summary:['role_id']};
async function dispatch(m){
 if(!m||typeof m!=='object'||Array.isArray(m)||typeof m.type!=='string'||!m.type.startsWith('orbit:'))W.fail('invalid_message','Unsupported extension action.');
 const op=m.type.slice(6),keys=shapes[op];if(!keys||Object.keys(m).some(k=>k!=='type'&&!keys.includes(k)))W.fail('invalid_message','Unexpected extension action parameters.');
 if(keys.includes('role_id')&&(typeof m.role_id!=='string'||!m.role_id||m.role_id.length>200))W.fail('invalid_role','Choose a configured role.');
 const data=Object.fromEntries(Object.entries(m).filter(([k])=>k!=='type'));
 if(op==='list')return W.native('list',data);
 if(op==='review_status')return W.native(op,data);
 if(op==='tabs')return {tabs:(await chrome.tabs.query({currentWindow:true})).filter(t=>/^https?:/.test(t.url||'')).map(t=>({id:t.id,title:t.title||t.url,url:t.url,active:t.active}))};
 if(op==='progress')return W.native('progress',data);
 if(op==='state')return {packet:await W.packet(m.role_id),binding:await W.binding(m.role_id),...(await W.native('progress',data)),...(await W.native('operation',data))};
 if(op==='observe')return W.observe(m.role_id);
 if(op==='cancel')return W.stop(m.role_id);
 if(op==='focus'){
   if(typeof m.field_key!=='string'||m.field_key.length>4096)W.fail('invalid_field','Choose a current field.');
   const c=await W.current(m.role_id);return {focused:await W.page(c.target,'focus',[m.field_key])};
 }
 if(['advice_list','review_event','review_summary'].includes(op))return W.native(op,data);
 return W.serial(async()=>{
   if(op==='bind'){
     if(!Number.isInteger(m.tab_id))W.fail('invalid_tab','Choose an employer tab.');
     const current=(await W.native('operation',{role_id:m.role_id})).operation;
     if(current&&['active','uncertain'].includes(current.state)){
       // The tab that ran the interrupted action may be gone (closed, or the browser restarted). Then only a new tab
       // can show what it left. Fill stays blocked until that read-only check (reconcile) is recorded.
       let old=null;try{old=await chrome.tabs.get(current.context?.tab_id);}catch{}
       if(old&&old.id!==m.tab_id&&W.exact(old.url,current.context.url))W.fail('busy','Check the interrupted action before choosing another tab.');
     }
     const p=await W.packet(m.role_id);await W.target({tab_id:m.tab_id},p);await W.store(m.role_id,{tab_id:m.tab_id});return {tab_id:m.tab_id};
   }
   if(op==='reconcile')return W.reconcile(m.role_id);
   if(['fact_preview','fact_confirm','advice_prepare','advice_import','review_start'].includes(op))return W.native(op,data);
   if(op==='fill'&&m.operation_id!==undefined&&(typeof m.operation_id!=='string'||!/^[A-Za-z0-9_.:-]{1,128}$/.test(m.operation_id)))W.fail('invalid_operation','Preparation action ID is invalid.');
   return W.execute(op,m.role_id,op==='fill'?(m.operation_id||crypto.randomUUID()):undefined);
 });
}
chrome.runtime.onMessage.addListener((message,sender,respond)=>{
 const urls=['popup.html','review.html'].map(p=>chrome.runtime.getURL(p));
 if(sender.id!==chrome.runtime.id||!urls.includes(sender.url)){respond({ok:false,error:{code:'untrusted_sender',message:'Use the Orbit extension review page.'}});return false;}
 dispatch(message).then(result=>respond({ok:true,result}),e=>respond({ok:false,error:{code:e.code||'action_failed',message:e.message||'Action failed. Scan the current tab and retry.'}}));return true;
});
