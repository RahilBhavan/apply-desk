"""Closed native request boundary shared by batch and canonical-system modes."""
import re

SHAPES = {
    'ping': (set(), set()), 'list': (set(), {'offset', 'limit'}),
    'packet': ({'role_id'}, set()), 'progress': ({'role_id'}, set()),
    'save': ({'role_id', 'record'}, set()),
    'begin': ({'role_id', 'operation_id', 'context'}, set()),
    'operation': ({'role_id'}, {'operation_id'}),
    'cancel': ({'role_id', 'operation_id'}, set()),
    'end': ({'role_id', 'operation_id', 'state'}, {'record'}),
    'reconcile': ({'role_id', 'operation_id', 'context', 'executor_idle', 'record'}, set()),
    'fact_preview': ({'role_id', 'label', 'value', 'source', 'scope', 'packet_digest'}, set()),
    'fact_confirm': ({'role_id', 'preview_id', 'label', 'value', 'source', 'scope', 'packet_digest'}, set()),
    'advice_prepare': ({'role_id', 'packet_digest', 'fact_keys'}, set()),
    'advice_import': ({'role_id', 'packet_digest', 'response'}, set()),
    'advice_list': ({'role_id'}, set()),
    'review_event': ({'role_id', 'packet_digest', 'session_id', 'event'}, set()),
    'review_summary': ({'role_id'}, set()),
    'review_start': ({'role_id', 'packet_digest', 'launch_id'}, set()),
    'review_status': ({'role_id'}, set()),
}


def validate(request, reject):
    if not isinstance(request, dict):
        reject('request', 'Request must be an object.')
    rid = request.get('id')
    if not isinstance(rid, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', rid):
        reject('request', 'A bounded request ID is required.')
    op = request.get('op')
    if not isinstance(op, str) or op not in SHAPES:
        reject('operation', 'Unsupported application operation.')
    required, optional = SHAPES[op]
    if 'role_id' in required:
        # A current worker asks for standing answers; older workers never send this.
        optional = optional | {'standing'}
        if 'standing' in request and request['standing'] is not True:
            reject('request', 'standing must be true when present.')
    if not required <= request.keys() or request.keys() - required - optional - {'id', 'op'}:
        reject('request', 'Unexpected or missing request properties.')
    if 'role_id' in required and (not isinstance(request['role_id'], str) or not 1 <= len(request['role_id']) <= 200):
        reject('role', 'Choose a configured role.')
    if op == 'list':
        offset, limit = request.get('offset', 0), request.get('limit', 100)
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            reject('request', 'Use offset >= 0 and limit between 1 and 100.')
    if op == 'review_start':
        if not isinstance(request['packet_digest'], str) or not re.fullmatch(r'[0-9a-f]{64}', request['packet_digest']):
            reject('stale', 'Current application packet is required.')
        if not isinstance(request['launch_id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', request['launch_id']):
            reject('request', 'A stable review launch ID is required.')
    return op, rid


def origin(config, caller, reject):
    if not re.fullmatch(r'chrome-extension://[a-p]{32}/', caller or '') or caller != config.get('allowed_origin'):
        reject('origin', 'Chrome caller origin is not configured.')
