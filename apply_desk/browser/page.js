/* design-owner: Orbit because this is private application preparation. */
(() => {
  if (globalThis.OrbitApply) return;
  const S = globalThis.__orbitScanner, C = globalThis.__orbitControls;
  const url = value => { const u = new URL(value); return u.href; };
  let active = null, revision = 0, lastFingerprint = '';
  const completed = new Map(), observedTrue = new Set();
  function validationPending() {
    const root = S.root(), selector = '[aria-busy="true"],[data-validation-pending="true"],[data-upload-pending="true"]';
    return !!(root?.matches?.(selector) || root?.querySelector(selector));
  }
  function currentPacket(packet) {
    if (!packet?.steps?.length) return packet;
    const candidates = packet.steps.filter(s => url(s.url) === url(location.href));
    // Same-URL steps require one uniquely agreeing configured question set.
    // resume_step_id identifies the document step, never the current step.
    const labels = new Set(S.scan().map(f => S.norm(f.label)));
    const scoped = (packet.fields || []).filter(f => f.step_id);
    const present = scoped.filter(f => labels.has(S.norm(f.label)));
    const matching = candidates.filter(s => {
      const own = scoped.filter(f => f.step_id === s.id);
      return own.length && present.length && present.every(f => own.some(q => S.norm(q.label) === S.norm(f.label))) && own.filter(f => f.required && !f.conditional).every(f => labels.has(S.norm(f.label)));
    });
    const step = candidates.length === 1 ? candidates[0] : matching.length === 1 ? matching[0] : null;
    if (!step) throw new Error('Current application step is ambiguous or undeclared.');
    const hasResume = !packet.resume_step_id || packet.resume_step_id === step.id;
    return {...packet,step_id:step.id,fields:(packet.fields || []).filter(f => !f.step_id || f.step_id === step.id),resume:hasResume?packet.resume:null,resume_issue:hasResume?packet.resume_issue:null};
  }
  async function snapshot(packet,extra = [],repair = false) {
    packet = currentPacket(packet);
    const entries = S.scan(), fields = await S.read(entries);
    // Greenhouse replaces an uploaded input with its filename. Count it only if Orbit sent the exact
    // T3 PDF in this document and the application now shows that same filename where the input was.
    const sent = globalThis.__orbitAttached?.get(S.doc), owner = S.root();
    if (packet?.resume && sent && sent.sha256 === packet.resume.sha256 && owner && !fields.some(f => f.kind === 'file' && S.norm(f.label) === S.norm(sent.label))
        && S.clean(owner.innerText).includes(sent.name))
      fields.push({key:`file|${S.norm(sent.label)}|1`,label:sent.label,question_id:sent.question_id,owner:S.identify(owner),committed:true,kind:'file',required:true,
        value:[sent.name],raw_value:null,options:[],valid:true,files:[{name:sent.name,size:sent.size,sha256:sent.sha256}]});
    for (const f of fields) if (f.kind === 'checkbox' && f.value === true) observedTrue.add(`${f.owner}|${f.question_id}`);
    // A one-option question (Lever's "Confirmation of Information Provided") shows as a single checkbox labelled by its option.
    const oneOption = (f,a) => f.kind === 'checkbox' && (a.options || []).length === 1 && S.norm(a.options[0]) === S.norm(f.label);
    // That checkbox carries its question's requiredness, so an unticked required terms box is still held.
    for (const f of fields) if (C.match(f,packet || {})?.required || (packet?.fields || []).some(a => a.required && !a.conditional && oneOption(f,a))) f.required = true;
    const form_digest = await S.digest(entries.map(f => ({key:f.key,required:f.required,options:f.kind === 'combobox' ? [] : f.options,type:f.e.type || '',name:f.e.name || '',id:f.e.id || ''})));
    const issues = [...S.access(entries),...extra];
    if (validationPending()) issues.push({code:'validation_pending',label:'Validation',message:'The application reports validation or upload work in progress.'});
    if (packet?.greenhouse_schema) {
      if (packet.greenhouse_schema.url !== location.href) issues.push({code:'schema_mismatch',label:'Application',message:'Public schema belongs to a different exact application URL.'});
      else issues.push(...S.reconcileGreenhouse(packet.greenhouse_schema).issues);
    }
    const labels = new Map();
    for (const f of fields) labels.set(S.norm(f.label),(labels.get(S.norm(f.label)) || 0)+1);
    for (const f of fields) if (labels.get(S.norm(f.label)) > 1) issues.push({code:'ambiguous_question',label:f.label,message:'Duplicate semantic questions require an explicit unambiguous adapter.'});
    if (packet) {
      for (const f of fields) {
        const a = C.match(f,packet);
        if (f.kind === 'unsupported') { issues.push({code:'unsupported_control',label:f.label,message:'This widget requires manual preparation and verification.'}); continue; }
        if (f.required && (C.empty(f.value) || f.kind === 'checkbox' && f.value === false && a?.answer == null)) issues.push({code:'missing_answer',label:f.label,message:'Required answer is empty or has no committed selection.'});
        if (!f.valid) issues.push({code:'invalid_value',label:f.label,message:'The browser reports an invalid value.'});
        if (f.raw_value?.trim() && C.empty(f.value)) issues.push({code:'manual_conflict',label:f.label,message:'Typed text has no committed selection. It was preserved for manual review.'});
        const expected = C.wanted(f,packet);
        if (C.consent.test(f.label)) { if (C.granted(f,packet) && f.value === true) continue; if (f.required || (f.kind === 'checkbox' ? f.value === true : !C.empty(f.value))) issues.push({code:'manual_consent',label:f.label,message:'Consent and attestations require manual review.'}); continue; }
        if ((!C.empty(f.value) || f.kind === 'checkbox' && expected !== null) && !C.agrees(f,packet)) issues.push({code:expected !== null ? 'manual_conflict' : 'unverified_answer',label:f.label,message:'Current value does not match a verified packet answer; it was preserved.'});
        else if ((f.required || a && C.usable(a)) && expected === null && f.kind !== 'combobox') issues.push({code:'unverified_answer',label:f.label,message:'No exact usable verified answer is available for this question.'});
      }
      // A page label may add a bracketed detail to the packet question: Location becomes Location (City).
      const shown = (f,a) => S.norm(f.label) === S.norm(a.label) || /\([^)]*\)\W*$/.test(f.label) && S.norm(f.label.replace(/\([^)]*\)\W*$/,'')) === S.norm(a.label)
        || oneOption(f,a);
      // One Workday step spans every page, so a question can sit on a later page; each page still verifies.
      const spanning = packet.step_id === 'workday-apply';
      for (const a of packet.fields || []) if (!spanning && a.required && !a.conditional && !fields.some(f => shown(f,a))) issues.push({code:'missing_field',label:a.label,message:'The required packet question is not present on this step.'});
      if (packet.resume && (!packet.steps?.length || packet.resume_step_id === packet.step_id || fields.some(f => f.kind === 'file')) && !fields.some(f => f.kind === 'file' && C.agrees(f,packet))) issues.push({code:'resume_unverified',label:'Resume',message:'Actual selected bytes do not match the reviewed resume.'});
      if (packet.resume_issue) issues.push({code:'resume_unavailable',label:'Resume',message:packet.resume_issue});
    }
    const access = issues.some(i => ['login_required','challenge','no_application_form','unsupported_frame'].includes(i.code));
    const status = access ? 'access_hold' : issues.some(i => i.code === 'manual_conflict') ? 'conflict' : issues.length ? 'needs_input' : packet ? 'verified_fields' : 'scanned';
    const fingerprint = JSON.stringify({form_digest,fields,issues,status,url:location.href});
    if (fingerprint !== lastFingerprint) { revision++; lastFingerprint = fingerprint; }
    return {document_id:S.doc,url:location.href,form_digest,fields,issues,status,repair_attempted:repair,observed_at:new Date().toISOString(),settled:false,revision,owner:entries[0]?.owner || '',...(packet?.step_id ? {step_id:packet.step_id} : {})};
  }
  // Wait across a minimum validation window, then require an unchanged readback.
  // This is bounded local evidence, not proof that every employer async task ended.
  async function settle(packet,cancelled) {
    const start = performance.now(); let previous = await snapshot(packet), stableSince = start;
    while (performance.now() - start < 2400) {
      if (cancelled()) return previous;
      await C.delay(100);
      const next = await snapshot(packet), now = performance.now();
      if (next.revision !== previous.revision) stableSince = now;
      previous = next;
      const pending = validationPending();
      if (!pending && now - start >= 1100 && now - stableSince >= 300) { next.settled = true; return next; }
    }
    previous.issues.push({code:'unsettled',label:'Validation',message:'The bounded validation window did not settle. Recheck manually.'});
    previous.status = 'needs_input'; return previous;
  }
  const status = () => ({operation_id:active?.id || null,state:active ? 'running' : 'idle',cancel_requested:!!active?.cancelled});
  function cancel(id) {
    if (active && active.id === id) active.cancelled = true;
    return status();
  }
  function focus(key) {
    if (typeof key !== 'string') return false;
    const matches = S.scan().filter(f => f.key === key);
    if (matches.length !== 1) return false;
    matches[0].e.focus(); matches[0].e.scrollIntoView({block:'center'}); return true;
  }
  async function run(request) {
    if (!request || !['scan','fill','verify','observe'].includes(request.operation)) throw new Error('Unsupported operation.');
    const packet = currentPacket(request.packet), fill = request.operation === 'fill';
    if (fill && (typeof request.operation_id !== 'string' || !/^[a-zA-Z0-9_.:-]{1,160}$/.test(request.operation_id))) throw new Error('Fill requires a stable operation_id.');
    const identity = fill ? await S.digest({packet,expected:request.expected}) : null;
    if (fill && completed.has(request.operation_id)) {
      const prior = completed.get(request.operation_id);
      if (prior.identity !== identity) throw new Error('Operation ID payload changed.');
      return prior.result;
    }
    if (active && request.operation !== 'observe') return snapshot(packet,[{code:'busy',label:'Preparation',message:'Another preparation operation is running.'}]);
    if (request.operation === 'observe') return snapshot(packet);
    const operation = {id:request.operation_id || null,cancelled:false}; active = operation;
    const cancelled = () => operation.cancelled;
    try {
      const allowed = packet?.allowed_urls || (packet ? [packet.apply_url] : []);
      if (request.operation !== 'scan' && (!packet || !allowed.some(u => url(u) === url(location.href)) || allowed.some(u => new URL(u).origin !== new URL(packet.apply_url).origin))) throw new Error('Wrong application URL or missing packet.');
      let before = await snapshot(packet);
      if (!fill) {
        if (request.operation === 'verify') return await settle(packet,cancelled);
        if (before.status === 'verified_fields') before.status = 'scanned';
        return before;
      }
      const remember = result => { completed.set(request.operation_id,{identity,result}); return result; };
      const expected = request.expected;
      if (!expected || expected.document_id !== S.doc || expected.form_digest !== before.form_digest || url(expected.url) !== url(location.href) || expected.owner && expected.owner !== before.owner || expected.revision !== undefined && expected.revision !== before.revision) return remember(await snapshot(packet,[{code:'stale_form',label:'Application',message:'Document, answers or form changed. Scan again before filling.'}]));
      // A duplicated question blocks every write only if T3 has a usable answer under that label.
      // An unanswered duplicate ("If so, please explain" twice, both empty) cannot misroute anything:
      // it stays held alone, and the pass below never writes a label the page shows twice.
      const answered = label => (packet.fields || []).some(x => S.norm(x.label) === S.norm(label) && C.usable(x));
      if (before.status === 'access_hold' || before.issues.some(i => i.code === 'schema_mismatch' || i.code === 'ambiguous_question' && answered(i.label))) return remember(before);
      const initialURL = location.href, owner = before.owner;
      async function pass(fields) {
        for (const original of fields) {
          if (cancelled() || location.href !== initialURL) break;
          const entries = S.scan(), entry = entries.find(f => f.key === original.key);
          if (!entry || entry.owner !== owner || entries.filter(f => S.norm(f.label) === S.norm(entry.label)).length !== 1) continue;
          const current = (await S.read([entry]))[0];
          if (current.kind === 'checkbox' && current.value === false && observedTrue.has(`${current.owner}|${current.question_id}`)) continue;
          if (C.occupied(current) || C.consent.test(current.label) && !C.granted(current,packet) || C.agrees(current,packet)) continue;
          if (entry.kind !== 'combobox' && C.wanted(current,packet) === null) continue;
          await C.apply(entry,packet,cancelled);
          if (entry.kind === 'checkbox' && entry.e.checked) observedTrue.add(`${entry.owner}|${entry.question_id}`);
        }
      }
      await pass(before.fields);
      let after = await settle(packet,cancelled), repair = false;
      if (!cancelled() && location.href === initialURL) {
        const targets = after.fields.filter(f => !C.occupied(f) && !C.agrees(f,packet) && !(C.consent.test(f.label) && !C.granted(f,packet)) && (f.kind === 'combobox' || C.wanted(f,packet) !== null));
        if (targets.length) { repair = true; await pass(targets); after = await settle(packet,cancelled); }
      }
      if (cancelled()) { after.issues.push({code:'cancelled',label:'Preparation',message:'Stopped between actions. Previously dispatched employer handlers may continue.'}); after.status = 'needs_input'; }
      if (location.href !== initialURL) { after.issues.push({code:'navigation_changed',label:'Application',message:'Navigation changed. Rescan this step.'}); after.status = 'needs_input'; }
      after.repair_attempted = repair;
      completed.set(request.operation_id,{identity,result:after});
      return after;
    } catch (error) {
      const result = await snapshot(null,[{code:'operation_error',label:'Preparation',message:String(error.message || error)}]); result.status = 'error';
      if (fill) completed.set(request.operation_id,{identity,result}); return result;
    } finally { if (active === operation) active = null; }
  }
  globalThis.OrbitApply = Object.freeze({run,status,cancel,focus});
})();
