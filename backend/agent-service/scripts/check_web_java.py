"""Explicit public search through Java -> Python -> SearXNG, isolated H2 only."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import threading
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', required=True, action='store_true')
    parser.parse_args()
    os.environ['INFOEXPLORER_WEB_ENABLED'] = 'true'
    os.environ['INFOEXPLORER_MODEL_ENABLED'] = 'false'
    os.environ['INFOEXPLORER_PLANNING_ENABLED'] = 'false'
    import uvicorn
    from app.main import app
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
                raise RuntimeError('Temporary Python server did not start')
            time.sleep(.05)
        java = Path(__file__).resolve().parents[2] / 'java-api'
        environment = os.environ.copy()
        environment['INFOEXPLORER_WEB_LIVE_TEST'] = '1'
        environment['INFOEXPLORER_TEST_AGENT_URL'] = f'http://127.0.0.1:{port}'
        log = java / 'target' / 'web-java-live.log'
        log.parent.mkdir(exist_ok=True)
        with log.open('w', encoding='utf-8') as stream:
            result = subprocess.run([str(java / 'mvnw.cmd'), '-o', '-Dtest=WebLiveIntegrationTests', 'test'],
                                    cwd=java, env=environment, stdout=stream, stderr=subprocess.STDOUT, timeout=240)
        for line in log.read_text(encoding='utf-8', errors='replace').splitlines():
            if any(marker in line for marker in ('LIVE_WEB_CHECK', 'Tests run:', 'BUILD SUCCESS', 'BUILD FAILURE', '[ERROR]')):
                print(line)
        return result.returncode
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        if thread.is_alive():
            raise RuntimeError('Temporary Python server did not stop')


if __name__ == '__main__':
    raise SystemExit(main())
