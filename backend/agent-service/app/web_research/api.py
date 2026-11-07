"""Opt-in web retrieval HTTP boundary. No model, database, or user-selected tools."""
from dataclasses import asdict
import os
from threading import Lock
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.web_research.budget import ExecutionBudget, Limits
from app.web_research.candidates import bounded_text
from app.web_research.content import read_content
from app.web_research.pipeline import Plan, execute
from app.web_research.searxng import SearxngSearch, SearxngSettings

router = APIRouter()
_run_lock = Lock()


class WireModel(BaseModel):
    model_config = ConfigDict(extra='forbid', alias_generator=to_camel, populate_by_name=True)


class WebRequest(WireModel):
    model_config = ConfigDict(extra='forbid', alias_generator=to_camel, populate_by_name=False, strict=True)
    run_id: str = Field(pattern=r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
    question: str
    language: Literal['en', 'zh'] = 'en'
    resume_from: str | None = Field(default=None, pattern=r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')

    @field_validator('question')
    @classmethod
    def question_limit(cls, value):
        return bounded_text(value, 4000)

    @field_validator('run_id', 'resume_from')
    @classmethod
    def canonical_id(cls, value):
        return str(UUID(value)) if value is not None else None


Code = Annotated[str, Field(pattern=r'^[A-Z][A-Z0-9_]{0,79}$')]
Hash = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
SourceId = Annotated[str, Field(pattern=r'^S[0-9a-f]{64}$')]
EvidenceId = Annotated[str, Field(pattern=r'^E([1-9]|1[0-6])$')]


class Metadata(WireModel):
    requested_url: str
    resolved_url: str
    resolved_host: str
    retrieved_at: str
    content_type: str
    http_requests: int = Field(ge=1, le=12)
    extractor: str
    published_text: str | None
    published_basis: Literal['extractor_unverified', 'unknown']
    truncated: bool
    extracted_text_hash: Hash
    normalization_version: Literal['paragraph-json-v1']


class CandidateWire(WireModel):
    source_id: SourceId
    requested_url: str
    canonical_url: str
    host: str
    title: str
    snippet: str
    rank: int = Field(ge=1, le=100)
    engines: list[str]
    published_text: str | None


class SourceWire(WireModel):
    candidate: CandidateWire
    status: Literal['READ', 'FAILED', 'SKIPPED']
    error_code: Code | None
    metadata: Metadata | None


class PassageWire(WireModel):
    evidence_id: EvidenceId
    source_id: SourceId
    paragraph_index: int = Field(ge=0, lt=1000)
    offset_utf16: int = Field(ge=0, le=30000)
    excerpt: str
    content_hash: Hash
    matched_question_ids: list[str]
    relevance: float = Field(ge=0, le=1.1)
    truncated: bool
    evidence_key: Hash


class QueryWire(WireModel):
    query: str
    round: Literal[0, 1]
    status: Literal['SUCCEEDED', 'FAILED']
    source_ids: list[SourceId] = Field(max_length=5)
    warnings: list[Literal['SEARCH_ENGINES_PARTIALLY_UNAVAILABLE']]
    error_code: Code | None


class CoverageWire(WireModel):
    question_id: str
    state: Literal['covered', 'partial', 'missing']
    evidence_ids: list[EvidenceId]


class ReviewWire(WireModel):
    coverage: list[CoverageWire] = Field(max_length=8)
    extra_queries: list[str] = Field(max_length=2)


class SnapshotWire(WireModel):
    round: Literal[0]
    evidence: list[PassageWire] = Field(max_length=8)
    decision: ReviewWire


class UsageWire(WireModel):
    searches: int = Field(ge=0, le=5)
    documents: int = Field(ge=0, le=8)
    model_calls: int = Field(ge=0, le=4)
    remaining_seconds: float = Field(ge=0, le=150)
    cancelled: bool


class OutcomeWire(WireModel):
    status: Literal['SUCCEEDED', 'FAILED']
    completion_reason: Code
    coverage: Literal['unknown', 'partial', 'sufficient']
    answer: str | None
    evidence: list[PassageWire] = Field(max_length=8)
    queries: list[QueryWire] = Field(max_length=5)
    sources: list[SourceWire] = Field(max_length=25)
    usage: UsageWire
    review_applied: bool
    run_id: str
    review_snapshot: SnapshotWire | None


class WebResponse(WireModel):
    schema_version: Literal['web-research-v2'] = 'web-research-v2'
    mode: Literal['web-extract'] = 'web-extract'
    language: Literal['en', 'zh']
    plan_mode: Literal['direct'] = 'direct'
    questions: dict[str, str]
    outcome: OutcomeWire


class WebRunner:
    def run(self, request: WebRequest):
        from app.web_research.execution_control import tool_call
        settings = SearxngSettings('http://127.0.0.1:8888',
                                  'zh-CN' if request.language == 'zh' else 'en-US')
        return execute(Plan({'Q1': request.question}, (request.question,)),
                       lambda q,t: tool_call('search',SearxngSearch(settings).search,q,t),
                       lambda c,t: tool_call('read',read_content,c,t),
                       budget=ExecutionBudget(Limits(model_calls=0)), run_id=request.run_id)


def get_web_runner():
    return WebRunner()


@router.post('/internal/v2/research/run', response_model=WebResponse)
def research_web(request: WebRequest, runner=Depends(get_web_runner)):
    if os.environ.get('INFOEXPLORER_WEB_ENABLED', 'false').lower() != 'true':
        raise HTTPException(status_code=503, detail={'code': 'WEB_DISABLED'})
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(status_code=429, detail={'code': 'WEB_BUSY'})
    try:
        from app.web_research.execution_control import Execution, current
        execution = Execution(request, 'web')
        execution.begin()
        if execution.cached is not None:
            return WebResponse.model_validate(execution.cached)
        token = current.set(execution)
        try:
            return _execute_web(request, runner, execution)
        finally:
            current.reset(token)
    finally:
        _run_lock.release()


def _execute_web(request, runner, execution):
    try:
        outcome = runner.run(request)
        response = WebResponse(language=request.language, questions={'Q1': request.question},
                               outcome=OutcomeWire.model_validate(asdict(outcome)))
        if response.outcome.run_id != request.run_id:
            raise ValueError('Execution identity mismatch')
        if len(response.model_dump_json(by_alias=True).encode('utf-8')) > 512 * 1024:
            raise HTTPException(status_code=502, detail={'code': 'WEB_RESPONSE_TOO_LARGE'})
        execution.finish(response.model_dump(by_alias=True))
        return response
    except Exception:
        execution.finish()
        raise
