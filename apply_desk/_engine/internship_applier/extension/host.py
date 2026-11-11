"""Bounded Chrome native messaging and preparation observations only."""
import base64
import hashlib
import json
import pathlib
import re
import struct
import sys
from urllib.parse import urlsplit, urldefrag
from ..common import attachment, atomic_json, digest, load_batch, locked, read_json, role_version
from ..fields import ALIASES, CONSENT, norm
SANCTIONED = r'north korea|\biran\b|\bcuba\b|\bsyria\b|\bsudan\b|crimea'
from .observations import valid_observation
from . import operations, facts, advice, metrics, protocol
from . import standing as standing_answers
from .answer_map import AnswerMap
from . import workday_flow
from ..workday_accounts import tenant as workday_tenant
from .schemas import validate_greenhouse_schema

MAX_FRAME = 900_000
MAX_PDF = 512 * 1024
STATUSES = {'scanned', 'needs_input', 'access_hold', 'conflict', 'verified_fields', 'error'}


class Rejected(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


def reject(code, message):
    raise Rejected(code, message)


def packet(folder, role, state=None, *, wire_role_id=None, system_context=None, standing=False, answer_map=None,
           member_mode=False):
    state = state or {}
    selected = facts.overlay(pathlib.Path(folder), role, state)
    source_version = role_version(role, folder)
    fields = []
    for source in role['fields']:
        if source.get('type') == 'input_hidden':
            # Hidden inputs (Greenhouse latitude and longitude) are set by the page's own widget.
            continue
        source = dict(source)
        for confirmation in selected:
            if confirmation['label'] == source['label']:
                source.update(answer=confirmation['value'], who='fact', basis=[confirmation['source']])
                for marker in ('needs', 'needs_rahil', 'needs_confirmation', 'to_confirm', 'assumption', 'assumptions', 'assumed', 'verification_problem'):
                    source.pop(marker, None)
        answer = source.get('answer', '')
        who = source.get('who', 'you')
        basis = source.get('basis') or []
        valid_basis = (isinstance(basis, list) and bool(basis)
                       and all(isinstance(item, str) and item.strip() for item in basis))
        check = source.get('verification')
        check = check if isinstance(check, dict) else {}
        verified = isinstance(answer, str) and bool(answer.strip()) and who in {'profile', 'fact'}
        if who == 'draft':
            verified = (isinstance(answer, str) and bool(answer.strip()) and check.get('status') == 'passed'
                        and check.get('answer_sha256') == digest(answer)
                        and isinstance(check.get('evidence_sha256'), str)
                        and bool(check['evidence_sha256']) and valid_basis
                        and (not role.get('evidence_sha256')
                             or check['evidence_sha256'] == role['evidence_sha256']))
        markers = ('needs', 'needs_rahil', 'needs_confirmation', 'to_confirm',
                   'assumption', 'assumptions', 'assumed', 'verification_problem')
        if any(source.get(key) for key in markers) or re.search(CONSENT, source['label'], re.I):
            verified = False

        if re.search(SANCTIONED, source['label'], re.I) and re.match(r'\s*yes\b', str(answer), re.I):
            verified = False
        # Nov 10 2026: the kit's resume rule gave "[attach the tailored resume PDF]" to a TELUS essay that
        # mentions a resume. A bracketed note is an instruction to the applicant, never a typed answer.
        if re.fullmatch(r'\s*\[[^\]]*\]\s*', str(answer)):
            verified = False
        fields.append({'label': source['label'], 'type': source.get('type', 'text'),
                       'options': source.get('options') or [], 'required': bool(source.get('required')),
                       'answer': answer, 'who': who, 'verified': bool(verified), 'basis': basis})
        if standing and verified and ALIASES.get(norm(answer)):
            # Approved spellings of the same place or school. The page still picks only an exact listed option.
            fields[-1]['aliases'] = ALIASES[norm(answer)]
        if 'step_id' in source:
            fields[-1]['step_id'] = source['step_id']
        if 'conditional' in source:
            fields[-1]['conditional'] = bool(source['conditional'])
    if standing and not member_mode:
        # Only a worker that rescans after a standing answer appears asks for them.
        answers = answer_map or AnswerMap(pathlib.Path(folder).resolve().parent.parent / 'answer-map.json')
        listed = {norm(f['label']): i for i, f in enumerate(fields)}
        for found in standing_answers.fields(pathlib.Path(folder), role, state, fields, CONSENT, answers):
            at = listed.get(norm(found['label']))
            if at is None:
                fields.append(found)
            else:
                # The kit listed this question and left it empty: answer it in place, under the kit's own label.
                fields[at] = {**fields[at], **{k: found[k] for k in ('answer', 'who', 'verified', 'basis')}}
    path = attachment(folder, role['resume'])
    resume = None
    resume_issue = 'The reviewed resume exceeds 512 KiB. Attach and verify it manually.'
    if path.stat().st_size <= MAX_PDF:
        data = path.read_bytes()
        resume_issue = 'The reviewed resume is not a supported PDF. Attach and verify it manually.'
        if len(data) <= MAX_PDF and data.startswith(b'%PDF-'):
            resume = {'name': path.name, 'sha256': hashlib.sha256(data).hexdigest(),
                      'base64': base64.b64encode(data).decode('ascii')}
            resume_issue = None
    result = {'role_id': wire_role_id or role['id'], 'company': role['company'], 'title': role['title'],
              'apply_url': role['apply_url'], 'role_version': role_version(role, folder),
              'fields': fields, 'resume': resume, 'resume_issue': resume_issue,

              'data_consent': False,

              'truth_attestation': False}
    # A Workday role's real apply page is recorded once it is reached (workday_flow).
    steps = role.get('steps') or workday_flow.steps_for(folder, role)
    if not isinstance(steps, list) or len(steps) > 100:
        reject('configuration', 'Invalid trusted application steps.')
    origin = urlsplit(role['apply_url'])
    allowed = [role['apply_url']]
    if workday_tenant(role['apply_url']):
        # Workday runs its whole application at one page under the posting.
        allowed.append(role['apply_url'].rstrip('/') + '/apply/applyManually')
    ids = set()
    for step in steps:
        if not isinstance(step, dict) or set(step) != {'id', 'url'} or not isinstance(step['id'], str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', step['id']) or step['id'] in ids:
            reject('configuration', 'Invalid trusted step identity.')
        target = urlsplit(step['url'])
        if (target.scheme, target.netloc) != (origin.scheme, origin.netloc) or target.username or target.password or target.fragment:
            reject('configuration', 'Steps require exact same-origin URLs.')
        ids.add(step['id'])
        if step['url'] not in allowed:
            allowed.append(step['url'])
    if any(f.get('step_id') not in ids for f in fields if 'step_id' in f) or ('resume_step_id' in role and role['resume_step_id'] not in ids):
        reject('configuration', 'Unknown configured field or resume step.')
    result.update(allowed_urls=allowed, steps=steps, source_role_version=source_version, confirmed_facts=selected)
    schema = validate_greenhouse_schema(role.get('greenhouse_schema'), role_id=role['id'], apply_url=role['apply_url'], reject=reject)
    if schema:
        result['greenhouse_schema'] = schema
    result['role_version'] = digest({'source': source_version, 'steps': steps, 'resume_step_id': role.get('resume_step_id'), 'confirmed_facts': selected, 'greenhouse_schema': schema})
    if 'resume_step_id' in role:
        result['resume_step_id'] = role['resume_step_id']
    if system_context is not None:
        result['system'] = system_context
    result['packet_digest'] = digest(result)
    return result


class Host:
    def __init__(self, config, origin):
        protocol.origin(config, origin, reject)
        self.folder = pathlib.Path(config['batch']).resolve()
        self.state = pathlib.Path(config['state']).resolve()
        self.selected_role_id = config.get('selected_role_id')
        self.packet_options = {key: config[key] for key in ('wire_role_id', 'system_context') if key in config}
        if not self.folder.is_dir():
            reject('configuration', 'Configured batch is unavailable.')
        if load_batch(self.folder).get('member_mode') is True:
            # Member batches never inherit the original owner's personal standing grants.
            self.packet_options['member_mode'] = True

    def handle(self, request):
        op, rid = protocol.validate(request, reject)
        if op == 'ping':
            return {'version': 2, 'host': 'com.orbit.applier'}
        if op in {'review_start', 'review_status'}:
            reject('configuration', 'Connect the existing T3 application root to use guarded review.')
        batch = load_batch(self.folder)
        if op == 'list':
            rows = [{'role_id': r['id'], 'company': r['company'], 'title': r['title'], 'apply_url': r['apply_url']} for r in batch['roles']]
            offset, limit = request.get('offset', 0), request.get('limit', 100)
            return {'roles': rows[offset:offset + limit], 'version': 2, 'mode': 'batch',
                    'next_offset': offset + limit if offset + limit < len(rows) else None}
        wanted = self.selected_role_id or request.get('role_id')
        role = next((r for r in batch['roles'] if r['id'] == wanted), None)
        if self.packet_options.get('wire_role_id', request['role_id']) != request['role_id']:
            role = None
        if role is None:
            reject('role', 'Role is not in the configured batch.')
        if op == 'packet' and not self.state.exists():
            return packet(self.folder, role, **self.packet_options, standing=request.get('standing') is True)
        with locked(self.state / 'observations.lock'):
            self.state.chmod(0o700)
            state = read_json(self.state / 'observations.json', {'roles': {}, 'requests': {}})
            current = packet(self.folder, role, state, **self.packet_options, standing=request.get('standing') is True)
            if op == 'packet':
                return current
            if op == 'review_summary':
                return metrics.summary(state, current['role_id'], current)
            if op.startswith('advice_'):
                record = state['roles'].get(role['id'])
                if not record or not valid_observation(record):
                    reject('advice', 'Scan the current application before preparing suggestions.')
                if op != 'advice_list' and request['packet_digest'] != current['packet_digest']:
                    reject('stale', 'Packet changed; prepare suggestions again.')
                try:
                    if op == 'advice_list':
                        return advice.list_advice(self.state, current, record)
                    if op == 'advice_import':
                        return advice.import_advice(self.state, current, record, request['response'])
                    keys = request['fact_keys']
                    if not isinstance(keys, list) or len(keys) > 100 or not all(isinstance(k, str) for k in keys) or len(keys) != len(set(keys)):
                        reject('advice', 'Choose bounded, unique available fact keys.')
                    available = {f'fact:{i}': f for i, f in enumerate(current['fields'])
                                 if f['verified'] and f['who'] in {'profile', 'fact'}}
                    if any(key not in available for key in keys):
                        reject('advice', 'Only explicitly selected confirmed fact descriptions may be included.')
                    return advice.prepare(self.folder, self.state, current, record,
                                          available_facts=[{'key': key, 'description': available[key]['label']} for key in keys])
                except ValueError as error:
                    reject('advice', str(error))
            if op == 'progress':
                saved = state['roles'].get(role['id'])
                if saved and any(saved[k] != current[k] for k in ('role_version', 'packet_digest')):
                    saved = None
                if saved and not valid_observation(saved):
                    reject('record', 'Saved observation is malformed; scan again.')
                steps = state.get('steps', {}).get(role['id'], {})
                steps = {k: v for k, v in steps.items() if v['packet_digest'] == current['packet_digest']}
                observed = [s['id'] for s in current['steps'] if s['id'] in steps]
                return {'record': saved, 'steps_observed': observed, 'all_steps_observed': bool(current['steps']) and len(observed) == len(current['steps']), 'step_records': steps}
            def save(record):
                self.validate_record(record, current)
                state['roles'][role['id']] = record
                steps = state.setdefault('steps', {}).setdefault(role['id'], {})
                steps = {k: v for k, v in steps.items() if v['packet_digest'] == current['packet_digest']}
                sid = record.get('step_id')
                if sid:
                    order = [s['id'] for s in current['steps']]
                    previous = steps.get(sid)
                    changed = previous is None or any(previous.get(k) != record.get(k) for k in ('form_digest', 'fields', 'status'))
                    if changed or record['status'] != 'verified_fields':
                        steps = {k: v for k, v in steps.items() if order.index(k) <= order.index(sid)}
                    steps[sid] = record
                state['steps'][role['id']] = steps
            if op == 'review_event':
                result = metrics.execute(state, request, current, reject)
            elif op in {'begin', 'operation', 'cancel', 'end', 'reconcile'}:
                result = operations.execute(state, request, current, reject, save)
            elif op in {'fact_preview', 'fact_confirm'}:
                result = facts.execute(self.folder, state, batch, role, current, request, reject)
            else:
                identity = digest(request)
                self.validate_record(request['record'], current)
                previous = state['requests'].get(rid)
                if previous is not None:
                    if previous != identity:
                        reject('request_conflict', 'Request ID was used with different contents.')
                    return {'record': request['record']}
                save(request['record'])
                state['requests'][rid] = identity
                result = {'record': request['record']}
            atomic_json(self.state / 'observations.json', state)
            return result

    def validate_record(self, record, current):
        required = {'role_version', 'packet_digest', 'url', 'document_id', 'form_digest', 'status', 'fields', 'issues', 'updated_at'}
        optional = {'step_id', 'observed_at', 'settled', 'revision', 'owner'}
        if not isinstance(record, dict) or not required <= record.keys() or record.keys() - required - optional:
            reject('record', 'Observation properties do not match the preparation contract.')
        if any(not isinstance(record[k], str) or not record[k] or len(record[k]) > 4096 for k in required - {'fields', 'issues'}):
            reject('record', 'Observation identity must contain bounded strings.')
        if record['status'] not in STATUSES or not valid_observation(record):
            reject('record', 'Invalid preparation observation.')
        if any(record[k] != current[k] for k in ('role_version', 'packet_digest')):
            reject('stale', 'Batch or packet changed; refresh before saving.')
        if (record['url'] if current['steps'] else urldefrag(record['url'])[0]) not in current['allowed_urls']:
            reject('url', 'Observation URL is not explicitly configured.')
        sid = record.get('step_id')
        if current['steps'] and (not sid or not any(s['id'] == sid and s['url'] == record['url'] for s in current['steps'])):
            reject('step', 'Observation must name its configured current step.')
        if sid and not current['steps']:
            reject('step', 'Step is not configured.')


def read_exact(stream, count):
    chunks = bytearray()
    while len(chunks) < count:
        chunk = stream.read(count - len(chunks))
        if not chunk:
            raise EOFError
        chunks.extend(chunk)
    return bytes(chunks)


def write_frame(stream, value):
    data = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
    if len(data) > MAX_FRAME:
        data = json.dumps({'id': value.get('id'), 'ok': False, 'error': {
            'code': 'oversized', 'message': 'Response exceeds the native message limit.'}}).encode()
    stream.write(struct.pack('@I', len(data)) + data)
    stream.flush()


def serve(config_path, origin, incoming=None, outgoing=None):
    incoming, outgoing = incoming or sys.stdin.buffer, outgoing or sys.stdout.buffer
    try:
        config = read_json(config_path)
        if config.get('system_root'):
            from .system_host import SystemHost
            host = SystemHost(config, origin)
        else:
            host = Host(config, origin)
    except Exception:
        write_frame(outgoing, {'id': None, 'ok': False, 'error': {'code': 'origin', 'message': 'Host configuration or Chrome caller origin rejected.'}})
        return 1
    while True:
        rid = None
        try:
            header = incoming.read(4)
            if not header:
                return 0
            if len(header) != 4:
                reject('framing', 'Truncated native message header.')
            size = struct.unpack('@I', header)[0]
            if not 0 < size <= MAX_FRAME:
                reject('oversized', 'Native request length is outside the permitted bound.')
            raw = read_exact(incoming, size)
            request = json.loads(raw.decode('utf-8'), parse_constant=lambda _: reject('json', 'Invalid JSON constant.'))
            rid = request.get('id') if isinstance(request, dict) else None
            result = host.handle(request)
            write_frame(outgoing, {'id': rid, 'ok': True, 'result': result})
        except Rejected as error:
            write_frame(outgoing, {'id': rid, 'ok': False, 'error': {'code': error.code, 'message': error.message}})
            if error.code in {'oversized', 'framing'}:
                return 1
        except (UnicodeError, json.JSONDecodeError, EOFError):
            write_frame(outgoing, {'id': rid, 'ok': False, 'error': {'code': 'json', 'message': 'Invalid or truncated JSON message.'}})
            return 1
        except Exception:
            write_frame(outgoing, {'id': rid, 'ok': False, 'error': {'code': 'unavailable', 'message': 'Configured batch or private observation state is unavailable.'}})
