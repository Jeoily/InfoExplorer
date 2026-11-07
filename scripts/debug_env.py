"""Local opt-in isolated development supervisor, not the daily deployment tool.

Fixed file-queue actions, owned children only, fresh H2, separate Java build.
No MySQL credentials, migrations, Docker changes, or arbitrary shell commands.
"""
import argparse
import ctypes
from ctypes import wintypes
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / 'logs/debug'
PYTHON = ROOT / 'backend/agent-service'
PORTS = {'python': 18000, 'java': 18080, 'frontend': 15173}
ACTIONS = {'status', 'start', 'stop', 'restart-python', 'rebuild-java', 'restart-frontend', 'shutdown'}
ERRORS = {'INVALID_REQUEST', 'IDLE_CHECK_FAILED', 'TASKS_ACTIVE', 'ALREADY_STARTED',
          'DEBUG_PORT_IN_USE', 'BUILD_FAILED', 'JAR_MISSING', 'CHILD_EXITED', 'HEALTH_TIMEOUT'}


def error_code(error):
    code = str(error)
    return code if code in ERRORS else 'OPERATION_FAILED'


def write_json(path, value):
    tmp = path.with_suffix('.writing')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def clean_env(source):
    # Allowlist OS/runtime variables rather than inheriting Spring/DB/tool options.
    allowed = {'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATH', 'PATHEXT', 'JAVA_HOME',
               'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA', 'PROGRAMFILES',
               'PROGRAMFILES(X86)', 'HOMEDRIVE', 'HOMEPATH', 'NUMBER_OF_PROCESSORS',
               'PROCESSOR_ARCHITECTURE', 'OS'}
    return {k: v for k, v in source.items() if k.upper() in allowed}


def listening(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=.3):
            return True
    except OSError:
        return False


def get_json(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=2) as response:
        return json.load(response)


