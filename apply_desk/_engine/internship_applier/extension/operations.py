"""Durable preparation reservations; unresolved writes never expire."""
import re
from ..common import digest, now


def context(value, current, reject):
    keys = {'tab_id', 'document_id', 'url', 'packet_digest', 'role_version'}
    if not isinstance(value, dict) or set(value) != keys:
        reject('context', 'Exact operation context is required.')
    if type(value['tab_id']) is not int or value['tab_id'] < 0:
        reject('context', 'Invalid tab identity.')
    if any(not isinstance(value[k], str) or not value[k] or len(value[k]) > 4096 for k in keys - {'tab_id'}):
        reject('context', 'Invalid context identity.')
    if value['url'] not in current['allowed_urls']:
        reject('url', 'Operation URL is not explicitly configured.')
    if any(value[k] != current[k] for k in ('packet_digest', 'role_version')):
        reject('stale', 'Refresh the current packet before beginning work.')


def execute(state, request, current, reject, save):
    verb, rid = request['op'], request['role_id']
    operations = state.setdefault('operations', {})
    oid = request.get('operation_id')
    if oid is not None and (not isinstance(oid, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', oid)):
        reject('operation_id', 'A bounded stable operation ID is required.')
    existing = operations.get(oid)
    if verb == 'operation':
        if oid is None:
            role_operations = [x for x in reversed(list(operations.values())) if x['role_id'] == rid]
            existing = next((x for x in role_operations if x['state'] in {'active', 'uncertain'}),
                            role_operations[0] if role_operations else None)
        if existing and existing['role_id'] != rid:
            reject('operation_conflict', 'Operation belongs to another role.')
        return {'operation': existing}
    if not oid:
        reject('operation_id', 'Operation ID is required.')
    if verb == 'begin':
        identity = digest({'role_id': rid, 'context': request['context']})
        if existing:
            if existing['identity'] != identity:
                reject('operation_conflict', 'Operation ID payload changed.')
            return {'operation': existing, 'duplicate': True}
        context(request['context'], current, reject)
        # Reserve all configured URLs: different steps of one application share ownership.
        urls = set(current['allowed_urls'])
        if any(x['state'] in {'active', 'uncertain'} and (x['role_id'] == rid or urls.intersection(x['allowed_urls'])) for x in operations.values()):
            reject('busy', 'An unresolved operation owns this application.')
        existing = {'id': oid, 'operation_id': oid, 'role_id': rid, 'identity': identity,
                    'context': request['context'], 'allowed_urls': current['allowed_urls'],
                    'state': 'active', 'cancel_requested': False, 'started_at': now()}
        operations[oid] = existing
        return {'operation': existing, 'duplicate': False}
    if not existing or existing['role_id'] != rid:
        reject('operation', 'Unknown operation for this role.')
    if verb == 'cancel':
        if existing['state'] in {'active', 'uncertain'}:
            existing['cancel_requested'] = True
        return {'operation': existing}
    identity = digest({k: v for k, v in request.items() if k != 'id'})
    if existing.get('end_identity') == identity:
        return {'operation': existing}
    if existing['state'] not in {'active', 'uncertain'}:
        reject('operation_conflict', 'Acknowledged operation cannot change.')
    if verb == 'reconcile':
        if request.get('executor_idle') is not True:
            reject('operation', 'Read-only reconciliation must establish an idle executor.')
        context(request['context'], current, reject)
        if any(request['context'][k] != request['record'].get(k) for k in ('url', 'packet_digest', 'role_version')):
            reject('context', 'Reconciliation observation must match its current context.')
        save(request['record'])
        existing['state'] = 'cancelled'
        existing['reconciled'] = True
    else:
        target = request.get('state')
        if target not in {'completed', 'cancelled', 'uncertain'}:
            reject('operation', 'Invalid ending state.')
        if target == 'completed' and 'record' not in request:
            reject('record', 'Completed work requires an observation.')
        if 'record' in request:
            if any(request['record'].get(k) != existing['context'][k] for k in ('url', 'packet_digest', 'role_version')):
                reject('context', 'Completion observation must match reserved context.')
            save(request['record'])
        existing['state'] = target
    existing['end_identity'] = identity
    existing['updated_at'] = now()
    return {'operation': existing}
