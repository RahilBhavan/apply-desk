/* design-owner: Orbit because this is private application preparation. */
'use strict';
(() => {
 const U=globalThis.OrbitUI,$=U.$;let bridge=null,preview=null;
 const shellQuote=value=>"'"+String(value).replaceAll("'","'\\''")+"'";
 const allowed=p=>(p?.fields||[]).filter(f=>!(/attest|certif|signature|agree|consent|privacy|resume|upload|demograph|race|ethnic|gender|disab|veteran/i.test(f.label))&&!/file/i.test(f.type));
 function invalidate(){preview=null;$('fact-confirm').disabled=true;$('fact-preview').textContent='Preview the exact scope before confirming.';}
 function payload(){const p=bridge.packet();return {role_id:bridge.role(),label:$('fact-label').value,value:$('fact-value').value,source:$('fact-source').value,scope:$('fact-scope').value,packet_digest:p.packet_digest};}
 async function refreshAdvice(){const r=await bridge.call('advice_list',{role_id:bridge.role()});$('advice-results').replaceChildren();for(const job of r.advice||[]){
   const box=U.node('article');box.append(U.node('p',`${job.model} · ${job.status}`),U.node('p','Run explicitly in the repository if you choose to use the configured API credential:','muted'),U.node('pre',`python3 -m internship_applier.extension advice ${shellQuote(job.task_path)} --api-key-env ANTHROPIC_API_KEY`,'value'));
   for(const a of job.attempts||[])box.append(U.node('p',`${a.status} · model calls ${a.model_calls} · billed cost ${a.cost_usd===null?'unknown':a.cost_usd}`,'muted'));
   for(const candidate of job.proposals||[]){const row=U.node('div');row.append(U.node('p',`${candidate.question_key} → ${candidate.fact_key||'Needs your answer'}`),U.node('p',candidate.reason,'muted'));
     const index=/^fact:(\d+)$/.exec(candidate.fact_key||''),source=index?bridge.packet().fields[Number(index[1])]:null,field=bridge.snapshot()?.fields.find(f=>f.key===candidate.question_key);
     if(source&&field&&allowed(bridge.packet()).some(f=>f.label===field.label)){const button=U.node('button','Review this mapping');button.type='button';button.addEventListener('click',()=>{$('fact-panel').open=true;$('fact-label').value=field.label;$('fact-value').value=source.answer;$('fact-source').value=`Explicitly selected confirmed fact: ${source.label}`;invalidate();$('fact-value').focus();});row.append(button);}box.append(row);
   }$('advice-results').append(box);
 }}
 globalThis.OrbitAssistance={
   canConfirm:()=>!!preview,
   attach(b){bridge=b;for(const id of ['fact-label','fact-value','fact-source','fact-scope'])$(id).addEventListener('input',invalidate);
     $('fact-preview-button').addEventListener('click',()=>bridge.action(async()=>{preview=await bridge.call('fact_preview',payload());$('fact-preview').textContent=`This confirmation affects ${preview.affected_roles.join(', ')}. It changes local packet facts only.`;$('fact-confirm').disabled=false;}));
     $('fact-confirm').addEventListener('click',()=>bridge.action(async()=>{if(!preview)throw new Error('Preview the exact fact first.');const r=await bridge.call('fact_confirm',{...payload(),preview_id:preview.preview_id});invalidate();await bridge.reload();U.notice(`Confirmed for ${r.affected_roles.length} role(s). Scan the current form before filling.`);}));
     $('advice-prepare').addEventListener('click',()=>bridge.action(async()=>{const fact_keys=[...$('advice-facts').querySelectorAll('input:checked')].map(e=>e.value);const r=await bridge.call('advice_prepare',{role_id:bridge.role(),packet_digest:bridge.packet().packet_digest,fact_keys});U.notice(r.status==='prepared'?'Suggestion task prepared locally. No model was called.':'No unknown questions need suggestions.');await refreshAdvice();}));
     $('advice-refresh').addEventListener('click',()=>bridge.action(refreshAdvice));
     $('advice-import').addEventListener('click',()=>bridge.action(async()=>{const response=JSON.parse($('advice-json').value);await bridge.call('advice_import',{role_id:bridge.role(),packet_digest:bridge.packet().packet_digest,response});await refreshAdvice();U.notice('Suggestions imported. Confirm a mapping explicitly before using it.');}));
   },
   render(p){invalidate();$('fact-label').replaceChildren();for(const f of allowed(p)){const o=U.node('option',f.label);o.value=f.label;$('fact-label').append(o);}$('advice-facts').replaceChildren();(p?.fields||[]).forEach((f,i)=>{if(!f.verified||!['profile','fact'].includes(f.who))return;const label=U.node('label',undefined,'fact-choice'),input=U.node('input');input.type='checkbox';input.value='fact:'+i;label.append(input,document.createTextNode(f.label));$('advice-facts').append(label);});$('advice-results').replaceChildren();$('advice-json').value='';}
 };
})();
