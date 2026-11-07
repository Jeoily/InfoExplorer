import json
from dataclasses import asdict
import pytest
from app.web_research.research_session import run_session
from app.web_research.recording import record_run, replay, check_report, ReplayError
from app.web_research.session_api import SessionWire
from app.web_research.pipeline import ToolFailure
from test_research_session import Model, search, read


class Auditor(Model):
    def __init__(self, fail=False):
        super().__init__()
        self.fail=fail
    def __call__(self, stage, request, timeout):
        if stage=='verify':
            assert request['data']['draftReport']['claims'][0]['text']=='A bounded inference'
            if self.fail:
                self.calls.append((stage,request,timeout))
                raise ToolFailure('MODEL_TIMEOUT')
            raw=super().__call__(stage,request,timeout)
            data=json.loads(raw)
            data['claims'][0]['text']='Public topic evidence.'
            data['claims'][0]['kind']='source_statement'
            return json.dumps({'checks':[{'claimIndex':0,'verdict':'revise',
                'reason':'Replace inference with the stated evidence.','replacement':data['claims'][0]}],
                'limitations':data['limitations']}).encode()
        return super().__call__(stage,request,timeout)


def test_audit_replaces_draft_and_replays_without_calls(tmp_path):
    model=Auditor()
    session=record_run(tmp_path,'fixture','Public topic','en',search,read,model,verify_report=True)
    assert session.version=='web-model-session-v2'
    assert session.usage.model_calls==4
    assert [c[0] for c in model.calls]==['plan','review','report','verify']
    assert session.report['claims'][0]['text']=='Public topic evidence.'
    SessionWire.model_validate(asdict(session))
    path=next(tmp_path.iterdir())
    assert replay(path)['session']['report']==session.report
    assert check_report(path)['report']==session.report


def test_failed_audit_never_publishes_unreviewed_draft(tmp_path):
    session=record_run(tmp_path,'fixture','Public topic','en',search,read,Auditor(True),verify_report=True)
    assert session.report is None and session.outcome.status=='FAILED'
    assert session.stop_reason=='MODEL_TIMEOUT' and session.usage.model_calls==4
    assert session.events[-1].stage=='verify'
    with pytest.raises(ReplayError,match='NO_VALIDATED_REPORT'):
        check_report(next(tmp_path.iterdir()))


def test_remove_preserves_supported_claims_and_rejects_missing_verdicts():
    from app.web_research.research_session import GroundedReportOutput, AuditOutput, apply_audit
    claim={'kind':'source_statement','text':'Public topic evidence.','evidenceIds':['E1'],
        'supportingQuotes':[{'evidenceId':'E1','quote':'Public topic evidence.'}]}
    draft=GroundedReportOutput.model_validate({'claims':[claim,{**claim,'text':'Unsupported extra assertion.'}],
        'limitations':['Limited evidence.']})
    checks=[{'claimIndex':0,'verdict':'keep','reason':'Direct support.','replacement':None},
            {'claimIndex':1,'verdict':'remove','reason':'No support.','replacement':None}]
    audit=AuditOutput(checks=checks,limitations=['Extra assertion is unsupported.'])
    assert len(apply_audit(draft,audit,{'E1':'Public topic evidence.'}).claims)==1
    with pytest.raises(ValueError):
        apply_audit(draft,AuditOutput(checks=checks[:1],limitations=['Limited.']),{'E1':'Public topic evidence.'})
