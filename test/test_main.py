import unittest
import logging
import os
from unittest.mock import patch

from ecs_scheduler.main import main


@patch('ecs_scheduler.scheduld.create')
@patch('ecs_scheduler.webapi.create')
@patch('ecs_scheduler.main.jobtasks.SqsTaskQueue')
@patch('ecs_scheduler.main.init')
class MainTests(unittest.TestCase):
    def test_starts_app(self, fake_init, fake_queue_class, create_webapi, create_scheduld):
        fake_init.config.return_value = {'aws': 'foo', 'webapi': {'debug': False}}

        main()

        fake_init.env.assert_called_with()
        fake_queue_class.assert_called_with('foo')
        create_scheduld.assert_called_with(fake_init.config.return_value)
        create_webapi.assert_called_with(fake_init.config.return_value, fake_queue_class.return_value)
        create_scheduld.return_value.start.assert_called_with()
        create_webapi.return_value.run.assert_called_with(debug=False, host='0.0.0.0', use_evalex=False)

    def test_starts_app_with_debug(self, fake_init, fake_queue_class, create_webapi, create_scheduld):
        fake_init.config.return_value = {'aws': 'foo', 'webapi': {'debug': True}}

        main()

        create_webapi.return_value.run.assert_called_with(debug=True, host=None, use_evalex=False)

    @patch.dict(os.environ, {'WERKZEUG_RUN_MAIN': 'true'})
    def test_does_not_start_scheduld_if_child_flask_process(self, fake_init, fake_queue_class, create_webapi, create_scheduld):
        fake_init.config.return_value = {'aws': 'foo', 'webapi': {'debug': False}}

        main()

        create_scheduld.assert_not_called()
        create_webapi.assert_called_with(fake_init.config.return_value, fake_queue_class.return_value)
        create_scheduld.return_value.start.assert_not_called()
        create_webapi.return_value.run.assert_called_with(debug=False, host='0.0.0.0', use_evalex=False)

    @patch.object(logging.getLogger('ecs_scheduler.main'), 'critical')
    def test_run_raises_exceptions(self, fake_log, fake_init, fake_queue_class, create_webapi, create_scheduld):
        fake_init.config.side_effect = Exception

        with self.assertRaises(Exception):
            main()

        fake_log.assert_called()
