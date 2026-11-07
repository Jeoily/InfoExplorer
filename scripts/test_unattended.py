"""Offline supervisor checks: fake credentials only; no MySQL/model/network calls."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unattended as u


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        base = u.ROOT / 'logs/supervisor-tests'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.directory = Path(self.temp.name)
        with patch.object(u.shutil, 'which', return_value='java'):
            self.manager = u.Supervisor(self.directory,
                {'test': 'FAKE_ROOT_PASSWORD', 'app': 'FAKE_APP_PASSWORD', 'model': 'FAKE_MODEL_KEY'})

    def tearDown(self):
        self.manager.close()
        self.temp.cleanup()

    def test_requests_cannot_inject_commands_paths_or_arguments(self):
        for data in ({'id': 'a'*32, 'action': 'python-start', 'command': 'anything'},
                     {'id': '../../x', 'action': 'check'}, {'id':'a'*32,'action':'shell'},
                     {'id':'a'*32,'action':['check']}, []):
            with self.subTest(data=data), self.assertRaises(ValueError):
                u.validate_request(data)
        self.assertEqual(u.validate_request({'id':'a'*32,'action':'check'}), ('a'*32,'check'))

    def test_children_receive_only_their_own_credentials(self):
        self.manager.base = u.clean_env({'PATH': 'example', 'MYSQL_PASSWORD': 'inherited',
            'MODEL_API_KEY': 'inherited', 'SPRING_DATASOURCE_PASSWORD': 'inherited',
            'INFOEXPLORER_MYSQL_TEST': '1'})
        python = self.manager.env('python')
        self.assertNotIn('MYSQL_PASSWORD', python)
        self.assertEqual(python['MODEL_API_KEY'], 'FAKE_MODEL_KEY')
        app = self.manager.env('app')
        self.assertEqual(app['MYSQL_USER'], 'infoexplorer_app')
        self.assertNotIn('MODEL_API_KEY', app)
        self.assertNotIn('INFOEXPLORER_MYSQL_TEST', app)
        test = self.manager.env('test')
        self.assertEqual(test['MYSQL_USER'], 'root')
        self.assertNotIn('MODEL_API_KEY', test)
        self.assertEqual(self.manager.env('none'), {'PATH': 'example'})

    def test_logs_redact_child_output_and_nonzero_exit_is_failure(self):
        source = 'import os; print(os.environ["MODEL_API_KEY"]); print("FAKE_ROOT_PASSWORD")'
        log = self.manager.run([sys.executable, '-c', source], 'python', 'fixture', timeout=15)
        content = Path(log).read_text(encoding='utf-8')
        self.assertNotIn('FAKE_', content)
        self.assertEqual(content.count('[REDACTED]'), 2)
        with self.assertRaisesRegex(ValueError, 'FIXTURE_FAILED'):
            self.manager.run([sys.executable, '-c', 'raise SystemExit(3)'], 'none', 'fixture', timeout=15)

    def test_failed_tests_never_start_backup_or_daily_java(self):
        with patch.object(self.manager, 'stop_service'), patch.object(u, 'listening', return_value=False), \
             patch.object(self.manager, 'maven', side_effect=ValueError('TEST_FAILED')), \
             patch.object(self.manager, 'run') as run, patch.object(self.manager, 'launch') as launch:
            with self.assertRaisesRegex(ValueError, 'TEST_FAILED'):
                self.manager.execute('java-deploy')
            run.assert_not_called()
            launch.assert_not_called()

    def test_failed_backup_never_starts_daily_java(self):
        with patch.object(self.manager, 'stop_service'), patch.object(u, 'listening', return_value=False), \
             patch.object(self.manager, 'maven'), \
             patch.object(self.manager, 'run', side_effect=ValueError('BACKUP_FAILED')), \
             patch.object(self.manager, 'launch') as launch:
            with self.assertRaisesRegex(ValueError, 'BACKUP_FAILED'):
                self.manager.execute('java-deploy')
            launch.assert_not_called()

    def test_compilation_refused_while_java_port_in_use(self):
        with patch.object(u, 'listening', return_value=True), patch.object(self.manager, 'maven') as maven:
            with self.assertRaisesRegex(ValueError, 'STOP_JAVA'):
                self.manager.execute('mysql-test')
            maven.assert_not_called()

    def test_atomic_status_is_only_explicit_public_metadata(self):
        path = self.directory / 'state.json'
        u.write_json(path, {'status': 'ready'})
        self.assertEqual(json.loads(path.read_text()), {'status': 'ready'})
        self.assertFalse(path.with_suffix('.tmp').exists())


if __name__ == '__main__':
    unittest.main()
