"""Member-only adapter; personal capabilities intentionally absent."""
def enabled(root):
    return False

def read_ledger(*args):
    raise ValueError('Personal ledgers are unavailable')

def save_ledger(*args):
    raise ValueError('Personal ledgers are unavailable')
