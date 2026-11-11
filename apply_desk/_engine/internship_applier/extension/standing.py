"""Member-only adapter; personal capabilities intentionally absent."""
def fields(*args, **kwargs):
    raise ValueError('Member facts must come from the member workspace')
