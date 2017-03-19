import unittest
from unittest.mock import patch
from ecs_scheduler.main import main


@patch('ecs_scheduler.testdemo.app.run')
@patch('ecs_scheduler.scheduld.app.run')
@patch('ecs_scheduler.webapi.server.run')
@patch('ecs_scheduler.main.jobtasks.SqsTaskQueue')
@patch('ecs_scheduler.main.init')
class MainTests(unittest.TestCase):
    def test_run_webapi(self, fake_init, fake_queue_class, fake_server_run, fake_app_run, fake_demo_run):
        fake_init.config.return_value = {'aws': 'foo', 'service_name': 'webapi'}

        main()

        fake_init.env.assert_called_with()
        fake_queue_class.assert_called_with('foo')
        fake_server_run.assert_called_with(fake_init.config.return_value, fake_queue_class.return_value)
        self.assertFalse(fake_app_run.called)
        self.assertFalse(fake_demo_run.called)

    def test_run_scheduld(self, fake_init, fake_queue_class, fake_server_run, fake_app_run, fake_demo_run):
        fake_init.config.return_value = {'aws': 'foo', 'service_name': 'scheduld'}

        main()

        fake_init.env.assert_called_with()
        fake_queue_class.assert_called_with('foo')
        fake_app_run.assert_called_with(fake_init.config.return_value, fake_queue_class.return_value)
        self.assertFalse(fake_server_run.called)
        self.assertFalse(fake_demo_run.called)

    def test_run_testdemo(self, fake_init, fake_queue_class, fake_server_run, fake_app_run, fake_demo_run):
        fake_init.config.return_value = {'aws': 'foo', 'service_name': 'who knows'}

        main()

        fake_init.env.assert_called_with()
        fake_queue_class.assert_called_with('foo')
        fake_demo_run.assert_called_with()
        self.assertFalse(fake_server_run.called)
        self.assertFalse(fake_app_run.called)

    @patch('logging.critical')
    def test_run_raises_exceptions(self, fake_log, fake_init, fake_queue_class, fake_server_run, fake_app_run, fake_demo_run):
        fake_init.config.side_effect = Exception

        with self.assertRaises(Exception):
            main()

        self.assertTrue(fake_log.called)
