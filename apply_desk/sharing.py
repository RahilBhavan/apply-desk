"""Keep personalized application links out of public club exports."""
from urllib.parse import parse_qsl, urlsplit
import re

PUBLIC_JOB_KEYS = {'gh_jid', 'job_id', 'jobid', 'requisitionid', 'reqid', 'postingid'}
PRIVATE_PATH = re.compile(r'/(?:invite|invitation|candidate|candidate-portal|my-applications|application-status)(?:/|$)', re.I)


def public_link(value):
    url = urlsplit(value)
    if PRIVATE_PATH.search(url.path):
        return False
    for key, item in parse_qsl(url.query, keep_blank_values=True):
        if key.casefold() not in PUBLIC_JOB_KEYS or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', item):
            return False
    return True
