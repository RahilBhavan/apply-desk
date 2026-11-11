"""Reproducible Mac runtime validation and bundled license notices."""
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess


def notices(destination):
    sections = ['Apply Desk runtime dependency notices. Each dependency retains its own license.\n']
    for distribution in sorted(importlib.metadata.distributions(), key=lambda d:d.metadata.get('Name','')):
        sections.append('\n\n## ' + distribution.metadata.get('Name','unknown') + ' ' + distribution.version + '\n')
        found = False
        for entry in distribution.files or []:
            if any(part.casefold() in {'licenses', 'license', 'license.txt', 'license.md', 'copying', 'copying.txt'} for part in entry.parts):
                path = distribution.locate_file(entry)
                if path.is_file():
                    try: sections.append(path.read_text(encoding='utf-8'))
                    except UnicodeError: continue
                    found = True
        if not found:
            sections.append(distribution.metadata.get('License-Expression') or distribution.metadata.get('License') or 'See the upstream distribution license.')
    import sys
    python_license = Path(sys.base_prefix) / ('lib/python' + str(sys.version_info.major) + '.' + str(sys.version_info.minor) + '/LICENSE.txt')
    if python_license.is_file():
        sections.append('\n\n## CPython\n' + python_license.read_text())
    Path(destination).write_text('\n'.join(sections))


def validate_macos(app):
    targets = []
    magic = {b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca',b'\xca\xfe\xba\xbf'}
    for path in sorted(Path(app).rglob('*')):
        if path.is_symlink() or not path.is_file(): continue
        with path.open('rb') as handle:
            if handle.read(4) not in magic: continue
        output = subprocess.run(['/usr/bin/vtool','-arch','arm64','-show-build',str(path)],check=True,capture_output=True,text=True).stdout
        versions = re.findall(r'^\s*minos\s+([0-9.]+)',output,re.M)
        if not versions and 'LC_VERSION_MIN_MACOSX' in output:
            versions = re.findall(r'^\s*version\s+([0-9.]+)',output,re.M)[:1]
        if not versions: raise ValueError('Cannot verify minimum macOS target: '+str(path))
        for version in versions:
            if tuple(int(part) for part in version.split('.')[:2]) > (13,0):
                raise ValueError('Bundled runtime requires macOS '+version+': '+str(path))
            targets.append({'path':str(path.relative_to(app)),'minos':version})
    if not targets: raise ValueError('No native app runtime found')
    return {'architecture':'arm64','target_macos':'13.0','native_files':targets}
