"""Optional actual-library checks using synthetic local HTML, never live websites."""
import importlib.util
import json
import multiprocessing
import time

import pytest

from app.web_research.candidates import parse_searxng
from app.web_research.extraction import ExtractionError, extract_html
from app.web_research.selection import select_passages

pytestmark = pytest.mark.skipif(importlib.util.find_spec("trafilatura") is None,
                                reason="Optional web extraction dependency is not installed")


def candidate():
    return parse_searxng(json.dumps({"results": [{"title": "Fallback title",
        "url": "https://example.org/article", "content": "snippet"}]}).encode()).candidates[0]


def html():
    paragraphs = [
        "后端工程负责数据库事务、业务接口和权限检查。每次研究任务都有独立执行记录，"
        "失败重试不会覆盖已有历史。本文使用本地示例说明工程行为，不是联网抓取的报道。",
        "前端工程负责用户界面和交互反馈。页面需要区分研究执行完成与资料是否充分，"
        "并允许读者从结论跳转到保存的证据段落，查阅其来源和获取时间。",
        "当网页读取失败或模型没有返回有效引用时，系统应保存已获得的公开资料，"
        "说明失败阶段，不应把搜索摘要当成已经阅读的完整文章。",
    ]
    return ("<!doctype html><html><head><meta charset='utf-8'><title>本地工程示例</title>"
            "<meta property='article:published_time' content='2026-09-01T10:00:00Z'>"
            "<link rel='canonical' href='http://127.0.0.1/private'>"
            "</head><body><nav>导航 菜单</nav><article><h1>本地工程示例</h1>"
            + "".join("<p>" + text + "</p>" for text in paragraphs)
            + "</article><script>fetch('http://127.0.0.1/private')</script>"
            "<footer>页脚导航</footer></body></html>").encode()


def test_real_trafilatura_extracts_local_chinese_html_without_source_substitution():
    source = candidate()
    result = extract_html(source, html())
    assert result.document.source_id == source.source_id
    assert result.document.host == "example.org"
    text = " ".join(result.document.paragraphs)
    assert "数据库事务" in text
    assert "前端工程" in text
    assert "fetch(" not in text
    assert "127.0.0.1" not in text
    assert result.published_text == "2026-09-01"
    assert result.extractor == "trafilatura-2.3.1-context-v2"
    assert select_passages([result.document], {"Q1": "数据库事务"})


def test_very_short_deadline_terminates_child_and_leaves_no_new_process():
    before = {process.pid for process in multiprocessing.active_children()}
    started = time.monotonic()
    with pytest.raises(ExtractionError, match="CONTENT_TIMEOUT"):
        extract_html(candidate(), html(), timeout=0.0001)
    assert time.monotonic() - started < 5
    assert {process.pid for process in multiprocessing.active_children()} == before


@pytest.mark.parametrize("body,media,code", [
    (b"", "text/html", "CONTENT_INVALID_RESPONSE"),
    (b"x" * (2 * 1024 * 1024 + 1), "text/html", "CONTENT_INVALID_RESPONSE"),
    (b"<!ENTITY bad SYSTEM 'file:///private'>", "text/html", "CONTENT_INVALID_RESPONSE"),
    (b"%PDF-1.7", "application/pdf", "CONTENT_UNSUPPORTED"),
], ids=["empty", "oversize", "external-entity", "pdf"])
def test_bad_input_is_rejected_before_parser(body, media, code):
    with pytest.raises(ExtractionError, match=code):
        extract_html(candidate(), body, content_type=media)


def test_markup_without_article_is_empty_not_a_fake_success():
    with pytest.raises(ExtractionError, match="CONTENT_EMPTY"):
        extract_html(candidate(), b"<html><body><script>hello()</script></body></html>")


def test_structure_keeps_definition_subject_and_wrapped_paragraph_together():
    from app.web_research.extraction import context_blocks
    raw = '''<doc title="API"><main><head rend="h1">Connection</head>
      <list rend="dl"><item rend="dt-1">Connection.tunnel(host)</item><item rend="dd-1">
      <p>Creates a proxy tunnel.\nThis does not create a new class.</p>
      <p>Added in version 3.2.</p></item></list>
      <list rend="dl"><item rend="dt-1">Connection.close()</item><item rend="dd-1">
      <p>Closes the connection.</p></item></list></main></doc>'''
    blocks, _, _, cut = context_blocks(raw)
    assert not cut
    assert len(blocks) == 2
    assert 'Connection.tunnel(host)' in blocks[0] and 'Added in version 3.2.' in blocks[0]
    assert 'This does not create a new class.' in blocks[0]
    assert 'Connection.close()' in blocks[1] and 'tunnel' not in blocks[1]


def test_structural_blocks_keep_context_on_long_sections_and_bound_output():
    from app.web_research.extraction import context_blocks
    from app.web_research.candidates import utf16_length
    raw = '<doc><main><head rend="h2">Subject</head><p>' + 'evidence 😀 ' * 6000 + '</p></main></doc>'
    blocks, _, _, cut = context_blocks(raw)
    assert cut and blocks
    assert all(b.startswith('Subject — ') and utf16_length(b) <= 1503 for b in blocks)
    assert sum(map(utf16_length, blocks)) <= 30000
