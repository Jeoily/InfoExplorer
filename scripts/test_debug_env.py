"""Offline supervisor isolation invariants. No real credentials/providers."""
import importlib
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import debug_env as debug


def test_unknown_exception_text_never_becomes_control_output():
    assert debug.error_code(RuntimeError('PRIVATE_SECRET'))=='OPERATION_FAILED'
    assert debug.error_code(RuntimeError('DEBUG_PORT_IN_USE'))=='DEBUG_PORT_IN_USE'


def manager(tmp_path, monkeypatch, mode='fixture'):
    monkeypatch.setattr(debug.shutil, 'which', lambda name: name)
    return debug.Supervisor(tmp_path, mode, {'MODEL_API_KEY': 'FAKE_SECRET',
        'MODEL_BASE_URL': 'https://example.org/v1', 'MODEL_ALLOWED_HOST': 'example.org', 'MODEL_NAME': 'fake'})


def test_environment_drops_inherited_database_and_tool_overrides(tmp_path, monkeypatch):
    for key in ('SPRING_APPLICATION_JSON', 'SPRING_PROFILES_ACTIVE', 'MYSQL_PASSWORD',
                'MODEL_API_KEY', 'JAVA_TOOL_OPTIONS', 'JDK_JAVA_OPTIONS', 'NODE_OPTIONS',
                'PYTHONPATH', 'INFOEXPLORER_DATA_DIR'):
        monkeypatch.setenv(key, 'PRIVATE_SENTINEL')
    m=manager(tmp_path,monkeypatch)
    for service in ('java','build','python','frontend'):
        env=m.env(service)
        assert 'PRIVATE_SENTINEL' not in json.dumps(env)
        assert 'FAKE_SECRET' not in json.dumps(env)
        assert env['TEMP']==str(tmp_path/'tmp')


def test_live_key_only_reaches_python(tmp_path,monkeypatch):
    m=manager(tmp_path,monkeypatch,'live')
    assert m.env('python')['MODEL_API_KEY']=='FAKE_SECRET'
    for name in ('java','build','frontend'):
        assert 'MODEL_API_KEY' not in m.env(name)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows process lifecycle')
def test_child_log_redacts_fake_key_and_restart_keeps_memory_only(tmp_path,monkeypatch):
    m=manager(tmp_path,monkeypatch,'live')
    for _ in range(2):
        entry=m.launch('python',[sys.executable,'-c',
            'import os; print(os.environ["MODEL_API_KEY"])'],tmp_path)
        try:
            assert entry[0].wait(timeout=10)==0
            entry[1].join(timeout=5)
            contents=entry[2].read_text(encoding='utf-8')
            assert 'FAKE_SECRET' not in contents
            assert '[REDACTED]' in contents
        finally:
            m.stop_entry(entry)


def test_java_command_forces_session_h2_and_disables_daily_config(tmp_path,monkeypatch):
    m=manager(tmp_path,monkeypatch)
    m.jar=tmp_path/'build.jar'
    args,cwd=m.command('java')
    assert cwd==tmp_path
    assert '--spring.datasource.driver-class-name=org.h2.Driver' in args
    assert '--spring.config.location=classpath:/application.properties' in args
    assert '--spring.profiles.active=debug' in args
    url=next(x for x in args if x.startswith('--spring.datasource.url='))
    assert str(tmp_path.as_posix()) in url and 'mysql' not in url
    assert '--agent.service.base-url=http://127.0.0.1:18000' in args


@pytest.mark.parametrize('data', [ {}, {'id':'a'*32,'action':'java-deploy'},
    {'id':'../escape','action':'stop'}, {'id':'a'*32,'action':'stop','cmd':'whoami'}])
def test_control_rejects_unscoped_actions(data):
    with pytest.raises(ValueError): debug.validate_request(data)


def test_occupied_port_never_kills_owner_or_builds(tmp_path,monkeypatch):
    m=manager(tmp_path,monkeypatch)
    monkeypatch.setattr(debug,'listening',lambda _: True)
    m.build=Mock()
    m.stop_all=Mock()
    with pytest.raises(RuntimeError,match='DEBUG_PORT_IN_USE'): m.execute('start')
    m.build.assert_not_called()
    m.stop_all.assert_not_called()


def test_partial_start_failure_cleans_owned_children(tmp_path,monkeypatch):
    m=manager(tmp_path,monkeypatch)
    monkeypatch.setattr(debug,'listening',lambda _: False)
    m.build=Mock()
    m.start_one=Mock(side_effect=[None, RuntimeError('CHILD_EXITED')])
    m.stop_all=Mock()
    with pytest.raises(RuntimeError): m.execute('start')
    m.stop_all.assert_called_once()


def test_active_tasks_block_normal_stop_and_restart(tmp_path,monkeypatch):
    m=manager(tmp_path,monkeypatch)
    proc=Mock(); proc.poll.return_value=None
    m.children['java']=(proc,None,None)
    monkeypatch.setattr(debug,'get_json',lambda _: {'items':[{'status':'RUNNING'}]})
    m.stop_all=Mock()
    for action in ('stop','shutdown','restart-python','rebuild-java'):
        with pytest.raises(RuntimeError,match='TASKS_ACTIVE'): m.execute(action)
    m.stop_all.assert_not_called()


def test_model_budget_survives_runner_restart_and_counts_failure(tmp_path,monkeypatch):
    monkeypatch.setenv('DEBUG_MODE','live')
    monkeypatch.setenv('DEBUG_SESSION',str(tmp_path))
    (tmp_path/'budget.json').write_text('{"limit":1,"used":0}',encoding='utf-8')
    import debug_agent
    module=importlib.reload(debug_agent)
    monkeypatch.setattr(module.SessionRunner,'run',Mock(side_effect=RuntimeError('PROVIDER_FAIL')))
    with pytest.raises(RuntimeError): module.LimitedRunner().run(None)
    module=importlib.reload(module)
    with pytest.raises(module.HTTPException) as error: module.LimitedRunner().run(None)
    assert error.value.status_code==429
    assert json.loads((tmp_path/'budget.json').read_text())['used']==1


def test_fixture_http_has_no_daily_network_routes(tmp_path,monkeypatch):
    monkeypatch.setenv('DEBUG_MODE','fixture')
    monkeypatch.setenv('DEBUG_SESSION',str(tmp_path))
    monkeypatch.setenv('INFOEXPLORER_WEB_MODEL_ENABLED','true')
    import debug_agent
    module=importlib.reload(debug_agent)
    paths=set(module.app.openapi()['paths'])
    assert module.health()['mode']=='fixture'
    assert '/internal/v1/research/run' not in paths
    assert '/internal/v2/research/run' not in paths
