"""Explicit local fixture lifecycle acceptance, no external provider or MySQL.

Requires no existing debug manager. Starts and owns its manager, then checks
port collision, real HTTP/proxy, isolated H2 restart persistence and job cleanup.
"""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4

import debug_env as debug


def footprint():
    files = []
    for folder in ('backend/java-api/data', 'backend/java-api/target/classes'):
        base = debug.ROOT/folder
        if base.exists():
            files.extend(p for p in base.rglob('*') if p.is_file())
    return {str(p.relative_to(debug.ROOT)): (p.stat().st_size, p.stat().st_mtime_ns) for p in files}


def control(action, expected=True):
    result = subprocess.run([sys.executable, str(debug.ROOT/'scripts/debug_env.py'), action],
                            capture_output=True, text=True, encoding='utf-8', timeout=430)
    data = json.loads(result.stdout)
    assert data['ok'] is expected, data
    return data


def request(path, data=None):
    headers = {'Content-Type': 'application/json', 'Idempotency-Key': uuid4().hex}
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request('http://127.0.0.1:15173'+path, data=body, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=5) as response:
        return json.load(response)


def task(question, expected):
    created=request('/api/v1/research-tasks', {'question':question,'language':'en','researchMode':'web-model'})
    deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        result=request('/api/v1/research-tasks/'+created['id'])
        if result['status'] in ('SUCCEEDED','FAILED'):
            assert result['status']==expected, result['errorCode']
            assert result['modelSession']['session']['outcome']['evidence']
            return result
        time.sleep(.2)
    raise AssertionError('TASK_TIMEOUT')


def check_records(session):
    records = list((debug.HOME/session/'recordings').glob('*/manifest.json'))
    assert len(records) >= 2, 'MISSING_STAGE_RECORDS'
    summary = []
    for manifest_file in records:
        manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
        actions = ['inspect', 'session', 'select', 'report-input']
        if manifest['researchStatus'] == 'SUCCEEDED':
            actions.append('report-check')
        for action in actions:
            completed = subprocess.run([sys.executable, str(debug.ROOT/'scripts/replay_research.py'),
                action, str(manifest_file.parent)], capture_output=True, text=True,
                encoding='utf-8', timeout=15, env={**debug.clean_env(os.environ), 'PYTHONIOENCODING':'utf-8'})
            assert completed.returncode == 0, 'REPLAY_CLI_FAILED_'+action
            value = json.loads(completed.stdout)
            if action == 'session':
                assert value['externalRequests'] == 0
                assert value['session']['outcome']['status'] == manifest['researchStatus']
        summary.append({'recordId':manifest['recordId'], 'status':manifest['researchStatus']})
    return summary


def main():
    before=footprint()
    daily_ports={p:debug.listening(p) for p in (8000,8080,5173,3306,8888)}
    check_dir=debug.ROOT/'logs'/('debug-check-'+uuid4().hex)
    check_dir.mkdir()
    # This script owns the exact handle used in the crash-cleanup test.
    env=debug.clean_env(os.environ)
    env.update(TEMP=str(check_dir), TMP=str(check_dir), PYTHONIOENCODING='utf-8')
    old=(debug.HOME/'current.json').read_text() if (debug.HOME/'current.json').exists() else ''
    with (check_dir/'manager.log').open('w',encoding='utf-8') as log:
        manager=subprocess.Popen([sys.executable,str(debug.ROOT/'scripts/debug_env.py'),'serve'],
            cwd=debug.ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                assert manager.poll() is None, 'MANAGER_EXITED'
                if (debug.HOME/'current.json').exists() and (debug.HOME/'current.json').read_text()!=old:
                    break
                time.sleep(.1)
            assert control('status')['data']['mode']=='fixture'
            with socket.socket() as guard:
                guard.bind(('127.0.0.1',15173)); guard.listen()
                assert control('start',False)['error']=='DEBUG_PORT_IN_USE'
                assert not control('status')['data']['services']
            print('DEBUG_CHECK port_conflict=passed',flush=True)
            first=control('start')['data']
            success=task('Public topic','SUCCEEDED')
            failure=task('fail report','FAILED')
            assert failure['errorCode']=='MODEL_INVALID_RESPONSE'
            records = check_records(first['session'])
            print('DEBUG_CHECK proxy_success_and_failure=passed',flush=True)
            next_status=control('restart-python')['data']
            assert first['services']['python']['pid']!=next_status['services']['python']['pid']
            assert first['services']['java']['pid']==next_status['services']['java']['pid']
            task('Public topic','SUCCEEDED')
            next_status=control('rebuild-java')['data']
            assert first['services']['java']['pid']!=next_status['services']['java']['pid']
            assert request('/api/v1/research-tasks/'+success['id'])==success
            assert request('/api/v1/research-tasks/'+failure['id'])==failure
            assert len(check_records(first['session'])) >= len(records)
            control('restart-frontend')
            assert request('/api/v1/research-tasks/'+success['id'])==success
            print('DEBUG_CHECK independent_restarts_and_h2_persistence=passed',flush=True)
            if '--browser' in sys.argv:
                import shutil
                subprocess.run([shutil.which('node'), str(debug.ROOT/'scripts/check_debug_ui.mjs'),
                    str(check_dir)], cwd=debug.ROOT, env=env, timeout=180, check=True)
            control('stop')
            assert not any(debug.listening(p) for p in debug.PORTS.values())
            assert not control('status')['data']['services']
            control('start')
            assert request('/api/v1/research-tasks/'+success['id'])==success
            # Closing/crashing the manager must also close descendant services.
            manager.kill(); manager.wait(timeout=10)
            deadline=time.monotonic()+15
            while any(debug.listening(p) for p in debug.PORTS.values()) and time.monotonic()<deadline:
                time.sleep(.2)
            assert not any(debug.listening(p) for p in debug.PORTS.values()), 'ORPHAN_SERVICE'
            assert footprint()==before, 'DAILY_FILES_CHANGED'
            assert {p:debug.listening(p) for p in daily_ports}==daily_ports, 'DAILY_PORTS_CHANGED'
            report={'passed':True,'session':first['session'],'fixtureOnly':True,'modelProviderRequests':0,
                    'dailyFilesUnchanged':True,'dailyPortsUnchanged':True,'crashCleanup':True,
                    'successTask':success['id'],'failureTask':failure['id'], 'replayRecords':records,
                    'browserChecked':'--browser' in sys.argv}
            (check_dir/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print('DEBUG_CHECK shutdown_crash_cleanup_daily_isolation=passed',flush=True)
            print(str(check_dir/'result.json'),flush=True)
        finally:
            if manager.poll() is None:
                try: control('shutdown')
                finally:
                    if manager.poll() is None:
                        manager.kill()
                    manager.wait(timeout=15)


if __name__=='__main__':
    main()
