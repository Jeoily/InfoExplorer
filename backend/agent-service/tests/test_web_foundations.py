"""Offline behavior/security checks for the not-yet-integrated web foundations."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json

import pytest

from app.web_research.budget import BudgetExceeded, ExecutionBudget, Limits
from app.web_research.candidates import SearchPayloadRejected, parse_searxng, utf16_length
from app.web_research.selection import Document, select_passages
from app.web_research.url_policy import (
    UrlRejected, public_ip, validate_candidate_url, validate_resolved_ips,
)


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


def test_budget_deadline_is_shared_across_stages_and_failed_calls():
    clock = Clock()
    budget = ExecutionBudget(Limits(searches=1, total_seconds=25), clock)
    assert budget.reserve("search") == 20
    clock.now = 19
    assert budget.reserve("document") == 6
    with pytest.raises(BudgetExceeded, match="EXHAUSTED"):
        budget.reserve("search")
    clock.now = 25
    with pytest.raises(BudgetExceeded, match="DEADLINE"):
        budget.reserve("model")
    assert budget.snapshot().searches == 1
    assert budget.snapshot().documents == 1
    assert budget.snapshot().model_calls == 0


def test_budget_concurrent_reservations_cannot_exceed_cap():
    budget = ExecutionBudget(Limits(searches=5))
    def attempt(_):
        try:
            budget.reserve("search")
            return True
        except BudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=16) as pool:
        assert sum(pool.map(attempt, range(100))) == 5
    assert budget.snapshot().searches == 5


def test_longer_model_wait_still_shares_deadline_and_does_not_extend_network_wait():
    clock = Clock()
    budget = ExecutionBudget(Limits(model_request_seconds=45), clock)
    assert budget.reserve('model') == 45
    assert budget.reserve('search') == 20
    assert budget.reserve('document') == 20
    clock.now = 139
    assert budget.reserve('model') == 11
    clock.now = 150
    with pytest.raises(BudgetExceeded, match='DEADLINE'):
        budget.reserve('model')
    assert budget.snapshot().model_calls == 2


def test_cancellation_blocks_future_work_without_refunding_attempts():
    budget = ExecutionBudget()
    budget.reserve("model")
    budget.cancel()
    budget.cancel()
    for action in (budget.checkpoint, lambda: budget.reserve("document")):
        with pytest.raises(BudgetExceeded, match="CANCELLED"):
            action()
    assert budget.snapshot().model_calls == 1
    assert budget.snapshot().cancelled


@pytest.mark.parametrize("kwargs", [
    {"searches": True}, {"documents": -1}, {"model_calls": 1.5},
    {"total_seconds": 0}, {"request_seconds": float("nan")},
    {"total_seconds": float("inf")}, {"total_seconds": True},
    {"model_request_seconds": 0}, {"model_request_seconds": float('nan')},
    {"model_request_seconds": True},
])
def test_budget_rejects_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        Limits(**kwargs)


@pytest.mark.parametrize("value", [
    "http://localhost/", "https://a.localhost/", "http://service/", "http://server.local/",
    "http://127.0.0.1/", "http://127.1/", "http://2130706433/", "http://0x7f000001/",
    "http://0177.0.0.1/", "http://0x7f.0.0.1/", "http://10.1.2.3/",
    "http://169.254.169.254/latest/", "http://100.64.0.1/", "http://192.168.1.1/",
    "http://[::1]/", "http://[::ffff:127.0.0.1]/", "http://[fe80::1%25eth0]/",
    "http://224.0.0.1/", "http://[ff02::1]/", "http://[64:ff9b::808:808]/",
    "http://user:password@example.org/", "http://@example.org/",
    "https://example.org:8080/", "https://example.org:abc/", "https://example.org:80/",
    "file:///etc/passwd", "ftp://example.org/a", "//example.org/a", "",
    "https://example.org\\@127.0.0.1/", "https://example.org/\nprivate",
    " https://example.org/", "https://exam_ple.org/", "https://%31%32%37.0.0.1/",
    "https://example.org/\ud800", "http://example.invalid/", "http://example.test/",
    "https://example.org../", "https://example.org/%zz", "https://example.org/%",
])
def test_rejects_unsafe_or_ambiguous_candidate_urls(value):
    with pytest.raises(UrlRejected) as raised:
        validate_candidate_url(value)
    assert str(raised.value) == "SOURCE_URL_REJECTED"
    assert "password" not in str(raised.value)


def test_url_normalization_preserves_meaningful_query_bytes_and_requested_url():
    value = "HTTPS://Example.ORG:443/a?x=a%2Fb&x=a+b&utm_source=feed&empty=&signature=abc%3D#section"
    result = validate_candidate_url(value)
    assert result.host == "example.org"
    assert result.canonical_url == "https://example.org/a?x=a%2Fb&x=a+b&empty=&signature=abc%3D"
    assert "utm_source=feed" in result.requested_url
    assert "#" not in result.requested_url


def test_unicode_domain_is_canonicalized_without_network():
    result = validate_candidate_url("https://例子.中国/文章")
    assert result.host.startswith("xn--")
    assert result.canonical_url.endswith("/文章")


@pytest.mark.parametrize("value", ["8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"])
def test_public_literal_addresses(value):
    assert public_ip(value)


@pytest.mark.parametrize("answers", [[], ["8.8.8.8", "127.0.0.1"], ["::1"],
                                      ["192.0.2.1"], ["not-an-ip"], ["8.8.8.8"] * 33])
def test_dns_policy_rejects_any_private_or_invalid_answer(answers):
    with pytest.raises(UrlRejected, match="ADDRESS_REJECTED"):
        validate_resolved_ips(answers)


def test_dns_policy_deduplicates_only_after_all_answers_checked():
    assert validate_resolved_ips(["8.8.8.8", "8.8.8.8", "1.1.1.1"]) == ("8.8.8.8", "1.1.1.1")


def entry(url="https://example.org/article", title="Public article", content="Search snippet"):
    return {"url": url, "title": title, "content": content, "engines": ["engine-one"]}


def batch(entries, **extra):
    return json.dumps({"results": entries, **extra}).encode()


def test_searx_parser_deduplicates_tracking_urls_but_keeps_article_identity():
    parsed = parse_searxng(batch([
        entry("https://example.org/a?id=1&utm_source=test"),
        entry("https://example.org/a?id=1"),
        entry("https://example.org/a?id=2"),
    ]))
    assert len(parsed.candidates) == 2
    assert parsed.duplicate_count == 1
    assert [item.rank for item in parsed.candidates] == [1, 3]
    assert parsed.candidates[0].snippet == "Search snippet"
    assert not hasattr(parsed.candidates[0], "excerpt")


def test_parser_filters_private_sources_and_preserves_partial_failure_warning():
    parsed = parse_searxng(batch([entry("http://127.0.0.1/"), entry()],
                                unresponsive_engines=[["engine-two", "private error details"]]))
    assert len(parsed.candidates) == 1
    assert parsed.rejected_count == 1
    assert parsed.warnings == ("SEARCH_ENGINES_PARTIALLY_UNAVAILABLE",)
    assert "private error details" not in repr(parsed)


def test_empty_results_and_policy_rejected_results_are_distinct_from_bad_json():
    assert parse_searxng(batch([])).candidates == ()
    rejected = parse_searxng(batch([entry("http://127.0.0.1/")]))
    assert rejected.rejected_count == 1
    assert rejected.candidates == ()


@pytest.mark.parametrize("raw", [
    b"{}", b"null", b"[]", b'{"results":null}', b"<html>captcha</html>",
    b'{"results":[],"results":[{}]}', b'{"results":[],"x":NaN}',
    batch([None]), batch([{"title": "missing url"}]),
    batch([entry()] * 101), b"x" * 262145,
], ids=["missing-results", "null", "array", "null-results", "captcha", "duplicate-key",
        "nonfinite-number", "null-entry", "missing-url", "too-many-results", "too-many-bytes"])
def test_invalid_search_payloads_fail_without_leaking_contents(raw):
    with pytest.raises(SearchPayloadRejected) as raised:
        parse_searxng(raw)
    assert str(raised.value) == "SEARCH_INVALID_RESPONSE"


def test_parser_preserves_unknown_publication_text_without_inventing_datetime():
    data = entry()
    data["publishedDate"] = "yesterday"
    result = parse_searxng(batch([data])).candidates[0]
    assert result.published_text == "yesterday"
    assert not hasattr(result, "published_at")


def test_parser_result_bound_and_truncation():
    parsed = parse_searxng(batch([entry(f"https://example.org/{i}") for i in range(8)]))
    assert len(parsed.candidates) == 5
    assert parsed.truncated


def doc(sid="s1", paragraphs=("backend handles databases and transactions",), host="example.org"):
    return Document(sid, host, "Software development", paragraphs)


def test_evidence_covers_multiple_questions_and_deduplicates_equal_text():
    documents = [doc(), doc("s2", ("frontend renders interfaces",), "other.org"), doc("s3")]
    results = select_passages(documents, {"Q1": "backend databases", "Q2": "frontend interfaces"})
    assert len(results) == 2
    assert {key for item in results for key in item.matched_question_ids} == {"Q1", "Q2"}
    assert [item.evidence_id for item in results] == ["E1", "E2"]
    assert all(item.content_hash == hashlib.sha256(item.excerpt.encode()).hexdigest() for item in results)


def test_evidence_does_not_fill_with_unrelated_text_or_title_only_matches():
    assert select_passages([doc()], {"Q1": "volcano eruption"}) == ()
    assert select_passages([Document("s1", "example.org", "databases", ("unrelated text",))],
                           {"Q1": "databases"}) == ()


def test_common_question_words_do_not_count_as_topic_evidence():
    assert select_passages([doc(paragraphs=('This is the guide and it is available to you.',))],
                           {'Q1':'What is a database transaction?'}) == ()


def test_more_complete_match_is_not_displaced_only_for_a_different_host():
    documents=[doc('a',('database transactions overview','database transactions isolation rollback'), 'one.org'),
               doc('b',('database unrelated description',), 'two.org')]
    selected=select_passages(documents,{'Q1':'database transactions isolation rollback'},max_evidence=1)
    assert selected[0].excerpt == 'database transactions isolation rollback'


def test_chinese_queries_and_later_paragraphs():
    results = select_passages([doc(paragraphs=("这是网站简介。", "后端负责数据库事务与接口。"))],
                              {"Q1": "后端数据库"})
    assert len(results) == 1
    assert results[0].paragraph_index == 1


def test_unicode_budget_does_not_split_surrogates():
    results = select_passages([doc(paragraphs=("backend " + "😀" * 1000,))], {"Q1": "backend"})
    assert len(results) == 1
    assert utf16_length(results[0].excerpt) <= 1600
    results[0].excerpt.encode("utf-8")
    assert results[0].truncated


def test_per_source_and_total_budget_are_enforced():
    documents = [doc(paragraphs=tuple(f"backend paragraph {i}" for i in range(10)))]
    assert len(select_passages(documents, {"Q1": "backend"})) == 2
    result = select_passages(documents, {"Q1": "backend"}, total_limit=25)
    assert sum(utf16_length(item.excerpt) for item in result) <= 25
    assert len(result) == 1


def test_selection_is_deterministic_and_does_not_mutate_inputs():
    documents = [doc(), doc("s2", ("backend transactions with a second source",), "other.org")]
    original = list(documents)
    first = select_passages(documents, {"Q1": "backend transactions"})
    assert first == select_passages(documents, {"Q1": "backend transactions"})
    assert documents == original


def test_duplicate_source_identifiers_are_not_silently_merged():
    with pytest.raises(ValueError):
        select_passages([doc(), doc()], {"Q1": "backend"})


def test_relevant_content_near_end_of_long_paragraph_is_not_lost():
    text = "irrelevant introduction " * 150 + "backend databases transactions"
    results = select_passages([doc(paragraphs=(text,))], {"Q1": "backend databases"})
    assert results
    assert "backend databases" in results[0].excerpt
    assert results[0].offset_utf16 > 0
    encoded = text.encode("utf-16-le")
    first = results[0]
    assert encoded[first.offset_utf16 * 2:(first.offset_utf16 + utf16_length(first.excerpt)) * 2].decode("utf-16-le") == first.excerpt


def test_utf16_offsets_remain_correct_after_emoji_window_boundary():
    text = "😀" * 1200 + " backend database"
    results = select_passages([doc(paragraphs=(text,))], {"Q1": "backend"})
    assert results
    for item in results:
        raw = text.encode("utf-16-le")
        assert raw[item.offset_utf16 * 2:(item.offset_utf16 + utf16_length(item.excerpt)) * 2].decode("utf-16-le") == item.excerpt
