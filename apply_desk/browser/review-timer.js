/* design-owner: Orbit because this is private application preparation. */
'use strict';
(() => {
 const U=globalThis.OrbitUI,$=U.$;let session=null,bridge;
 async function render(){if(!bridge.role())return;const r=await bridge.call('review_summary',{role_id:bridge.role()});session=r.sessions.find(s=>s.current&&s.status==='unfinished')||null;const t=r.current_totals;$('timer-status').textContent=`${t.finished} completed timer(s); ${t.unfinished} unfinished; ${t.abandoned} abandoned. Completed elapsed time: ${t.completed_timer_seconds===null?'unknown':Math.round(t.completed_timer_seconds)+' seconds'}. Attention and productivity remain unmeasured.`;}
 globalThis.OrbitTimer={attach(b){bridge=b;for(const event of ['start','finish','abandon'])$('timer-'+event).addEventListener('click',()=>bridge.action(async()=>{if(!bridge.packet())throw new Error('Choose a current role first.');if(event!=='start'&&!session)throw new Error('Start a review timer first.');await bridge.call('review_event',{role_id:bridge.role(),packet_digest:bridge.packet().packet_digest,session_id:session?.session_id||crypto.randomUUID(),event});await render();U.notice('Review timer event recorded locally. It does not approve or submit an application.');}));},render};
})();
