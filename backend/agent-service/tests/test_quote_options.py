import json
import pytest
from app.web_research.quote_options import quote_options
from app.web_research.research_session import run_session, validate_report, GroundedReportOutput, provider_payload
from app.web_research.recording import record_run, replay, check_report
from app.web_research.candidates import utf16_length
from test_research_session import Model, search, read


def test_citations_derived_once_from_multiple_quotes_in_one_evidence():
    text='First documented fact. ' * 12 + 'Second documented fact. ' * 12
    options=quote_options(text)
    assert len(options)>1
    draft=GroundedReportOutput.model_validate({'claims':[{
        'kind':'source_statement','text':'Two documented facts.',
        'supportingQuotes':[{'evidenceId':'E1','quoteId':options[0]['quoteId']},
                            {'evidenceId':'E1','quoteId':options[1]['quoteId']}]}],
        'limitations':['Public evidence only.']})
    assert draft.claims[0].evidenceIds==['E1']
    validate_report(draft,{'E1':text})
    assert len(draft.claims[0].supportingQuotes)==2


def test_explicit_incompatible_old_citation_list_is_not_silently_repaired():
    draft=GroundedReportOutput.model_validate({'claims':[{
        'kind':'source_statement','text':'Public fact.','evidenceIds':['E2'],
        'supportingQuotes':[{'evidenceId':'E1','quoteId':'Q1'}]}],
        'limitations':['Public evidence only.']})
    with pytest.raises(ValueError):
        validate_report(draft,{'E1':'A sufficiently long public fact.','E2':'Another sufficiently long fact.'})


@pytest.mark.parametrize('text',[
    'A public statement. Another independently readable public statement.',
    '公开资料说明网页与数据库之间的分工。'*60,
    'x'*1599,
    'A public sentence with an emoji 😀. '*30,
    '  Whitespace\n normalized public evidence. ',
])
def test_options_are_bounded_exact_and_deterministic(text):
    options=quote_options(text)
    assert options == quote_options(text)
    normalized=' '.join(text.split())
    assert options
    for item in options:
        assert 12 <= utf16_length(item['quote']) <= 300
        assert item['quote'] in normalized
    assert len({o['quoteId'] for o in options})==len(options)


def reference_model(stage, request, timeout):
    raw=Model()(stage,request,timeout)
    data=json.loads(raw)
    if stage=='report':
        evidence=request['data']['evidence'][0]
        data['claims'][0]['supportingQuotes']=[{'evidenceId':evidence['id'], 'quoteId':evidence['quoteOptions'][0]['quoteId']}]
    return json.dumps(data).encode()


def test_reference_resolves_to_exact_quote_and_replays(tmp_path):
    result=record_run(tmp_path,'fixture','Public topic','en',search,read,reference_model)
    assert result.outcome.status=='SUCCEEDED'
    path=next(tmp_path.iterdir())
    assert replay(path)['session']['report']==result.report
    assert check_report(path)['answer']==result.outcome.answer
    stored=''.join(p.read_text(encoding='utf-8') for p in path.glob('*.json'))
    assert 'Public topic evidence.' in stored


@pytest.mark.parametrize('reference',[
    {'evidenceId':'E1','quoteId':'Q99'},
    {'evidenceId':'E2','quoteId':'Q1'},
    {'evidenceId':'E1','quoteId':'Q1','quote':'Public topic evidence.'},
])
def test_invalid_or_ambiguous_references_fail(reference):
    def complete(stage,request,timeout):
        data=json.loads(Model()(stage,request,timeout))
        if stage=='report':data['claims'][0]['supportingQuotes']=[reference]
        return json.dumps(data).encode()
    result=run_session('Public topic','en',search,read,complete)
    assert result.outcome.status=='FAILED'
    assert result.report is None


def test_resolved_output_does_not_depend_on_future_option_ids():
    draft=GroundedReportOutput.model_validate({'claims':[{'kind':'source_statement','text':'A public claim',
        'evidenceIds':['E1'],'supportingQuotes':[{'evidenceId':'E1','quoteId':'Q1'}]}], 'limitations':['Only public evidence.']})
    validate_report(draft,{'E1':'Public topic evidence.'})
    saved=provider_payload(draft)['claims'][0]['supportingQuotes'][0]
    assert saved=={'evidenceId':'E1','quote':'Public topic evidence.'}
