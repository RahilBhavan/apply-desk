/* design-owner: Orbit because this is private application preparation. */
'use strict';
(() => {
 const W=globalThis.OrbitWorker;let busy=false;
 async function current(role){const p=await W.packet(role),b=await W.binding(role),tab=await W.target(b,p),target=await W.inject(tab);return {p,b,tab,target};}
 W.stop=async role=>{
   const existing=(await W.native('operation',{role_id:role})).operation;
   if(!existing||!['active','uncertain'].includes(existing.state))return {operation:null,message:'No active preparation action.'};
   const operation_id=existing.operation_id||existing.id;
   await W.native('cancel',{role_id:role,operation_id});
   let acknowledged=false;
   try{const c=await current(role);await W.page(c.target,'cancel',[operation_id]);const state=await W.page(c.target,'status');acknowledged=state?.state==='idle'||!state?.operation_id;}
   catch{/* The durable action remains unresolved until a read-only reconciliation. */}
   return {operation:existing,cancel_requested:true,acknowledged,message:'Stop requested. An action already dispatched to the site cannot be undone.'};
 };
 W.reconcile=async role=>{
   const old=(await W.native('operation',{role_id:role})).operation;
   if(!old||!['active','uncertain'].includes(old.state))return {operation:null,message:'No interrupted action needs reconciliation.'};
   const c=await current(role),executor=await W.page(c.target,'status');
   if(executor?.operation_id&&executor.state!=='idle')W.fail('busy','The page is still preparing fields. Request Stop, then check again.');
   const s=await W.read(c.target,{operation:'verify',packet:c.p},c.p);
   const result=await W.native('reconcile',{role_id:role,operation_id:old.operation_id||old.id,context:W.context(c.p,c.tab,c.target),executor_idle:true,record:W.record(c.p,s)});
   // A reconciliation is evidence, not permission to replay the interrupted write.
   await W.store(role,{tab_id:c.tab.id});
   return {packet:c.p,snapshot:s,binding:{tab_id:c.tab.id},saved:true,reconciled:true,...result};
 };
 W.execute=async(op,role,operation_id)=>{
   const c=await current(role),{p,b,tab,target}=c;
   if(op==='fill'&&(!b.expected||b.worker_epoch!==W.epoch||b.packet_digest!==p.packet_digest||b.role_version!==p.role_version))W.fail('scan_required','Scan the current packet and form before filling.');
   let reserved=false;
   if(op==='fill'){
     const begin=await W.native('begin',{role_id:role,operation_id,context:W.context(p,tab,target)}),state=begin.operation?.state;
     if(['completed','cancelled','reconciled'].includes(state)){
       const progress=await W.native('progress',{role_id:role});return {packet:p,snapshot:progress.record,binding:{tab_id:tab.id},saved:true,duplicate:true,operation:begin.operation};
     }
     if(begin.duplicate)return {packet:p,binding:{tab_id:tab.id},pending:true,operation:begin.operation,message:'This action is already reserved. Check the interrupted action before continuing.'};
     reserved=true;
   }
   try{
     const s=await W.read(target,{operation:op,packet:p,expected:b.expected||null,operation_id},p);
     const executor=await W.page(target,'status');
     const record=W.record(p,s);
     if(op==='fill')await W.native('end',{role_id:role,operation_id,state:executor?.cancel_requested||s.issues.some(i=>i.code==='cancelled')?'cancelled':'completed',record});
     else await W.native('save',{role_id:role,record});
     if(op==='scan'){
       // A scan can reveal questions that standing answers cover. Rescan once against that packet, so Fill sees one stable packet.
       const q=await W.packet(role);
       if(q.packet_digest!==p.packet_digest){const s2=await W.read(target,{operation:op,packet:q,expected:b.expected||null,operation_id},q);await W.native('save',{role_id:role,record:W.record(q,s2)});await W.remember(role,q,tab,target,s2);return {packet:q,snapshot:s2,binding:{tab_id:tab.id},saved:true};}
     }
     await W.remember(role,p,tab,target,s);
     return {packet:p,snapshot:s,binding:{tab_id:tab.id},saved:true};
   }catch(error){
     if(reserved){try{await W.native('end',{role_id:role,operation_id,state:'uncertain'});}catch{}}
     throw error;
   }
 };
 W.observe=async role=>{
   if(busy)return {busy:true};
   const {p,b,tab,target}=await current(role);
   const executor=await W.page(target,'status');if(executor?.operation_id&&executor.state!=='idle')return {busy:true,executor};
   const s=await W.read(target,{operation:'observe',packet:p},p);
   const changed=b.observed_digest!==await W.fingerprint(s)||b.packet_digest!==p.packet_digest||b.chrome_document_id!==target.documentIds[0];
   return {packet:p,snapshot:s,binding:{tab_id:tab.id},changed,requires_verify:changed||!b.settled,historical:false};
 };
 W.serial=async fn=>{if(busy)W.fail('busy','Another preparation action is running. Wait or request Stop.');busy=true;try{return await fn();}finally{busy=false;}};
 W.current=current;
})();
