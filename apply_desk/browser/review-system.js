/* design-owner: Orbit because this is private application preparation. */
'use strict';
globalThis.OrbitSystem=(()=>{
 let api=null,packet=null,launchId=null,launchPacket=null,status='not_started';
 const $=id=>document.getElementById(id);
 const active=()=>['reserved','starting','ready','unknown','interrupted'].includes(status);
 function controls(pending){const remote=packet?.transport?.manual_submission===true;$('t3-review').disabled=pending||!packet?.system||active()||remote;$('t3-status-button').disabled=pending||!packet?.system||remote;}
 function display(value){status=value.status;if(['closed','failed'].includes(status))launchId=null;$('t3-status').textContent=({not_started:'No guarded review has been opened.',reserved:'Opening your application review browser…',starting:'Preparing the selected application in your review browser…',ready:'Review is open. Inspect its fresh form values and approve there.',closed:'The review browser closed. Check application history before continuing.',failed:'Review stopped. Check the local runner log before trying again.',unknown:'The earlier launch needs reconciliation. Do not start a replacement.'})[status]||value.message||'Review status needs checking.';}
 return {
  render(value){packet=value;$('system-review').hidden=!value?.system;if(!value?.system)return;const actions=document.querySelector('section[aria-label="Preparation actions"]');if(actions)actions.before($('system-review'));if(launchPacket!==value.packet_digest){launchId=null;status='not_started';launchPacket=value.packet_digest;}$('t3-resume').textContent='Custom resume: '+(value.resume?.name||'Selected T3 PDF')+'. Its existing formatting is preserved.';$('t3-status').textContent=value.transport?.manual_submission?'Connected live to T3 on box. Choose this Mac’s employer tab, then Scan → Fill → Verify below. Review every answer and submit manually in that tab. Guarded submission from Mac is not connected.':'Start here to sign in, edit and review in one guarded browser session. Scan and Fill below are optional for a separate tab.';},
  controls,
  attach(value){api=value;$('t3-review').addEventListener('click',()=>api.action(async()=>{const p=api.packet();if(!p?.system)throw new Error('Connect your T3 application system first.');if(!launchId)launchId=crypto.randomUUID();display(await api.call('review_start',{role_id:api.role(),packet_digest:p.packet_digest,launch_id:launchId}));}));$('t3-status-button').addEventListener('click',()=>api.action(async()=>display(await api.call('review_status',{role_id:api.role()}))));}
 };
})();
