"""Validate explicitly configured Greenhouse question evidence, never fetch a form.

Shape provenance: https://docs.greenhouse.io/job-board, retrieved 2026-11-07.
This is a closed preparation envelope around the documented questions[] shape,
not an unrestricted API response parser or a vendor compatibility claim.
"""
import json
import math
import re
from urllib.parse import parse_qs, urlsplit

TYPES = frozenset({'input_file', 'input_text', 'textarea',
                   'multi_value_single_select', 'multi_value_multi_select'})
SELECTS = frozenset({'multi_value_single_select', 'multi_value_multi_select'})
NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,195}(?:\[\])?\Z')
ID = re.compile(r'[A-Za-z0-9_.:-]{1,200}\Z')
JOB = re.compile(r'[1-9][0-9]{0,19}\Z')


def _text(value, limit):
    return (isinstance(value, str) and bool(value.strip()) and len(value) <= limit
            and not any(ord(c) < 32 for c in value))


def validate_greenhouse_schema(raw, *, role_id, apply_url, reject):
    """Return a detached scanner-compatible schema or reject a configured hold.

    `None` disables the adapter. The caller supplies trusted batch role_id and
    exact apply_url; raw must explicitly repeat both. An external job ID exposed
    by /jobs/<id> or gh_jid must agree. If a custom URL exposes neither, the
    configured envelope is only an explicit job association, not independent
    proof of an employer's external identity. Unknown widgets are rejected.
    `reject(code, message)` must raise the caller's boundary exception.
    """
    if raw is None:
        return None

    def fail(message):
        reject('schema', message)
        raise ValueError(message)  # A non-raising callback must never bypass validation.

    if not _text(role_id, 200) or not _text(apply_url, 4096):
        fail('A trusted role and exact application URL are required.')
    try:
        target = urlsplit(apply_url)
        port = target.port
    except (ValueError, TypeError):
        fail('Invalid configured application URL.')
    if (target.scheme not in {'http', 'https'} or not target.hostname
            or target.username or target.password or target.fragment or port == 0):
        fail('Configured application URL must be an exact HTTP URL without credentials or fragment.')
    if not isinstance(raw, dict) or set(raw) != {'provider', 'role_id', 'job_id', 'url', 'questions'}:
        fail('Greenhouse schema envelope has unexpected or missing properties.')
    if raw['provider'] != 'greenhouse' or raw['role_id'] != role_id or raw['url'] != apply_url:
        fail('Schema provider, role or exact application URL does not match configuration.')
    job = raw['job_id']
    if not isinstance(job, str) or not JOB.fullmatch(job):
        fail('Greenhouse external job ID must be a bounded positive decimal string.')
    if JOB.fullmatch(role_id) and role_id != job:
        fail('Numeric trusted role identity must agree with the external job ID.')
    exposed = []
    match = re.search(r'/jobs/([0-9]+)/?\Z', target.path)
    if match:
        exposed.append(match.group(1))
    query = parse_qs(target.query, keep_blank_values=True)
    if 'gh_jid' in query:
        exposed.extend(query['gh_jid'])
    if any(value != job for value in exposed) or len(query.get('gh_jid', [])) > 1:
        fail('Schema external job ID does not exactly match the configured URL identity.')
    # Avoid unbounded serialization of an untrusted caller's containers.
    questions = raw['questions']
    if not isinstance(questions, list) or not 1 <= len(questions) <= 200:
        fail('Schema requires between one and 200 questions.')
    result, names, ids, labels = [], set(), set(), set()
    total_fields, total_values, total_chars = 0, 0, len(apply_url) + len(role_id)
    for question in questions:
        if (not isinstance(question, dict) or not {'label', 'required', 'fields'} <= question.keys()
                or question.keys() - {'id', 'label', 'required', 'fields'}):
            fail('Question has unexpected or missing properties.')
        label, required, fields = (question[k] for k in ('label', 'required', 'fields'))
        if not _text(label, 1000) or type(required) is not bool:
            fail('Question label and requiredness must be bounded explicit values.')
        normalized = ' '.join(label.casefold().split())
        if normalized in labels:
            fail('Duplicate semantic question labels require manual review.')
        labels.add(normalized)
        total_chars += len(label)
        if not isinstance(fields, list) or not 1 <= len(fields) <= 20:
            fail('A question requires one to 20 documented fields.')
        clean_fields = []
        for field in fields:
            total_fields += 1
            if total_fields > 500:
                fail('Schema exceeds 500 fields.')
            if (not isinstance(field, dict) or not {'name', 'type'} <= field.keys()
                    or field.keys() - {'name', 'type', 'values'}):
                fail('Field has unexpected or missing properties.')
            name, kind = field['name'], field['type']
            if not isinstance(name, str) or not NAME.fullmatch(name) or name in names:
                fail('Field name must be a unique bounded form parameter.')
            if not isinstance(kind, str) or kind not in TYPES:
                fail('Unknown or hidden schema widgets require manual review.')
            names.add(name)
            total_chars += len(name) + len(kind)
            clean = {'name': name, 'type': kind}
            if 'values' in field or kind in SELECTS:
                values = field.get('values')
                if (not isinstance(values, list) or len(values) > 500
                        or kind in SELECTS and not values or kind not in SELECTS and values):
                    fail('Select fields require bounded options; text and file fields cannot carry options.')
                clean_values, option_labels, option_values = [], set(), set()
                for option in values:
                    total_values += 1
                    if total_values > 2000:
                        fail('Schema exceeds 2000 total options.')
                    if not isinstance(option, dict) or set(option) != {'label', 'value'}:
                        fail('Option must contain only label and value.')
                    ol, value = option['label'], option['value']
                    if not _text(ol, 1000):
                        fail('Option labels must be bounded nonempty text.')
                    if not (isinstance(value, str) and len(value) <= 1000
                            or type(value) in {int, float} and abs(value) <= 2 ** 53 - 1 and math.isfinite(value)):
                        fail('Option value must be bounded text or a finite safe number.')
                    nl = ' '.join(ol.casefold().split())
                    nv = str(value)
                    if nl in option_labels or nv in option_values:
                        fail('Ambiguous duplicate option labels or values require manual review.')
                    option_labels.add(nl)
                    option_values.add(nv)
                    total_chars += len(ol) + len(str(value))
                    clean_values.append({'label': ol, 'value': value})
                clean['values'] = clean_values
            clean_fields.append(clean)
        qid = question.get('id', clean_fields[0]['name'].removesuffix('[]'))
        if not isinstance(qid, str) or not ID.fullmatch(qid) or qid in ids:
            fail('Question identity must be unique bounded text.')
        ids.add(qid)
        total_chars += len(qid)
        if total_chars > 100000:
            fail('Schema text exceeds the preparation packet budget.')
        result.append({'id': qid, 'label': label, 'required': required, 'fields': clean_fields})
    canonical = {'provider': 'greenhouse', 'role_id': role_id, 'job_id': job,
                 'url': apply_url, 'questions': result}
    if len(json.dumps(canonical, ensure_ascii=False).encode('utf-8')) > 250000:
        fail('Schema exceeds the native packet byte budget.')
    return canonical
