"""Only this adapter loads the selected legacy preparation engine."""
from pathlib import Path
import sys


def load():
    bundled = Path(__file__).parent / '_engine'
    if bundled.is_dir() and str(bundled) not in sys.path:
        sys.path.insert(0, str(bundled))
    from internship_applier.extension.host import Host, Rejected, read_exact, write_frame, MAX_FRAME
    return Host, Rejected, read_exact, write_frame, MAX_FRAME


def browser_source():
    bundled = Path(__file__).parent / 'browser'
    if bundled.is_dir():
        return bundled
    return Path(__file__).resolve().parent.parent / 'internship_applier/extension/browser'
