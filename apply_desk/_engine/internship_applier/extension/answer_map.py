"""Member-only adapter; personal capabilities intentionally absent."""
class AnswerMap:
    def __init__(self, *args, **kwargs):
        raise ValueError('Personal answer maps are unavailable in member mode')
