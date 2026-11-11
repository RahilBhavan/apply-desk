"""Versioned, member-scoped desktop sessions and controlled update handoff."""
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from . import __version__


def _detect_identity():
    marker = Path(__file__).parent / 'build-id.txt'
    build = marker.read_text().strip() if marker.is_file() else hashlib.sha256(
        (Path(__file__).parent / 'web_server.py').read_bytes()).hexdigest()
    return {'version': __version__, 'build_id': build}


# Cache the loaded build identity. An in-place Finder update must not make an
# already-running old process report the new bundle's marker as its own.
_LOADED_IDENTITY = _detect_identity()


def identity():
    return dict(_LOADED_IDENTITY)


def directory(root):
    key = hashlib.sha256(str(Path(root).expanduser().absolute()).encode()).hexdigest()[:20]
    return Path(root).expanduser().absolute().parent / 'runtime' / key


def existing(root):
    session = json.loads((directory(root) / 'session.json').read_text())
    # Saved addresses are constrained to this app's loopback HTTP scheme.
    from urllib.parse import urlsplit
    address = urlsplit(session['url'])
    if address.scheme != 'http' or address.hostname != '127.0.0.1' or not address.port or address.path not in {'', '/'}:
        raise ValueError('Invalid saved app address')
    with urlopen(session['url'] + '/health', timeout=3) as response:
        health = json.load(response)
    if health.get('instance_id') != session['instance_id']:
        raise ValueError('Another application owns the saved address')
    return session, health


def stop(session):
    request = Request(session['url'] + '/api/shutdown', data=b'{}',
                      headers={'Content-Type': 'application/json', 'X-Apply-Desk': session['shutdown_token']})
    with urlopen(request, timeout=5) as response:
        return json.load(response)
