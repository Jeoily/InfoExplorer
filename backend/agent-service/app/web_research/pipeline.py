"""Injectable, bounded web research coordinator (not connected to live routes).

Adapters own network safety and real transport deadlines. Tests inject offline
tools. Planning is an input here; a future model planner must share this budget.
"""
from dataclasses import asdict, dataclass, field
import hashlib
import re
from uuid import UUID, uuid4
from typing import Callable

from app.web_research.budget import BudgetExceeded, ExecutionBudget, Usage
from app.web_research.candidates import Candidate, SearchBatch, bounded_text, utf16_length
from app.web_research.selection import Document, Passage, SourceMetadata, select_passages
from app.web_research.identity import EvidenceRegistry
from app.web_research.observation import emit
from app.web_research.url_policy import UrlRejected, validate_candidate_url

_ERRORS = frozenset({"SEARCH_TIMEOUT", "SEARCH_UNAVAILABLE", "SEARCH_RATE_LIMITED", "SEARCH_CONFIG_ERROR",
                     "SEARCH_INVALID_RESPONSE", "CONTENT_TIMEOUT", "CONTENT_UNAVAILABLE",
                     "CONTENT_UNSUPPORTED", "CONTENT_DISALLOWED", "CONTENT_INVALID_RESPONSE",
                     "SOURCE_URL_REJECTED", "SOURCE_ADDRESS_REJECTED", "MODEL_TIMEOUT",
                     "MODEL_UNAVAILABLE", "MODEL_INVALID_RESPONSE", "MODEL_RATE_LIMITED"})
_ERRORS = _ERRORS | frozenset({"CONTENT_EMPTY", "CONTENT_TOO_LARGE", "CONTENT_REDIRECT_REJECTED",
    "CONTENT_ROBOTS_UNSUPPORTED", "CONTENT_ROBOTS_UNAVAILABLE", "CONTENT_UNSUPPORTED_ENCODING",
    "CONTENT_REQUEST_LIMIT", "CONTENT_EXTRACTOR_NOT_INSTALLED", "CONTENT_EXTRACTION_FAILED"})
_ERRORS = _ERRORS | frozenset({"MODEL_AUTH_ERROR", "MODEL_CONFIG_ERROR", "MODEL_INPUT_TOO_LARGE", "MODEL_BUSY"})


class ToolFailure(Exception):
    def __init__(self, code: str):
        if code not in _ERRORS:
            raise ValueError("Unknown tool error code")
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Plan:
    questions: dict[str, str]
    queries: tuple[str, ...]
    evidence_needs: dict[str, str] = field(default_factory=dict)
    retrieval_terms: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class CoverageItem:
    question_id: str
    state: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class Review:
    coverage: tuple[CoverageItem, ...]
    extra_queries: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewSnapshot:
    round: int
    evidence: tuple[Passage, ...]
    decision: Review


@dataclass(frozen=True)
class Claim:
    text: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class GeneratedReport:
    claims: tuple[Claim, ...]
    limitations: tuple[str, ...] = ()


@dataclass
class QueryAttempt:
    query: str
    round: int
    status: str = "PENDING"
    source_ids: list[str] = field(default_factory=list)
    warnings: tuple[str, ...] = ()
    error_code: str | None = None


@dataclass
class SourceAttempt:
    candidate: Candidate
    status: str = "DISCOVERED"
    error_code: str | None = None
    metadata: SourceMetadata | None = None


@dataclass(frozen=True)
class Outcome:
    status: str
    completion_reason: str
    coverage: str
    answer: str | None
    evidence: tuple[Passage, ...]
    queries: tuple[QueryAttempt, ...]
    sources: tuple[SourceAttempt, ...]
    usage: Usage
    # Review refers to the evidence set at review time; after supplementation it
    # is intentionally not exposed as an assessment of the final evidence set.
    review_applied: bool
    run_id: str
    review_snapshot: ReviewSnapshot | None


