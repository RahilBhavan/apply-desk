"""Explicit local review timers; elapsed wall time is not measured attention."""
import datetime as dt
import re
from ..common import now

IDS = re.compile(r'[A-Za-z0-9_.:-]{1,128}')
DISCLAIMER = 'Self-reported timer events; server-clock elapsed time is not actual attention time or an outcome measure.'


def execute(state, request, current, reject):
    """Mutate caller-owned state under its observation lock; caller persists atomically."""
    keys = {'role_id', 'packet_digest', 'session_id', 'event'}
    if not isinstance(request, dict) or not keys <= request.keys() or request.keys() - keys - {'id', 'op', 'standing'}:
        reject('review_event', 'Exact review event properties are required.')
    for key in ('role_id', 'session_id'):
        if not isinstance(request[key], str) or not IDS.fullmatch(request[key]):
            reject('review_event', 'A bounded stable review identity is required.')
    if not isinstance(request['packet_digest'], str) or not 1 <= len(request['packet_digest']) <= 128:
        reject('review_event', 'A bounded packet digest is required.')
    if not isinstance(request['event'], str) or request['event'] not in {'start', 'finish', 'abandon'}:
        reject('review_event', 'Unsupported review event.')
    if request['packet_digest'] != current['packet_digest'] or request['role_id'] != current['role_id']:
        reject('stale', 'Review event requires the current role and packet.')
    sessions = state.setdefault('review_sessions', {})
    sid, event = request['session_id'], request['event']
    existing = sessions.get(sid)
    if existing and existing['role_id'] != request['role_id']:
        reject('review_conflict', 'Review session belongs to another role.')
    same_packet = existing and all(existing[k] == current[k] for k in ('packet_digest', 'role_version'))
    if event == 'start':
        if existing:
            if not same_packet:
                reject('review_conflict', 'Review session packet changed; use a new session ID.')
            return {'session': existing, 'duplicate': True, 'disclaimer': DISCLAIMER}
        existing = {'session_id': sid, 'role_id': request['role_id'], 'packet_digest': current['packet_digest'],
                    'role_version': current['role_version'], 'source': 'user_review_timer', 'status': 'unfinished',
                    'started_at': now(), 'ended_at': None, 'ending_event': None, 'elapsed_seconds': None,
                    'attention_seconds': None, 'human_productivity_gain': None, 'cost_usd': None}
        sessions[sid] = existing
        return {'session': existing, 'duplicate': False, 'disclaimer': DISCLAIMER}
    if not existing:
        reject('review_event', 'Start this review session before ending it.')
    if existing['ending_event'] is not None:
        if existing['ending_event'] != event or existing.get('ending_packet_digest', existing['packet_digest']) != current['packet_digest']:
            reject('review_conflict', 'An ended review session cannot be changed.')
        return {'session': existing, 'duplicate': True, 'disclaimer': DISCLAIMER}
    if event == 'finish' and not same_packet:
        reject('stale', 'Changed packet cannot complete an earlier review timer.')
    ended = now()
    elapsed = (dt.datetime.fromisoformat(ended) - dt.datetime.fromisoformat(existing['started_at'])).total_seconds()
    if elapsed < 0:
        elapsed = None
        existing['clock_anomaly'] = True
    existing.update(ended_at=ended, elapsed_seconds=elapsed, ending_event=event,
                    ending_packet_digest=current['packet_digest'],
                    status='finished' if event == 'finish' else 'abandoned')
    return {'session': existing, 'duplicate': False, 'disclaimer': DISCLAIMER}


def summary(state, role, current):
    """Historical sessions are retained; current totals exclude changed packets and unfinished work."""
    rid = role if isinstance(role, str) else role.get('id', role.get('role_id'))
    sessions = []
    for row in state.get('review_sessions', {}).values():
        if row['role_id'] != rid:
            continue
        is_current = all(row[k] == current[k] for k in ('packet_digest', 'role_version'))
        sessions.append({**row, 'current': is_current,
                         'display_status': row['status'] if is_current else 'historical_' + row['status']})
    current_rows = [s for s in sessions if s['current']]
    finished = [s for s in current_rows if s['status'] == 'finished']
    elapsed = sum(s['elapsed_seconds'] for s in finished) if finished and all(s['elapsed_seconds'] is not None for s in finished) else None
    return {'sessions': sessions, 'source': 'user_review_timer', 'disclaimer': DISCLAIMER,
            'current_totals': {'started': len(current_rows), 'finished': len(finished),
                               'unfinished': sum(s['status'] == 'unfinished' for s in current_rows),
                               'abandoned': sum(s['status'] == 'abandoned' for s in current_rows),
                               'completed_timer_seconds': elapsed, 'attention_seconds': None,
                               'prepared_per_human_review_minute': None,
                               'human_productivity_gain': None, 'cost_usd': None}}
