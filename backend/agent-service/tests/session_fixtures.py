"""Public synthetic inputs only. Used by offline Python/Java/browser integration."""
from dataclasses import replace
from hashlib import sha256
import json
from test_research_session import Model, search, read
from app.web_research.selection import SourceMetadata
from app.web_research.research_session import run_session
from app.web_research.pipeline import ToolFailure
from app.web_research.candidates import parse_searxng


def read_with_metadata(candidate, timeout):
    doc = replace(read(candidate, timeout), paragraphs=('Public topic evidence fallback.',))
    metadata = SourceMetadata(candidate.requested_url, candidate.canonical_url, candidate.host,
        '2026-10-19T00:00:00Z', 'text/html', 1, 'offline-fixture', None, 'unknown', False,
        sha256(json.dumps(doc.paragraphs, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest())
    return replace(doc, metadata=metadata)


class FixtureRunner:
    def __init__(self, session_run=run_session):
        self.session_run = session_run

    def run(self, request):
        question = request.question
        def mutate(stage, data):
            if question == 'empty' and stage == 'review':
                data['coverage'][0].update(state='missing', evidenceIds=[], gap='No usable evidence')
            if question == 'fail report' and stage == 'report':
                data['claims'][0]['evidenceIds'] = ['E16']
            if question == 'fallback' and stage == 'plan':
                data['unexpected'] = True
        model = Model(supplement=question == 'supplement', mutate=mutate)
        if question == 'auth failure':
            def model(*_):
                raise ToolFailure('MODEL_AUTH_ERROR')
        selected_search = (lambda *_: parse_searxng(b'{"results":[]}')) if question == 'empty' else search
        return self.session_run(question, request.language, selected_search, read_with_metadata, model, run_id=request.run_id)
