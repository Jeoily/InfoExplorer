"""Offline execution scenarios, not a question-quality benchmark."""
from dataclasses import replace
import json

import pytest

from app.web_research.budget import ExecutionBudget, Limits
from app.web_research.candidates import parse_searxng
from app.web_research.pipeline import (
    Claim, CoverageItem, GeneratedReport, Plan, Review, ToolFailure, execute,
)
from app.web_research.selection import Document


def candidates(*paths, warnings=False):
    return parse_searxng(json.dumps({
        "results": [{"url": f"https://example.org/{path}", "title": "Public software article",
                     "content": "A search snippet, not body evidence"} for path in paths],
        "unresponsive_engines": [["engine", "error"]] if warnings else [],
    }).encode())


def read(candidate, timeout):
    assert 0 < timeout <= 20
    return Document(candidate.source_id, candidate.host, candidate.title,
                    ("backend databases and frontend interfaces",))


def plan():
    return Plan({"Q1": "backend databases", "Q2": "frontend interfaces"}, ("software development",))


def test_evidence_needs_can_match_english_body_for_chinese_question_without_becoming_evidence():
    original = {'Q1': '前端开发负责什么？'}
    def reader(candidate, timeout):
        return Document(candidate.source_id, candidate.host, candidate.title,
                        ('Frontend development builds browser interfaces using HTML and CSS.',))
    plain = execute(Plan(original, ('frontend development',)), lambda *_: candidates('article'), reader)
    assert not plain.evidence
    captured = []
    def review(questions, evidence, timeout):
        captured.append(questions)
        return Review((CoverageItem('Q1', 'covered', (evidence[0].evidence_id,)),))
    result = execute(Plan(original, ('frontend development',), {'Q1': 'frontend development interfaces'}),
                     lambda *_: candidates('article'), reader, review=review)
    assert result.status == 'SUCCEEDED'
    assert result.evidence[0].excerpt.startswith('Frontend development builds')
    assert result.evidence[0].matched_question_ids == ('Q1',)
    assert captured == [original]


def test_retrieval_hints_do_not_create_evidence_without_matching_body():
    def reader(candidate, timeout):
        return Document(candidate.source_id, candidate.host, 'frontend', ('Volcanic ash.',))
    result = execute(Plan({'Q1': '前端工作'}, ('frontend',), {'Q1': 'frontend HTML CSS'}),
                     lambda *_: candidates('article'), reader)
    assert not result.evidence


def test_unknown_question_in_evidence_needs_is_rejected_before_search():
    with pytest.raises(ValueError, match='evidence needs'):
        execute(Plan({'Q1': 'topic'}, ('topic',), {'Q2': 'unrelated'}),
                lambda *_: pytest.fail('no search'), read)


def test_no_model_pipeline_saves_evidence_and_trace_without_claiming_coverage():
    result = execute(plan(), lambda *_: candidates("article"), read)
    assert result.status == "SUCCEEDED"
    assert result.completion_reason == "COMPLETED"
    assert result.coverage == "unknown"
    assert result.usage.searches == result.usage.documents == 1
    assert result.usage.model_calls == 0
    assert "未经模型" in result.answer
    assert result.sources[0].status == "READ"
    assert result.evidence[0].source_id == result.queries[0].source_ids[0]


def test_same_source_found_by_two_queries_is_read_only_once():
    seen = []
    def reader(candidate, timeout):
        seen.append(candidate.source_id)
        return read(candidate, timeout)
    result = execute(Plan({"Q1": "backend"}, ("one", "two")), lambda *_: candidates("same"), reader)
    assert result.status == "SUCCEEDED"
    assert len(seen) == result.usage.documents == 1
    assert len(result.queries) == 2
    assert result.queries[0].source_ids == result.queries[1].source_ids


def test_one_failed_search_does_not_discard_successful_search():
    def search(query, timeout):
        if query == "one":
            raise ToolFailure("SEARCH_TIMEOUT")
        return candidates("article")
    result = execute(Plan({"Q1": "backend"}, ("one", "two")), search, read)
    assert result.status == "SUCCEEDED"
    assert result.queries[0].error_code == "SEARCH_TIMEOUT"
    assert result.queries[1].status == "SUCCEEDED"
    assert result.evidence


def test_all_search_failures_are_not_empty_success():
    def search(*_):
        raise ToolFailure("SEARCH_RATE_LIMITED")
    result = execute(plan(), search, read)
    assert result.status == "FAILED"
    assert not result.evidence
    assert result.answer is None
    assert result.usage.documents == 0


