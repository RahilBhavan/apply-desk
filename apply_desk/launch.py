"""Open a local member desk from an installed package or the source archive."""
from pathlib import Path
import sys

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from apply_desk.web_server import run

if __name__ == '__main__':
    run(Path.home() / 'Library/Application Support/Apply Desk/member')
