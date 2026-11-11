"""File boundaries and content identities shared by box and the portable runner."""
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import pathlib
import re
import tempfile


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    path = pathlib.Path(path)
    if path.name == 'ledger.json':
        from .database import enabled, save_ledger
        if enabled(path.parent):
            save_ledger(path.parent, value)
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out, ensure_ascii=False, indent=1, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    finally:
        pathlib.Path(tmp).unlink(missing_ok=True)


@contextlib.contextmanager
def locked(path, blocking=True):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        os.chmod(path, 0o600)
        flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        fcntl.flock(handle, flags)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def read_json(path, default=None):
    path = pathlib.Path(path)
    if path.name == 'ledger.json':
        from .database import enabled, read_ledger
        if enabled(path.parent):
            return read_ledger(path.parent)
    return json.loads(path.read_text()) if path.exists() else default


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value):
        raise ValueError('invalid application ID')
    return value


def attachment(batch_dir, name):
    base = pathlib.Path(batch_dir).resolve()
    target = (base / name).resolve()
    if target.parent != base or not target.is_file() or target.suffix.lower() != '.pdf':
        raise ValueError('resume must be a PDF directly in the batch folder')
    return target


def load_batch(folder):
    value = read_json(pathlib.Path(folder) / 'batch.json')
    if not isinstance(value, dict) or not isinstance(value.get('roles'), list):
        raise ValueError('batch.json must contain a roles list')
    seen = set()
    for role in value['roles']:
        rid = safe_id(role['id'])
        if rid in seen:
            raise ValueError('duplicate role ID in batch')
        seen.add(rid)
        if not re.match(r'https?://', role['apply_url']):
            raise ValueError('application URL must use HTTP or HTTPS')
        attachment(folder, role['resume'])
        if not isinstance(role.get('fields'), list):
            raise ValueError('role must contain its field definitions')
    return value


def role_version(role, batch_dir):
    return digest({'id': role['id'], 'company': role['company'], 'title': role['title'],
                   'url': role['apply_url'], 'resume_sha256': file_hash(attachment(batch_dir, role['resume'])),
                   'fields': role['fields'], 'defaults': role.get('defaults', [])})
