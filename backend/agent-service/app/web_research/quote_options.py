"""Bounded exact evidence anchors; no model text, retrieval or fuzzy matching."""
import re
from app.web_research.candidates import bounded_text, utf16_length


def quote_options(excerpt):
    text = bounded_text(excerpt, 1600)
    result = []
    start = 0
    while start < len(text):
        chunk = text[start:].encode('utf-16-le')[:600].decode('utf-16-le', errors='ignore')
        if start + len(chunk) < len(text):
            boundaries = [m.end() for m in re.finditer(r'[。！？；]|[.!?;](?:\s|$)', chunk)]
            end = boundaries[-1] if boundaries and boundaries[-1] >= 40 else chunk.rfind(' ')
            if end >= 40:
                chunk = chunk[:end]
        quote = chunk.strip()
        if utf16_length(quote) >= 12:
            result.append({'quoteId':f'Q{len(result)+1}', 'quote':quote})
        start += len(chunk)
    return result
