import unittest
import logging
import logging.handlers
from unittest.mock import patch
from ecs_scheduler import init


class InitModuleTests(unittest.TestCase):
    @patch.object(logging, 'basicConfig')
    @patch.dict('os.environ', clear=True)
    def test_env_with_no_predefined_vars(self, fake_log):
        init.env()

        fake_log.assert_called_with(level=None, handlers=unittest.mock.ANY, format='%(levelname)s:%(name)s:%(asctime)s %(message)s')
        pos_args, expected_args = fake_log.call_args
        expected_handlers = expected_args['handlers']
        self.assertEqual(1, len(expected_handlers))
        self.assertIsInstance(expected_handlers[0], logging.StreamHandler)

    @patch.object(logging, 'basicConfig')
    @patch.dict('os.environ', {'LOG_LEVEL': 'INFO'})
    def test_env_sets_loglevel_if_specified(self, fake_log):
        init.env()

        fake_log.assert_called_with(level=logging.INFO, handlers=unittest.mock.ANY, format='%(levelname)s:%(name)s:%(asctime)s %(message)s')

    @patch.object(logging, 'basicConfig')
    @patch('os.makedirs')
    @patch.dict('os.environ', {'LOG_FOLDER': 'foo/bar/testlog', 'HOSTNAME': 'testhost'})
    def test_env_sets_logfile_if_specified(self, fake_makedirs, fake_log):
        with patch.object(logging.handlers, 'RotatingFileHandler', spec=logging.handlers.RotatingFileHandler) as fake_file_handler:
            init.env()
            fake_makedirs.assert_called_with('foo/bar/testlog/testhost', exist_ok=True)
            fake_file_handler.assert_called_with('foo/bar/testlog/testhost/app.log', maxBytes=5*1024*1024, backupCount=1)
        
        pos_args, expected_args = fake_log.call_args
        expected_handlers = expected_args['handlers']
        self.assertEqual(2, len(expected_handlers))
        self.assertIsInstance(expected_handlers[1], logging.handlers.RotatingFileHandler)

    @patch.object(logging, 'basicConfig')
    @patch('os.makedirs')
    @patch.dict('os.environ', {'LOG_FOLDER': 'foo/bar/testlog'}, clear=True)
    def test_env_sets_logfile_if_hostname_missing(self, fake_makedirs, fake_log):
        with patch.object(logging.handlers, 'RotatingFileHandler', spec=logging.handlers.RotatingFileHandler) as fake_file_handler:
            init.env()
            fake_makedirs.assert_called_with('foo/bar/testlog/local', exist_ok=True)
            fake_file_handler.assert_called_with('foo/bar/testlog/local/app.log', maxBytes=5*1024*1024, backupCount=1)
        
        pos_args, expected_args = fake_log.call_args
        expected_handlers = expected_args['handlers']
        self.assertEqual(2, len(expected_handlers))
        self.assertIsInstance(expected_handlers[1], logging.handlers.RotatingFileHandler)

    @patch('yaml.safe_load')
    @patch('builtins.open')
    @patch.dict('os.environ', clear=True)
    def test_config_loads_default(self, fake_open, fake_yaml):
        test_config = {}
        fake_yaml.return_value = test_config

        result = init.config()

        self.assertIs(test_config, result)
        fake_open.assert_called_with('config/config_default.yaml')

    @patch('yaml.safe_load')
    @patch('builtins.open')
    @patch.dict('os.environ', {'RUN_ENV': 'dev'})
    def test_config_loads_env(self, fake_open, fake_yaml):
        test_config = {'foo': 4, 'bar': {'baz': 'bort', 'bart': 'boo'}, 'hoop': 10}
        env_config = {'bar': {'baz': 'devbort', 'blort': 5}, 'foo': 20}
        fake_yaml.side_effect = [test_config, env_config]

        result = init.config()
        
        self.assertEqual(20, result['foo'])
        self.assertEqual(10, result['hoop'])
        self.assertEqual('devbort', result['bar']['baz'])
        self.assertEqual(5, result['bar']['blort'])
        self.assertEqual('boo', result['bar']['bart'])
        fake_open.assert_any_call('config/config_default.yaml')
        fake_open.assert_called_with('config/config_dev.yaml')

    @patch.object(logging.getLogger('ecs_scheduler.init'), 'warning')
    @patch('yaml.safe_load')
    @patch('builtins.open', side_effect=[unittest.mock.DEFAULT, FileNotFoundError])
    @patch.dict('os.environ', {'RUN_ENV': 'dev'})
    def test_config_skips_envload_if_filenotfound(self, fake_open, fake_yaml, fake_log):
        test_config = {}
        fake_yaml.return_value = test_config

        result = init.config()

        self.assertIs(test_config, result)
        fake_open.assert_any_call('config/config_default.yaml')
        fake_open.assert_called_with('config/config_dev.yaml')

    @patch('yaml.safe_load')
    @patch('builtins.open')
    @patch.dict('os.environ', {'COMPONENT': 'foo'})
    def test_config_sets_component_if_env_specified(self, fake_open, fake_yaml):
        test_config = {'component_name': 'bar'}
        fake_yaml.return_value = test_config

        result = init.config()

        self.assertEqual('foo', test_config['component_name'])

    @patch.object(logging.getLogger('ecs_scheduler.init'), 'warning')
    @patch('yaml.safe_load')
    @patch('builtins.open')
    @patch.dict('os.environ', clear=True)
    def test_config_fallsbacktodefault_if_component_env_not_set(self, fake_open, fake_yaml, fake_log):
        test_config = {'component_name': 'bar'}
        fake_yaml.return_value = test_config

        result = init.config()

        self.assertEqual('bar', test_config['component_name'])

    @patch('yaml.safe_load')
    @patch('builtins.open')
    @patch.dict('os.environ', clear=True)
    def test_config_does_not_set_sleeptime_if_not_in_env(self, fake_open, fake_yaml):
        test_config = {'scheduld': {'sleep_in_seconds': 10}}
        fake_yaml.return_value = test_config

        result = init.config()

        self.assertEqual(10, test_config['scheduld']['sleep_in_seconds'])

    @patch('yaml.safe_load')
    @patch('builtins.open')
    @patch.dict('os.environ', {'SLEEP_IN_SECONDS': '20'})
    def test_config_sets_sleeptime_if_env_specified(self, fake_open, fake_yaml):
        test_config = {'scheduld': {'sleep_in_seconds': 10}}
        fake_yaml.return_value = test_config

        result = init.config()

        self.assertEqual(20, test_config['scheduld']['sleep_in_seconds'])

    @patch.object(logging.getLogger('ecs_scheduler.init'), 'warning')
    @patch('yaml.safe_load')
    @patch('builtins.open')
    @patch.dict('os.environ', {'SLEEP_IN_SECONDS': 'nope'})
    def test_config_fallsbacktodefault_if_sleeptime_env_not_integer(self, fake_open, fake_yaml, fake_log):
        test_config = {'scheduld': {'sleep_in_seconds': 10}}
        fake_yaml.return_value = test_config

        result = init.config()

        self.assertEqual(10, test_config['scheduld']['sleep_in_seconds'])
