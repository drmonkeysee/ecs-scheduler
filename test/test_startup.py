import unittest
import logging
import logging.handlers
from unittest.mock import patch

from ecs_scheduler import startup


class InitTests(unittest.TestCase):
    @patch('ecs_scheduler.startup.triggers')
    @patch('ecs_scheduler.startup.init_env')
    def test(self, env, triggers):
        startup.init()

        env.assert_called_with()
        triggers.init.assert_called_with()


class InitEnvTests(unittest.TestCase):
    @patch.object(logging, 'basicConfig')
    @patch.dict('os.environ', clear=True)
    def test_with_no_predefined_vars(self, fake_log):
        startup.init_env()

        fake_log.assert_called_with(level=None, handlers=unittest.mock.ANY, format='%(levelname)s:%(name)s:%(asctime)s %(message)s')
        pos_args, expected_args = fake_log.call_args
        expected_handlers = expected_args['handlers']
        self.assertEqual(1, len(expected_handlers))
        self.assertIsInstance(expected_handlers[0], logging.StreamHandler)

    @patch.object(logging, 'basicConfig')
    @patch.dict('os.environ', {'LOG_LEVEL': 'INFO'})
    def test_sets_loglevel_if_specified(self, fake_log):
        startup.init_env()

        fake_log.assert_called_with(level=logging.INFO, handlers=unittest.mock.ANY, format='%(levelname)s:%(name)s:%(asctime)s %(message)s')

    @patch.object(logging, 'basicConfig')
    @patch('os.makedirs')
    @patch.dict('os.environ', {'LOG_FOLDER': 'foo/bar/testlog', 'HOSTNAME': 'testhost'})
    def test_sets_logfile_if_specified(self, fake_makedirs, fake_log):
        with patch.object(logging.handlers, 'RotatingFileHandler', spec=logging.handlers.RotatingFileHandler) as fake_file_handler:
            startup.init_env()
            fake_makedirs.assert_called_with('foo/bar/testlog/testhost', exist_ok=True)
            fake_file_handler.assert_called_with('foo/bar/testlog/testhost/app.log', maxBytes=5*1024*1024, backupCount=1)
        
        pos_args, expected_args = fake_log.call_args
        expected_handlers = expected_args['handlers']
        self.assertEqual(2, len(expected_handlers))
        self.assertIsInstance(expected_handlers[1], logging.handlers.RotatingFileHandler)

    @patch.object(logging, 'basicConfig')
    @patch('os.makedirs')
    @patch.dict('os.environ', {'LOG_FOLDER': 'foo/bar/testlog'}, clear=True)
    def test_sets_logfile_if_hostname_missing(self, fake_makedirs, fake_log):
        with patch.object(logging.handlers, 'RotatingFileHandler', spec=logging.handlers.RotatingFileHandler) as fake_file_handler:
            startup.init_env()
            fake_makedirs.assert_called_with('foo/bar/testlog/local', exist_ok=True)
            fake_file_handler.assert_called_with('foo/bar/testlog/local/app.log', maxBytes=5*1024*1024, backupCount=1)
        
        pos_args, expected_args = fake_log.call_args
        expected_handlers = expected_args['handlers']
        self.assertEqual(2, len(expected_handlers))
        self.assertIsInstance(expected_handlers[1], logging.handlers.RotatingFileHandler)
