from dataclasses import replace
from uuid import uuid4
import pytest

from app.web_research.identity import EvidenceRegistry
from app.web_research.pipeline import Claim, CoverageItem, GeneratedReport, Plan, Review, execute
from app.web_research.pipeline import _render, ToolFailure
from app.web_research.selection import Document, select_passages
from test_web_pipeline import candidates


def test_identity_survives_reordering_and_removal_but_differs_between_runs():
    selected = select_passages([Document('source', 'example.org', 'backend',
        ('backend storage', 'backend interfaces'))], {'Q1': 'backend'})
    run_id = str(uuid4())
    registry = EvidenceRegistry(run_id)
    original = registry.bind(selected)
    reordered = registry.bind(tuple(reversed(selected)))
    assert reordered == tuple(reversed(original))
    assert registry.bind((selected[1],))[0] == original[1]
    new_run = EvidenceRegistry(str(uuid4())).bind(selected)
    assert new_run[0].evidence_key != original[0].evidence_key
    changed = registry.bind((replace(selected[0], offset_utf16=1),))[0]
    assert changed.evidence_id == 'E3'
    assert changed.evidence_key != original[0].evidence_key


def test_supplement_preserves_review_snapshot_and_never_rebinds_e1():
    batches = {'initial': candidates('old'), 'supplement': candidates('new')}
    def read(candidate, _):
        text = 'backend' if candidate.requested_url.endswith('old') else 'backend databases frontend interfaces'
        return Document(candidate.source_id, candidate.host, candidate.title, (text,))
    def review(_, evidence, __):
        assert evidence[0].excerpt == 'backend'
        return Review((CoverageItem('Q1', 'partial', ('E1',)),
                       CoverageItem('Q2', 'missing', ())), ('supplement',))
    def generate(_, evidence, __):
        assert evidence[0].evidence_id == 'E2'  # New best-ranked text gets a new ID.
        return GeneratedReport((Claim('Backend excerpt', ('E1',)),))
    result = execute(Plan({'Q1': 'backend databases', 'Q2': 'frontend interfaces'}, ('initial',)),
                     lambda q, _: batches[q], read, review=review, generate=generate)
    assert result.status == 'SUCCEEDED'
    assert result.coverage == 'partial'
    assert result.review_snapshot.evidence[0].excerpt == 'backend'
    assert result.review_snapshot.evidence[0].evidence_id == 'E1'
    final_e1 = next(e for e in result.evidence if e.evidence_id == 'E1')
    assert final_e1 == result.review_snapshot.evidence[0]
    assert result.review_snapshot.decision.coverage[0].evidence_ids == ('E1',)
    assert result.review_applied is True


def test_invalid_review_is_not_saved_as_valid_snapshot():
    batch = candidates('one')
    result = execute(Plan({'Q1': 'backend'}, ('initial',)), lambda *_: batch,
        lambda c, _: Document(c.source_id, c.host, c.title, ('backend',)),
        review=lambda *_: Review((CoverageItem('Q1', 'covered', ('E99',)),)))
    assert result.status == 'FAILED'
    assert result.review_snapshot is None
    assert result.evidence[0].evidence_key


def test_report_cannot_cite_removed_evidence_even_if_it_existed_in_review():
    selected = select_passages([Document('source', 'example.org', 'backend',
        ('backend storage', 'backend interfaces'))], {'Q1': 'backend'})
    evidence = EvidenceRegistry(str(uuid4())).bind(selected)
    with pytest.raises(ToolFailure, match='MODEL_INVALID_RESPONSE'):
        _render(GeneratedReport((Claim('Claim with removed citation', ('E1',)),)), (evidence[1],))
