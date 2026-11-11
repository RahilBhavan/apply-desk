/* design-owner: Orbit because this is private application preparation. */
'use strict';
(() => {
 const U=globalThis.OrbitUI={};
 U.$=id=>document.getElementById(id);
 U.node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
 U.value=v=>v===null||v===undefined||v===''?'Empty':typeof v==='boolean'?(v?'Yes · checked':'No · unchecked'):Array.isArray(v)?(v.length?v.join('; '):'No committed selection'):String(v);
 U.notice=(message,error=false)=>{U.$('notice').textContent=message;U.$('notice').className=error?'error':'';};
 const names={scanned:'Form scanned',needs_input:'Needs your input',access_hold:'Access needs attention',conflict:'Review conflicting values',verified_fields:'This step’s fields match the packet',error:'Preparation needs attention'};
 U.draw=(s,p,{historical=false,changed=false,focus,recheck}={})=>{
   U.$('result').hidden=!s;if(!s)return;
   const scroll=scrollY,expanded=new Set([...U.$('fields').querySelectorAll('details[open]')].map(e=>e.dataset.field));
   U.$('stage').textContent=historical?'Saved preparation observation':changed?'Form changed · verify again':names[s.status]||s.status;
   U.$('observed').textContent=(historical?'Historical observation · ':'Last observed · ')+(s.observed_at||s.updated_at||'time unavailable')+(s.settled?' · bounded validation checked':' · validation not settled');
   U.$('summary').textContent=`${s.fields.length} observed fields · ${s.issues.length} holds. Final submission remains manual.`;
   U.$('issues').replaceChildren();for(const i of s.issues)U.$('issues').append(U.node('li',[i.label,i.message].filter(Boolean).join(' · '),'hold'));
   if(changed)U.$('issues').prepend(U.node('li','Values, validity or structure changed after the last settled check. Recheck before relying on it.','hold'));
   const filter=U.$('field-filter').value,fragment=document.createDocumentFragment();
   for(const f of s.fields){
     const attention=s.issues.some(i=>i.label===f.label)||f.kind==='unsupported'||f.valid===false;
     if(filter==='attention'&&!attention||filter==='matched'&&attention)continue;
     const entry=U.node(attention?'article':'details',undefined,'field');entry.dataset.field=f.key;
     if(!attention){entry.open=expanded.has(f.key);entry.append(U.node('summary',`${f.label} · matched observation`));}else entry.append(U.node('h3',f.label||'Unlabeled field'));
     entry.append(U.node('span',`${f.kind} · ${f.required?'required':'optional'}`,'badge'));
     const matches=(p?.fields||[]).filter(x=>x.label.trim().toLowerCase()===(f.label||'').trim().toLowerCase()),proposed=matches.length===1?matches[0]:null;
     const values=U.node('div',undefined,'values'),current=U.node('div'),proposal=U.node('div');
     current.append(U.node('p','Current value','value-label'),U.node('p',U.value(f.raw_value?.trim()&&!f.value?.length?f.raw_value:f.value),'value'));
     for(const file of f.files||[])current.append(U.node('p',`${file.name} · ${file.size} bytes · SHA-256 ${file.sha256||'unverified'}`,'value'));
     proposal.append(U.node('p','Proposed answer','value-label'),U.node('p',proposed?U.value(proposed.answer):'No unique packet answer. Review manually.','value'));
     if(proposed)proposal.append(U.node('p',proposed.verified?'Packet provenance checked.':'Missing or unverified answer.',proposed.verified?'muted':'hold'));
     values.append(current,proposal);entry.append(values);
     const tools=U.node('div',undefined,'field-actions');for(const [label,fn]of [['Find field',focus],['Recheck field',recheck]]){const b=U.node('button',label);b.type='button';b.addEventListener('click',()=>fn?.(f.key));tools.append(b);}entry.append(tools);
     if(f.options?.length){const d=U.node('details');d.append(U.node('summary','Available choices'),U.node('p',f.options.join('\n'),'value'));entry.append(d);}
     if(proposed?.basis?.length){const d=U.node('details');d.append(U.node('summary','Answer basis'),U.node('p',proposed.basis.join('\n'),'value'));entry.append(d);}
     fragment.append(entry);
   }
   U.$('fields').replaceChildren(fragment);scrollTo({top:scroll,behavior:'instant'});
 };
 U.steps=(progress,p)=>{
   U.$('step-progress').replaceChildren();
   if(!p?.steps?.length)return;
   U.$('step-progress').append(U.node('p',`${progress.steps_observed?.length||0}/${p.steps.length} configured steps observed · historical evidence, not submission approval.`,'muted'));
   for(const step of p.steps){const record=progress.step_records?.[step.id];U.$('step-progress').append(U.node('p',`${step.id}: ${record?(names[record.status]||record.status):'Not observed'}`));}
 };
})();
