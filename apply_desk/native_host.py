"""Live member bridge around the existing scan/fill/verify journal. Never submits."""
import json
from pathlib import Path
import struct
import sys
from .engine import load
from .workspace import Workspace

HOST_NAME = 'com.applydesk.host'


def capture(workspace, role_id, record):
    if not record:
        return
    fields = record['fields']
    labels = [field['label'] for field in fields]
    questions = []
    for field in fields:
        kind = field['kind']
        if labels.count(field['label']) != 1 or kind not in {'text', 'select', 'radio'}:
            continue
        options = field['options'] if kind in {'select', 'radio'} else []
        if kind in {'select', 'radio'} and (not options or len(set(options)) != len(options)):
            continue
        questions.append({'label': field['label'], 'type': kind, 'options': options, 'required': field['required']})
    if questions:
        workspace.capture(role_id, questions[:200], workspace.context(role_id)['revision'])


class MemberHost:
    def __init__(self, config, origin):
        Host, _, _, _, _ = load()
        if not isinstance(config, dict) or set(config) != {'workspace', 'allowed_origin', 'state'}:
            raise ValueError('Only a dedicated member workspace can connect')
        self.workspace = Workspace(config['workspace'])
        self.origin, self.config = origin, config
        self.Host = Host
        self._host()

    def _host(self):
        host = self.Host({'batch': str(self.workspace.engine_snapshot()), 'state': self.config['state'],
                          'allowed_origin': self.config['allowed_origin']}, self.origin)
        return host

    def handle(self, request):
        _, Rejected, _, _, _ = load()
        if not isinstance(request, dict):
            raise Rejected('request', 'Expected a native request object')
        operation = request.get('op')
        if isinstance(operation, str) and (operation.startswith(('fact_', 'advice_')) or operation in {'review_start', 'review_status'}):
            raise Rejected('member_review', 'Open Apply Desk to review answers. Submit yourself in the employer tab.')
        host = self._host()
        result = host.handle(request)
        from .storage import atomic_json
        import time
        atomic_json(self.workspace.root / 'browser-seen.json', {'at': time.time()})
        record = request.get('record')
        if record and request['op'] in {'save', 'end', 'reconcile'}:
            capture(self.workspace, request['role_id'], record)
        return result


def serve(config_path, origin, incoming=None, outgoing=None):
    _, Rejected, read_exact, write_frame, max_frame = load()
    incoming, outgoing = incoming or sys.stdin.buffer, outgoing or sys.stdout.buffer
    try:
        config = json.loads(Path(config_path).read_text())
        host = MemberHost(config, origin)
    except (ValueError, OSError, Rejected):
        write_frame(outgoing, {'id': None, 'ok': False, 'error': {'code': 'configuration', 'message': 'Member workspace or extension identity unavailable'}})
        return 1
    while True:
        request_id = None
        try:
            header = incoming.read(4)
            if not header:
                return 0
            if len(header) != 4:
                raise ValueError('Truncated native frame')
            size = struct.unpack('@I', header)[0]
            if not 0 < size <= max_frame:
                raise ValueError('Oversized native frame')
            request = json.loads(read_exact(incoming, size))
            request_id = request.get('id') if isinstance(request, dict) else None
            result = host.handle(request)
            write_frame(outgoing, {'id': request_id, 'ok': True, 'result': result})
        except Rejected as error:
            write_frame(outgoing, {'id': request_id, 'ok': False, 'error': {'code': error.code, 'message': error.message}})
        except (ValueError, OSError, EOFError, KeyError, TypeError):
            write_frame(outgoing, {'id': request_id, 'ok': False, 'error': {'code': 'unavailable', 'message': 'Application changed or workspace is unavailable; refresh and scan again'}})
            return 1
