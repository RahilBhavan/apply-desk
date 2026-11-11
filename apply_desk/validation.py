"""Validate member inputs and public club lists at entry points."""
import csv
import io
import re
from urllib.parse import urlsplit, urlunsplit

PROFILE_LABELS = {'first_name': 'First name', 'last_name': 'Last name',
                  'email': 'Email', 'phone': 'Phone', 'school': 'School',
                  'degree': 'Degree', 'major': 'Major', 'graduation_year': 'Graduation year',
                  'linkedin': 'LinkedIn', 'website': 'Website'}
FORM_ONLY = re.compile(r'attest|certif|signature|agree|accept|consent|privacy|terms|'
                       r'password|security code|verification code|one.time|captcha|'
                       r'upload|resume|cover letter|demograph|race|ethnic|gender|disab|veteran', re.I)


def text(value, limit=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or '\x00' in value:
        raise ValueError('Expected nonempty bounded text')
    return value.strip()


def profile(raw):
    if not isinstance(raw, dict) or not raw or raw.keys() - PROFILE_LABELS.keys():
        raise ValueError('Use only documented profile keys; never include credentials')
    return {key: text(value) for key, value in raw.items()}


def public_url(raw):
    value = text(raw, 4096)
    url = urlsplit(value)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.port not in {None, 443} or '.' not in url.hostname
            or url.hostname.endswith(('.local', '.localhost'))):
        raise ValueError('Job URL must be a public HTTPS address without credentials')
    import ipaddress
    try:
        ipaddress.ip_address(url.hostname)
    except ValueError:
        pass
    else:
        raise ValueError('Job URL must use an employer hostname')
    return urlunsplit(('https', url.netloc.lower(), url.path or '/', url.query, ''))


def jobs_csv(raw):
    if not isinstance(raw, str) or len(raw) > 2_000_000:
        raise ValueError('Club CSV exceeds 2 MB')
    reader = csv.DictReader(io.StringIO(raw))
    if set(reader.fieldnames or []) != {'company', 'title', 'apply_url'} or len(reader.fieldnames) != 3:
        raise ValueError('CSV needs exactly company,title,apply_url; private member columns are forbidden')
    rows = []
    for row in reader:
        if len(rows) >= 2000 or None in row or None in row.values():
            raise ValueError('Malformed or oversized club list')
        rows.append({'company': text(row['company'], 200), 'title': text(row['title'], 300),
                     'apply_url': public_url(row['apply_url'])})
    return rows


def questions(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 200:
        raise ValueError('Capture between 1 and 200 questions')
    result = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {'label', 'type', 'options', 'required'}:
            raise ValueError('Question needs label,type,options,required')
        label = text(item['label'])
        if item['type'] not in {'text', 'textarea', 'select', 'radio'} or type(item['required']) is not bool:
            raise ValueError('Unsupported question kind')
        options = item['options']
        if not isinstance(options, list) or len(options) > 300:
            raise ValueError('Invalid question choices')
        options = [text(option) for option in options]
        if len(set(options)) != len(options) or bool(options) != (item['type'] in {'select', 'radio'}):
            raise ValueError('Choice questions need unique exact options; text questions have none')
        if label in {q['label'] for q in result}:
            raise ValueError('Repeated labels require manual preparation')
        result.append({**item, 'label': label, 'options': options})
    return result
