"""Single-worker durable execution identities and public retrieval reuse.

This is not model replay or a distributed queue. No provider credentials or
raw model output are stored here. Cancel is cooperative at stage boundaries.
"""
from contextvars import ContextVar
from contextlib import contextmanager, asynccontextmanager
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from time import time, monotonic
from uuid import UUID

from fastapi import APIRouter, HTTPException
from app.web_research.budget import BudgetExceeded

@asynccontextmanager
async def lifespan(app):
    recover()
    yield


router = APIRouter(lifespan=lifespan)
current = ContextVar('research_execution', default=None)


def recover():
    with connection() as db:
        db.execute("UPDATE execution SET state='INTERRUPTED',updated=? WHERE state='RUNNING'",(time(),))


def root():
    configured = os.environ.get('INFOEXPLORER_EXECUTION_DIR')
    if not configured and os.environ.get('DEBUG_SESSION'):
        configured = str(Path(os.environ['DEBUG_SESSION'])/'executions')
    return Path(configured) if configured else Path(__file__).resolve().parents[2]/'data'/'executions'


@contextmanager
def connection():
    directory = root()
    directory.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(directory/'control.sqlite3', timeout=5)
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS execution (id TEXT PRIMARY KEY, identity TEXT, state TEXT, stage TEXT, cancelled INTEGER NOT NULL DEFAULT 0, updated REAL, response TEXT, reused INTEGER NOT NULL DEFAULT 0)')
    db.execute('CREATE TABLE IF NOT EXISTS retrieval (run_id TEXT, key TEXT, kind TEXT, value TEXT, created REAL, PRIMARY KEY(run_id,key))')
    try:
        with db:
            yield db
    finally:
        db.close()


def canonical(run_id):
    try:
        return str(UUID(run_id))
    except (ValueError, TypeError):
        raise HTTPException(400, detail={'code':'INVALID_RUN_ID'}) from None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


class Execution:
    def __init__(self, request, mode):
        self.id = request.run_id
        self.identity = digest([request.question, request.language, mode])
        self.parent = request.resume_from
        self.cached = None
        self.deadline = monotonic()+150

    def begin(self):
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM execution WHERE id=?', (self.id,)).fetchone()
            if row:
                if row['cancelled']:
                    raise HTTPException(409, detail={'code':'EXECUTION_CANCELLED'})
                if row['identity'] != self.identity:
                    raise HTTPException(409, detail={'code':'EXECUTION_ID_CONFLICT'})
                if row['state']=='DONE' and row['response']:
                    self.cached = json.loads(row['response'])
                    return
                # Includes a previous process crash: never silently repeat a model request.
                raise HTTPException(409, detail={'code':'EXECUTION_ALREADY_STARTED'})
            if self.parent:
                parent = db.execute('SELECT identity FROM execution WHERE id=?', (self.parent,)).fetchone()
                if parent and parent['identity'] != self.identity:
                    raise HTTPException(409, detail={'code':'RESUME_ID_CONFLICT'})
            db.execute('INSERT INTO execution(id,identity,state,stage,updated) VALUES(?,?,?,?,?)',
                       (self.id,self.identity,'RUNNING','starting',time()))

    def check(self):
        with connection() as db:
            row = db.execute('SELECT cancelled FROM execution WHERE id=?',(self.id,)).fetchone()
        if row and row['cancelled']:
            raise BudgetExceeded('EXECUTION_CANCELLED')
        if monotonic() >= self.deadline:
            raise BudgetExceeded('EXECUTION_DEADLINE')

    def stage(self, name):
        self.check()
        with connection() as db:
            db.execute('UPDATE execution SET stage=?,updated=? WHERE id=?',(name,time(),self.id))

    def finish(self, response=None):
        raw = json.dumps(response, ensure_ascii=False) if response is not None else None
        with connection() as db:
            db.execute('UPDATE execution SET state=?,stage=?,response=?,updated=? WHERE id=?',
                       ('DONE' if raw else 'FAILED','finished',raw,time(),self.id))

    def tool(self, kind, tool, argument, timeout):
        self.stage('search' if kind=='search' else 'read')
        value = argument if isinstance(argument,str) else asdict(argument)
        key = digest(['retrieval-v1',kind,value])
        cached = None
        if self.parent:
            with connection() as db:
                cached = db.execute('SELECT value,created FROM retrieval WHERE run_id=? AND key=? AND created>?',
                                    (self.parent,key,time()-3600)).fetchone()
        if cached:
            from app.web_research.recording import batch, document
            result = (batch if kind=='search' else document)(json.loads(cached['value']))
            with connection() as db:
                db.execute('UPDATE execution SET reused=reused+1 WHERE id=?',(self.id,))
        else:
            result = tool(argument, min(timeout,max(.001,self.deadline-monotonic())))
        raw = json.dumps(asdict(result),ensure_ascii=False)
        # At most five searches/eight documents per attempt, bounded by the pipeline.
        if len(raw.encode()) <= 1024*1024:
            with connection() as db:
                db.execute('INSERT OR REPLACE INTO retrieval VALUES(?,?,?,?,?)',
                           (self.id,key,kind,raw,cached['created'] if cached else time()))
        self.check()
        return result


def tool_call(kind, tool, argument, timeout):
    if getattr(tool, '_records_tools', False):
        return tool(argument,timeout)
    execution = current.get()
    return execution.tool(kind,tool,argument,timeout) if execution else tool(argument,timeout)


@router.get('/internal/research/executions/{run_id}')
def status(run_id: str):
    with connection() as db:
        row = db.execute('SELECT * FROM execution WHERE id=?',(canonical(run_id),)).fetchone()
    if not row:
        raise HTTPException(404,detail={'code':'EXECUTION_NOT_FOUND'})
    return {'runId':row['id'],'state':row['state'],'stage':row['stage'],
            'cancelRequested':bool(row['cancelled']),'updatedAt':int(row['updated']*1000),'reused':row['reused']}


@router.post('/internal/research/executions/{run_id}/cancel')
def cancel(run_id: str):
    run_id = canonical(run_id)
    with connection() as db:
        # A tombstone closes cancel-before-start races. Completed output remains immutable.
        db.execute("INSERT OR IGNORE INTO execution(id,state,stage,cancelled,updated) VALUES(?,'CANCELLED','finished',1,?)",(run_id,time()))
        db.execute("UPDATE execution SET cancelled=1,updated=? WHERE id=? AND state='RUNNING'",(time(),run_id))
    return {'runId':run_id,'accepted':True}
