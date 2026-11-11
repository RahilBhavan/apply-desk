"""Validate untrusted browser observations before storage or presentation."""
import re

KINDS = {'text', 'date', 'file', 'checkbox', 'checkgroup', 'radio', 'select', 'multiselect', 'combobox', 'unsupported'}


def text(value, limit=16384):
    return isinstance(value, str) and len(value) <= limit


def strings(value):
    return isinstance(value, list) and len(value) <= 1000 and all(text(item) for item in value)


def valid_field(field):
    required = {'key', 'label', 'kind', 'required', 'value', 'options', 'valid', 'files'}
    if not isinstance(field, dict) or not required <= field.keys() or field.keys() - required - {'raw_value', 'question_id', 'owner', 'committed', 'native_payload'}:
        return False
    if not all(text(field[key]) for key in ('key', 'label', 'kind')) or field['kind'] not in KINDS:
        return False
    if type(field['required']) is not bool or type(field['valid']) is not bool:
        return False
    if not (text(field['value']) or type(field['value']) is bool or strings(field['value'])):
        return False
    if field['kind'] == 'multiselect':
        payload = field.get('native_payload')
        if (not strings(field['value']) or type(field.get('committed')) is not bool
                or not isinstance(payload, dict) or set(payload) != {'name', 'selected_values', 'form_values', 'exclusive'}
                or not text(payload['name'], 4096) or type(payload['exclusive']) is not bool
                or not strings(payload['selected_values']) or not strings(payload['form_values'])
                or len(payload['selected_values']) != len(field['value'])):
            return False
    elif 'native_payload' in field:
        return False
    if not strings(field['options']) or field.get('raw_value') is not None and not text(field['raw_value']):
        return False
    if any(k in field and not text(field[k], 4096) for k in ('question_id', 'owner')):
        return False
    if 'committed' in field and type(field['committed']) is not bool:
        return False
    files = field['files']
    if not isinstance(files, list) or len(files) > 100:
        return False
    for file in files:
        if not isinstance(file, dict) or set(file) != {'name', 'size', 'sha256'}:
            return False
        if not text(file['name']) or type(file['size']) is not int or file['size'] < 0:
            return False
        if not isinstance(file['sha256'], str) or not re.fullmatch('[a-f0-9]{64}', file['sha256']):
            return False
    return True


def valid_observation(record):
    if not isinstance(record, dict) or 'fields' not in record or 'issues' not in record or 'status' not in record:
        return False
    if any(k in record and not text(record[k], 4096) for k in ('step_id', 'observed_at', 'owner')):
        return False
    if 'settled' in record and type(record['settled']) is not bool:
        return False
    if 'revision' in record and (type(record['revision']) is not int or record['revision'] < 0):
        return False
    fields, issues = record['fields'], record['issues']
    if not isinstance(fields, list) or len(fields) > 500 or not all(valid_field(f) for f in fields):
        return False
    if not isinstance(issues, list) or len(issues) > 1000:
        return False
    for issue in issues:
        if not isinstance(issue, dict) or set(issue) != {'code', 'label', 'message'}:
            return False
        if not all(text(issue[key]) for key in issue) or not re.fullmatch('[a-z_]{1,64}', issue['code']):
            return False
    return record['status'] != 'verified_fields' or bool(fields) and not issues and record.get('settled', True) is True
