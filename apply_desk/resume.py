"""Locally extract source text; never turn a resume claim into a confirmed profile fact."""
from io import BytesIO


def extract(pdf):
    if b'%%EOF' not in pdf[-1024:]:
        return {'status': 'unreadable', 'text': ''}
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(pdf), strict=True)
        if reader.is_encrypted:
            return {'status': 'encrypted', 'text': ''}
        text = '\n\n'.join(page.extract_text() or '' for page in reader.pages[:10])[:50000].strip()
        return {'status': 'extracted' if text else 'no_text', 'text': text,
                'scope': 'First ten pages, up to 50,000 characters; user-provided source, not independently verified'}
    except Exception:
        # PDF parsers expose format-specific exception types. A parse failure leaves drafting evidence absent.
        return {'status': 'unreadable', 'text': ''}
