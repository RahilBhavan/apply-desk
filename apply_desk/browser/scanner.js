/* design-owner: Orbit because this is private application preparation. */
(() => {
  if (globalThis.__orbitScanner) return;
  const clean = x => String(x ?? '').replace(/\s+/g, ' ').trim();
  const norm = x => clean(x).toLowerCase().replace(/\s*\*$/, '').replace(/[^a-z0-9]+/g, ' ').trim();
  const visible = e => !e.closest('[hidden],[aria-hidden="true"]') && getComputedStyle(e).display !== 'none' && getComputedStyle(e).visibility !== 'hidden' && !!e.getClientRects().length;
  // Lever wraps a field and its live search results in one label; only its .application-label is the question.
  const labelText = e => { const own = e.querySelector('.application-label'); if (own) return own.textContent; const c = e.cloneNode(true); c.querySelectorAll('input,select,textarea,[role="combobox"],[role="listbox"]').forEach(n => n.remove()); return c.textContent; };
  // Ashby typeaheads and date pickers and Lever card selects have no label of their own: the question sits
  // on the enclosing entry. A label bound to another control never names this one.
  const entryLabel = e => { for (let n = e.parentElement, i = 0; n && i < 5 && !n.matches('form,body'); n = n.parentElement, i++) {
      const head = n.querySelector('label,legend,.application-label'); if (!head) continue;
      return head.contains(e) || head.control && head.control !== e ? '' : clean(labelText(head)).replace(/\s*[*\u2731]$/, ''); }
    return ''; };
  // A Workday listbox button shows its value as text and in aria-label; its question is the label element.
  const baseLabel = e => e.matches('button[aria-haspopup="listbox"]') && e.labels?.length ? clean([...e.labels].map(labelText).join(' ')) : e.tagName === 'BUTTON' ? clean(e.textContent) : clean(e.getAttribute('aria-label') || (e.getAttribute('aria-labelledby') || '').split(/\s+/).map(id => document.getElementById(id)?.textContent || '').join(' ') || [...(e.labels || [])].map(labelText).join(' ') || e.closest('fieldset')?.querySelector('legend')?.textContent || entryLabel(e) || e.getAttribute('placeholder') || e.name || e.id);
  // Greenhouse uploads say only "Attach"; the question text is on the enclosing labelled group.
  const generic = /^(attach|upload|upload file|choose file|browse)$/i;
  const label = e => { const own = baseLabel(e); if (e.type !== 'file' || !generic.test(own)) return own;
    const group = e.closest('[role="group"][aria-labelledby],[role="group"][aria-label]');
    const named = group && clean(group.getAttribute('aria-label') || group.getAttribute('aria-labelledby').split(/\s+/).map(id => document.getElementById(id)?.textContent || '').join(' ')).replace(/\s*\*$/, '');
    return named || own; };
  // Toggle buttons (Ashby Yes/No) carry their choice in aria-pressed; native controls in checked.
  const pressed = e => e.tagName === 'BUTTON' ? e.getAttribute('aria-pressed') === 'true' : !!e.checked;
  const hash = async bytes => [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(x => x.toString(16).padStart(2,'0')).join('');
  const digest = x => hash(new TextEncoder().encode(JSON.stringify(x)));
  const doc = crypto.randomUUID(), fileCache = new WeakMap(), commits = new WeakMap(), identities = new WeakMap(), nativeBindings = new WeakMap();
  let identity = 0;
  const identify = e => { if (!identities.has(e)) identities.set(e, `owner-${++identity}`); return identities.get(e); };
  function root() {
    const forms = [...document.forms].filter(visible);
    const explicit = forms.filter(f => /application|apply/i.test([f.getAttribute('aria-label'),f.id,f.className].join(' ')));
    const candidates = explicit.length ? explicit : forms.filter(f => [...f.elements].some(e => e.type === 'file' && /resume|cv/i.test(label(e))));
    if (candidates.length || forms.length) return candidates.length === 1 ? candidates[0] : null;
    // Workday: no form element; the current step's page container holds the questions.
    if (document.querySelector('[data-automation-id="applyFlowPage"]')) {
      const pages = [...document.querySelectorAll('[data-automation-id^="applyFlow"][data-automation-id$="Page"]')].filter(visible);
      const step = pages.filter(b => b.getAttribute('data-automation-id') !== 'applyFlowPage');
      return step.length === 1 ? step[0] : pages.length === 1 ? pages[0] : null;
    }
    // Formless boards (Ashby): one outermost application-form container, never its separate autofill pane.
    const boxes = [...document.querySelectorAll('div[class*="application-form"],section[class*="application-form"]')]
      .filter(b => !/autofill/i.test(b.className) && visible(b) && b.querySelector('input,textarea,select'));
    const outer = boxes.filter(b => !boxes.some(o => o !== b && o.contains(b)));
    // Several sections (e.g. a voluntary survey): the application is the one holding the resume upload.
    const owners = outer.length === 1 ? outer : outer.filter(b => [...b.querySelectorAll('input[type="file"]')].some(e => /resume|cv/i.test(label(e))));
    return owners.length === 1 ? owners[0] : null;
  }
  const owned = (e,r) => !!r && (e.form ? e.form === r : r.contains(e));
  function options(e) {
    const ids = (e.getAttribute('aria-controls') || e.getAttribute('aria-owns') || '').split(/\s+/).filter(Boolean);
    // A Workday search input lists its results as promptOption entries with no aria link.
    if (!ids.length && e.matches('input[data-uxi-widget-type="selectinput"]')) return [...document.querySelectorAll('[data-automation-id="promptOption"]')].filter(visible);
    return ids.flatMap(id => [...(document.getElementById(id)?.querySelectorAll('[role="option"]') || [])]);
  }
  const widget = e => {
    const box = e.closest('[class*="__control"]')?.parentElement || e.parentElement;
    return box?.tagName === 'FORM' ? null : box;
  };
  function payload(e) {
    const box = widget(e);
    // Only inputs inside the one owning widget, never arbitrary form-wide IDs.
    const inputs = box && box.tagName !== 'FORM' ? [...box.querySelectorAll('input[type="hidden"]')] : [];
    return {complete:inputs.length <= 20 && inputs.every(x => x.value.trim() !== ''),signature:JSON.stringify(inputs.map(x => [x.name,x.id,x.value]))};
  }
  const clearCommit = event => { if (event.target?.matches?.('[role="combobox"]')) commits.delete(event.target); };
  document.addEventListener('input',clearCommit,true);
  document.addEventListener('change',clearCommit,true);
  new MutationObserver(records => {
    for (const record of records) if (record.attributeName === 'aria-expanded' && record.oldValue === 'false') commits.delete(record.target);
  }).observe(document,{subtree:true,attributes:true,attributeOldValue:true,attributeFilter:['aria-expanded']});
  function scan() {
    const entries = [], seen = new Set(), counts = new Map(), r = root();
    if (!r) return entries;
    const toggles = new Map();
    for (const b of r.querySelectorAll('button[aria-pressed]')) {
      if (!visible(b) || b.disabled || b.closest('nav,[role="search"],header')) continue;
      if (!toggles.has(b.parentElement)) toggles.set(b.parentElement, []);
      toggles.get(b.parentElement).push(b);
    }
    for (const [box, group] of toggles) if (group.length >= 2 && group.length <= 12) box.querySelectorAll('input').forEach(i => seen.add(i));
    for (const e of document.querySelectorAll('input,textarea,select,[role="combobox"],[role="radio"],[role="checkbox"],[contenteditable="true"],button[aria-haspopup="listbox"]')) {
      if (!owned(e,r) || seen.has(e) || (!visible(e) && e.type !== 'file') || e.disabled || (['hidden','submit','button','image','reset','search','password'].includes(e.type) && !e.matches('button[aria-haspopup="listbox"]'))) continue;
      if (e.closest('nav,[role="search"],header')) continue;
      let kind = e.readOnly ? 'unsupported' : e.matches('[role="combobox"],button[aria-haspopup=\"listbox\"],input[data-uxi-widget-type=\"selectinput\"]') ? 'combobox' : e.tagName === 'SELECT' ? (e.multiple ? (e.matches(':disabled') ? 'unsupported' : 'multiselect') : 'select') : ['radio','checkbox','date','file'].includes(e.type) ? e.type : e.matches('[role="radio"],[role="checkbox"],[contenteditable]') ? 'unsupported' : 'text';
      let group = [e], title = label(e);
      if (kind === 'radio' || kind === 'checkbox') {
        const scope = document;
        const peers = [...scope.querySelectorAll(`input[type="${kind}"]`)].filter(p => owned(p,r) && visible(p) && !p.disabled && ((e.name && p.name === e.name) || (!e.name && e.closest('fieldset') && p.closest('fieldset') === e.closest('fieldset'))));
        if (kind === 'radio' || peers.length > 1) { group = peers.length ? peers : [e]; title = clean(e.closest('fieldset')?.querySelector('legend')?.textContent || e.getAttribute('aria-label') || e.name || label(e)); if (kind === 'checkbox') kind = 'checkgroup'; }
      }
      group.forEach(p => seen.add(p));
      const opts = kind === 'multiselect' ? [...e.options].filter(o => !o.disabled && !o.parentElement?.disabled && o.value !== '').map(o => clean(o.textContent)) : kind === 'select' ? [...e.options].filter(o => !o.disabled && o.value !== '').map(o => clean(o.textContent)) : kind === 'combobox' ? options(e).map(o => clean(o.textContent)) : ['radio','checkgroup'].includes(kind) ? group.map(label) : [];
      const base = `${kind}|${norm(title)}`, count = (counts.get(base) || 0) + 1; counts.set(base,count);
      entries.push({key:`${base}|${count}`,label:title,kind,owner:identify(r),question_id:e.name || e.id || base,required:group.some(p => p.required || p.getAttribute('aria-required') === 'true'),options:opts,e,group});
    }
    for (const [box, group] of toggles) {
      if (group.length < 2 || group.length > 12) continue;
      const entry = box.closest('[class*="field-entry"],fieldset,[role="group"],[role="radiogroup"]') || box.parentElement;
      const heading = entry?.querySelector('legend,label'), hidden = box.querySelector('input');
      const title = clean(box.getAttribute('aria-label') || (heading ? labelText(heading) : ''));
      if (!title) continue;
      const base = `radio|${norm(title)}`, count = (counts.get(base) || 0) + 1; counts.set(base,count);
      const required = /required/i.test(heading?.className || '') || /\*\s*$/.test(heading?.textContent || '') || !!hidden?.required;
      entries.push({key:`${base}|${count}`,label:title,kind:'radio',owner:identify(r),question_id:hidden?.name || hidden?.id || base,required,options:group.map(label),e:group[0],group});
    }
    return entries;
  }
  function nativePayload(f) {
    const e = f.e, form = e.form, selected = [...e.selectedOptions].map(o => o.value);
    // Do not construct FormData(form): it dispatches the site's formdata handlers.
    // Snapshot only this native field; ambiguous same-name controls remain held.
    const data = new FormData(), exclusive = !!e.name && !!form && !e.matches(':disabled') && ![...form.elements].some(other => other !== e && other.name === e.name && !other.matches(':disabled'));
    if (exclusive) for (const option of e.selectedOptions) if (!option.matches(':disabled')) data.append(e.name,option.value);
    const values = exclusive ? data.getAll(e.name) : [];
    const signature = JSON.stringify([e.name,[...e.options].map(o => [clean(o.textContent),o.value])]);
    let bindings = form && nativeBindings.get(form);
    if (!bindings) { bindings = new Map(); if (form) nativeBindings.set(form,bindings); }
    if (!bindings.has(f.key)) bindings.set(f.key,signature);
    return {payload:{name:e.name,selected_values:selected,form_values:values,exclusive},
      committed:exclusive && bindings.get(f.key) === signature && JSON.stringify(selected) === JSON.stringify(values)};
  }
  async function read(entries) {
    return Promise.all(entries.map(async f => {
      const {e,group,kind} = f; let value = '', files = [], native = null;
      if (kind === 'file') { files = await Promise.all([...e.files].map(async x => ({name:x.name,size:x.size,sha256:await (fileCache.get(x) || (() => { const result = x.arrayBuffer().then(hash); fileCache.set(x,result); return result; })())}))); value = files.map(x => x.name); }
      else if (kind === 'checkbox') value = e.checked;
      else if (['radio','checkgroup'].includes(kind)) value = group.filter(pressed).map(label);
      else if (kind === 'multiselect') { value = [...e.selectedOptions].map(o => clean(o.textContent)); native = nativePayload(f); }
      else if (kind === 'select') value = [...e.selectedOptions].filter(o => o.value !== '').map(o => clean(o.textContent));
      else if (kind === 'combobox' && e.matches('button[aria-haspopup="listbox"],input[data-uxi-widget-type="selectinput"]')) {
        // Workday: a listbox button shows its chosen value ("Select One" is empty); a search input shows pills.
        const pills = [...(e.closest('[data-automation-id^="formField"]')?.querySelectorAll('[data-automation-id="selectedItem"]') || [])].map(p => clean(p.textContent));
        const text = e.tagName === 'BUTTON' ? clean(e.textContent) : '';
        value = e.getAttribute('aria-expanded') === 'true' ? [] : e.tagName === 'BUTTON' ? (text && !/^select one$/i.test(text) ? [text] : []) : pills;
      }
      else if (kind === 'combobox') {
        // A highlighted option alone is never a committed application answer.
        const box = widget(e);
        // A phone-country chip shows only a dial code; its flag class names the country (+1 is both US and CA).
        const chips = [...(box?.querySelectorAll('[class*="singleValue"],[class*="single-value"],[class*="multiValueLabel"],[class*="multi-value__label"]') || [])].map(p => { const flag = [...(p.querySelector('.iti__flag')?.classList || [])].find(x => /^iti__[a-z]{2}$/.test(x)); return clean((flag ? flag.slice(5).toUpperCase() + ' ' : '') + p.textContent); });
        const raw = clean(e.value ?? e.textContent), closed = e.getAttribute('aria-expanded') === 'false';
        const accepted = commits.get(e), submitted = payload(e);
        value = closed && submitted.complete && accepted && accepted.payload === submitted.signature && raw && norm(accepted.value) === norm(raw) ? [raw] : closed && submitted.complete && chips.length && (!raw || chips.some(c => norm(c) === norm(raw))) ? chips : [];
      } else value = e.value ?? '';
      const raw_value = kind === 'combobox' && e.tagName === 'INPUT' ? e.value : null;
      return {key:f.key,label:f.label,question_id:f.question_id,owner:f.owner,committed:native ? native.committed : kind !== 'combobox' || (Array.isArray(value) && value.length > 0),...(native ? {native_payload:native.payload} : {}),kind,required:f.required,value,raw_value,options:f.options,valid:group.every(p => p.getAttribute('aria-invalid') !== 'true' && (!p.validity || p.validity.valid)),files};
    }));
  }
  function access(entries) {
    const text = clean(document.body?.innerText).slice(0,12000), issues = [];
    if ([...document.querySelectorAll('input[type="password"]')].some(visible)) issues.push({code:'login_required',label:'Access',message:'Sign in manually before preparing this application.'});
    if (/verify (that )?you('re| are) (a )?human|are you a robot|complete the security check|access denied|press and hold/i.test(text) || [...document.querySelectorAll('iframe')].some(e => visible(e) && /recaptcha|hcaptcha|challenges.cloudflare|arkoselabs/i.test(e.src) && !/size=invisible/.test(e.src))) issues.push({code:'challenge',label:'Access',message:'A visible access or human verification challenge requires manual action.'});
    if ([...document.querySelectorAll('iframe')].some(e => visible(e) && !/recaptcha|hcaptcha|challenges.cloudflare/i.test(e.src))) issues.push({code:'unsupported_frame',label:'Embedded content',message:'Embedded controls cannot be verified by this main-frame adapter.'});
    const recognized = !!root() && entries.length > 0;
    if (!recognized) issues.push({code:'no_application_form',label:'Application',message:'No recognized application form is visible.'});
    return issues;
  }
  // Explicit read-only adapter for the documented Greenhouse Job Board API
  // questions[].fields[{name,type,values:[{label,value}]}] shape. A local schema
  // is evidence only; it neither fetches a tenant nor authorizes any writes.
  function reconcileGreenhouse(schema) {
    if (!schema || !Array.isArray(schema.questions) || schema.questions.length > 200) throw new Error('Invalid Greenhouse question schema.');
    const r = root(), observed = scan(), fields = [], issues = [], mapped = new Set();
    if (!r) return {adapter:'greenhouse-public-schema',fields,issues:[{code:'application_owner_unknown',label:'Application',message:'A single application-owned form is required.'}]};
    for (const q of schema.questions) {
      if (!q || typeof q.label !== 'string' || q.label.length > 1000 || typeof q.required !== 'boolean' || !Array.isArray(q.fields) || q.fields.length > 20) throw new Error('Invalid Greenhouse question.');
      for (const field of q.fields) {
        if (!field || typeof field.name !== 'string' || field.name.length > 200 || !['input_file','input_text','textarea','multi_value_single_select','multi_value_multi_select'].includes(field.type)) throw new Error('Unsupported Greenhouse schema field.');
        if (field.values !== undefined && (!Array.isArray(field.values) || field.values.length > 500 || field.values.some(v => !v || typeof v.label !== 'string' || v.label.length > 1000 || !['string','number'].includes(typeof v.value)))) throw new Error('Invalid Greenhouse options.');
        const matches = observed.filter(f => f.e.name === field.name);
        if (matches.length !== 1 || norm(matches[0].label) !== norm(q.label)) { issues.push({code:'schema_mismatch',label:q.label,message:'Public schema and application-owned observed question do not uniquely agree.'}); continue; }
        const f = matches[0], expectedKind = {input_file:['file'],input_text:['text','date'],textarea:['text'],multi_value_single_select:['select','combobox','radio'],multi_value_multi_select:['checkgroup','multiselect']}[field.type];
        const values = field.values || [];
        const labels = xs => JSON.stringify(xs.map(norm).sort());
        const payloadOptions = ['select','multiselect'].includes(f.kind) ? [...f.e.options].filter(o => !o.disabled && (f.kind === 'select' || !o.parentElement?.disabled) && o.value !== '').map(o => ({label:clean(o.textContent),value:o.value})) : ['radio','checkgroup'].includes(f.kind) ? f.group.map(e => ({label:label(e),value:e.value})) : null;
        const payloadMismatch = values.length && payloadOptions && (payloadOptions.length !== values.length || values.some(v => !payloadOptions.some(o => norm(o.label) === norm(v.label) && String(o.value) === String(v.value))));
        if (!expectedKind.includes(f.kind) || !!q.required !== !!f.required || values.length && labels(values.map(v => v.label)) !== labels(f.options) || payloadMismatch) { issues.push({code:'schema_mismatch',label:q.label,message:'Observed widget type, requiredness, options or native payload values differ from the public schema.'}); continue; }
        mapped.add(f.key);
        fields.push({key:f.key,question_id:field.name,owner:f.owner,label:q.label,kind:f.kind});
      }
    }
    for (const f of observed) if (!mapped.has(f.key)) issues.push({code:'schema_mismatch',label:f.label,message:'Observed question is not covered by the configured public schema.'});
    return {adapter:'greenhouse-public-schema',fields,issues};
  }
  globalThis.__orbitScanner = {clean,norm,visible,label,pressed,hash,digest,doc,scan,read,access,options,root,identify,reconcileGreenhouse,markCommit:(e,value) => commits.set(e,{value,payload:payload(e).signature})};
})();
