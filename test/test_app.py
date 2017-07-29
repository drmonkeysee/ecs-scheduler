import unittest
import logging
import os
from unittest.mock import patch, ANY

from ecs_scheduler.app import create


@patch('atexit.register')
@patch('werkzeug.serving.is_running_from_reloader')
@patch('ecs_scheduler.app.ElasticsearchStore')
@patch('ecs_scheduler.app.scheduld.create')
@patch('ecs_scheduler.app.webapi.create')
@patch('ecs_scheduler.app.datacontext.Jobs')
@patch('ecs_scheduler.app.operations.DirectQueue')
@patch('ecs_scheduler.app.startup')
class CreateTests(unittest.TestCase):
    def test_starts_daemon_in_prod_mode(self, startup, queue_class, datacontext, create_webapi, create_scheduld, es_store, reloader, exit_register):
        reloader.return_value = False
        create_webapi.return_value.debug = False

        result = create()

        startup.init.assert_called_with()
        queue_class.assert_called_with()
        datacontext.load.assert_called_with(store=es_store.return_value)
        create_scheduld.assert_called_with(queue_class.return_value, datacontext.load.return_value)
        create_webapi.assert_called_with(queue_class.return_value, datacontext.load.return_value)
        create_scheduld.return_value.start.assert_called_with()
        exit_register.assert_called_with(ANY, create_scheduld.return_value)
        self.assertIs(create_webapi.return_value, result)

    def test_starts_daemon_in_reloader(self, startup, queue_class, datacontext, create_webapi, create_scheduld, es_store, reloader, exit_register):
        reloader.return_value = True
        create_webapi.return_value.debug = True

        result = create()

        startup.init.assert_called_with()
        queue_class.assert_called_with()
        datacontext.load.assert_called_with(store=es_store.return_value)
        create_scheduld.assert_called_with(queue_class.return_value, datacontext.load.return_value)
        create_webapi.assert_called_with(queue_class.return_value, datacontext.load.return_value)
        create_scheduld.return_value.start.assert_called_with()
        exit_register.assert_called_with(ANY, create_scheduld.return_value)
        self.assertIs(create_webapi.return_value, result)

    def test_skips_daemon_if_debug_and_not_reloader(self, startup, queue_class, datacontext, create_webapi, create_scheduld, es_store, reloader, exit_register):
        reloader.return_value = False
        create_webapi.return_value.debug = True

        result = create()

        startup.init.assert_called_with()
        queue_class.assert_called_with()
        datacontext.load.assert_called_with(store=es_store.return_value)
        create_scheduld.assert_not_called()
        create_webapi.assert_called_with(queue_class.return_value, datacontext.load.return_value)
        create_scheduld.return_value.start.assert_not_called()
        exit_register.assert_not_called()
        self.assertIs(create_webapi.return_value, result)

    @patch.object(logging.getLogger('ecs_scheduler.app'), 'critical')
    def test_startup_logs_exceptions(self, fake_log, startup, queue_class, datacontext, create_webapi, create_scheduld, es_store, reloader, exit_register):
        startup.init.side_effect = RuntimeError

        with self.assertRaises(RuntimeError):
            create()

        fake_log.assert_called()
