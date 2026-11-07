"""Explicit model-research API; v2 extraction remains independent."""
from dataclasses import asdict
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from app.web_research.api import WireModel, WebRequest, OutcomeWire, UsageWire, Code, Hash, _run_lock
from app.web_research.content import read_content
from app.web_research.model_completion import JsonCompletion
from app.model import ModelError
from app.web_research.pipeline import ToolFailure
from app.web_research.research_session import PlanOutput, ReviewOutput, ReportOutput, run_session
from app.web_research.searxng import SearxngSearch, SearxngSettings

router = APIRouter()


class EventWire(WireModel):
    stage: Literal['plan', 'review', 'report', 'verify']
    status: Literal['SUCCEEDED', 'FAILED']
    code: Code | None
    input_hash: Hash


class SessionWire(WireModel):
    version: Literal['web-model-session-v1', 'web-model-session-v2']
    run_id: str
    plan_mode: Literal['model', 'direct']
    plan_reason: Code | None
    plan: PlanOutput | None
    decision: ReviewOutput | None
    report: ReportOutput | None
    stop_reason: Code
    events: list[EventWire] = Field(max_length=4)
    usage: UsageWire
    outcome: OutcomeWire | None


class SessionResponse(WireModel):
    schema_version: Literal['web-research-v3'] = 'web-research-v3'
    mode: Literal['web-model'] = 'web-model'
    language: Literal['en', 'zh']
    session: SessionWire


class SessionRunner:
    def __init__(self, session_run=run_session, *, verify_report=False):
        self.session_run = session_run
        self.verify_report = verify_report

    def run(self, request):
        complete = JsonCompletion.from_env()
        search = SearxngSearch(SearxngSettings('http://127.0.0.1:8888',
            'zh-CN' if request.language == 'zh' else 'en-US'))
        return self.session_run(request.question, request.language, search.search, read_content,
                           complete, run_id=request.run_id, verify_report=self.verify_report)


def get_session_runner():
    return SessionRunner()


@router.post('/internal/v3/research/run', response_model=SessionResponse)
def research_session(request: WebRequest, runner=Depends(get_session_runner)):
    if os.environ.get('INFOEXPLORER_WEB_MODEL_ENABLED', 'false').lower() != 'true':
        raise HTTPException(503, detail={'code': 'WEB_MODEL_DISABLED'})
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(429, detail={'code': 'WEB_BUSY'})
    try:
        from app.web_research.execution_control import Execution, current
        execution = Execution(request, 'web-model')
        execution.begin()
        if execution.cached is not None:
            return SessionResponse.model_validate(execution.cached)
        token = current.set(execution)
        try:
            return _execute_session(request, runner, execution)
        finally:
            current.reset(token)
    finally:
        _run_lock.release()


def _execute_session(request, runner, execution):
    try:
        try:
            session = runner.run(request)
        except (ToolFailure, ModelError) as error:
            raise HTTPException(502, detail={'code': error.code}) from None
        response = SessionResponse(language=request.language,
            session=SessionWire.model_validate(asdict(session)))
        if response.session.run_id != request.run_id or (response.session.outcome and
                response.session.outcome.run_id != request.run_id):
            raise ValueError('Execution identity mismatch')
        if len(response.model_dump_json(by_alias=True).encode('utf-8')) > 512 * 1024:
            raise HTTPException(502, detail={'code': 'WEB_RESPONSE_TOO_LARGE'})
        execution.finish(response.model_dump(by_alias=True))
        return response
    except Exception:
        execution.finish()
        raise
