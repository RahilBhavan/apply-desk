"""Explicit local setup actions requested by the member UI."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import time
from .integration import install_browser, write_project


def install_app():
    """Install the exact opened bundle in a stable per-user Applications path."""
    if sys.platform != 'darwin' or not getattr(sys, 'frozen', False):
        return {'status': 'source_mode', 'executable': sys.executable}
    executable = Path(sys.executable).resolve()
    app = next((p for p in executable.parents if p.suffix == '.app'), None)
    if app is None:
        raise ValueError('Open the Apply Desk app bundle')
    import fcntl
    import plistlib
    import tempfile
    expected = 'org.applydesk.app'
    if plistlib.loads((app / 'Contents/Info.plist').read_bytes()).get('CFBundleIdentifier') != expected:
        raise ValueError('This bundle is not Apply Desk')
    user_destination = Path.home() / 'Applications/Apply Desk.app'
    system_destination = Path('/Applications/Apply Desk.app')
    if app in {user_destination, system_destination}:
        return {'status': 'installed', 'executable': str(executable)}
    destination = user_destination
    destination.parent.mkdir(exist_ok=True)
    support = Path.home() / 'Library/Application Support/Apply Desk'
    support.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (support / 'install.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if destination.is_symlink():
            raise ValueError('The application install path must not be a symbolic link')
        if destination.exists() and plistlib.loads((destination / 'Contents/Info.plist').read_bytes()).get('CFBundleIdentifier') != expected:
            raise ValueError('Another app owns the installation path')
        # Stage a complete verified bundle, then swap directories. Never merge an
        # update into live files or leave obsolete signed resources behind.
        with tempfile.TemporaryDirectory(prefix='.apply-desk-update-', dir=destination.parent) as temporary:
            stage = Path(temporary) / 'Apply Desk.app'
            backup = Path(temporary) / 'Previous.app'
            subprocess.run(['/usr/bin/ditto', str(app), str(stage)], check=True, capture_output=True)
            subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(stage)], check=True, capture_output=True)
            if destination.exists():
                destination.rename(backup)
            try:
                stage.rename(destination)
            except OSError:
                if backup.exists():
                    backup.rename(destination)
                raise
    return {'status': 'installed', 'executable': str(destination / 'Contents/MacOS/ApplyDesk')}


def browser_setup(workspace):
    installed = install_app()
    if getattr(sys, 'frozen', False) and installed['executable'] != sys.executable:
        result = subprocess.run([installed['executable'], '--workspace', str(workspace), 'install-browser'],
                                check=True, capture_output=True, text=True, timeout=30)
        return json.loads(result.stdout)
    return install_browser(workspace)


def t3_setup(workspace, open_app=True):
    installed = install_app()
    if getattr(sys, 'frozen', False) and installed['executable'] != sys.executable:
        result = subprocess.run([installed['executable'], '--workspace', str(workspace), 'setup-t3'],
                                check=True, capture_output=True, text=True, timeout=40)
        return json.loads(result.stdout)
    result = write_project(workspace)
    cli = Path.home() / '.t3/bin/t3'
    if not cli.is_file():
        result.update(status='needs_t3', message='Install T3 Code, open it once and sign in to your chosen provider. Then press Connect T3 again.')
        return result
    if open_app:
        subprocess.run([str(cli), 'app', result['project']], check=True, capture_output=True, timeout=30)
    result.update(status='project_ready', message='Open a new conversation in this project, approve the Apply Desk connector, and ask it to prepare your captured questions.')
    return result


def open_local(target):
    if sys.platform != 'darwin':
        raise ValueError('This setup action is available in the Mac release')
    if target == 'extensions':
        subprocess.run(['/usr/bin/open', '-a', 'Google Chrome', 'chrome://extensions'], check=True, capture_output=True)
    elif target == 'browser_folder':
        folder = Path.home() / 'Library/Application Support/Apply Desk/browser'
        subprocess.run(['/usr/bin/open', str(folder)], check=True, capture_output=True)
    else:
        raise ValueError('Choose a setup action shown in Apply Desk')
    return {'status': 'opened'}


def status(workspace):
    workspace = Path(workspace)
    support = Path.home() / 'Library/Application Support/Apply Desk'
    result = {'browser_installed': (support / 'native-config.json').is_file(), 'browser_seen': False,
              'connector_seen': False, 'version': '0.2.0'}
    for filename, key in [('browser-seen.json', 'browser_seen'), ('connector-seen.json', 'connector_seen')]:
        try:
            row = json.loads((workspace / filename).read_text())
            result[key] = time.time() - row['at'] < 86400
            if key == 'connector_seen':
                result['connector_client'] = row.get('client', 'MCP client')
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return result
