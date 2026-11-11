"""Create a source release from explicit owned-code/asset allowlists."""
import hashlib
import json
from pathlib import Path
import shutil

ENGINE = ['__init__.py', 'common.py', 'fields.py',
          'extension/__init__.py', 'extension/host.py', 'extension/observations.py',
          'extension/operations.py', 'extension/advice.py', 'extension/metrics.py',
          'extension/protocol.py', 'extension/closed.py', 'extension/schemas.py']
# Explicit member-only adapters replace personal standing-answer, account, fact-intake
# and ledger capabilities. The release contains none of that owner's policy/history code.
MEMBER_ADAPTERS = {
    'database.py': "def enabled(root):\n    return False\n\ndef read_ledger(*args):\n    raise ValueError('Personal ledgers are unavailable')\n\ndef save_ledger(*args):\n    raise ValueError('Personal ledgers are unavailable')\n",
    'extension/standing.py': "def fields(*args, **kwargs):\n    raise ValueError('Member facts must come from the member workspace')\n",
    'extension/answer_map.py': "class AnswerMap:\n    def __init__(self, *args, **kwargs):\n        raise ValueError('Personal answer maps are unavailable in member mode')\n",
    'workday_accounts.py': "def tenant(url):\n    return None\n",
    'extension/workday_flow.py': "def steps_for(folder, role):\n    return []\n",
    'extension/facts.py': "def overlay(folder, role, state):\n    return []\n\ndef execute(*args, **kwargs):\n    raise ValueError('Confirm answers in Apply Desk')\n",
}
BROWSER = ['manifest.json', 'worker.js', 'worker-core.js', 'worker-actions.js',
           'scanner.js', 'controls.js', 'page.js', 'popup.html', 'review.html',
           'review.css', 'review-ui.js', 'review-assistance.js', 'review-timer.js',
           'review-system.js', 'review.js', 'fonts/BarlowCondensed-Bold.woff2',
           'fonts/BarlowCondensed-OFL.txt', 'fonts/DMSans.woff2', 'fonts/DMSans-OFL.txt', 'fonts/SOURCE.txt']


