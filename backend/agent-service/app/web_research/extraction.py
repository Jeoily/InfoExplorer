"""Optional Trafilatura extraction of ALREADY downloaded HTML, in a child process.

No network downloader is provided here. Input byte/time limits are enforced;
there is not yet an OS-level memory sandbox. Used only by explicitly enabled web routes.
"""
from dataclasses import dataclass
import math
import multiprocessing
import sys
import time
import xml.etree.ElementTree as ET

from app.web_research.candidates import Candidate, bounded_text, utf16_length
from app.web_research.selection import Document


class ExtractionError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ExtractedPage:
    document: Document
    published_text: str | None
    truncated: bool
    extractor: str = "trafilatura-2.3.1-context-v2"


def context_blocks(raw: str) -> tuple[tuple[str, ...], str | None, str | None, bool]:
    """Preserve structural paragraphs and definition-list subjects, never line wraps.

    Heading/definition text is copied from the extracted document. It is context,
    not a generated factual summary. Each bounded block repeats its own subject.
    """
    root = ET.fromstring(raw)
    main = root.find('main')
    if main is None:
        return (), root.get('title'), root.get('date'), False
    groups = []
    headings = []
    def text(node):
        return ' '.join(''.join(node.itertext()).split())
    def walk(parent, definition=''):
        current = definition
        for node in parent:
            if node.tag == 'head':
                try:
                    level = int(node.get('rend', 'h2')[1:])
                except ValueError:
                    level = 2
                while headings and headings[-1][0] >= level:
                    headings.pop()
                headings.append((level, text(node)))
            elif node.tag == 'item' and node.get('rend', '').startswith('dt'):
                current = text(node)
            elif node.tag in {'p', 'quote', 'code', 'table'} or (node.tag == 'item' and not len(node)):
                body = text(node)
                if body:
                    context = ' / '.join([v for _, v in headings] + ([current] if current else []))
                    groups.append((context, body))
            else:
                walk(node, current)
    walk(main)
    blocks, pending, old_context = [], '', None
    truncated = False
    def flush():
        nonlocal pending
        if pending:
            prefix = old_context or ''
            # Keep the nearest subject when the heading path is unusually long.
            prefix = prefix.encode('utf-16-le')[-800:].decode('utf-16-le', errors='ignore')
            blocks.append((prefix + ' — ' if prefix else '') + pending)
            pending = ''
    for context, body in groups:
        if context != old_context:
            flush()
            old_context = context
        for word in body.split():
            if pending and utf16_length(pending + ' ' + word) > 1100:
                flush()
            # A pathological unbroken token is bounded without hiding truncation.
            if utf16_length(word) > 1100:
                word = word.encode('utf-16-le')[:2200].decode('utf-16-le', errors='ignore')
                truncated = True
            pending += (' ' if pending else '') + word
    flush()
    retained, size = [], 0
    for block in blocks:
        if size + utf16_length(block) > 30000 or len(retained) >= 1000:
            truncated = True
            break
        retained.append(block)
        size += utf16_length(block)
    return tuple(retained), root.get('title'), root.get('date'), truncated


def _no_network(event, args):
    if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo", "socket.sendto"}:
        raise RuntimeError("Extraction network disabled")


def _extract_worker(sender, html: bytes):
    try:
        sys.addaudithook(_no_network)
        from trafilatura import extract
        raw = extract(html, output_format="xml", with_metadata=True,
                      include_comments=False, include_tables=True,
                      include_links=False, include_images=False,
                      date_extraction_params={"extensive_search": False})
        if raw is None:
            sender.send(("CONTENT_EMPTY", None))
            return
        paragraphs, title, date, truncated = context_blocks(raw)
        if not paragraphs:
            sender.send(("CONTENT_EMPTY", None))
            return
        # Cap IPC output, not just the final caller-visible Document.
        sender.send((None, {"paragraphs": paragraphs, "title": title[:512] if isinstance(title, str) else None,
                            "date": date[:100] if isinstance(date, str) else None,
                            "truncated": truncated}))
    except ImportError:
        sender.send(("CONTENT_EXTRACTOR_NOT_INSTALLED", None))
    except Exception:
        sender.send(("CONTENT_EXTRACTION_FAILED", None))
    finally:
        sender.close()


def extract_html(candidate: Candidate, html: bytes, *, content_type: str = "text/html",
                 timeout: float = 10.0) -> ExtractedPage:
    """Extract local bytes; callers must have verified the download separately.

    The URL/title identity stays tied to the actual candidate. An HTML canonical
    link or author-controlled metadata cannot redirect or replace the source.
    """
    if (not isinstance(html, bytes) or not html or len(html) > 2 * 1024 * 1024
            or b"<!ENTITY" in html.upper()):
        raise ExtractionError("CONTENT_INVALID_RESPONSE")
    if not isinstance(content_type, str) or content_type.split(";", 1)[0].strip().lower() not in {
            "text/html", "application/xhtml+xml"}:
        raise ExtractionError("CONTENT_UNSUPPORTED")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 20:
        raise ValueError("Invalid extraction timeout")
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_extract_worker, args=(sender, html), daemon=True)
    deadline = time.monotonic() + timeout
    try:
        process.start()
        sender.close()
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not receiver.poll(remaining):
            raise ExtractionError("CONTENT_TIMEOUT")
        code, payload = receiver.recv()
        if time.monotonic() >= deadline:
            raise ExtractionError("CONTENT_TIMEOUT")
        if code is not None:
            raise ExtractionError(code)
        paragraphs = tuple(payload["paragraphs"])
        if not paragraphs:
            raise ExtractionError("CONTENT_EMPTY")
        # Newlines removed above may reduce the length; never exceed the shared budget.
        if sum(utf16_length(line) for line in paragraphs) > 30000:
            raise ExtractionError("CONTENT_INVALID_RESPONSE")
        title = payload["title"] or candidate.title
        try:
            title = bounded_text(title, 512)
        except ValueError:
            title = candidate.title
        return ExtractedPage(Document(candidate.source_id, candidate.host, title, paragraphs),
                             payload["date"], payload["truncated"])
    except (EOFError, OSError):
        raise ExtractionError("CONTENT_EXTRACTION_FAILED") from None
    finally:
        sender.close()
        receiver.close()
        if process.pid is not None:
            process.join(timeout=0.1)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join(timeout=2)
            process.close()
