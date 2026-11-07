from types import SimpleNamespace
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi import HTTPException
from app.web_research.execution_control import Execution, current, cancel, status, recover, connection
from app.web_research.budget import ExecutionBudget, BudgetExceeded
from session_fixtures import FixtureRunner
from test_research_session import search, read


def request(parent=None,question='public topic'):
    return SimpleNamespace(run_id=str(uuid4()),resume_from=parent,question=question,language='en')


def test_cancel_before_start_and_after_start_are_durable():
    req=request(); cancel(req.run_id)
    with pytest.raises(HTTPException) as exc: Execution(req,'web-model').begin()
    assert exc.value.detail['code']=='EXECUTION_CANCELLED'
    req=request(); run=Execution(req,'web-model');run.begin()
    token=current.set(run)
    try:
        run.stage('plan'); cancel(req.run_id)
        with pytest.raises(BudgetExceeded,match='EXECUTION_CANCELLED'): ExecutionBudget().reserve('model')
        recover()
        assert status(req.run_id)['state']=='INTERRUPTED'
        assert status(req.run_id)['cancelRequested']
    finally: current.reset(token)


def test_duplicate_identity_returns_saved_result_or_refuses_reexecution():
    req=request(); run=Execution(req,'web-model');run.begin()
    with pytest.raises(HTTPException): Execution(req,'web-model').begin()
    run.finish({'safe':'result'})
    replay=Execution(req,'web-model');replay.begin();assert replay.cached=={'safe':'result'}
    req.question='different'
    with pytest.raises(HTTPException): Execution(req,'web-model').begin()


def test_atomic_claim_with_concurrent_duplicates():
    req=request()
    # Schema creation before concurrent clients; BEGIN IMMEDIATE owns the claim.
    with connection(): pass
    def begin(_):
        try: Execution(req,'web').begin();return True
        except HTTPException:return False
    with ThreadPoolExecutor(4) as pool: assert sum(pool.map(begin,range(4)))==1


def test_only_matching_fresh_successful_retrieval_is_reused():
    req=request(); run=Execution(req,'web-model');run.begin()
    batch=run.tool('search',search,'public topic',10)
    run.tool('read',read,batch.candidates[0],10)
    run.finish()
    child=request(req.run_id); resumed=Execution(child,'web-model');resumed.begin()
    def forbidden(*_): raise AssertionError('external request')
    assert resumed.tool('search',forbidden,'public topic',10)==batch
    assert resumed.tool('read',forbidden,batch.candidates[0],10).paragraphs
    assert status(child.run_id)['reused']==2
    wrong=request(req.run_id,'another question')
    with pytest.raises(HTTPException):Execution(wrong,'web-model').begin()
    with connection() as db: db.execute('UPDATE retrieval SET created=0')
    expired=request(req.run_id); expired_run=Execution(expired,'web-model');expired_run.begin()
    with pytest.raises(AssertionError):expired_run.tool('search',forbidden,'public topic',10)


def test_resumed_session_preserves_sources_and_offline_recording(tmp_path):
    from app.web_research.recording import record_run,replay
    def recorded(*args,**kwargs):return record_run(tmp_path/'records','fixture',*args,**kwargs)
    req=request();first=Execution(req,'web-model');first.begin()
    token=current.set(first)
    try:result=FixtureRunner(session_run=recorded).run(req)
    finally:current.reset(token)
    first.finish()
    child=request(req.run_id);second=Execution(child,'web-model');second.begin()
    token=current.set(second)
    try:result2=FixtureRunner(session_run=recorded).run(child)
    finally:current.reset(token)
    assert result2.report==result.report
    assert status(child.run_id)['reused']>0
    for path in (tmp_path/'records').iterdir():
        assert replay(path)['externalRequests']==0