def test_unavailable_engines_with_zero_results_do_not_claim_successful_empty_search():
    result = execute(plan(), lambda *_: candidates(warnings=True), read)
    assert result.status == "FAILED"
    assert result.queries[0].error_code == "SEARCH_UNAVAILABLE"


def test_empty_search_returns_no_evidence_and_never_generates_report():
    result = execute(plan(), lambda *_: candidates(), read,
                     generate=lambda *_: pytest.fail("No evidence must not generate a report"))
    assert result.status == "SUCCEEDED"
    assert result.completion_reason == "NO_USABLE_EVIDENCE"
    assert result.usage.model_calls == 0


def test_failed_reads_never_fall_back_to_search_snippets():
    def reader(*_):
        raise ToolFailure("CONTENT_DISALLOWED")
    result = execute(plan(), lambda *_: candidates("article"), reader)
    assert result.status == "FAILED"
    assert result.completion_reason == "CONTENT_UNAVAILABLE"
    assert not result.evidence
    assert result.sources[0].error_code == "CONTENT_DISALLOWED"


def test_one_bounded_supplement_round_and_report_have_shared_usage():
    searched = []
    def search(query, timeout):
        searched.append(query)
        return candidates(query.replace(" ", "-"))
    def reviewer(questions, evidence, timeout):
        return Review((CoverageItem("Q1", "covered", ("E1",)),
                       CoverageItem("Q2", "missing", ())), ("frontend reference", "software development"))
    def report(questions, evidence, timeout):
        return GeneratedReport((Claim("A statement based on supplied evidence", ("E1",)),), ("Limited public evidence",))
    result = execute(plan(), search, read, review=reviewer, generate=report)
    assert result.status == "SUCCEEDED"
    assert searched == ["software development", "frontend reference"]
    assert result.usage.searches == 2
    assert result.usage.model_calls == 2
    assert result.coverage == "partial"  # A supplement is not a second verification.
    assert [attempt.round for attempt in result.queries] == [0, 1]
    assert "[E1]" in result.answer


def test_sufficient_review_does_not_run_suggested_extra_queries():
    def reviewer(*_):
        return Review((CoverageItem("Q1", "covered", ("E1",)),
                       CoverageItem("Q2", "covered", ("E1",))), ("unnecessary",))
    result = execute(plan(), lambda *_: candidates("article"), read, review=reviewer)
    assert result.status == "SUCCEEDED"
    assert result.coverage == "sufficient"
    assert result.usage.searches == 1


def test_false_coverage_references_are_rejected_and_evidence_retained():
    def reviewer(*_):
        return Review((CoverageItem("Q1", "covered", ("E99",)), CoverageItem("Q2", "missing", ())))
    result = execute(plan(), lambda *_: candidates("article"), read, review=reviewer)
    assert result.status == "FAILED"
    assert result.completion_reason == "MODEL_INVALID_RESPONSE"
    assert result.evidence
    assert result.coverage == "unknown"


@pytest.mark.parametrize("report", [
    GeneratedReport((Claim("Invented source", ("E99",)),)),
    GeneratedReport((Claim("No citation", ()),)),
    GeneratedReport((Claim("Embedded fake [E99]", ("E1",)),)),
    GeneratedReport((Claim("Valid", ("E1",)),), ("Fake limitation [E99]",)),
    GeneratedReport((), ()),
    GeneratedReport(None, ()),
], ids=["unknown-id", "missing-id", "inline-fake", "limitation-fake", "empty", "wrong-type"])
def test_bad_report_does_not_destroy_public_evidence(report):
    result = execute(plan(), lambda *_: candidates("article"), read, generate=lambda *_: report)
    assert result.status == "FAILED"
    assert result.completion_reason == "MODEL_INVALID_RESPONSE"
    assert result.evidence
    assert result.answer is None


def test_report_failure_preserves_read_sources_and_charges_once():
    def report(*_):
        raise ToolFailure("MODEL_TIMEOUT")
    result = execute(plan(), lambda *_: candidates("article"), read, generate=report)
    assert result.status == "FAILED"
    assert result.usage.model_calls == 1
    assert result.sources[0].status == "READ"
    assert result.evidence


def test_deadline_keeps_earlier_evidence_but_drops_late_document():
    now = [0.0]
    budget = ExecutionBudget(Limits(total_seconds=10), lambda: now[0])
    count = 0
    def reader(candidate, timeout):
        nonlocal count
        count += 1
        if count == 2:
            now[0] = 11
        return read(candidate, timeout)
    result = execute(plan(), lambda *_: candidates("one", "two"), reader, budget=budget)
    assert result.status == "FAILED"
    assert result.completion_reason == "EXECUTION_DEADLINE"
    assert result.evidence
    assert result.sources[1].status == "FAILED"
    assert result.usage.documents == 2


