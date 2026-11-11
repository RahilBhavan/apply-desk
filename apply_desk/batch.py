"""Pure translation from member-owned facts into existing preparation packets."""
from .validation import PROFILE_LABELS


def roles(state):
    from .workspace import prepared
    result = []
    for role_id, job in state['jobs'].items():
        if role_id in state.get('submissions', {}):
            continue
        fields = {label.casefold(): {'label': label, 'answer': state['profile'][key], 'type': 'text',
                  'who': 'profile', 'basis': ['profile:' + key]}
                  for key, label in PROFILE_LABELS.items() if key in state['profile']}
        if state['profile'].get('first_name') and state['profile'].get('last_name'):
            fields['full name'] = {'label': 'Full name', 'answer': state['profile']['first_name'] + ' ' + state['profile']['last_name'],
                                   'type': 'text', 'who': 'profile', 'basis': ['profile:first_name', 'profile:last_name']}
        for field in prepared(state, role_id):
            # Unanswered observations belong to the inbox, not the browser's trusted packet.
            # Profile fields remain byte-identical after a scan so Scan -> Fill does not stale itself.
            if field['who'] == 'fact' and field['answer']:
                fields[field['label'].casefold()] = field
        result.append({'id': role_id, 'company': job['company'], 'title': job['title'],
                       'apply_url': job['apply_url'], 'resume': 'resume.pdf',
                       'fields': [fields[key] for key in sorted(fields)]})
    return result
