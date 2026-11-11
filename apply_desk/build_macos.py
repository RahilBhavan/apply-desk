"""Build a self-contained app for Apple Silicon Macs (macOS 13+)."""
import argparse
import json
from pathlib import Path
import plistlib
import platform
import hashlib
import shutil
import subprocess
import sys


def build(output):
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise SystemExit('Build on an Apple Silicon Mac using an arm64 Python interpreter')
    source = Path(__file__).resolve().parent
    sys.path.insert(0, str(source.parent))
    from apply_desk.build_support import notices, validate_macos
    if not (source / '_engine').is_dir() or not (source / 'browser/manifest.json').is_file():
        raise SystemExit('Build from the complete standalone source release')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    for path in sorted(source.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix in {'.py', '.js', '.html', '.css'}:
            digest.update(path.relative_to(source).as_posix().encode()); digest.update(path.read_bytes())
    (source / 'build-id.txt').write_text(digest.hexdigest())
    notices(source / 'THIRD_PARTY_LICENSES.txt')
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
               '--name', 'ApplyDesk', '--target-arch', 'arm64', '--distpath', str(output / 'bin'), '--workpath', str(output / 'work'),
               '--specpath', str(output), '--paths', str(source.parent), '--paths', str(source / '_engine'),
               '--collect-data', 'mcp', '--copy-metadata', 'mcp', '--collect-all', 'certifi',
               '--add-data', str(source / 'web') + ':apply_desk/web',
               '--add-data', str(source / 'browser') + ':apply_desk/browser',
               '--add-data', str(source / '_engine') + ':apply_desk/_engine',
               '--add-data', str(source / 'LICENSE') + ':apply_desk',
               '--add-data', str(source / 'build-id.txt') + ':apply_desk',
               '--add-data', str(source / 'THIRD_PARTY_LICENSES.txt') + ':apply_desk',
               '--add-data', str(source / 'extension-key.txt') + ':apply_desk']
    for path in sorted((source / '_engine/internship_applier').rglob('*.py')):
        name = '.'.join(path.relative_to(source / '_engine').with_suffix('').parts)
        if name.endswith('.__init__'):
            name = name[:-9]
        command += ['--hidden-import', name]
    command.append(str(source / 'desktop_entry.py'))
    subprocess.run(command, check=True)
    app = output / 'Apply Desk.app'
    if app.exists():
        raise SystemExit('Choose new build output; an existing app is never overwritten')
    info = {'CFBundleName': 'Apply Desk', 'CFBundleDisplayName': 'Apply Desk',
            'CFBundleIdentifier': 'org.applydesk.app', 'CFBundleVersion': '0.2.0',
            'CFBundleShortVersionString': '0.2.0', 'LSMinimumSystemVersion': '13.0',
            'NSHighResolutionCapable': True}
    # Let PyInstaller classify framework code vs resources. A flat hand-built bundle
    # incorrectly treats dist-info directories as executable code during signing.
    spec = output / 'ApplyDesk.spec'
    with spec.open('a') as handle:
        handle.write("\napp = BUNDLE(coll, name='Apply Desk.app', bundle_identifier='org.applydesk.app', info_plist=" + repr(info) + ")\n")
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', str(output / 'bin'),
                    '--workpath', str(output / 'work'), str(spec)], check=True)
    subprocess.run(['/usr/bin/ditto', str(output / 'bin/Apply Desk.app'), str(app)], check=True)
    subprocess.run(['/usr/bin/lipo', str(app / 'Contents/MacOS/ApplyDesk'), '-verify_arch', 'arm64'], check=True)
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    validation = validate_macos(app)
    (output / 'build-validation.json').write_text(json.dumps(validation, indent=2))
    readme = output / 'READ ME FIRST.txt'
    readme.write_text('Apply Desk 0.2.0\n\nOpen Apply Desk.app. It opens your private desk in a browser.\n'
        'Confirm your profile, install Chrome support and follow the in-app steps. Connect T3 with your own provider account.\n'
        'Review each application and submit in the employer tab. No Python or Terminal setup is required.\n\n'
        'This community build is ad-hoc signed, not Apple notarized. If macOS blocks it, use System Settings > Privacy & Security > Open Anyway after verifying the release checksum.\n')
    image_root = output / 'image'
    image_root.mkdir()
    shutil.copytree(app, image_root / app.name, symlinks=True)
    shutil.copyfile(readme, image_root / readme.name)
    shutil.copyfile(source / 'THIRD_PARTY_LICENSES.txt', image_root / 'THIRD_PARTY_LICENSES.txt')
    (image_root / 'Applications').symlink_to('/Applications')
    image = output / 'Apply-Desk-0.2.0.dmg'
    subprocess.run(['/usr/bin/hdiutil', 'create', '-volname', 'Apply Desk', '-srcfolder', str(image_root),
                    '-format', 'UDZO', str(image)], check=True)
    return app, image


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps([str(path) for path in build(args.output)]))