def windows_job():
    """Attach this supervisor to a kill-on-close job before creating children.

    Windows closes the handle on supervisor exit, including console close/crash.
    Do not close it early: the supervisor itself belongs to the job.
    """
    if os.name != 'nt':
        raise RuntimeError('WINDOWS_REQUIRED')
    class Basic(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                    ('flags', wintypes.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t),
                    ('active', wintypes.DWORD), ('affinity', ctypes.c_size_t),
                    ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]
    class Io(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ('r', 'w', 'o', 'rb', 'wb', 'ob')]
    class Extended(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', Io), ('pm', ctypes.c_size_t), ('jm', ctypes.c_size_t),
                    ('pp', ctypes.c_size_t), ('jp', ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    handle = kernel.CreateJobObjectW(None, None)
    info = Extended()
    info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not handle or not kernel.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
        raise RuntimeError('DEBUG_JOB_SETUP_FAILED')
    if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
        raise RuntimeError('DEBUG_JOB_ASSIGN_FAILED')
    return handle


def validate_request(data):
    if (not isinstance(data, dict) or set(data) != {'id', 'action'}
            or not isinstance(data['id'], str) or not re.fullmatch('[a-f0-9]{32}', data['id'])
            or data['action'] not in ACTIONS):
        raise ValueError('INVALID_REQUEST')
    return data['id'], data['action']


class Supervisor:
    def __init__(self, directory, mode='fixture', model=None, record_public=False):
        self.directory, self.mode, self.model = directory, mode, model or {}
        self.children = {}
        self.record_public = record_public
        self.temp = directory / 'tmp'
        self.temp.mkdir()
        self.java = shutil.which('java')
        self.node = shutil.which('node')
        if not self.java or not self.node:
            raise RuntimeError('JAVA_OR_NODE_MISSING')

    def env(self, service):
        env = clean_env(os.environ)
        env.update(TEMP=str(self.temp), TMP=str(self.temp), PYTHONIOENCODING='utf-8')
        if service == 'python':
            env.update(PYTHONPATH=os.pathsep.join(map(str, [ROOT/'scripts', PYTHON/'.web-deps', PYTHON])),
                       DEBUG_MODE=self.mode, DEBUG_SESSION=str(self.directory),
                       DEBUG_RECORD_PUBLIC='true' if self.record_public else 'false',
                       INFOEXPLORER_WEB_MODEL_ENABLED='true', INFOEXPLORER_MODEL_ENABLED='false',
                       INFOEXPLORER_WEB_ENABLED='false', INFOEXPLORER_PLANNING_ENABLED='false',
                       INFOEXPLORER_MODEL_DIAGNOSTICS='false')
            if self.mode == 'live':
                env.update(self.model)
        elif service == 'frontend':
            env['INFOEXPLORER_API_URL'] = 'http://127.0.0.1:18080'
            env['INFOEXPLORER_DEBUG_UI'] = 'true'
        return env

    def launch(self, name, argv, cwd):
        process = subprocess.Popen(argv, cwd=cwd, env=self.env(name), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW)
        log = self.directory / (name + '-' + uuid4().hex + '.log')
        secret = self.model.get('MODEL_API_KEY', '')
        def drain():
            with log.open('w', encoding='utf-8') as output:
                for raw in iter(process.stdout.readline, b''):
                    line = raw.decode('utf-8', errors='replace')
                    output.write(line.replace(secret, '[REDACTED]') if secret else line)
                    output.flush()
            process.stdout.close()
        thread = threading.Thread(target=drain, daemon=True)
        thread.start()
        return process, thread, log

    def stop_entry(self, entry):
        process, thread, _ = entry
        if process.poll() is None:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20,
                creationflags=subprocess.CREATE_NO_WINDOW)
            process.wait(timeout=20)
        thread.join(timeout=5)

    def stop_all(self):
        for name in ('frontend', 'java', 'python'):
            if name in self.children:
                self.stop_entry(self.children.pop(name))

    def ensure_idle(self):
        entry = self.children.get('java')
        if entry and entry[0].poll() is None:
            for state in ('RUNNING', 'PENDING'):
                page = get_json('http://127.0.0.1:18080/api/v1/research-tasks?status=' + state)
                if not isinstance(page.get('items'), list):
                    raise RuntimeError('IDLE_CHECK_FAILED')
                if page['items']:
                    raise RuntimeError('TASKS_ACTIVE')

    def build(self):
        # Copy sources, never compile the daily target directory/devtools tree.
        build = self.directory / ('build-' + uuid4().hex)
        build.mkdir()
        original = ROOT / 'backend/java-api'
        for name in ('pom.xml', 'mvnw.cmd'):
            shutil.copy2(original/name, build/name)
        for name in ('src', '.mvn'):
            shutil.copytree(original/name, build/name)
        entry = self.launch('build', ['powershell.exe', '-NoProfile', '-Command',
            r'& .\mvnw.cmd -o -DskipTests package; exit $LASTEXITCODE'], build)
        try:
            if entry[0].wait(timeout=300):
                raise RuntimeError('BUILD_FAILED')
        finally:
            self.stop_entry(entry)
        self.jar = build/'target/java-api-0.0.1-SNAPSHOT.jar'
        if not self.jar.is_file():
            raise RuntimeError('JAR_MISSING')

    def command(self, name):
        if name == 'python':
            return [sys.executable, '-m', 'uvicorn', 'debug_agent:app', '--host', '127.0.0.1',
                    '--port', '18000', '--workers', '1', '--no-access-log'], ROOT
        if name == 'frontend':
            return [self.node, str(ROOT/'frontend/node_modules/vite/bin/vite.js'),
                    '--host', '127.0.0.1', '--port', '15173', '--strictPort'], ROOT/'frontend'
        database = (self.directory/'db/infoexplorer-debug').as_posix()
        return [self.java, '-Dspring.devtools.restart.enabled=false', '-Djava.io.tmpdir='+str(self.temp),
                '-jar', str(self.jar), '--server.address=127.0.0.1', '--server.port=18080',
                '--spring.profiles.active=debug', '--spring.config.location=classpath:/application.properties',
                '--spring.datasource.url=jdbc:h2:file:'+database+';DB_CLOSE_ON_EXIT=FALSE',
                '--spring.datasource.driver-class-name=org.h2.Driver', '--spring.datasource.username=sa',
                '--spring.datasource.password=', '--spring.flyway.locations=classpath:db/migration',
                '--spring.flyway.clean-disabled=true', '--agent.service.base-url=http://127.0.0.1:18000',
                '--agent.service.research-read-timeout-ms=175000'], self.directory

    def start_one(self, name):
        if listening(PORTS[name]):
            raise RuntimeError('DEBUG_PORT_IN_USE')
        argv, cwd = self.command(name)
        self.children[name] = self.launch(name, argv, cwd)
        path = '/actuator/health' if name == 'java' else '/health'
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if self.children[name][0].poll() is not None:
                raise RuntimeError('CHILD_EXITED')
            try:
                if name == 'frontend':
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    with opener.open('http://127.0.0.1:15173', timeout=1) as response:
                        if response.status == 200:
                            return
                else:
                    health = get_json(f'http://127.0.0.1:{PORTS[name]}{path}')
                    if health.get('status') == 'UP':
                        if name != 'python' or health.get('session') == self.directory.name:
                            return
            except (OSError, ValueError):
                pass
            time.sleep(.3)
        raise RuntimeError('HEALTH_TIMEOUT')

    def status(self):
        return {'session': self.directory.name, 'mode': self.mode, 'database': 'isolated-h2',
                'services': {name: {'pid': entry[0].pid, 'running': entry[0].poll() is None,
                                    'port': PORTS[name], 'log': str(entry[2])}
                             for name, entry in self.children.items()}}

    def execute(self, action):
        if action == 'status':
            return self.status()
        self.ensure_idle()
        if action in {'stop', 'shutdown'}:
            self.stop_all()
        elif action == 'start':
            if self.children:
                raise RuntimeError('ALREADY_STARTED')
            if any(listening(p) for p in PORTS.values()):
                raise RuntimeError('DEBUG_PORT_IN_USE')
            try:
                self.build()
                for name in ('python', 'java', 'frontend'):
                    self.start_one(name)
            except Exception:
                self.stop_all()
                raise
        else:
            name = {'restart-python': 'python', 'rebuild-java': 'java', 'restart-frontend': 'frontend'}[action]
            if name in self.children:
                self.stop_entry(self.children.pop(name))
            try:
                if name == 'java':
                    self.build()
                self.start_one(name)
            except Exception:
                if name in self.children:
                    self.stop_entry(self.children.pop(name))
                raise
        return self.status()


def control(action):
    current = json.loads((HOME/'current.json').read_text(encoding='utf-8'))
    session = current['session']
    if not isinstance(session, str) or not re.fullmatch('[a-f0-9]{32}', session):
        raise RuntimeError('INVALID_SESSION')
    directory = HOME/session
    request_id = uuid4().hex
    write_json(directory/(request_id+'.request.json'), {'id': request_id, 'action': action})
    # status is a fresh request, never inferred from a stale PID or status file.
    deadline = time.monotonic() + (8 if action == 'status' else 420)
    result = directory/(request_id+'.result.json')
    while time.monotonic() < deadline:
        if result.exists():
            data = json.loads(result.read_text(encoding='utf-8'))
            print(json.dumps(data, ensure_ascii=False))
            return 0 if data['ok'] else 1
        time.sleep(.2)
    print(json.dumps({'ok': False, 'error': 'NO_REPLY_DO_NOT_RESUBMIT', 'request': request_id,
                      'result': str(result)}))
    return 1


def serve(args):
    job = windows_job()  # retained for process lifetime
    HOME.mkdir(parents=True, exist_ok=True)
    # Lock prevents two supervisors sharing the same fixed debug ports/current pointer.
    import msvcrt
    guard = (HOME/'manager.lock').open('a+b')
    guard.seek(0)
    try:
        msvcrt.locking(guard.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        raise RuntimeError('DEBUG_MANAGER_ALREADY_RUNNING') from None
    directory = HOME/uuid4().hex
    directory.mkdir()
    model = {}
    if args.live_model:
        if not all((args.base_url, args.allowed_host, args.model, args.attempts)):
            raise RuntimeError('LIVE_CONFIG_AND_BUDGET_REQUIRED')
        model = dict(MODEL_BASE_URL=args.base_url, MODEL_ALLOWED_HOST=args.allowed_host,
                     MODEL_NAME=args.model, MODEL_API_KEY=getpass.getpass('API key (hidden): '))
        # Validate format locally without a provider request or environment dump.
        sys.path.insert(0, str(PYTHON))
        from unittest.mock import patch
        from app.model import ModelSettings
        with patch.dict(os.environ, {**model, 'INFOEXPLORER_WEB_MODEL_ENABLED': 'true'}, clear=True):
            ModelSettings.from_env(enabled_variable='INFOEXPLORER_WEB_MODEL_ENABLED')
    write_json(directory/'budget.json', {'limit': args.attempts if args.live_model else 0, 'used': 0})
    supervisor = Supervisor(directory, 'live' if args.live_model else 'fixture', model, args.record_public)
    write_json(HOME/'current.json', {'session': directory.name})
    print('READY: isolated debug manager; use control start. Mode='+supervisor.mode, flush=True)
    try:
        while True:
            for path in sorted(directory.glob('*.request.json')):
                request_id = path.name.split('.')[0]
                result = directory/(request_id+'.result.json')
                if result.exists():
                    continue
                action = None
                try:
                    if path.stat().st_size > 1024:
                        raise ValueError('INVALID_REQUEST')
                    request_id2, action = validate_request(json.loads(path.read_text(encoding='utf-8-sig')))
                    if request_id2 != request_id:
                        raise ValueError('INVALID_REQUEST')
                    output = {'ok': True, 'data': supervisor.execute(action)}
                except Exception as error:
                    # Only our fixed codes; no arbitrary exception details/credentials.
                    output = {'ok': False, 'error': error_code(error)}
                write_json(result, output)
                if action == 'shutdown' and output['ok']:
                    return
            time.sleep(.2)
    finally:
        supervisor.stop_all()
        write_json(directory/'closed.json', {'closed': True})
        guard.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['serve', *sorted(ACTIONS)])
    parser.add_argument('--live-model', action='store_true')
    parser.add_argument('--record-public', action='store_true')
    parser.add_argument('--base-url')
    parser.add_argument('--allowed-host')
    parser.add_argument('--model')
    parser.add_argument('--attempts', type=int, choices=range(1, 11))
    args = parser.parse_args()
    try:
        if args.action == 'serve':
            serve(args)
            return 0
        return control(args.action)
    except KeyboardInterrupt:
        return 0
    except Exception:
        print('DEBUG_SETUP_FAILED: check prerequisites or existing debug manager; no services reused.', flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
