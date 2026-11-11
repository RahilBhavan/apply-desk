"""Member-only adapter; personal capabilities intentionally absent."""
def overlay(folder, role, state):
    return []

def execute(*args, **kwargs):
    raise ValueError('Confirm answers in Apply Desk')
