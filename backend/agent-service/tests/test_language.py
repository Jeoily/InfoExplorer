import io
import json
from urllib.parse import urlsplit, parse_qs
import pytest
from test_api import base_url, post
from app.main import app
import app.search as search_module

@pytest.mark.parametrize('language,host', [('en','en.wikipedia.org'),('zh','zh.wikipedia.org')])
def test_request_language_controls_fixed_host(monkeypatch, base_url, language, host):
    monkeypatch.setenv('INFOEXPLORER_MODEL_ENABLED','false')
    monkeypatch.setenv('SEARCH_WIKIPEDIA_LANGUAGE','en' if language=='zh' else 'zh')
    class Opener:
        def open(self, request, timeout):
            url=urlsplit(request.full_url)
            assert url.hostname == host
            assert parse_qs(url.query)['gsrsearch'] == ['请告诉我什么是全栈工程师']
            return io.BytesIO(json.dumps({'query':{'pages':[{'title':'软件工程','extract':'公开资料'}]}}).encode())
    monkeypatch.setattr(search_module,'build_opener',lambda *args: Opener())
    status, body=post(base_url, json.dumps({'question':'请告诉我什么是全栈工程师','language':language}).encode(), '/internal/v1/research/run')
    assert status == 200
    assert body['provider'] == 'wikipedia-'+language
    assert host in body['evidence'][0]['url']

@pytest.mark.parametrize('language',['ZH','', 'fr', 'https://example.org', 1, []])
def test_invalid_language_never_searches(monkeypatch,base_url,language):
    monkeypatch.setattr(search_module,'build_opener',lambda *args: pytest.fail('invalid input triggered network'))
    assert post(base_url, json.dumps({'question':'topic','language':language}).encode(), '/internal/v1/research/run')[0] == 400

def test_missing_language_defaults_en_and_empty_remains_empty(monkeypatch, base_url):
    monkeypatch.setenv('INFOEXPLORER_MODEL_ENABLED','false')
    class Opener:
        def open(self, request, timeout):
            assert urlsplit(request.full_url).hostname == 'en.wikipedia.org'
            return io.BytesIO(b'{"batchcomplete":true}')
    monkeypatch.setattr(search_module,'build_opener',lambda *args: Opener())
    status, data=post(base_url, b'{"question":"no results"}', '/internal/v1/research/run')
    assert status == 200
    assert data['evidence']==[] and data['generation'] is None and data['provider']=='wikipedia-en'
