import unittest
import logging.handlers
from unittest.mock import patch, Mock

import ecs_scheduler.webapi.home
import ecs_scheduler.webapi.jobs
from ecs_scheduler.webapi import create, setup, _add_etag


@patch('flask.Flask')
class CreateTests(unittest.TestCase):
    def test(self, flask):
        result = create()

        self.assertIs(flask.return_value, result)


@patch('flask_cors.CORS')
@patch('flask_restful.Api')
class SetupTests(unittest.TestCase):
    def setUp(self):
        self._flask = Mock(config={})
        self._queue = Mock()
        self._dc = Mock()

    def test_setup_server(self, flask_restful, cors):
        setup(self._flask, self._queue, self._dc)

        flask_restful.assert_called_with(self._flask, catch_all_404s=True)
        flask_restful.return_value.add_resource.assert_any_call(ecs_scheduler.webapi.home.Home, '/')
        flask_restful.return_value.add_resource.assert_any_call(ecs_scheduler.webapi.jobs.Jobs, '/jobs', resource_class_args=(self._queue, self._dc))
        flask_restful.return_value.add_resource.assert_any_call(ecs_scheduler.webapi.jobs.Job, '/jobs/<job_id>', resource_class_args=(self._queue, self._dc))
        cors.assert_called_with(self._flask, allow_headers='Content-Type')
        self._flask.after_request.assert_called_with(_add_etag)
        self._flask.logger.addHandler.assert_not_called()
        self.assertFalse(self._flask.config['ERROR_404_HELP'])

    @patch('logging.getLogger')
    def test_adds_file_handler_if_present(self, get_log, flask_restful, cors):
        mock_handler = Mock(spec=logging.handlers.RotatingFileHandler)
        get_log.return_value.handlers = Mock(), mock_handler, Mock()

        setup(self._flask, self._queue, self._dc)

        self._flask.logger.addHandler.assert_called_with(mock_handler)
