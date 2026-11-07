"""Local fixed-action supervisor. Credentials stay in memory/child environment.

Not a security boundary against code edited by the same local Windows user.
No HTTP control port, shell command requests, persistent credentials or retries.
The private per-session request directory is only for this project's local agent.
"""
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / 'backend/java-api'
PYTHON = ROOT / 'backend/agent-service'
MYSQL = Path('C:/Program Files/MySQL/MySQL Server 8.4/bin')
ACTIONS = {'check', 'python-start', 'python-stop', 'mysql-test', 'java-deploy', 'java-stop', 'shutdown'}


def clean_env(source):
    return {k: v for k, v in source.items() if not k.upper().startswith(
        ('MYSQL', 'MODEL_', 'INFOEXPLORER_', 'SPRING_', 'SEARXNG_SECRET', 'UNATTENDED_'))}


def write_json(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def listening(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=1):
            return True
    except OSError:
        return False


def validate_request(data):
    if not isinstance(data, dict) or set(data) != {'id', 'action'}:
        raise ValueError('INVALID_REQUEST')
    if not isinstance(data['id'], str) or not re.fullmatch(r'[a-f0-9]{32}', data['id']):
        raise ValueError('INVALID_REQUEST_ID')
    if not isinstance(data['action'], str) or data['action'] not in ACTIONS:
        raise ValueError('INVALID_ACTION')
    return data['id'], data['action']


class Supervisor:
    def __init__(self, directory, secrets):
        self.directory, self.secrets = directory, secrets
        self.children = {}
        self.base = clean_env(os.environ)
        self.java = shutil.which('java')
        if not self.java:
            raise ValueError('JAVA_NOT_FOUND')

    def env(self, purpose):
        env = self.base.copy()
        if purpose == 'python':
            env.update(PYTHONPATH=f'{PYTHON / ".web-deps"};{PYTHON}',
                MODEL_BASE_URL='https://api.agnes-ai.cn/v1', MODEL_ALLOWED_HOST='api.agnes-ai.cn',
                MODEL_NAME='agnes-2.5-flash', MODEL_API_KEY=self.secrets['model'],
                INFOEXPLORER_WEB_ENABLED='true', INFOEXPLORER_WEB_MODEL_ENABLED='true',
                INFOEXPLORER_MODEL_ENABLED='false', INFOEXPLORER_PLANNING_ENABLED='false',
                INFOEXPLORER_MODEL_DIAGNOSTICS='true')
        elif purpose in {'test', 'app'}:
            env.update(MYSQL_HOST='127.0.0.1', MYSQL_PORT='3306', MYSQL_DATABASE='infoexplorer',
                       MYSQL_USER='root' if purpose == 'test' else 'infoexplorer_app',
                       MYSQL_PASSWORD=self.secrets[purpose])
            if purpose == 'test':
                env['INFOEXPLORER_MYSQL_TEST'] = '1'
        elif purpose in {'root-cli', 'app-cli'}:
            env['MYSQL_PWD'] = self.secrets['test' if purpose == 'root-cli' else 'app']
        return env

    def launch(self, argv, purpose, label, cwd=JAVA):
        # No new console window; children have their own process group for cleanup.
        process = subprocess.Popen(argv, cwd=cwd, env=self.env(purpose),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
        path = self.directory / (label + '-' + uuid4().hex + '.log')
        secrets = tuple(v for v in self.secrets.values() if v)
        def drain():
            with path.open('w', encoding='utf-8') as output:
                for raw in iter(process.stdout.readline, b''):
                    line = raw.decode('utf-8', errors='replace')
                    for secret in secrets:
                        line = line.replace(secret, '[REDACTED]')
                    output.write(line)
                    output.flush()
            process.stdout.close()
        thread = threading.Thread(target=drain, daemon=True)
        thread.start()
        return process, thread, str(path)

    def stop(self, entry):
        process, thread, _ = entry
        if process.poll() is None:
            if os.name == 'nt':
                # Only the exact child still held by this supervisor, never a port owner.
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                process.terminate()
            process.wait(timeout=20)
        thread.join(timeout=5)

    def run(self, argv, purpose, label, timeout=600):
        entry = self.launch(argv, purpose, label)
        try:
            code = entry[0].wait(timeout=timeout)
            entry[1].join(timeout=5)
            if code:
                raise ValueError(label.upper().replace('-', '_') + '_FAILED')
            return entry[2]
        finally:
            self.stop(entry)

    def maven(self, arguments, purpose, label):
        # Arguments are fixed in code, not taken from a request file.
        command = '& .\\mvnw.cmd -o ' + arguments + '; exit $LASTEXITCODE'
        return self.run(['powershell.exe', '-NoProfile', '-Command', command], purpose, label)

    def idle(self):
        if not listening(8080):
            return
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for status in ('RUNNING', 'PENDING'):
            with opener.open('http://127.0.0.1:8080/api/v1/research-tasks?status=' + status,
                             timeout=5) as response:
                page = json.load(response)
            if not isinstance(page, dict) or not isinstance(page.get('items'), list):
                raise ValueError('CANNOT_CONFIRM_IDLE')
            if page['items']:
                raise ValueError('TASKS_ACTIVE_WAIT_BEFORE_STOP')

    def stop_service(self, name):
        self.idle()
        entry = self.children.get(name)
        if entry:
            self.stop(entry)
            del self.children[name]

    def wait_health(self, name, port, path):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(90):
            if self.children[name][0].poll() is not None:
                raise ValueError(name.upper() + '_EXITED')
            try:
                with opener.open(f'http://127.0.0.1:{port}{path}', timeout=1) as response:
                    if json.load(response).get('status') == 'UP':
                        return
            except (OSError, ValueError):
                pass
            time.sleep(1)
        self.stop(self.children.pop(name))
        raise ValueError(name.upper() + '_START_TIMEOUT')

    def execute(self, action):
        if action == 'check':
            for user, purpose in [('root', 'root-cli'), ('infoexplorer_app', 'app-cli')]:
                args = [str(MYSQL / 'mysql.exe'), '--no-defaults', '--no-login-paths',
                        '--host=127.0.0.1', '--port=3306', '--ssl-mode=REQUIRED', '--user=' + user,
                        '--batch', '--execute=SELECT 1']
                if user == 'infoexplorer_app':
                    args.append('--database=infoexplorer')
                self.run(args, purpose, 'check-' + user, timeout=20)
            self.run([sys.executable, '-c',
                      'from app.web_research.model_completion import JsonCompletion; JsonCompletion.from_env()'],
                     'python', 'model-config', timeout=20)
        elif action == 'python-start':
            self.stop_service('python')
            if listening(8000):
                raise ValueError('PORT_8000_ALREADY_USED')
            self.children['python'] = self.launch([sys.executable, '-m', 'uvicorn', 'app.main:app',
                '--host', '127.0.0.1', '--port', '8000', '--workers', '1'], 'python', 'python', PYTHON)
            self.wait_health('python', 8000, '/health')
        elif action in {'java-stop', 'python-stop'}:
            self.stop_service(action.split('-')[0])
        elif action == 'mysql-test':
            if listening(8080):
                raise ValueError('STOP_JAVA_BEFORE_COMPILATION')
            return {'log': self.maven("'-Dtest=MySqlIntegrationTests' test", 'test', 'mysql-test')}
        elif action == 'java-deploy':
            self.stop_service('java')
            if listening(8080):
                raise ValueError('PORT_8080_ALREADY_USED')
            # Must pass both isolated suites before touching the daily database.
            self.maven('test', 'none', 'java-tests')
            self.maven("'-Dtest=MySqlIntegrationTests' test", 'test', 'mysql-test')
            self.maven("'-DskipTests' package", 'none', 'java-package')
            backup = ROOT / 'backups/mysql' / ('unattended_' + uuid4().hex + '.sql')
            backup.parent.mkdir(parents=True, exist_ok=True)
            self.run([str(MYSQL / 'mysqldump.exe'), '--no-defaults', '--no-login-paths',
                '--host=127.0.0.1', '--port=3306', '--user=root', '--ssl-mode=REQUIRED',
                '--single-transaction', '--quick', '--no-tablespaces', '--set-gtid-purged=OFF',
                '--routines', '--events', '--triggers', '--default-character-set=utf8mb4',
                '--result-file=' + str(backup), '--databases', 'infoexplorer'], 'root-cli', 'backup')
            if not backup.exists() or backup.stat().st_size == 0:
                raise ValueError('BACKUP_EMPTY')
            with backup.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            write_json(backup.with_suffix('.metadata.json'),
                {'sha256': digest, 'bytes': backup.stat().st_size, 'restoreVerified': False})
            temp = JAVA / 'target/runtime-temp' / uuid4().hex
            temp.mkdir(parents=True)
            self.children['java'] = self.launch([self.java, '-Dspring.devtools.restart.enabled=false',
                '-Djava.io.tmpdir=' + str(temp), '-jar',
                str(JAVA / 'target/java-api-0.0.1-SNAPSHOT.jar'), '--spring.profiles.active=mysql',
                '--server.address=127.0.0.1'], 'app', 'java')
            self.wait_health('java', 8080, '/actuator/health')
            return {'backup': str(backup), 'sha256': digest}
        elif action == 'shutdown':
            self.idle()
            return {'shutdown': True}
        else:
            raise ValueError('INVALID_ACTION')
        return {}

    def close(self):
        for entry in list(self.children.values()):
            self.stop(entry)
        self.children.clear()
        self.secrets.clear()


def main():
    if not listening(3306):
        print('Start MySQL84 in an administrator PowerShell, then run this again.')
        return 1
    if listening(8000) or listening(8080):
        print('Stop existing Python/Java services first. MySQL must remain running.')
        return 1
    print('Local unattended preparation. Keep this window open. Ctrl+C stops owned services.')
    print('Passwords/keys are hidden; never saved. Daily Java deploy requires tests and backup.')
    secrets = {name: getpass.getpass(prompt) for name, prompt in (
        ('test', 'MySQL root password (tests/backup): '),
        ('app', 'MySQL infoexplorer_app password: '),
        ('model', 'Agnes API key (confirmed free; max 10 research attempts this goal): '))}
    if not all(secrets.values()):
        print('EMPTY_CREDENTIAL: restart preparation; do not send credentials to chat.')
        return 1
    directory = ROOT / 'logs/unattended' / uuid4().hex
    directory.mkdir(parents=True)
    manager = Supervisor(directory, secrets)
    try:
        manager.execute('check')
        write_json(directory.parent / 'current.json', {'session': str(directory), 'pid': os.getpid(),
            'status': 'ready', 'modelAttemptLimit': 10})
        print('READY - tell Codex preparation is ready. Keep this window open.')
        seen = set()
        while True:
            for path in sorted(directory.glob('*.request.json')):
                if path.name in seen:
                    continue
                seen.add(path.name)
                result = {'status': 'failed'}
                try:
                    if path.stat().st_size > 1024:
                        raise ValueError('REQUEST_TOO_LARGE')
                    identity, action = validate_request(json.loads(path.read_text(encoding='utf-8-sig')))
                    write_json(directory / 'status.json', {'action': action, 'id': identity, 'status': 'running'})
                    result = {'status': 'passed', **manager.execute(action)}
                except Exception as error:
                    # Only controlled error codes. Never serialize exception input/credentials.
                    code = str(error) if isinstance(error, ValueError) else type(error).__name__
                    result['code'] = code if re.fullmatch(r'[A-Z_]{3,80}', code) else 'ACTION_FAILED'
                write_json(path.with_name(path.name.replace('.request.json', '.result.json')), result)
                write_json(directory / 'status.json', result)
                print('Action finished:', result['status'], result.get('code', ''))
                if result.get('shutdown'):
                    return 0
            time.sleep(1)
    except KeyboardInterrupt:
        print('Stopping owned services. Interrupted tasks may require retry later.')
        return 0
    except Exception:
        print('PREPARATION_FAILED. Check redacted logs in logs/unattended; do not send credentials.')
        return 1
    finally:
        manager.close()
        write_json(directory.parent / 'current.json', {'session': str(directory), 'status': 'stopped'})


if __name__ == '__main__':
    raise SystemExit(main())
