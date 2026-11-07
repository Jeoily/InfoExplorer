"""Opt-in real HTTP/public search smoke. Owns a temporary local server, no DB/model."""
import argparse
import json
import os
import socket
import threading
import time
from urllib.request import Request, build_opener, ProxyHandler
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', required=True)
    parser.parse_args()
    os.environ['INFOEXPLORER_WEB_ENABLED'] = 'true'
    os.environ['INFOEXPLORER_MODEL_ENABLED'] = 'false'
    import uvicorn
    from app.main import app
    from app.web_research.api import WebResponse
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError('Temporary server did not start')
            time.sleep(0.05)
        run_id = str(uuid4())
        request = Request(f'http://127.0.0.1:{port}/internal/v2/research/run',
            data=json.dumps({'runId': run_id, 'question': 'Python http.client documentation',
                             'language': 'en'}).encode(),
            headers={'Content-Type': 'application/json'})
        with build_opener(ProxyHandler({})).open(request, timeout=170) as response:
            raw = response.read(512 * 1024 + 1)
        if len(raw) > 512 * 1024:
            raise RuntimeError('Response size exceeded contract')
        result = WebResponse.model_validate_json(raw)
        outcome = result.outcome
        assert outcome.run_id == run_id
        assert outcome.usage.model_calls == 0
        assert outcome.review_snapshot is None
        summary = {'schema': result.schema_version, 'mode': result.mode,
            'status': outcome.status, 'reason': outcome.completion_reason,
            'coverage': outcome.coverage, 'responseBytes': len(raw),
            'evidenceCount': len(outcome.evidence),
            'readSources': sum(s.status == 'READ' for s in outcome.sources),
            'sourceErrors': [s.error_code for s in outcome.sources if s.error_code],
            'warnings': [w for q in outcome.queries for w in q.warnings],
            'usage': outcome.usage.model_dump(by_alias=True)}
        print(json.dumps(summary, ensure_ascii=True))
        return 0 if outcome.status == 'SUCCEEDED' and outcome.evidence else 1
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        if thread.is_alive():
            raise RuntimeError('Temporary server did not stop')


if __name__ == '__main__':
    raise SystemExit(main())
