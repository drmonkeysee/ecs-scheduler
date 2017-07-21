import unittest
import logging
from unittest.mock import patch, Mock

import ecs_scheduler.webapi.home
import ecs_scheduler.webapi.jobs
from ecs_scheduler.webapi import create


@patch('ecs_scheduler.webapi.JobStore')
@patch('flask_cors.CORS')
@patch('flask_restful.Api')
@patch('flask.Flask')
class CreateTests(unittest.TestCase):
    def setUp(self):
        self._queue = Mock()
        self._dc = Mock()

    def test_create_server(self, fake_flask, fake_flask_restful, fake_cors, fake_jobstore):
        result = create(self._queue, self._dc)

        self.assertIsNotNone(result)
        fake_flask_restful.assert_called_with(fake_flask.return_value, catch_all_404s=True)
        fake_flask_restful.return_value.add_resource.assert_any_call(ecs_scheduler.webapi.home.Home, '/')
        fake_jobstore.assert_called_with()
        fake_flask_restful.return_value.add_resource.assert_any_call(ecs_scheduler.webapi.jobs.Jobs, '/jobs', resource_class_args=(fake_jobstore.return_value, self._queue))
        fake_flask_restful.return_value.add_resource.assert_any_call(ecs_scheduler.webapi.jobs.Job, '/jobs/<job_id>', resource_class_args=(fake_jobstore.return_value, self._queue))
        fake_cors.assert_called_with(fake_flask.return_value, allow_headers='Content-Type')
        fake_flask.return_value.logger.addHandler.assert_not_called()

    @patch('logging.getLogger')
    def test_adds_file_handler_if_present(self, get_log, fake_flask, fake_flask_restful, fake_cors, fake_jobstore):
        mock_handler = Mock(spec=logging.handlers.RotatingFileHandler)
        get_log.return_value.handlers = Mock(), mock_handler, Mock()

        result = create(self._queue, self._dc)

        fake_flask.return_value.logger.addHandler.assert_called_with(mock_handler)
