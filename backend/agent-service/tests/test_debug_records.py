import json
import importlib
from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi import HTTPException
import debug_records
from app.web_research.recording import record_run
from test_research_session import Model, search, read


def test_browser_view_and_reviews_are_read_only(tmp_path):
    run_id=str(uuid4())
    record_run(tmp_path,'fixture','Public topic','en',search,read,Model(),run_id=run_id)
    before={str(f):f.read_bytes() for f in tmp_path.rglob('*.json')}
    result=debug_records.view(tmp_path,run_id)
    assert result['mode']=='fixture'
    assert result['researchStatus']=='SUCCEEDED'
    assert 'instructions' not in json.dumps(result)
    for action in ('session','select','report-check'):
        assert debug_records.review(tmp_path,run_id,action)['externalRequests']==0
    assert before=={str(f):f.read_bytes() for f in tmp_path.rglob('*.json')}


@pytest.mark.parametrize('identifier,status',[('../secret',400),(str(uuid4()),404)])
def test_invalid_or_missing_record(tmp_path,identifier,status):
    with pytest.raises(HTTPException) as error:
        debug_records.view(tmp_path,identifier)
    assert error.value.status_code==status


def test_corrupt_record_and_unknown_action_fail_closed(tmp_path):
    run_id=str(uuid4())
    record_run(tmp_path,'fixture','Public topic','en',search,read,Model(),run_id=run_id)
    for f in tmp_path.glob('*/000.json'):
        f.write_bytes(b'{}')
    for action in ('session','select','report-check','live'):
        with pytest.raises(HTTPException):
            debug_records.review(tmp_path,run_id,action)
    with pytest.raises(HTTPException) as error:
        debug_records.view(tmp_path,run_id)
    assert error.value.status_code==409


def test_fixed_report_generation_is_explicit_budgeted_and_preserves_source(tmp_path,monkeypatch):
    run_id=str(uuid4())
    records=tmp_path/'recordings'
    record_run(records,'fixture','Public topic','en',search,read,Model(),run_id=run_id)
    before={str(f):f.read_bytes() for f in records.rglob('*.json')}
    monkeypatch.setenv('DEBUG_MODE','live');monkeypatch.setenv('DEBUG_SESSION',str(tmp_path))
    (tmp_path/'budget.json').write_text('{"limit":1,"used":0}')
    import debug_agent
    module=importlib.reload(debug_agent)
    model=Model()
    monkeypatch.setattr(module.JsonCompletion,'from_env',lambda:model)
    result=module.report_generation(run_id)
    assert result['status']=='SUCCEEDED' and len(model.calls)==1
    assert model.calls[0][0]=='report'
    assert before=={str(f):f.read_bytes() for f in records.rglob('*.json')}
    assert len(list((tmp_path/'report-generations').glob('*.json')))==1
    with pytest.raises(HTTPException) as error: module.report_generation(run_id)
    assert error.value.status_code==429


def test_failed_generation_consumes_budget_without_storing_raw_text(tmp_path,monkeypatch):
    run_id=str(uuid4())
    record_run(tmp_path/'recordings','fixture','Public topic','en',search,read,Model(),run_id=run_id)
    monkeypatch.setenv('DEBUG_MODE','live');monkeypatch.setenv('DEBUG_SESSION',str(tmp_path))
    (tmp_path/'budget.json').write_text('{"limit":1,"used":0}')
    import debug_agent
    module=importlib.reload(debug_agent)
    monkeypatch.setattr(module.JsonCompletion,'from_env',lambda:Mock(return_value=b'REJECTED_RAW_SENTINEL'))
    assert module.report_generation(run_id)['status']=='FAILED'
    assert json.loads((tmp_path/'budget.json').read_text())['used']==1
    assert 'REJECTED_RAW_SENTINEL' not in ''.join(f.read_text() for f in (tmp_path/'report-generations').glob('*.json'))


def test_reselected_generation_uses_saved_documents_and_marks_stale_coverage(tmp_path):
    from app.web_research.recording import regenerate_report
    run_id=str(uuid4())
    record_run(tmp_path,'fixture','Public topic','en',search,read,Model(),run_id=run_id)
    path=next(p for p in tmp_path.iterdir() if p.is_dir())
    before={str(f):f.read_bytes() for f in path.rglob('*.json')}
    model=Model()
    result=regenerate_report(path,model,reselection=True)
    assert result['reselected'] and result['completionCalls']==1
    assert result['searchRequests']==result['readRequests']==0
    assert model.calls[0][1]['data']['finalCoverageNotRechecked'] is True
    assert before=={str(f):f.read_bytes() for f in path.rglob('*.json')}
