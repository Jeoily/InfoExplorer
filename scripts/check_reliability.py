"""Explicit real local HTTP/crash acceptance with synthetic external tools only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from uuid import uuid4
from debug_env import ROOT, clean_env, listening

directory=ROOT/'logs'/('reliability-check-'+uuid4().hex)
directory.mkdir()
env=clean_env(os.environ)
env.update(JAVA_HOME='E:/DevTools/Java/jdk-21',TEMP=str(directory),TMP=str(directory),
           PYTHONIOENCODING='utf-8',RELIABILITY_DIR=str(directory),
           INFOEXPLORER_EXECUTION_DIR=str(directory/'executions'),
           INFOEXPLORER_WEB_MODEL_ENABLED='true',INFOEXPLORER_MODEL_ENABLED='false',
           PYTHONPATH=os.pathsep.join(str(ROOT/p) for p in ['scripts','backend/agent-service/.web-deps','backend/agent-service','backend/agent-service/tests']))
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
processes={}


def request(path,data=None,key=None,base='http://127.0.0.1:18180/api/v1/research-tasks'):
    headers={'Content-Type':'application/json'}
    if key:headers['Idempotency-Key']=key
    req=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),headers=headers)
    with opener.open(req,timeout=8) as response:return json.load(response)


def wait(get,predicate,seconds=30):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        try:
            value=get()
            if predicate(value):return value
        except (urllib.error.URLError,ConnectionError,TimeoutError):pass
        time.sleep(.15)
    raise AssertionError('LOCAL_ACCEPTANCE_TIMEOUT')


def launch(name,args,cwd=ROOT,extra=None):
    log=(directory/(name+'-'+uuid4().hex+'.log')).open('w',encoding='utf-8')
    process=subprocess.Popen(args,cwd=cwd,env={**env,**(extra or {})},stdin=subprocess.DEVNULL,stdout=log,
        stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    log.close();processes[name]=process
    return process


def stop(name):
    process=processes.pop(name,None)
    if process and process.poll() is None:
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW,timeout=15)
        process.wait(timeout=15)


def start_python():
    launch('python',[sys.executable,'-m','uvicorn','reliability_fixture:app','--host','127.0.0.1','--port','18100'])
    wait(lambda:request('/health',base='http://127.0.0.1:18100'),lambda v:v['status']=='UP')


def start_java(jar):
    launch('java',['E:/DevTools/Java/jdk-21/bin/java.exe','-Djava.io.tmpdir='+str(directory),'-jar',str(jar),
        '--server.port=18180','--agent.service.base-url=http://127.0.0.1:18100',
        '--spring.datasource.url=jdbc:h2:file:'+str(directory/'db').replace('\\','/')+';DB_CLOSE_ON_EXIT=FALSE',
        '--spring.datasource.username=sa','--research.worker.poll-delay-ms=100'])
    wait(lambda:request('/actuator/health',base='http://127.0.0.1:18180'),lambda v:v['status']=='UP')


def create(question,key=None):return request('',{'question':question,'language':'en','researchMode':'web-model'},key or uuid4().hex)
def done(id):return wait(lambda:request('/'+id),lambda t:t['status'] in ('SUCCEEDED','FAILED'))
def stage(id,name):return wait(lambda:request('/'+id+'/progress'),lambda p:p['stage']==name)


def main():
    for port in (18100,18180,15174):assert not listening(port),'TEST_PORT_IN_USE'
    build=directory/'build';build.mkdir()
    for name in ('pom.xml','mvnw.cmd'):shutil.copy2(ROOT/'backend/java-api'/name,build/name)
    for name in ('src','.mvn'):shutil.copytree(ROOT/'backend/java-api'/name,build/name)
    compile=launch('build',['powershell.exe','-NoProfile','-Command',r'& .\mvnw.cmd -o -DskipTests package; exit $LASTEXITCODE'],build)
    assert compile.wait(timeout=180)==0,'BUILD_FAILED'
    jar=build/'target/java-api-0.0.1-SNAPSHOT.jar'
    result={'externalProviderRequests':0,'checks':[]}
    try:
        start_python();start_java(jar)
        # Cancellation while a tool is in flight; queue cancellation never contacts Python.
        task=create('cancel read');p=stage(task['id'],'read')
        queued=create('queued cancel');assert queued['status']=='PENDING'
        q=request('/'+queued['id']+'/cancel',{'expectedRunId':None})
        assert q['errorCode']=='EXECUTION_CANCELLED'
        request('/'+task['id']+'/cancel',{'expectedRunId':p['runId']})
        failed=done(task['id']);assert failed['errorCode']=='EXECUTION_CANCELLED'
        request('/'+task['id']+'/retry',{'failedRunId':failed['runId']})
        success=done(task['id']);assert success['status']=='SUCCEEDED',success['errorCode']
        assert request('/'+task['id']+'/progress')['reused']==2
        result['checks'].append('running_cancel_queued_cancel_retrieval_reuse')
        # Same execution response replay must not call tools/model again.
        count=len((directory/'calls.jsonl').read_text().splitlines())
        request('/internal/v3/research/run',{'runId':success['runId'],'question':'cancel read','language':'en'},base='http://127.0.0.1:18100')
        assert len((directory/'calls.jsonl').read_text().splitlines())==count
        result['checks'].append('duplicate_internal_request_no_extra_calls')
        for service in ('java','python'):
            task=create('restart '+service);p=stage(task['id'],'report')
            stop(service)
            (lambda:start_java(jar) if service=='java' else start_python())()
            failed=done(task['id']);assert failed['status']=='FAILED'
            if service=='java':assert failed['errorCode']=='EXECUTION_INTERRUPTED'
            # Old Python call is cooperatively cancelled; wait for its bounded fixture call.
            if service=='java':time.sleep(5.5)
            request('/'+task['id']+'/retry',{'failedRunId':failed['runId']})
            success=done(task['id']);assert success['status']=='SUCCEEDED',success['errorCode']
            assert request('/'+task['id']+'/progress')['reused']==2
            result['checks'].append(service+'_crash_restart_and_safe_retry')
        deadline=done(create('deadline')['id']);assert deadline['errorCode']=='EXECUTION_DEADLINE'
        result['checks'].append('deadline_terminal_without_report')
        # Browser uses the same real services and isolated data, no external tools.
        launch('frontend',['D:/Program Files/nodejs/node.exe',str(ROOT/'frontend/node_modules/vite/bin/vite.js'),
               '--host','127.0.0.1','--port','15174','--strictPort'],ROOT/'frontend',
               {'INFOEXPLORER_API_URL':'http://127.0.0.1:18180','INFOEXPLORER_DEBUG_UI':'false'})
        wait(lambda:listening(15174),bool)
        browser=launch('browser',['D:/Program Files/nodejs/node.exe',str(ROOT/'scripts/check_reliability_browser.mjs'),str(directory)])
        assert browser.wait(timeout=100)==0,'BROWSER_FAILED'
        result['checks'].append('browser_refresh_cancel_duplicate_submit')
        (directory/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({'ok':True,'directory':str(directory),**result}),flush=True)
    finally:
        for name in list(processes):stop(name)


if __name__=='__main__':main()
