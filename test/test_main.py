import unittest
from unittest.mock import patch
from ecs_scheduler.main import main


@patch('ecs_scheduler.taskdemo.app.run')
@patch('ecs_scheduler.scheduld.app.run')
@patch('ecs_scheduler.webapi.server.run')
@patch('ecs_scheduler.main.jobtasks.SqsTaskQueue')
@patch('ecs_scheduler.main.init')
class MainTests(unittest.TestCase):
    def test_run_webapi(self, fake_init, fake_queue_class, fake_server_run, fake_app_run, fake_demo_run):
        fake_init.config.return_value = {'aws': 'foo', 'component_name': 'webapi'}

        main()

        fake_init.env.assert_called_with()
        fake_queue_class.assert_called_with('foo')
        fake_server_run.assert_called_with(fake_init.config.return_value, fake_queue_class.return_value)
        fake_app_run.assert_not_called()
        fake_demo_run.assert_not_called()

    def test_run_scheduld(self, fake_init, fake_queue_class, fake_server_run, fake_app_run, fake_demo_run):
        fake_init.config.return_value = {'aws': 'foo', 'component_name': 'scheduld'}

        main()

        fake_init.env.assert_called_with()
        fake_queue_class.assert_called_with('foo')
        fake_app_run.assert_called_with(fake_init.config.return_value, fake_queue_class.return_value)
        fake_server_run.assert_not_called()
        fake_demo_run.assert_not_called()

    def test_run_taskdemo(self, fake_init, fake_queue_class, fake_server_run, fake_app_run, fake_demo_run):
        fake_init.config.return_value = {'aws': 'foo', 'component_name': 'who knows'}

        main()

        fake_init.env.assert_called_with()
        fake_queue_class.assert_called_with('foo')
        fake_demo_run.assert_called_with()
        fake_server_run.assert_not_called()
        fake_app_run.assert_not_called()

    @patch('logging.critical')
    def test_run_raises_exceptions(self, fake_log, fake_init, fake_queue_class, fake_server_run, fake_app_run, fake_demo_run):
        fake_init.config.side_effect = Exception

        with self.assertRaises(Exception):
            main()

        fake_log.assert_called()
