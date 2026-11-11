"""Frozen app entry point: Finder UI, local MCP or Chrome native messaging."""
from pathlib import Path
import sys

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'native-host':
        from apply_desk.native_host import serve
        if len(sys.argv) != 5 or sys.argv[2] != '--config':
            return 2
        return serve(sys.argv[3], sys.argv[4])
    from apply_desk.__main__ import main as cli
    if len(sys.argv) == 1:
        if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
            from apply_desk.mac_actions import install_app
            installed = install_app()
            if installed['executable'] != sys.executable:
                import subprocess
                subprocess.Popen([installed['executable']], start_new_session=True)
                return 0
        return cli(['--workspace', str(Path.home() / 'Library/Application Support/Apply Desk/member'), 'serve'])
    return cli(sys.argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
