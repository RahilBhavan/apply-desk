const $ = s => document.querySelector(s);
let lastState = null, editing = false, shareId = null;
let pendingActions = 0;
const token = $('meta[name="apply-desk-token"]').content;
const notice = (message, error = false) => { $('#notice').textContent = message; $('#notice').classList.toggle('error', error); };
async function api(path, body) {
  const response = await fetch('/api/' + path, { method: body ? 'POST' : 'GET',
    headers: { 'Content-Type': 'application/json', 'X-Apply-Desk': token },
    ...(body ? { body: JSON.stringify(body) } : {}) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Unable to save. Try again.');
  return data;
}
function element(tag, text, className) {
  const node = document.createElement(tag); node.textContent = text;
  if (className) node.className = className;
  return node;
}
async function act(button, action) {
  pendingActions++; button.disabled = true;
  try { await action(); } catch (error) { notice(error.message, true); }
  finally { pendingActions--; button.disabled = false; if (!$('#share-confirm').checked) $('#download-jobs').disabled = true; }
}
async function refresh() {
  const state = await api('state'); lastState = state;
  $('#onboarding').hidden = state.initialized && !editing;
  $('#desk').hidden = !state.initialized || editing;
  if (!state.initialized) return;
  $('#resume-text').textContent = state.resume_text || 'No readable text was extracted. T3 can use your confirmed profile, but needs your input for experience details.';
  $('#browser-status').textContent = state.setup.browser_seen ? 'Connected. Chrome has reached your private workspace.' : state.setup.browser_installed ? 'Helper installed. Load the extension in Chrome to finish setup.' : 'Install the helper, then approve the extension in Chrome.';
  $('#t3-status').textContent = state.setup.connector_seen ? `Connector reached by ${state.setup.connector_client || 'your MCP client'}.` : 'Connect a dedicated T3 project for your applications.';
  $('#greeting').textContent = `${state.profile.first_name || 'Your'}${state.profile.first_name ? '’s' : ''} applications`;
  $('#jobs').replaceChildren();
  for (const job of state.jobs) {
    const row = element('article', '', 'row');
    row.append(element('h3', job.title), element('p', job.company));
    const link = element('a', 'Open employer application ↗');
    link.href = job.apply_url; link.target = '_blank'; link.rel = 'noopener noreferrer';
    row.append(link);
    if (state.submissions[job.id]) row.append(element('p', 'Submitted · recorded by you', 'hint'));
    else {
      const submitted = element('button', 'Record as submitted', 'secondary');
      submitted.addEventListener('click', () => { if (confirm('Have you already submitted this application on the employer’s site?')) act(submitted, async () => {
        await api('submitted', {role_id: job.id, revision: state.revision}); notice('Submission recorded. Apply Desk will no longer offer this job for preparation.'); await refresh();
      }); });
      row.append(element('p', 'After you submit on the employer’s site:', 'hint'), submitted);
    }
    $('#jobs').append(row);
  }
  if (!state.jobs.length) $('#jobs').append(element('p', 'No jobs yet. Import a club list above.', 'hint'));
  $('#questions').replaceChildren();
  for (const question of state.questions) {
    if (/attest|certif|signature|agree|accept|consent|privacy|terms|password|security code|verification code|captcha|resume|cover letter|demograph|race|ethnic|gender|disab|veteran/i.test(question.label)) continue;
    const job = state.jobs.find(job => job.id === question.role_id);
    const form = element('form', '', 'row question-form');
    form.append(element('p', `${job.company} · ${job.title}`, 'hint'));
    const label = element('label', question.label);
    const input = document.createElement(question.options.length ? 'select' : 'textarea');
    input.required = true;
    if (question.options.length) {
      const empty = element('option', 'Choose your answer'); empty.value = ''; input.append(empty);
      for (const option of question.options) { const item = element('option', option); item.value = option; input.append(item); }
    } else { input.rows = 3; }
    label.append(input); form.append(label);
    const button = element('button', 'Save my confirmed answer'); form.append(button);
    form.addEventListener('submit', event => { event.preventDefault(); act(button, async () => {
      await api('answer', {role_id: question.role_id, label: question.label, answer: input.value, revision: state.revision});
      notice('Answer saved. Scan the employer form again to use the updated answer.'); await refresh();
    }); });
    $('#questions').append(form);
  }
  $('#proposals').replaceChildren();
  for (const proposal of state.proposals) {
    const row = element('article', '', 'row');
    const job = state.jobs.find(job => job.id === proposal.role_id);
    row.append(element('p', job ? `${job.company} · ${job.title}` : 'Application', 'hint'),
      element('h3', proposal.label), element('p', proposal.answer, 'answer'));
    row.append(element('p', 'Sources: ' + proposal.evidence.join(', '), 'hint'));
    if (proposal.status === 'accepted') row.append(element('p', 'Previously confirmed. Current questions determine whether this answer is still usable.', 'hint'));
    else if (proposal.stale) row.append(element('p', 'Context changed. Ask T3 to prepare a fresh answer.', 'hint'));
    else {
      const button = element('button', 'Confirm this answer');
      button.addEventListener('click', () => act(button, async () => {
        await api('accept', { proposal_id: proposal.id });
        notice('Answer confirmed. Scan the employer form again to fill it with this answer.'); await refresh();
      })); row.append(button);
    }
    $('#proposals').append(row);
  }
  if (!state.proposals.length) $('#proposals').append(element('p', 'No drafts waiting. Connect T3 below to prepare answers from your confirmed profile.', 'hint'));
}
$('#profile-form').addEventListener('submit', event => {
  event.preventDefault(); const button = event.submitter;
  act(button, async () => {
    const file = $('#resume').files[0];
    if ((!file && !lastState?.initialized) || file?.size > 512 * 1024) throw new Error('Choose a PDF of at most 512 KiB.');
    const bytes = file ? new Uint8Array(await file.arrayBuffer()) : new Uint8Array();
    let binary = ''; for (const byte of bytes) binary += String.fromCharCode(byte);
    const profile = Object.fromEntries([...new FormData(event.target)].filter(([key, value]) => value.trim()));
    const updating = lastState?.initialized;
    await api(updating ? 'profile' : 'init', { profile, ...(file ? {resume: btoa(binary)} : {}), ...(updating ? {revision: lastState.revision} : {}) });
    editing = false; $('#cancel-profile').hidden = true;
    notice(updating ? 'Profile updated. Drafts must be reviewed against the new facts.' : 'Workspace created. Import your club’s job list next.'); await refresh();
  });
});
$('#import-form').addEventListener('submit', event => {
  event.preventDefault(); act(event.submitter, async () => {
    const file = $('#csv').files[0];
    if (file.size > 2000000) throw new Error('Choose a CSV smaller than 2 MB.');
    const result = await api('jobs', { csv: (await file.text()).replace(/^\uFEFF/, '') });
    notice(`Imported ${result.added} new jobs. Duplicate entries were kept once.`); await refresh();
  });
});
$('#add-job-form').addEventListener('submit', event => {
  event.preventDefault(); act(event.submitter, async () => {
    await api('job-add', Object.fromEntries(new FormData(event.target)));
    notice('Job added. Open its application, then click the Apply Desk extension.'); event.target.reset(); await refresh();
  });
});
$('#setup-browser').addEventListener('click', event => act(event.target, async () => {
  const result = await api('setup-browser', {});
  $('#browser-path').textContent = result.browser_folder; $('#browser-instructions').hidden = false;
  notice('Chrome helper installed. Follow the steps below to load the extension.'); await refresh();
}));
$('#open-extensions').addEventListener('click', event => act(event.target, () => api('open-local', {target: 'extensions'})));
$('#copy-folder').addEventListener('click', event => act(event.target, async () => {
  await navigator.clipboard.writeText($('#browser-path').textContent); notice('Folder path copied. Paste it into Chrome’s Load unpacked folder chooser.');
}));
$('#setup-t3').addEventListener('click', event => act(event.target, async () => {
  const result = await api('setup-t3', {}); $('#t3-result').textContent = result.message;
  notice(result.status === 'needs_t3' ? 'T3 needs to be installed and opened first.' : 'T3 project configured. Start a new conversation there and approve the connector.');
}));
$('#share-jobs').addEventListener('click', event => act(event.target, async () => {
  const result = await api('share-preview', {}); shareId = result.share_id;
  $('#share-links').replaceChildren();
  for (const job of result.jobs) {
    const line = element('p', `${job.company} · ${job.title}: ${job.apply_url}`); $('#share-links').append(line);
  }
  $('#share-status').textContent = `${result.jobs.length} public links. ${result.excluded} personalized or unrecognized links excluded. Review the links before downloading.`;
  $('#share-confirm').checked = false; $('#download-jobs').disabled = true; $('#share-review').hidden = false;
}));
$('#share-confirm').addEventListener('change', () => { $('#download-jobs').disabled = !$('#share-confirm').checked; });
$('#download-jobs').addEventListener('click', event => act(event.target, async () => {
  if (!$('#share-confirm').checked) throw new Error('Review the public links first.');
  const result = await api('share-jobs', {share_id: shareId}); const url = URL.createObjectURL(new Blob([result.csv], {type:'text/csv'}));
  const link = element('a', ''); link.href=url; link.download='club-jobs.csv'; link.click(); URL.revokeObjectURL(url);
}));
$('#refresh').addEventListener('click', event => act(event.target, async () => { await refresh(); notice('Answers are up to date.'); }));
$('#export').addEventListener('click', event => act(event.target, async () => {
  const result = await api('export', {}); $('#export-result').textContent = 'Private batch saved: ' + result.batch;
  notice('Preparation snapshot saved. No application was submitted.');
}));
$('#connection').addEventListener('click', event => act(event.target, async () => {
  $('#connection-result').textContent = JSON.stringify(await api('connection', {}), null, 2);
}));
refresh().catch(error => notice(error.message, true));

// A visible desk picks up browser scans and T3 drafts without requiring a manual refresh.
let updating = false;
setInterval(async () => {
  if (document.hidden || updating || document.activeElement?.matches('input,textarea,select') || pendingActions > 0) return;
  updating = true; try { await refresh(); } catch {} finally { updating = false; }
}, 5000);

$('#edit-profile').addEventListener('click', async () => {
  editing = true;
  for (const input of $('#profile-form').querySelectorAll('input[name]')) input.value = lastState.profile[input.name] || '';
  $('#resume').required = false; $('#resume').value = ''; $('#confirmed').checked = false;
  $('#save-profile').textContent = 'Save confirmed changes'; $('#cancel-profile').hidden = false;
  await refresh(); $('#profile-form input').focus();
});
$('#cancel-profile').addEventListener('click', async () => { editing = false; await refresh(); });

$('#quit').addEventListener('click', event => act(event.target, async () => { await api('shutdown', {}); notice('Apply Desk has quit. You can close this tab.'); }));