SearchTool = Callable[[str, float], SearchBatch]
ContentTool = Callable[[Candidate, float], Document]
ReviewTool = Callable[[dict[str, str], tuple[Passage, ...], float], Review]
ReportTool = Callable[[dict[str, str], tuple[Passage, ...], float], GeneratedReport]


def _normalize_queries(queries, limit: int, text_limit: int = 200) -> tuple[str, ...]:
    if not isinstance(queries, tuple) or not 1 <= len(queries) <= limit:
        raise ValueError("Invalid query count")
    result = tuple(bounded_text(query, text_limit) for query in queries)
    if len({query.casefold() for query in result}) != len(result):
        raise ValueError("Duplicate queries")
    return result


def _validate_review(review: Review, questions: dict[str, str], evidence: tuple[Passage, ...]):
    if (not isinstance(review, Review) or not isinstance(review.coverage, tuple)
            or len(review.coverage) != len(questions)):
        raise ToolFailure("MODEL_INVALID_RESPONSE")
    ids = {item.evidence_id for item in evidence}
    seen = set()
    for item in review.coverage:
        if (not isinstance(item, CoverageItem) or not isinstance(item.question_id, str)
                or item.question_id not in questions or item.question_id in seen
                or not isinstance(item.state, str) or item.state not in {"covered", "partial", "missing"}
                or not isinstance(item.evidence_ids, tuple)
                or any(not isinstance(key, str) for key in item.evidence_ids)
                or len(item.evidence_ids) != len(set(item.evidence_ids))
                or not set(item.evidence_ids) <= ids
                or (item.state in {"covered", "partial"} and not item.evidence_ids)):
            raise ToolFailure("MODEL_INVALID_RESPONSE")
        seen.add(item.question_id)
    if review.extra_queries:
        try:
            _normalize_queries(review.extra_queries, 2)
        except ValueError:
            raise ToolFailure("MODEL_INVALID_RESPONSE") from None
    elif not isinstance(review.extra_queries, tuple):
        raise ToolFailure("MODEL_INVALID_RESPONSE")


def _render(report: GeneratedReport, evidence: tuple[Passage, ...]) -> str:
    if (not isinstance(report, GeneratedReport) or not isinstance(report.claims, tuple)
            or not isinstance(report.limitations, tuple) or len(report.claims) > 12
            or len(report.limitations) > 8 or (not report.claims and not report.limitations)):
        raise ToolFailure("MODEL_INVALID_RESPONSE")
    ids = {item.evidence_id for item in evidence}
    lines = []
    try:
        for claim in report.claims:
            if not isinstance(claim, Claim) or not isinstance(claim.evidence_ids, tuple):
                raise ValueError()
            text = bounded_text(claim.text, 1000)
            if (not claim.evidence_ids or len(claim.evidence_ids) > 8
                    or not set(claim.evidence_ids) <= ids or len(set(claim.evidence_ids)) != len(claim.evidence_ids)
                    or re.search(r"\[E\d+\]", text)):
                raise ValueError()
            lines.append(text + " " + "".join(f"[{key}]" for key in claim.evidence_ids))
        for limitation in report.limitations:
            text = bounded_text(limitation, 500)
            if re.search(r"\[E\d+\]", text):
                raise ValueError()
            lines.append("限制：" + text)
        answer = "\n\n".join(lines)
        if utf16_length(answer) > 16000:
            raise ValueError()
        return answer
    except (ValueError, TypeError, AttributeError):
        raise ToolFailure("MODEL_INVALID_RESPONSE") from None


