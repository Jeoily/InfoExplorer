"""Deterministic passage selection for already extracted public text.

Scores express lexical relevance, never credibility or factual correctness.
This module cannot turn search snippets into documents and has no I/O.
"""
from dataclasses import dataclass
import hashlib
import re
import unicodedata

from app.web_research.candidates import bounded_text, utf16_length

_STOPWORDS = frozenset('a an the and or of to in on at for from by with as is are was were be been being '
    'it its this that these those what which who how when where why do does did can could should would '
    'will may might have has had their them they you your we our explain describe tell please'.split())


@dataclass(frozen=True)
class SourceMetadata:
    requested_url: str
    resolved_url: str
    resolved_host: str
    retrieved_at: str
    content_type: str
    http_requests: int
    extractor: str
    published_text: str | None
    published_basis: str
    truncated: bool
    extracted_text_hash: str
    normalization_version: str = "paragraph-json-v1"


@dataclass(frozen=True)
class Document:
    source_id: str
    host: str
    title: str
    paragraphs: tuple[str, ...]
    metadata: SourceMetadata | None = None


@dataclass(frozen=True)
class Passage:
    evidence_id: str
    source_id: str
    paragraph_index: int
    offset_utf16: int
    excerpt: str
    content_hash: str
    matched_question_ids: tuple[str, ...]
    relevance: float
    truncated: bool
    evidence_key: str = ""


def _terms(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    terms = set(re.findall(r"[a-z0-9]+", normalized)) - _STOPWORDS
    for block in re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]+", normalized):
        if len(block) == 1:
            terms.add(block)
        else:
            terms.update(block[i:i + 2] for i in range(len(block) - 1))
    return terms


def _clip(text: str, limit: int) -> tuple[str, bool]:
    raw = text.encode("utf-16-le")
    return raw[:limit * 2].decode("utf-16-le", errors="ignore"), len(raw) > limit * 2


def _coverage(values: set[str], terms: set[str]) -> float:
    if not values:
        return 0.0
    scores = [len(values & terms) / len(values)]
    # Translated aliases are alternatives, not extra words an English passage
    # must match in Chinese (or vice versa). Require two distinct matches before
    # a language-specific group can override the overall score.
    latin = {v for v in values if v.isascii()}
    for group in (latin, values - latin):
        overlap = group & terms
        if len(group)>=2 and len(overlap)>=2:
            scores.append(len(overlap)/len(group))
    return max(scores)


def _subject_terms(text: str) -> set[str]:
    # Remove question/section framing, not domain names. Only the actual
    # question before '?' participates; generated evidence-needs are auxiliary.
    text = re.split(r'[?？]', text, maxsplit=1)[0]
    text = re.sub(r'通常|负责哪些工作|做什么|是什么|什么是|的角色|的作用|的职责|请解释|分别', ' ', text)
    return _terms(text)


def _definition_focus(excerpt: str, question: str) -> str | None:
    """Reward the requested API subject, not an incidental mention in a method.

    Only extractor-preserved class/exception declarations qualify. This is a
    relevance hint for definition questions, never a source trust signal.
    """
    if not re.search(r"\bwhat\s+(?:is|are)\b|\bdefine\b|是什么|什么是|定义", question, re.I):
        return None
    # Use the last structural separator: an earlier heading can itself contain
    # an em dash. Ignore declaration arguments and mentions in the body.
    context, separator, _ = excerpt.rpartition(" — ")
    if not separator:
        return None
    subject = context.rsplit(" / ", 1)[-1]
    match = re.match(r"(?:class|exception)\s+([\w.]+)\s*\(", subject)
    if not match:
        return None
    name = match.group(1).rsplit(".", 1)[-1].casefold()
    return name if name in _terms(question) else None