def test_zero_budget_blocks_calls_before_dispatch():
    budget = ExecutionBudget(Limits(searches=0))
    result = execute(plan(), lambda *_: pytest.fail("Must not call"), read, budget=budget)
    assert result.status == "FAILED"
    assert result.usage.searches == 0
    assert result.queries[0].status == "FAILED"


def test_read_budget_interleaves_initial_queries_and_never_exceeds_six():
    seen = []
    def search(query, timeout):
        return candidates(*(f"{query}-{i}" for i in range(5)))
    def reader(candidate, timeout):
        seen.append(candidate.requested_url.rsplit("/", 1)[1])
        return read(candidate, timeout)
    result = execute(Plan({"Q1": "backend"}, ("one", "two", "three")), search, reader)
    assert seen == ["one-0", "two-0", "three-0", "one-1", "two-1", "three-1"]
    assert result.usage.documents == 6


def test_adapter_cannot_replace_valid_candidate_with_private_url():
    original = candidates("article")
    hostile = replace(original, candidates=(replace(original.candidates[0], requested_url="http://127.0.0.1/"),))
    result = execute(plan(), lambda *_: hostile, lambda *_: pytest.fail("Private source reached reader"))
    assert result.status == "FAILED"
    assert result.queries[0].error_code == "SEARCH_INVALID_RESPONSE"


def test_reader_cannot_substitute_unrelated_source_identity():
    result = execute(plan(), lambda *_: candidates("article"),
                     lambda *_: Document("different", "example.org", "Wrong source", ("backend",)))
    assert result.status == "FAILED"
    assert result.sources[0].error_code == "CONTENT_INVALID_RESPONSE"


def test_pre_cancelled_run_has_no_tool_calls():
    budget = ExecutionBudget()
    budget.cancel()
    result = execute(plan(), lambda *_: pytest.fail("Must not search"), read, budget=budget)
    assert result.status == "FAILED"
    assert result.completion_reason == "EXECUTION_CANCELLED"
    assert result.queries == ()


def test_model_may_report_insufficient_evidence_without_fabricating_claims():
    result = execute(plan(), lambda *_: candidates("article"), read,
                     generate=lambda *_: GeneratedReport((), ("资料不足以得出结论",)))
    assert result.status == "SUCCEEDED"
    assert result.coverage == "partial"
    assert "资料不足" in result.answer
    assert result.evidence


@pytest.mark.parametrize("item", [
    CoverageItem([], "covered", ("E1",)), CoverageItem("Q1", [], ("E1",)),
    CoverageItem("Q1", "covered", (["E1"],)), CoverageItem("Q1", "covered", ()),
], ids=["bad-id", "bad-state", "bad-citation", "unfounded-coverage"])
def test_malformed_coverage_is_a_safe_failure(item):
    result = execute(plan(), lambda *_: candidates("article"), read,
                     review=lambda *_: Review((item, CoverageItem("Q2", "missing", ()))))
    assert result.status == "FAILED"
    assert result.completion_reason == "MODEL_INVALID_RESPONSE"


def test_unread_sources_are_terminal_skips_not_pending_reads():
    def search(query, timeout):
        return candidates(*(f"{query}-{index}" for index in range(5)))
    result = execute(Plan({"Q1": "backend"}, ("one", "two")), search, read)
    assert sum(item.status == "READ" for item in result.sources) == 6
    assert sum(item.status == "SKIPPED" for item in result.sources) == 4
    assert all(item.error_code == "READ_LIMIT" for item in result.sources if item.status == "SKIPPED")


def test_all_attempted_reads_fail_even_if_unread_candidates_remain():
    def search(query, timeout):
        return candidates(*(f"{query}-{index}" for index in range(5)))
    def reader(*_):
        raise ToolFailure("CONTENT_UNAVAILABLE")
    result = execute(Plan({"Q1": "backend"}, ("one", "two")), search, reader)
    assert result.status == "FAILED"
    assert result.completion_reason == "CONTENT_UNAVAILABLE"


def test_original_question_can_be_used_as_long_direct_query():
    text = "backend " * 400
    result = execute(Plan({"Q1": text}, (text,)), lambda *_: candidates("article"), read)
    assert result.status == "SUCCEEDED"
    assert result.queries[0].query == text.strip()
