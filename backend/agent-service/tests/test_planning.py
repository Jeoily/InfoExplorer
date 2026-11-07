import json
import pytest
from app.planning import QueryPlanner, parse_plan, retrieve
from app.model import ModelError, ModelSettings
from app.search import SearchError, WikipediaSearch
from test_api import base_url, post

SETTINGS=ModelSettings('https://models.example.org/v1','fixture','placeholder')

def response(data, **message):
    return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(data),**message}}]}).encode()

def test_planner_sends_question_only_and_records_metadata():
    def transport(settings, body):
        payload=json.loads(body)
        assert 'tools' not in payload and payload['stream'] is False
        assert json.loads(payload['messages'][1]['content']) == {'question':'比较前后端','language':'zh'}
        return response({'intent':'比较技能','queries':['前端开发','后端开发']})
    plan=QueryPlanner(SETTINGS,transport).plan('比较前后端','zh')
    assert plan.mode=='model' and plan.generation.promptVersion=='search-plan-v1'
    assert len(plan.queries)==2 and all(q.language=='zh' for q in plan.queries)

@pytest.mark.parametrize('queries',[[],['a']*4,['A','a'],['https://evil.example'],['a'*101],['x\n'],[1],['<script>']])
def test_invalid_plan_falls_back_without_partial_execution(queries):
    planner=QueryPlanner(SETTINGS,lambda *_:response({'intent':'topic','queries':queries}))
    plan=planner.plan('original','en')
    assert plan.mode=='direct' and plan.reason=='MODEL_INVALID_RESPONSE'
    assert [q.query for q in plan.queries]==['original']

def test_tool_call_and_extra_fields_rejected():
    for raw in [response({'intent':'x','queries':['x']},tool_calls=[{'name':'shell'}]),
                response({'intent':'x','queries':['x'],'url':'https://evil.example'})]:
        with pytest.raises(ModelError): parse_plan(raw,'en')

def test_timeout_falls_back_once():
    calls=[]
    def transport(*_):
        calls.append(1)
        raise ModelError('MODEL_TIMEOUT')
    plan=QueryPlanner(SETTINGS,transport).plan('original','en')
    assert plan.reason=='MODEL_TIMEOUT' and calls==[1]

def test_round_robin_dedup_and_query_provenance_with_partial_failure():
    planner=QueryPlanner(SETTINGS,lambda *_:response({'intent':'compare','queries':['a','b','c']}))
    class Provider:
        def search(self,q):
            if q=='c': raise SearchError('SEARCH_TIMEOUT')
            titles=['common',q+'1',q+'2',q+'3',q+'4']
            return WikipediaSearch().parse({'query':{'pages':[{'title':t,'extract':'public text'} for t in titles]}},q)
    report=retrieve('original question','en',Provider(),planner)
    assert len(report.evidence)==5
    assert [e.title for e in report.evidence]==['common','a1','b1','a2','b2']
    assert report.plan.queries[0].evidenceIds==['E1','E2','E4']
    assert report.plan.queries[1].evidenceIds==['E1','E3','E5']
    assert report.plan.queries[2].status=='FAILED'
    assert report.query=='original question'

def test_empty_is_success_but_all_network_failures_are_not():
    class Empty:
        def search(self,q):return WikipediaSearch().parse({'batchcomplete':True},q)
    report=retrieve('topic','en',Empty(),QueryPlanner())
    assert not report.evidence and report.plan.queries[0].status=='SUCCEEDED'
    class Failed:
        def search(self,q):raise SearchError('SEARCH_UNAVAILABLE')
    with pytest.raises(SearchError):retrieve('topic','en',Failed(),QueryPlanner())


def test_config_failure_is_visible_direct_http_fallback(monkeypatch,base_url):
    from app.main import app
    from app.search import get_search_provider
    monkeypatch.setenv('INFOEXPLORER_PLANNING_ENABLED','true')
    monkeypatch.setenv('INFOEXPLORER_MODEL_ENABLED','true')
    monkeypatch.setenv('MODEL_BASE_URL','invalid')
    class Provider:
        def search(self,q): return WikipediaSearch().parse({'batchcomplete':True},q)
    app.dependency_overrides[get_search_provider]=lambda:Provider()
    try:
        status,body=post(base_url,b'{"question":"topic"}','/internal/v1/research/run')
        assert status==200 and body['plan']['reason']=='MODEL_CONFIG_ERROR'
        assert body['plan']['queries'][0]['query']=='topic' and body['generation'] is None
    finally:
        app.dependency_overrides.clear()
