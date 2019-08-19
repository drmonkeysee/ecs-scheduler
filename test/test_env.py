import logging
import logging.handlers
import unittest
from unittest.mock import patch

from ecs_scheduler import env, __version__


@patch('ecs_scheduler.env.triggers')
class InitTests(unittest.TestCase):
    @patch.object(logging, 'basicConfig')
    @patch.dict('os.environ', clear=True)
    def test(self, fake_log, triggers):
        env.init()

        triggers.init.assert_called_with()

    @patch.object(logging, 'basicConfig')
    @patch.dict('os.environ', clear=True)
    def test_with_no_predefined_vars(self, fake_log, triggers):
        env.init()

        fake_log.assert_called_with(
            level=None,
            handlers=unittest.mock.ANY,
            format='%(levelname)s:%(name)s:%(asctime)s %(message)s'
        )
        pos_args, expected_args = fake_log.call_args
        expected_handlers = expected_args['handlers']
        self.assertEqual(1, len(expected_handlers))
        self.assertIsInstance(expected_handlers[0], logging.StreamHandler)

    @patch.object(logging, 'basicConfig')
    @patch.dict('os.environ', {'ECSS_LOG_LEVEL': 'INFO'})
    def test_sets_loglevel_if_specified(self, fake_log, triggers):
        env.init()

        fake_log.assert_called_with(
            level=logging.INFO,
            handlers=unittest.mock.ANY,
            format='%(levelname)s:%(name)s:%(asctime)s %(message)s'
        )

    @patch.object(logging, 'basicConfig')
    @patch('os.path.abspath', side_effect=lambda p: '/abs/path/' + p)
    @patch('os.makedirs')
    @patch.dict(
        'os.environ', {'ECSS_LOG_FOLDER': 'foo/bar/testlog'}, clear=True
    )
    def test_sets_logfile(self, fake_makedirs, abspath, fake_log, triggers):
        with patch.object(
            logging.handlers, 'RotatingFileHandler',
            spec=logging.handlers.RotatingFileHandler
        ) as fake_file_handler:
            env.init()
            fake_makedirs.assert_called_with(
                '/abs/path/foo/bar/testlog', exist_ok=True
            )
            fake_file_handler.assert_called_with(
                'foo/bar/testlog/app.log', maxBytes=5*1024*1024, backupCount=1
            )

        pos_args, expected_args = fake_log.call_args
        expected_handlers = expected_args['handlers']
        self.assertEqual(2, len(expected_handlers))
        self.assertIsInstance(expected_handlers[1],
                              logging.handlers.RotatingFileHandler)

    @patch.object(logging, 'basicConfig')
    @patch('os.path.abspath', side_effect=lambda p: '/abs/path/' + p)
    @patch('os.makedirs')
    @patch.dict(
        'os.environ',
        {
            'ECSS_LOG_FOLDER': 'foo/bar/{HOSTNAME}/testlog',
            'HOSTNAME': 'testhost',
        },
        clear=True
    )
    def test_sets_logfile_with_env_vars(
        self, fake_makedirs, abspath, fake_log, triggers
    ):
        with patch.object(
            logging.handlers, 'RotatingFileHandler',
            spec=logging.handlers.RotatingFileHandler
        ) as fake_file_handler:
            env.init()
            fake_makedirs.assert_called_with(
                '/abs/path/foo/bar/testhost/testlog', exist_ok=True
            )
            fake_file_handler.assert_called_with(
                'foo/bar/testhost/testlog/app.log',
                maxBytes=5*1024*1024,
                backupCount=1
            )

        pos_args, expected_args = fake_log.call_args
        expected_handlers = expected_args['handlers']
        self.assertEqual(2, len(expected_handlers))
        self.assertIsInstance(
            expected_handlers[1], logging.handlers.RotatingFileHandler
        )


class GetVarTests(unittest.TestCase):
    @patch.dict('os.environ', {'ECSS_FOO': 'foobar'})
    def test_return_var(self):
        value = env.get_var('FOO')

        self.assertEqual('foobar', value)

    @patch.dict('os.environ', clear=True)
    def test_return_missing_var(self):
        value = env.get_var('FOO')

        self.assertIsNone(value)

    @patch.dict('os.environ', clear=True)
    def test_return_default_var(self):
        value = env.get_var('FOO', default='def_foo')

        self.assertEqual('def_foo', value)

    @patch.dict(
        'os.environ', {'ECSS_FOO': 'foo{BAZ}bar', 'BAZ': '12'}, clear=True
    )
    def test_applies_environ_to_formatted_value(self):
        value = env.get_var('FOO')

        self.assertEqual('foo12bar', value)

    @patch.dict('os.environ', {'ECSS_FOO': 'foobar'})
    def test_return_required_var(self):
        value = env.get_var('FOO', required=True)

        self.assertEqual('foobar', value)

    @patch.dict('os.environ', clear=True)
    def test_raises_on_missing_required_var(self):
        with self.assertRaises(KeyError):
            env.get_var('FOO', required=True)

    @patch.dict(
        'os.environ', {'ECSS_FOO': 'foo{BAZ}bar', 'BAZ': '12'}, clear=True
    )
    def test_applies_environ_to_formatted_required_value(self):
        value = env.get_var('FOO', required=True)

        self.assertEqual('foo12bar', value)


@patch('setuptools_scm.get_version')
class GetVersionTests(unittest.TestCase):
    def test_get_from_setuptools(self, scm):
        result = env.get_version()

        self.assertIs(scm.return_value, result)

    def test_get_fallsback_to_hardcoded_if_scm_fails(self, scm):
        scm.side_effect = LookupError

        result = env.get_version()

        self.assertEqual(__version__, result)
