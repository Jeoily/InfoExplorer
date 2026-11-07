"""Debug-only HTTP entry; never imported by the daily application.

Fixture mode exposes only v3 research with synthetic tools. Live mode is explicit
and reserves a session-wide attempt before any provider work, across restarts.
"""
import json
import os
from pathlib import Path
import sys
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from app.web_research.session_api import router, get_session_runner, SessionRunner
from app.web_research.recording import record_run, report_input, regenerate_report, write_file, encoded
from app.web_research.model_completion import JsonCompletion
from app.web_research.api import _run_lock
from app.web_research.research_session import run_session
import debug_records

app = FastAPI(title='InfoExplorer ISOLATED DEBUG')
app.include_router(router)
from app.web_research.execution_control import router as execution_router
app.include_router(execution_router)
lock = Lock()
mode = os.environ['DEBUG_MODE']
directory = Path(os.environ['DEBUG_SESSION'])


def recorded_session(*args, **kwargs):
    return record_run(directory/'recordings', mode, *args, **kwargs)


def reserve_attempt():
    with lock:
        path = directory / 'budget.json'
        budget = json.loads(path.read_text(encoding='utf-8'))
        if budget['used'] >= budget['limit']:
            raise HTTPException(429, detail={'code': 'DEBUG_BUDGET_EXHAUSTED'})
        budget['used'] += 1
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(budget), encoding='utf-8')
        tmp.replace(path)


class LimitedRunner:
    def run(self, request):
        # v3 also has a process lock. Single Python worker only.
        reserve_attempt()
        runner = recorded_session if os.environ.get('DEBUG_RECORD_PUBLIC')=='true' else run_session
        return SessionRunner(session_run=runner, verify_report=True).run(request)


if mode == 'fixture':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend/agent-service/tests'))
    from session_fixtures import FixtureRunner
    app.dependency_overrides[get_session_runner] = lambda: FixtureRunner(session_run=recorded_session)
elif mode == 'live':
    app.dependency_overrides[get_session_runner] = LimitedRunner
else:
    raise RuntimeError('INVALID_DEBUG_MODE')


@app.get('/health')
def health():
    return {'status': 'UP', 'mode': mode, 'session': directory.name}


@app.get('/__debug/records/{run_id}')
def record_view(run_id: str):
    return debug_records.view(directory/'recordings', run_id)


@app.get('/__debug/records/{run_id}/review/{action}')
def record_review(run_id: str, action: str):
    return debug_records.review(directory/'recordings', run_id, action)


@app.post('/__debug/records/{run_id}/report-generation')
def report_generation(run_id: str, reselection: bool = False):
    """Explicit REAL single completion. Never invoked by offline review buttons."""
    if mode != 'live':
        raise HTTPException(403, detail='LIVE_MODE_REQUIRED')
    path = debug_records.locate(directory/'recordings', run_id)
    try:
        report_input(path)
    except Exception:
        raise HTTPException(409, detail='NO_REPORT_INPUT') from None
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(429, detail='WEB_BUSY')
    try:
        complete = JsonCompletion.from_env()
        reserve_attempt()
        target = directory/'report-generations'
        target.mkdir(exist_ok=True)
        attempt_id = uuid4().hex
        file = target/(attempt_id+'.json')
        write_file(file, encoded({'status':'STARTED','parentRecordId':path.name,'attemptId':attempt_id}))
        try:
            result = regenerate_report(path, complete, reselection=reselection)
            result.update(status='SUCCEEDED', attemptId=attempt_id)
        except Exception as error:
            from app.web_research.research_session import OutputPolicyError
            from app.web_research.pipeline import ToolFailure
            from app.model import ModelError
            code = error.code if isinstance(error,(ToolFailure,ModelError)) else 'MODEL_INVALID_RESPONSE'
            result={'status':'FAILED','attemptId':attempt_id,'parentRecordId':path.name,'code':code,
                    'reason':error.reason if isinstance(error,OutputPolicyError) else 'generation_failed',
                    'completionCalls':1}
        write_file(file, encoded(result))
        return result
    finally:
        _run_lock.release()
