"""Postings the employer closed: recorded once from the live page, then left out of the role list."""
import json
import os
import pathlib
import re
import tempfile
import time

FILE = 'closed-postings.json'
CLOSED = re.compile(r"page you are looking for (doesn.?t|does not) exist|no longer accepting applications|"
                    r"(position|job|role) has been filled|(job|posting|position) (you are looking for )?is no longer (open|available)|"
                    r"^\s*job not found|\bjob not found\b|(job|posting) (posting )?has expired|this job is closed|"
                    r"no longer (open|available) for applications", re.I)


def is_closed(text):
    return bool(CLOSED.search(text or ''))


def load(root):
    try:
        data = json.loads((pathlib.Path(root) / FILE).read_text())
    except (FileNotFoundError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def record(root, role_key, url, text):
    data = load(root)
    data[role_key] = {'url': url, 'seen_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'evidence': ' '.join((text or '').split())[:200]}
    fd, tmp = tempfile.mkstemp(dir=root, prefix='.closed-')
    with os.fdopen(fd, 'w') as out:
        json.dump(data, out, indent=1, sort_keys=True)
    os.chmod(tmp, 0o600)
    os.replace(tmp, pathlib.Path(root) / FILE)


def excluded(root):
    data = load(root)
    return set(data), {row.get('url') for row in data.values() if isinstance(row, dict)}
