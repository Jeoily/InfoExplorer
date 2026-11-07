"""Run real Java/Python HTTP integration with in-memory search/model fixtures only.

Usage: python tests/run_offline_contract.py [path-to-mvn.cmd]
The Java test profile uses isolated databases; no live providers or credentials.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from app.main import app
from app.model import ModelError, ModelSettings, ReportGenerator, get_report_generator
from app.search import WikipediaSearch, get_search_provider
from app.schemas.search_request import ResearchRequest
from app.planning import QueryPlanner, get_query_planner


class FixtureSearch:
    def __init__(self, language="en"):
        self.language = language
    def search(self, question):
        if question == "EMPTY_RESULT":
            return WikipediaSearch(self.language).parse({"batchcomplete": True}, question)
        return WikipediaSearch(self.language).parse({"query": {"pages": [
            {"title": "Artificial intelligence", "extract": "Public offline example of artificial intelligence."}]}}, question)


retry_fixture_calls = 0


def fixture_transport(settings, body):
    global retry_fixture_calls
    question = json.loads(json.loads(body)["messages"][1]["content"])["question"]
    if question == "RETRY_ONCE":
        retry_fixture_calls += 1
        if retry_fixture_calls == 1:
            raise ModelError("MODEL_TIMEOUT")
    if question in {"MODEL_TIMEOUT", "MODEL_RATE_LIMITED"}:
        raise ModelError(question)
    ref = "E9" if question == "MODEL_INVALID_RESPONSE" else "E1"
    content = {"claims": [{"text": "Offline fixture research result", "evidenceIds": [ref]}],
               "limitations": ["Offline integration fixture; no cloud model was called."]}
    return json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}]}).encode()


def fixture_provider(request: ResearchRequest):
    return FixtureSearch(request.language)


def fixture_planner(request: ResearchRequest):
    if request.question != "PLAN_FIXTURE":
        return QueryPlanner()
    def transport(*_):
        return json.dumps({"choices":[{"finish_reason":"stop","message":{"content":json.dumps(
            {"intent":"Compare public topics","queries":["topic one","topic two"]})}}]}).encode()
    return QueryPlanner(ModelSettings("https://models.example.org/v1","fixture-model","placeholder"),transport)


def main():
    app.dependency_overrides[get_search_provider] = fixture_provider
    app.dependency_overrides[get_query_planner] = fixture_planner
    app.dependency_overrides[get_report_generator] = lambda: ReportGenerator(
        ModelSettings("https://models.example.org/v1", "fixture-model", "test-only-placeholder"), fixture_transport)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Offline test server did not start")
            time.sleep(0.02)
        java_dir = Path(__file__).resolve().parents[2] / "java-api"
        environment = os.environ.copy()
        environment["INFOEXPLORER_TEST_AGENT_URL"] = f"http://127.0.0.1:{port}"
        environment["INFOEXPLORER_TEST_AGENT_MODE"] = "offline"
        environment["INFOEXPLORER_MODEL_ENABLED"] = "false"
        environment.pop("MODEL_API_KEY", None)
        environment.pop("INFOEXPLORER_LIVE_SEARCH", None)
        executable = sys.argv[1] if len(sys.argv) > 1 else str(java_dir / "mvnw.cmd")
        return subprocess.run([executable, "-o", "test"], cwd=java_dir, env=environment,
                              timeout=180, check=False).returncode
    finally:
        server.should_exit = True
        thread.join(5)
        listener.close()
        app.dependency_overrides.clear()
        if thread.is_alive():
            raise RuntimeError("Offline test server did not stop")


if __name__ == "__main__":
    raise SystemExit(main())
