/* design-owner: Orbit because this is private application preparation. */
(() => {
  if (globalThis.__orbitControls) return;
  const S = globalThis.__orbitScanner;
  const consent = /certif|attest|signature|terms|consent|i agree|agree to|acknowledg|privacy|policy|pledge|declar|truthful|accurate and complete|sms|text message/i;
  // The whole label must be one of these sentences, so any other policy, use, term, statement or opt-in stays his.
  const policy = '(?:candidate |applicant )?(?:privacy|data protection) (?:policy|notice)';
  const plain = [
    new RegExp(`^(?:i )?(?:consent|agree) to (?:the )?(?:collection and )?processing of my (?:personal )?(?:data|information)(?: (?:under|in accordance with|as described in) (?:the )?${policy})?(?: for (?:this|my) application)?$`),
    new RegExp(`^(?:i )?(?:have )?(?:read|acknowledge|accept|agree to)(?: and (?:accept|agree to|acknowledge|understand))? the ${policy}$`),
    // "I agree to allow <employer> to store and process my data for ... my current application": one to three name words.
    /^(?:by checking this box )?i agree to allow (?:(?!and |or |its |partners?|affiliates?|third)[a-z0-9]+ ){1,3}to (?:store and )?process my (?:personal )?data for the purpose of considering my (?:eligibility regarding my current )?application(?: for employment)?$/,
  ];
  // accurate or complete. A label that also mentions terms, an NDA, an agreement or a consequence stays his.
  const statements = '(?:information|answers|statements|details|responses)';
  const truthful = [
    new RegExp(`^(?:by checking this box )?(?:i )?(?:hereby )?(?:certify|confirm|attest|declare|affirm)(?: that)?(?: all)?(?: of)?(?: the)?(?: personal)? ${statements}` +
               `(?: i)?(?: have)?(?: (?:gave|given|provided|submitted|entered|supplied))?(?: (?:in|on|with) (?:this|my) application| above| to(?: [a-z0-9]+){1,4})?` +
               `(?: including(?: (?!agree|terms?\\b|consent|bound|arbitrat|disclos|nda\\b|waive|release|result|terminat|dismiss|authori|background|consequence)[a-z0-9]+){1,60})? (?:is|are) (?:true|accurate|correct|complete)(?:(?: and)? (?:true|accurate|correct|complete)){0,3}` +
               `(?: to the best of my knowledge)?$`),
  ];
  const granted = (f,p) => f.kind === 'checkbox' && (
    p?.data_consent === true && plain.some(r => r.test(S.norm(f.label))) ||
    p?.truth_attestation === true && truthful.some(r => r.test(S.norm(f.label))));
  const empty = v => v === '' || v == null || Array.isArray(v) && !v.length;
  const occupied = f => f.value !== false && !empty(f.value) || typeof f.raw_value === 'string' && f.raw_value.trim() !== '';
  const match = (f,p) => { const found = (p.fields || []).filter(x => S.norm(x.label) === S.norm(f.label)); return found.length === 1 ? found[0] : null; };
  const usable = a => a?.verified === true && !consent.test(a.label) && a.answer !== undefined && a.answer !== null && String(a.answer).trim() !== '' && !/needs.?confirmation|assumption|unknown|to be confirmed/i.test(`${a.who || ''} ${a.answer}`);
  const choice = (options,answer,aliases) => {
    for (const alt of [...String(answer).split('||'),...(Array.isArray(aliases) ? aliases : [])]) { const found = options.filter(o => S.norm(o) === S.norm(alt)); if (found.length === 1) return found[0]; }
    return null;
  };
  function wanted(f,p) {
    if (f.kind === 'file') return /resume|\bcv\b/i.test(f.label) && p.resume ? p.resume.sha256 : null;
    if (granted(f,p)) return true;
    const a = match(f,p); if (!usable(a) || consent.test(f.label)) return null;
    if (['radio','select','combobox'].includes(f.kind)) return choice(f.options,a.answer,a.aliases);
    if (f.kind === 'multiselect') {
      if (f.committed === false) return null;
      const tokens = String(a.answer).split(';').map(S.norm), options = f.options.map(S.norm);
      if (tokens.some(v => !v) || new Set(tokens).size !== tokens.length || new Set(options).size !== options.length) return null;
      const values = tokens.map(token => { const found = f.options.filter(o => S.norm(o) === token); return found.length === 1 ? found[0] : null; });
      return values.every(Boolean) ? values : null;
    }
    if (f.kind === 'checkgroup') { const values = String(a.answer).split(';').map(v => choice(f.options,v)); return values.every(Boolean) ? values : null; }
    if (f.kind === 'checkbox') return /^(yes|true)$/i.test(a.answer) ? true : /^(no|false)$/i.test(a.answer) ? false : null;
    return String(a.answer);
  }
  function agrees(f,p) {
    if (f.kind === 'file') return f.files.length === 1 && f.files[0].sha256 === p.resume?.sha256;
    if (f.kind === 'multiselect' && f.committed !== true) return false;
    if (f.kind === 'combobox') {
      if (!f.committed) return false;
      const a = match(f,p);
      const values = Array.isArray(f.value) ? f.value : [f.value];
      return usable(a) && values.length === 1 && !!choice(values,a.answer,a.aliases);
    }
    const want = wanted(f,p);
    if (want === null) return false;
    // Boards reformat phone numbers after entry; the same last 10 digits is the same number.
    if (f.kind === 'text' && /phone|mobile|telephone/i.test(f.label)) { const d = x => String(x ?? '').replace(/\D/g,''); return d(want).length >= 10 && d(f.value).slice(-10) === d(want).slice(-10); }
    if (Array.isArray(f.value)) return JSON.stringify(f.value.map(S.norm).sort()) === JSON.stringify((Array.isArray(want) ? want : [want]).map(S.norm).sort());
    return typeof want === 'boolean' ? f.value === want : String(f.value).trim() === want.trim();
  }
  const delay = ms => new Promise(r => setTimeout(r,ms));
  function set(e,value) {
    const proto = e.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto,'value').set.call(e,value);
    e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true}));
  }
  // React search boxes ignore a plain input event. Typed InputEvents open their menus.
  async function type(e,text) {
    const proto = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
    proto.set.call(e,''); e.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'deleteContentBackward'}));
    for (const ch of text) {
      e.dispatchEvent(new KeyboardEvent('keydown',{key:ch,bubbles:true,cancelable:true}));
      proto.set.call(e,e.value + ch);
      e.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:ch}));
      e.dispatchEvent(new KeyboardEvent('keyup',{key:ch,bubbles:true}));
      await delay(5);
    }
    // Workday search inputs list matches only after Enter.
    if (e.matches('input[data-uxi-widget-type="selectinput"]')) for (const t of ['keydown','keypress','keyup']) e.dispatchEvent(new KeyboardEvent(t,{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));
  }
  async function apply(f,p,cancelled = () => false) {
    const {e,kind} = f;
    if (kind === 'combobox') {
      const a = match(f,p); if (!usable(a) || consent.test(f.label)) return;
      e.focus();
      if (e.getAttribute('aria-expanded') !== 'true') e.click();
      // Only the observed owning combobox and its associated options may be clicked.
      // Each listed answer is also a search, in order: a double major may match only its second subject.
      const searches = [...new Set(String(a.answer).split('||').map(x => x.trim()).filter(Boolean))].slice(0,3);
      for (const search of searches) {
        if (e.tagName === 'INPUT') await type(e,search);
        // Each search gets 2 s, so an empty first search cannot use up the next one's time.
        const deadline = performance.now() + 2000;
        // Wait while a remote search still lists nothing. Stop after 1.2 s if options show but none match.
        for (let i=0;performance.now() < deadline;i++) {
          if (cancelled()) return;
          const opts = S.options(e).filter(S.visible), pick = choice([...new Set(opts.map(o => S.clean(o.textContent)))],a.answer,a.aliases);
          // Options with the same text show the applicant the same choice (Greenhouse lists some places twice).
          if (pick) { const candidates = opts.filter(o => S.clean(o.textContent) === pick); if (candidates.length) candidates[0].click(); await delay(80); if (e.getAttribute('aria-expanded') === 'false' && S.norm(e.value ?? e.textContent) === S.norm(pick)) S.markCommit(e,pick); return; }
          if (i >= 11 && opts.length) break;
          await delay(100);
        }
      }
      if (e.tagName === 'INPUT') set(e,'');
      // Leave no open menu behind: some boards hide the rest of the form while one is open.
      e.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',code:'Escape',keyCode:27,bubbles:true,cancelable:true})); e.blur();
      return;
    }
    const want = wanted(f,p); if (want === null) return;
    if (kind === 'file') {
      const resume = p.resume;
      if (!resume || !/\.pdf$/i.test(resume.name) || !/^[a-f0-9]{64}$/i.test(resume.sha256)) return;
      const bytes = Uint8Array.from(atob(resume.base64),c => c.charCodeAt(0));
      if (bytes.length > 524288 || await S.hash(bytes) !== resume.sha256 || new TextDecoder().decode(bytes.slice(0,5)) !== '%PDF-') return;
      const transfer = new DataTransfer(); transfer.items.add(new File([bytes],resume.name,{type:'application/pdf'})); e.files = transfer.files;
      // Remember the exact bytes sent in this document: some boards then swap the input for its filename.
      (globalThis.__orbitAttached ||= new Map()).set(S.doc,{name:resume.name,size:bytes.length,sha256:resume.sha256,label:f.label,question_id:f.question_id});
      e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true}));
    } else if (kind === 'multiselect') {
      const selected = want.map(value => [...e.options].find(o => S.clean(o.textContent) === value && !o.disabled && !o.parentElement?.disabled && o.value !== ''));
      if (selected.some(option => !option)) return;
      // Commit the complete set before handlers observe either event.
      for (const option of e.options) option.selected = selected.includes(option);
      e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true}));
    } else if (kind === 'select') {
      const selected = [...e.options].find(o => S.clean(o.textContent) === want && !o.disabled); if (!selected) return;
      e.value = selected.value; e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true}));
    } else if (['radio','checkgroup'].includes(kind)) {
      const values = Array.isArray(want) ? want : [want];
      for (const control of f.group) if (values.includes(S.label(control)) && !S.pressed(control)) control.click();
    } else if (kind === 'checkbox') { if (e.checked !== want) e.click(); }
    else if (kind === 'text' || kind === 'date') {
      // A date picker's text box commits only a full numeric date; other text stays as an uncommitted value.
      if (kind === 'text' && e.closest('[class*="datepicker"]') && !/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(want.trim())) return;
      // A number box (Ashby's Number field) silently empties "(424) 502-7162"; give it the same number's digits.
      set(e,kind === 'text' && e.type === 'number' && /phone|mobile|telephone/i.test(f.label) ? want.replace(/\D/g,'') : want); e.blur();
    }
    await delay(50);
  }
  globalThis.__orbitControls = {consent,granted,empty,occupied,match,usable,wanted,agrees,apply,delay};
})();
