from app.web_research import diagnostics
from app.web_research.research_session import run_session
from test_research_session import search, read, Model
import json
import pytest
from pydantic import ValidationError
from app.web_research.research_session import GroundedReportOutput


@pytest.mark.parametrize('mutation,expected', [
    ('missing', 'report_quote_missing'), ('long', 'schema_length'),
    ('type', 'schema_type'), ('extra', 'schema_extra'), ('value', 'schema_value')])
def test_schema_categories_never_include_provider_fields_or_values(mutation, expected):
    claim = {'kind': 'source_statement', 'text': 'Public claim', 'evidenceIds': ['E1'],
             'supportingQuotes': [{'evidenceId': 'E1', 'quote': 'Public topic evidence.'}]}
    if mutation == 'missing':
        del claim['supportingQuotes']
    elif mutation == 'long':
        claim['supportingQuotes'][0]['quote'] = 'PRIVATE_SENTINEL' * 30
    elif mutation == 'type':
        claim['supportingQuotes'] = 'PRIVATE_SENTINEL'
    elif mutation == 'extra':
        claim['PRIVATE_SENTINEL'] = 'PRIVATE_SENTINEL'
    else:
        claim['kind'] = 'PRIVATE_SENTINEL'
    with pytest.raises(ValidationError) as caught:
        GroundedReportOutput.model_validate({'claims': [claim], 'limitations': ['Limited sources']})
    assert diagnostics.schema_reason(caught.value) == expected


def test_rejection_log_contains_categories_not_model_text(monkeypatch, tmp_path):
    path=tmp_path/'diagnostics.log'
    monkeypatch.setenv('INFOEXPLORER_MODEL_DIAGNOSTICS','true')
    monkeypatch.setattr(diagnostics,'PATH',path)
    try:
        run_session('Public topic','en',search,read,lambda *_: b'not-json PRIVATE_SENTINEL')
        def mutate(stage,data):
            if stage=='report':
                data['claims'][0]['evidenceIds']=['PRIVATE_SENTINEL']
        result=run_session('Public topic','en',search,read,Model(mutate=mutate))
        assert result.stop_reason=='MODEL_INVALID_RESPONSE'
        text=path.read_text(encoding='utf-8')
        assert 'reason=json_syntax' in text and 'reason=references' in text
        assert 'PRIVATE_SENTINEL' not in text and 'Public topic' not in text
        diagnostics.rejected('report','PRIVATE_SENTINEL')
        assert path.read_text(encoding='utf-8')==text
    finally:
        for handler in list(diagnostics._logger.handlers):
            if isinstance(handler, diagnostics.RotatingFileHandler):
                handler.close()
                diagnostics._logger.removeHandler(handler)


def test_diagnostics_disabled_by_default(monkeypatch,tmp_path):
    monkeypatch.delenv('INFOEXPLORER_MODEL_DIAGNOSTICS',raising=False)
    path=tmp_path/'unused.log'
    monkeypatch.setattr(diagnostics,'PATH',path)
    diagnostics.rejected('report','schema')
    assert not path.exists()


@pytest.mark.parametrize('raw,expected', [
    (b' ', 'json_empty'), (b'```json\n{}\n```', 'json_fenced'),
    (b'{} PRIVATE_SENTINEL', 'json_trailing'),
    (b'{"text":"PRIVATE_SENTINEL', 'json_unterminated'),
    (b'PRIVATE_SENTINEL', 'json_syntax')])
def test_json_syntax_categories_do_not_disclose_or_repair_content(raw, expected):
    with pytest.raises(json.JSONDecodeError) as caught:
        json.loads(raw)
    assert diagnostics.json_reason(raw, caught.value) == expected