def assemble(destination, repo=None):
    repo = Path(repo or Path(__file__).resolve().parent.parent)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    manifest = []

    def copy(source, target):
        if source.is_symlink() or not source.is_file():
            raise ValueError('Release source is missing or symbolic: ' + str(source))
        raw = source.read_bytes()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        manifest.append({'source': str(source.relative_to(repo)), 'sha256': hashlib.sha256(raw).hexdigest()})

    own = repo / 'apply_desk'
    for source in sorted(own.glob('*.py')):
        copy(source, destination / 'apply_desk' / source.name)
    for relative in ['pyproject.toml', 'README.md', 'LICENSE', 'extension-key.txt']:
        copy(own / relative, destination / 'apply_desk' / relative)
    for name in ('CONTRIBUTING.md', 'PRIVACY.md'):
        copy(own / name if (own / name).is_file() else repo / name, destination / name)
    workflow = own / 'ci.yml' if (own / 'ci.yml').is_file() else repo / '.github/workflows/ci.yml'
    copy(workflow, destination / '.github/workflows/ci.yml')
    mac_workflow = own / 'macos-release.yml' if (own / 'macos-release.yml').is_file() else repo / '.github/workflows/macos-release.yml'
    copy(mac_workflow, destination / '.github/workflows/macos-release.yml')
    copy(own / 'README.md', destination / 'README.md')
    copy(own / 'LICENSE', destination / 'LICENSE')
    project = (own / 'pyproject.toml').read_text().replace('package-dir = {apply_desk = "."}', 'package-dir = {apply_desk = "apply_desk"}')
    (destination / 'pyproject.toml').write_text(project)
    for relative in ['web/index.html', 'web/app.js', 'web/style.css', 'examples/profile.json', 'examples/club-jobs.csv']:
        copy(own / relative, destination / 'apply_desk' / relative)
    for relative in ENGINE:
        copy((repo / 'internship_applier' / relative if (repo / 'internship_applier').is_dir() else own / '_engine/internship_applier' / relative), destination / 'apply_desk/_engine/internship_applier' / relative)
    for relative, text in MEMBER_ADAPTERS.items():
        target = destination / 'apply_desk/_engine/internship_applier' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('"""Member-only adapter; personal capabilities intentionally absent."""\n' + text)
        manifest.append({'source': 'apply_desk.release:member-adapter/' + relative,
                         'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    # Retain compatibility field names, but remove owner-specific historical comments.
    import io
    import tokenize
    host = destination / 'apply_desk/_engine/internship_applier/extension/host.py'
    tokens = tokenize.generate_tokens(io.StringIO(host.read_text()).readline)
    sanitized = [token._replace(string='') if token.type == tokenize.COMMENT and 'rahil' in token.string.casefold() else token
                 for token in tokens]
    text = '\n'.join(line.rstrip() for line in tokenize.untokenize(sanitized).splitlines()) + '\n'
    # Personal grants are absent even for direct use of the bundled low-level Host.
    import re
    text = re.sub(r"('data_consent'|'truth_attestation'):\s*not member_mode", r"\1: False", text)
    host.write_text(text)
    for relative in BROWSER:
        copy((repo / 'internship_applier/extension/browser' / relative if (repo / 'internship_applier').is_dir() else own / 'browser' / relative), destination / 'apply_desk/browser' / relative)
    browser = destination / 'apply_desk/browser'
    for path in browser.glob('*.js'):
        path.write_text('\n'.join(line for line in path.read_text().splitlines()
                                  if not (line.lstrip().startswith('//') and 'rahil' in line.casefold())) + '\n')
    configuration = json.loads((browser / 'manifest.json').read_text())
    configuration.update(name='Apply Desk', version='0.2.0', description='Prepare applications from your private Apply Desk workspace.',
                         key=(own / 'extension-key.txt').read_text().strip())
    (browser / 'manifest.json').write_text(json.dumps(configuration, indent=2))
    worker = browser / 'worker-core.js'
    worker.write_text(worker.read_text().replace('com.orbit.applier', 'com.applydesk.host'))
    for name in ('popup.html', 'review.html'):
        path = browser / name
        path.write_text(path.read_text().replace('Orbit ·', 'Apply Desk ·').replace('>Orbit<', '>Apply Desk<'))
    with (browser / 'review.css').open('a') as output:
        output.write('\n/* Answers are confirmed in the member desk, never through legacy intake. */\n#fact-panel,#advice-panel{display:none!important}\n')
    (destination / 'SOURCE_MANIFEST.json').write_text(json.dumps(manifest, indent=2))
    (destination / 'AGENTS.md').write_text('''# Apply Desk

Use fictional data for verification. Keep profiles, PDFs, credentials and browser sessions out of Git. Preserve exact packet identity and interrupted-action journals. Confirmed facts, resume source text, model drafts and member approval are separate. The connector cannot confirm or submit. Mac releases are Apple Silicon only and must pass native minimum-OS/signature checks. Read README and CONTRIBUTING before changes; run the documented behavior checks. Never test by sending a live application.
''')
    (destination / '.gitignore').write_text('**/__pycache__/\n**/build/\n**/*.egg-info/\n.venv/\n.build-venv/\ndist/\nruntime/\nmember/\nexports/\n*.pdf\n*.sqlite*\n.mcp.json\n.codex/config.toml\nnative-config.json\n.DS_Store\n')
    for name in ('test_apply_desk_workspace.py', 'test_apply_desk_mcp.py', 'test_apply_desk_web.py',
                 'frozen_mac_smoke.py', 'test_apply_desk_club_browser.py', 'test_apply_desk_engine_browser.py', 'test_apply_desk_updates.py', 'test_apply_desk_native.py', 'test_apply_desk_setup.py'):
        source = repo / 'tests' / name
        if source.exists():
            copy(source, destination / 'tests' / name)
    outputs = {str(path.relative_to(destination)): hashlib.sha256(path.read_bytes()).hexdigest() for path in destination.rglob('*') if path.is_file() and path.name != 'SOURCE_MANIFEST.json'}
    (destination / 'SOURCE_INPUTS.json').write_text(json.dumps(manifest, indent=2))
    (destination / 'SOURCE_FILES.json').write_text(json.dumps(outputs, indent=2))
    (destination / 'SOURCE_MANIFEST.json').write_text(json.dumps({'inputs': 'SOURCE_INPUTS.json', 'files': 'SOURCE_FILES.json'}, indent=2))
    return destination