def execute(plan: Plan, search: SearchTool, read: ContentTool, *,
            review: ReviewTool | None = None, generate: ReportTool | None = None,
            budget: ExecutionBudget | None = None, run_id: str | None = None, observer=None,
            per_source: int = 2) -> Outcome:
    if type(per_source) is not int or not 1 <= per_source <= 4:
        raise ValueError('Invalid per-source limit')
    run_id = str(UUID(run_id)) if run_id is not None else str(uuid4())
    registry = EvidenceRegistry(run_id)
    if (not isinstance(plan, Plan) or not isinstance(plan.questions, dict)
            or not 1 <= len(plan.questions) <= 8):
        raise ValueError("Invalid plan")
    questions = {bounded_text(key, 64): bounded_text(text, 4000)
                 for key, text in plan.questions.items()}
    if len(questions) != len(plan.questions):
        raise ValueError("Duplicate question identifiers")
    if not isinstance(plan.evidence_needs, dict) or not set(plan.evidence_needs) <= set(questions):
        raise ValueError("Invalid evidence needs")
    if not isinstance(plan.retrieval_terms, dict) or not set(plan.retrieval_terms) <= set(questions):
        raise ValueError("Invalid retrieval terms")
    for terms in plan.retrieval_terms.values():
        if not isinstance(terms, tuple) or len(terms)>12:
            raise ValueError("Invalid retrieval terms")
        for term in terms:
            bounded_text(term,80)
    selection_questions = {
        key: bounded_text(text + ' ' + bounded_text(plan.evidence_needs.get(key, ''), 300, allow_empty=True)
                          + ' ' + ' '.join(plan.retrieval_terms.get(key, ())), 4000)
        for key, text in questions.items()
    }
    # A direct fallback may contain the original 4000-unit question. A future
    # model planner must apply its own stricter generated-query limit.
    initial_queries = _normalize_queries(plan.queries, 3, 4000)
    budget = budget or ExecutionBudget()
    attempts: list[QueryAttempt] = []
    sources: dict[str, SourceAttempt] = {}
    documents: list[Document] = []
    evidence: tuple[Passage, ...] = ()
    seen_queries: set[str] = set()
    coverage, reviewed = "unknown", False
    snapshot = None

    def select():
        selected = registry.bind(select_passages(documents, selection_questions, per_source=per_source)) if documents else ()
        if observer is not None:
            emit(observer, 'selection', {'questions': selection_questions,
                'documents': [asdict(d) for d in documents], 'evidence': [asdict(e) for e in selected],
                'perSource': per_source})
        return selected

    def finish(status: str, reason: str, answer: str | None = None) -> Outcome:
        # Keep already read material even if the deadline interrupts a later stage.
        kept = select()
        for source in sources.values():
            if source.status == "DISCOVERED":
                source.status = "SKIPPED"
                source.error_code = "READ_LIMIT" if reason in {"COMPLETED", "NO_USABLE_EVIDENCE", "CONTENT_UNAVAILABLE"} else reason
        return Outcome(status, reason, coverage, answer, kept, tuple(attempts),
                       tuple(sources.values()), budget.snapshot(), reviewed, run_id, snapshot)

    def collect(queries: tuple[str, ...], round_number: int, read_cap: int):
        batches = []
        for query in queries:
            budget.checkpoint()
            normalized = bounded_text(query, 4000)
            if normalized.casefold() in seen_queries:
                continue
            seen_queries.add(normalized.casefold())
            attempt = QueryAttempt(normalized, round_number)
            attempts.append(attempt)
            try:
                batch = search(normalized, budget.reserve("search"))
                budget.checkpoint()
                if (not isinstance(batch, SearchBatch) or not isinstance(batch.candidates, tuple)
                        or not isinstance(batch.warnings, tuple) or len(batch.candidates) > 5):
                    raise ToolFailure("SEARCH_INVALID_RESPONSE")
                if any(warning != "SEARCH_ENGINES_PARTIALLY_UNAVAILABLE" for warning in batch.warnings):
                    raise ToolFailure("SEARCH_INVALID_RESPONSE")
                if not batch.candidates and batch.warnings:
                    raise ToolFailure("SEARCH_UNAVAILABLE")
                try:
                    for candidate in batch.candidates:
                        url = validate_candidate_url(candidate.requested_url)
                        sid = "S" + hashlib.sha256(url.canonical_url.encode("utf-8")).hexdigest()
                        if (candidate.source_id != sid or candidate.canonical_url != url.canonical_url
                                or candidate.host != url.host):
                            raise ValueError()
                        bounded_text(candidate.title, 512)
                except (UrlRejected, ValueError, AttributeError, TypeError):
                    raise ToolFailure("SEARCH_INVALID_RESPONSE") from None
                attempt.status = "SUCCEEDED"
                attempt.warnings = batch.warnings
                attempt.source_ids = [candidate.source_id for candidate in batch.candidates]
                for candidate in batch.candidates:
                    old = sources.get(candidate.source_id)
                    if old is not None and old.candidate.canonical_url != candidate.canonical_url:
                        raise ToolFailure("SEARCH_INVALID_RESPONSE")
                    sources.setdefault(candidate.source_id, SourceAttempt(candidate))
                batches.append(batch.candidates)
            except ToolFailure as error:
                attempt.status, attempt.error_code = "FAILED", error.code
                batches.append(())
        consumed = 0
        # Interleave queries so one query cannot monopolize the reading budget.
        for rank in range(5):
            for batch in batches:
                if rank >= len(batch) or consumed >= read_cap:
                    continue
                candidate = batch[rank]
                source = sources[candidate.source_id]
                if source.status != "DISCOVERED":
                    continue
                try:
                    timeout = budget.reserve("document")
                    consumed += 1
                    source.status = "READING"
                    document = read(candidate, timeout)
                    budget.checkpoint()
                    if (not isinstance(document, Document) or document.source_id != candidate.source_id
                            or document.host != candidate.host or not isinstance(document.paragraphs, tuple)):
                        raise ToolFailure("CONTENT_INVALID_RESPONSE")
                    try:
                        select_passages([document], questions)  # size/type policy before retention
                    except (ValueError, TypeError, UnicodeError):
                        raise ToolFailure("CONTENT_INVALID_RESPONSE") from None
                    documents.append(document)
                    source.metadata = document.metadata
                    source.status = "READ"
                except ToolFailure as error:
                    source.status, source.error_code = "FAILED", error.code

    try:
        collect(initial_queries, 0, 6)
        if not any(attempt.status == "SUCCEEDED" for attempt in attempts):
            return finish("FAILED", "SEARCH_UNAVAILABLE")
        evidence = select()
        if review is not None:
            decision = review(dict(questions), evidence, budget.reserve("model"))
            _validate_review(decision, questions, evidence)
            snapshot = ReviewSnapshot(0, evidence, decision)
            reviewed = True
            budget.checkpoint()
            sufficient = all(item.state == "covered" for item in decision.coverage)
            coverage = "sufficient" if sufficient else "partial"
            if not sufficient and decision.extra_queries:
                collect(_normalize_queries(decision.extra_queries, 2), 1, 2)
                evidence = select()
                # No second model review: additional evidence does not prove all gaps closed.
                coverage = "partial"
        if not evidence:
            coverage = "partial"
            if sources and not documents and any(source.status == "FAILED" for source in sources.values()):
                return finish("FAILED", "CONTENT_UNAVAILABLE")
            return finish("SUCCEEDED", "NO_USABLE_EVIDENCE", "本次未获得可用正文证据，不代表相关资料不存在。")
        if generate is None:
            answer = "公开资料摘录（未经模型分析或事实核验）：\n\n" + "\n\n".join(
                f"[{item.evidence_id}] {item.excerpt}" for item in evidence)
        else:
            report = generate(dict(questions), evidence, budget.reserve("model"))
            budget.checkpoint()
            answer = _render(report, evidence)
            if not report.claims:
                coverage = "partial"
        budget.checkpoint()
        return finish("SUCCEEDED", "COMPLETED", answer)
    except BudgetExceeded as error:
        for attempt in attempts:
            if attempt.status == "PENDING":
                attempt.status, attempt.error_code = "FAILED", error.code
        for source in sources.values():
            if source.status == "READING":
                source.status, source.error_code = "FAILED", error.code
        return finish("FAILED", error.code)
    except ToolFailure as error:
        return finish("FAILED", error.code)
