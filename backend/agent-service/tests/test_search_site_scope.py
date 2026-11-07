"""Search engines may ignore a site operator; do not spend the read budget on mirrors."""
import json

import pytest

from app.web_research.candidates import parse_searxng, query_site_host, transport_query


def test_site_filter_precedes_top_results_limit_and_checks_label_boundary():
    urls = ['https://mirror.org/' + str(i) for i in range(6)] + [
        'https://docs.example.org.attacker.org/page',
        'https://notdocs.example.org/page',
        'https://docs.example.org/page',
        'https://v3.docs.example.org/page',
    ]
    raw = json.dumps({'results': [{'url': u, 'title': 'Reference'} for u in urls]}).encode()
    batch = parse_searxng(raw, query='API guide site:docs.example.org')
    assert [c.host for c in batch.candidates] == ['docs.example.org', 'v3.docs.example.org']
    assert batch.rejected_count == 8
    assert not batch.truncated
    assert len(parse_searxng(raw).candidates) == 5


@pytest.mark.parametrize('query', [
    'API -site:example.org', 'site:a.org OR site:b.org', 'site:a.org site:b.org',
    'site:https://example.org', '"site:example.org"',
    '(site:example.org) OR tutorial', 'API site:localhost',
])
def test_ambiguous_or_unsupported_operators_are_not_misinterpreted(query):
    assert query_site_host(query) is None


def test_case_insensitive_host_operator():
    assert query_site_host('API SITE:Docs.Example.ORG') == 'docs.example.org'


def test_path_scope_is_enforced_after_transport_translation():
    query = 'site:docs.example.org/current/api.html Channel'
    assert transport_query(query) == 'site:docs.example.org Channel'
    raw = json.dumps({'results': [{'url': u, 'title': 'API'} for u in [
        'https://docs.example.org/old/api.html',
        'https://docs.example.org/current/api.html-extra',
        'https://docs.example.org/current/api.html',
    ]]}).encode()
    batch = parse_searxng(raw, query=query)
    assert len(batch.candidates) == 1
    assert batch.candidates[0].canonical_url.endswith('/current/api.html')
    assert batch.rejected_count == 2
    assert transport_query('site:docs.example.org/current/api.html') == 'site:docs.example.org api.html'
