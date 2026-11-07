import importlib.util
import json
from dataclasses import replace
from unittest.mock import Mock

import pytest

from app.web_research import content as c
from app.web_research.candidates import parse_searxng
from app.web_research.download import DownloadedPage, DownloadError
from app.web_research.extraction import ExtractedPage, ExtractionError
from app.web_research.pipeline import Plan, ToolFailure, execute
from app.web_research.selection import Document


def batch():
    return parse_searxng(b'{"results":[{"title":"Fixture","url":"https://example.org/article"}]}')


@pytest.fixture
def setup(monkeypatch):
    source = batch().candidates[0]
    page = DownloadedPage(source.requested_url, "https://docs.example.org/final", b"<html/>",
                          "text/html", "2026-10-19T00:00:00+00:00", 3)
    result = ExtractedPage(Document(source.source_id, source.host, "Title", ("Public research evidence.",)),
                           "2026-10-01", True)
    download, extract = Mock(return_value=page), Mock(return_value=result)
    monkeypatch.setattr(c, "download_html", download)
    monkeypatch.setattr(c, "extract_html", extract)
    return source, download, extract


def test_redirect_provenance_and_unverified_date_are_retained(setup):
    source, _, _ = setup
    result = c.read_content(source)
    assert result.source_id == source.source_id
    assert result.metadata.resolved_host == "docs.example.org"
    assert result.metadata.requested_url == source.requested_url
    assert result.metadata.http_requests == 3
    assert result.metadata.published_basis == "extractor_unverified"
    assert result.metadata.truncated
    assert len(result.metadata.extracted_text_hash) == 64


def test_extraction_receives_only_remaining_budget(setup, monkeypatch):
    source, download, extract = setup
    clock = [100.0]
    monkeypatch.setattr(c.time, "monotonic", lambda: clock[0])
    def fetch(*args):
        clock[0] += 7
        return download.return_value
    download.side_effect = fetch
    c.read_content(source, 10)
    assert extract.call_args.kwargs["timeout"] == 3


def test_download_exhaustion_does_not_start_parser(setup, monkeypatch):
    source, download, extract = setup
    clock = [100.0]
    monkeypatch.setattr(c.time, "monotonic", lambda: clock[0])
    def fetch(*args):
        clock[0] += 11
        return download.return_value
    download.side_effect = fetch
    with pytest.raises(ToolFailure, match="CONTENT_TIMEOUT"):
        c.read_content(source, 10)
    extract.assert_not_called()


@pytest.mark.parametrize("kind,code", [(DownloadError,"CONTENT_ROBOTS_UNSUPPORTED"),
    (DownloadError,"CONTENT_TOO_LARGE"), (DownloadError,"CONTENT_UNSUPPORTED_ENCODING"),
    (ExtractionError,"CONTENT_EMPTY"), (ExtractionError,"CONTENT_EXTRACTOR_NOT_INSTALLED"),
    (ExtractionError,"CONTENT_EXTRACTION_FAILED")])
def test_failures_keep_fixed_codes_without_retry(setup, kind, code):
    source, download, extract = setup
    target = download if kind is DownloadError else extract
    target.side_effect = kind(code)
    with pytest.raises(ToolFailure, match=code): c.read_content(source)
    assert target.call_count == 1
    if kind is DownloadError: extract.assert_not_called()


def test_unknown_internal_error_is_not_exposed(setup):
    source, download, _ = setup
    download.side_effect = DownloadError("unexpected diagnostic details")
    with pytest.raises(ToolFailure, match="^CONTENT_UNAVAILABLE$"): c.read_content(source)


def test_hash_preserves_paragraph_boundaries_and_missing_date(setup):
    source, _, extract = setup
    first = c.read_content(source)
    extract.return_value = replace(extract.return_value, published_text=None,
        document=replace(extract.return_value.document, paragraphs=("Public research", "evidence.")))
    second = c.read_content(source)
    assert first.metadata.extracted_text_hash != second.metadata.extracted_text_hash
    assert second.metadata.published_basis == "unknown"


def test_report_failure_keeps_read_provenance(setup):
    _, _, _ = setup
    def failed(*args): raise ToolFailure("MODEL_UNAVAILABLE")
    result = execute(Plan({"Q1":"research evidence"}, ("research",)), lambda *a: batch(),
                     c.read_content, generate=failed)
    assert result.status == "FAILED"
    assert result.evidence
    assert result.sources[0].metadata.resolved_url.endswith("/final")


def test_empty_extraction_is_distinct_in_source_failure(setup):
    _, _, extract = setup
    extract.side_effect = ExtractionError("CONTENT_EMPTY")
    result = execute(Plan({"Q1":"research"}, ("research",)), lambda *a: batch(), c.read_content)
    assert result.sources[0].error_code == "CONTENT_EMPTY"
    assert not result.evidence


@pytest.mark.skipif(importlib.util.find_spec("trafilatura") is None, reason="Optional extractor absent")
def test_real_parser_and_coordinator_with_offline_html(monkeypatch):
    source = batch().candidates[0]
    paragraphs = ["Public research evidence supports reviewing database transactions and failure recovery. " * 5,
                  "Source provenance records the retrieval time and the original document address. " * 5]
    html = ("<html><head><title>Research evidence</title></head><body><article>" +
            "".join("<p>" + p + "</p>" for p in paragraphs) + "</article></body></html>").encode()
    monkeypatch.setattr(c, "download_html", lambda *a: DownloadedPage(source.requested_url,
        source.requested_url, html, "text/html", "2026-10-19T00:00:00+00:00", 2))
    result = execute(Plan({"Q1":"database transactions"}, ("database transactions",)),
                     lambda *a: batch(), c.read_content)
    assert result.status == "SUCCEEDED"
    assert result.evidence and result.sources[0].metadata.extractor == "trafilatura-2.3.1-context-v2"
