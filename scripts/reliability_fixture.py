"""Explicit offline acceptance server. Never loaded by daily startup scripts."""
import json
import os
from pathlib import Path
import time
from app.main import app
from app.web_research.session_api import get_session_runner
from app.web_research.research_session import run_session
from app.web_research.budget import ExecutionBudget, Limits
from app.web_research.recording import record_run
from session_fixtures import read_with_metadata
from test_research_session import Model, search

directory=Path(os.environ['RELIABILITY_DIR'])


class Runner:
    def run(self,request):
        def logged(stage):
            with (directory/'calls.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps({'runId':request.run_id,'stage':stage})+'\n')
        def find(query,timeout):
            logged('search');return search(query,timeout)
        def read(candidate,timeout):
            logged('read')
            if request.question=='cancel read':time.sleep(5)
            return read_with_metadata(candidate,timeout)
        model=Model()
        def complete(stage,data,timeout):
            logged(stage)
            if request.question in {'restart java','restart python','browser slow'} and stage=='report':time.sleep(5)
            if request.question=='deadline' and stage=='plan':time.sleep(.2)
            return model(stage,data,timeout)
        return record_run(directory/'records','fixture',request.question,request.language,find,read,complete,
            run_id=request.run_id,budget=ExecutionBudget(Limits(total_seconds=.1 if request.question=='deadline' else 150,model_request_seconds=45)))


app.dependency_overrides[get_session_runner]=Runner