def _windows(text: str, limit: int):
    """Inspect the entire bounded paragraph, not just its introductory prefix."""
    start = 0
    while start < len(text):
        excerpt, has_more = _clip(text[start:], limit)
        if excerpt:
            yield utf16_length(text[:start]), excerpt, start > 0 or has_more
        if not has_more:
            break
        # A small overlap keeps a phrase crossing a boundary searchable. Advance
        # one codepoint when the limit cannot hold an astral character.
        start += max(1, len(excerpt) - min(64, len(excerpt) // 4))


def select_passages(documents: list[Document], questions: dict[str, str], *,
                    max_evidence: int = 8, per_source: int = 2,
                    passage_limit: int = 1600, total_limit: int = 12800) -> tuple[Passage, ...]:
    """Greedy subquestion coverage with definition-subject relevance hints.

    Indices refer to extracted paragraphs, not original HTML or DOM offsets.
    Empty/no lexical match yields no evidence rather than unrelated padding.
    """
    if (len(documents) > 8 or len(questions) > 8
            or any(type(n) is not int or n <= 0 for n in
                   (max_evidence, per_source, passage_limit, total_limit))
            or max_evidence > 8 or per_source > 4 or passage_limit > 1600 or total_limit > 12800):
        raise ValueError("Invalid selection limits")
    if not documents or not questions:
        return ()
    question_texts = {bounded_text(key, 64): bounded_text(value, 4000)
                      for key, value in questions.items()}
    question_terms = {key: _terms(value) for key, value in question_texts.items()}
    if len(question_terms) != len(questions):
        raise ValueError("Duplicate question identifiers")
    pool = []
    source_ids = set()
    for doc in documents:
        sid, host = bounded_text(doc.source_id, 100), bounded_text(doc.host, 253)
        if sid in source_ids or len(doc.paragraphs) > 1000:
            raise ValueError("Duplicate source or excessive paragraphs")
        source_ids.add(sid)
        title_terms = _terms(bounded_text(doc.title, 512))
        document_size = 0
        for index, paragraph in enumerate(doc.paragraphs):
            text = bounded_text(paragraph, 30000, allow_empty=True)
            document_size += utf16_length(text)
            if document_size > 30000:
                raise ValueError("Extracted document exceeds limit")
            if not text:
                continue
            for offset, excerpt, truncated in _windows(text, passage_limit):
                context, separator, body = excerpt.partition(' — ')
                # Ancestor/page headings repeat for every section and can make
                # unrelated advice appear to cover every requested subject.
                nearest = context.rsplit(' / ', 1)[-1]
                terms = _terms(nearest + ' ' + body if separator else excerpt)
                matches = tuple(key for key, values in question_terms.items() if values & terms)
                if not matches:
                    continue
                score = max(_coverage(question_terms[key], terms) for key in matches)
                # A few generic words in a long question are not useful evidence.
                # This is a lexical floor, not a confidence/credibility score.
                if score < .08:
                    continue
                score += 0.1 * max((len(values & title_terms) / len(values)
                                    for values in question_terms.values() if values), default=0.0)
                digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
                strengths = {key: _coverage(values, terms)
                             for key, values in question_terms.items() if values}
                # Structural headings help distinguish a focused section from
                # a long aside that happens to mention several query terms.
                heading, separator, _ = excerpt.partition(' — ')
                if separator:
                    heading_terms = _terms(heading.rsplit(' / ', 1)[-1])
                    for key, values in question_terms.items():
                        if values:
                            strengths[(key, 'heading')] = len(values & heading_terms) / len(values)
                    if ' / ' in heading:
                        subject_terms = _subject_terms(heading.rsplit(' / ', 1)[-1])
                        for key, question in question_texts.items():
                            overlap = subject_terms & _subject_terms(question)
                            if subject_terms and len(overlap) / len(subject_terms) >= .5:
                                strengths[(key, 'subject_heading', tuple(sorted(subject_terms)))] = 2 * len(overlap) / len(subject_terms)
                # Track each requested subject separately, including when the
                # direct fallback keeps a compound question in a single Q1.
                for key in question_terms:
                    subject = _definition_focus(excerpt, question_texts[key])
                    if subject:
                        strengths[(key, subject)] = 2.0
                pool.append((sid, host, index, excerpt, digest, matches, score, truncated, offset, strengths))
    selected = []
    counts, hosts = {}, {}
    covered, source_coverage, hashes = {}, {}, set()
    used = 0
    while pool and len(selected) < max_evidence:
        eligible = [item for item in pool if counts.get(item[0], 0) < per_source
                    and item[4] not in hashes and used + utf16_length(item[3]) <= total_limit]
        if not eligible:
            break
        # Stable input ordering breaks exact ties, making offline results reproducible.
        # A single incidental word does not exhaust a subquestion's coverage.
        # Combine global and within-source gains: another source covering a
        # subject must not erase the value of this source's focused section.
        # Host diversity only breaks ties; neither gain measures source trust.
        best = max(eligible, key=lambda item: (sum(max(0, value-covered.get(key, 0)) for key,value in item[9].items())
                                              + sum(max(0, value-source_coverage.get(item[0], {}).get(key, 0))
                                                    for key, value in item[9].items()),
                                              sum(max(0, value-source_coverage.get(item[0], {}).get(key, 0))
                                                  for key, value in item[9].items()),
                                              item[6], -hosts.get(item[1], 0)))
        pool.remove(best)
        sid, host, index, excerpt, digest, matches, score, truncated, offset, strengths = best
        selected.append(Passage(f"E{len(selected) + 1}", sid, index, offset, excerpt, digest,
                                matches, round(score, 6), truncated))
        counts[sid] = counts.get(sid, 0) + 1
        hosts[host] = hosts.get(host, 0) + 1
        for key, value in strengths.items():
            covered[key] = max(covered.get(key, 0), value)
            local = source_coverage.setdefault(sid, {})
            local[key] = max(local.get(key, 0), value)
        hashes.add(digest)
        used += utf16_length(excerpt)
    return tuple(selected)
