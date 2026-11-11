"""Loopback-only member UI with per-process request authorization."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import subprocess
import sys
import uuid
from .workspace import Workspace, revision, proposal_context

ASSETS = Path(__file__).parent / 'web'


def make_server(root, port=0, instance_id=""):
    root = Path(root).expanduser().absolute()
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, data, content_type='application/json'):
            raw = json.dumps(data).encode() if content_type == 'application/json' else data
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self, api=False):
            expected = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != expected:
                self.respond(403, {'error': 'Use the local Apply Desk address printed at launch'})
                return False
            if self.headers.get('Origin') not in {None, 'http://' + expected}:
                self.respond(403, {'error': 'Foreign browser origin refused'})
                return False
            if api and not secrets.compare_digest(self.headers.get('X-Apply-Desk', ''), token):
                self.respond(403, {'error': 'Reload Apply Desk to reconnect'})
                return False
            return True

        def do_GET(self):
            if not self.authorized(self.path.startswith('/api/')):
                return
            if self.path == '/health':
                from .runtime import identity
                self.respond(200, {'instance_id': instance_id, **identity()})
            elif self.path == '/':
                html = (ASSETS / 'index.html').read_text().replace('REQUEST_TOKEN', token)
                self.respond(200, html.encode(), 'text/html; charset=utf-8')
            elif self.path in {'/app.js', '/style.css'}:
                path = ASSETS / self.path[1:]
                self.respond(200, path.read_bytes(), 'text/javascript' if path.suffix == '.js' else 'text/css')
            elif self.path == '/api/state':
                try:
                    if not (root / 'workspace.json').exists():
                        self.respond(200, {'initialized': False})
                        return
                    workspace = Workspace(root)
                    from .mac_actions import status
                    from .workspace import prepared
                    with workspace.state() as state:
                        current = revision(state)
                        self.respond(200, {'initialized': True, 'profile': state['profile'], 'revision': current, 'setup': status(root),
                            'questions': [{'role_id': role_id, **field} for role_id in state['jobs'] for field in prepared(state, role_id) if not field['answer']],
                            'resume_text': state.get('resume_text', ''), 'resume_parse': state.get('resume_parse', 'unreadable'), 'submissions': state.get('submissions', {}), 'jobs': [{'id': key, **job} for key, job in state['jobs'].items()],
                            'proposals': [{'id': key, **proposal, 'stale': (proposal.get('context_hash') != proposal_context(state, proposal['role_id'], proposal['label']) if proposal.get('context_hash') else proposal['revision'] != current)}
                                          for key, proposal in state['proposals'].items()]})
                except (OSError, ValueError):
                    self.respond(400, {'error': 'Cannot read workspace; check its local files'})
            else:
                self.respond(404, {'error': 'Not found'})

        def do_POST(self):
            if not self.authorized(api=True):
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 3_000_000 or self.headers.get_content_type() != 'application/json':
                    raise ValueError('Expected JSON of at most 3 MB')
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('Expected a JSON object')
                if self.path == '/api/shutdown':
                    self.respond(200, {'status': 'stopping'})
                    import threading
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                if self.path == '/api/init':
                    Workspace.create_pdf(root, body.get('profile'), base64.b64decode(body.get('resume', ''), validate=True))
                    result = {'status': 'initialized'}
                else:
                    workspace = Workspace(root)
                    if self.path == '/api/profile':
                        pdf = base64.b64decode(body['resume'], validate=True) if body.get('resume') else None
                        result = workspace.update_profile(body.get('profile'), pdf, body.get('revision'))
                    elif self.path == '/api/submitted':
                        result = workspace.record_submission(body.get('role_id'), body.get('revision'))
                    elif self.path == '/api/setup-browser':
                        from .mac_actions import browser_setup
                        result = browser_setup(root)
                    elif self.path == '/api/setup-t3':
                        from .mac_actions import t3_setup
                        result = t3_setup(root)
                    elif self.path == '/api/open-local':
                        from .mac_actions import open_local
                        result = open_local(body.get('target'))
                    elif self.path == '/api/answer':
                        result = workspace.confirm_answer(body.get('role_id'), body.get('label'), body.get('answer'), body.get('revision'))
                    elif self.path == '/api/share-preview':
                        result = workspace.share_preview()
                    elif self.path == '/api/share-jobs':
                        if not isinstance(body.get('share_id'), str):
                            raise ValueError('Review the public links before sharing')
                        result = {'csv': workspace.export_jobs(body['share_id'])}
                    elif self.path == '/api/job-add':
                        import csv
                        import io
                        data = io.StringIO()
                        writer = csv.DictWriter(data, fieldnames=['company', 'title', 'apply_url'])
                        writer.writeheader()
                        writer.writerow({key: body.get(key, '') for key in writer.fieldnames})
                        result = workspace.import_jobs(data.getvalue())
                    elif self.path == '/api/jobs':
                        result = workspace.import_jobs(body.get('csv'))
                    elif self.path == '/api/accept':
                        result = workspace.accept(body.get('proposal_id', ''))
                    elif self.path == '/api/export':
                        result = workspace.export_batch(root / 'exports' / ('batch-' + uuid.uuid4().hex))
                    elif self.path == '/api/connection':
                        from .integration import connection
                        result = connection(root)
                    else:
                        self.respond(404, {'error': 'Not found'})
                        return
                self.respond(200, result)
            except subprocess.SubprocessError:
                self.respond(400, {'error': 'Setup could not finish. Check that Chrome or T3 is installed, then try again.'})
            except (OSError, ValueError, TypeError) as error:
                self.respond(400, {'error': str(error)})

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.request_token = token
    return server


def run(root, port=0, open_browser=True):
    import fcntl
    from urllib.request import urlopen
    from .storage import atomic_json
    root = Path(root).expanduser().absolute()
    from .runtime import directory, existing, identity, stop
    runtime = directory(root)
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (runtime / 'desktop.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            session, health = existing(root)
            if health.get('build_id') == identity()['build_id']:
                if open_browser:
                    import webbrowser
                    webbrowser.open(session['url'])
                return
            # Opening an updated bundle is an explicit update action. Ask only this
            # member's authenticated old instance to exit, then acquire its released lock.
            stop(session)
            import time
            deadline = time.monotonic() + 15
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise ValueError('The previous app has not stopped. Quit it before opening this update.')
                    time.sleep(0.1)
        instance_id = secrets.token_urlsafe(20)
        server = make_server(root, port, instance_id)
        url = f'http://127.0.0.1:{server.server_port}'
        atomic_json(runtime / 'session.json', {'url': url, 'instance_id': instance_id, 'shutdown_token': server.request_token, **identity()})
        print(f'Apply Desk: {url}', flush=True)
        if open_browser:
            import webbrowser
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            (runtime / 'session.json').unlink(missing_ok=True)
