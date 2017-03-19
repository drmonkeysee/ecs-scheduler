import unittest
import ecs_scheduler.webapi.home
import ecs_scheduler.webapi.jobs
from unittest.mock import patch, Mock
from ecs_scheduler.webapi import server


@patch.object(server, 'JobStore')
@patch('flask.ext.cors.CORS')
@patch('flask_restful.Api')
@patch('flask.Flask')
class ServerTests(unittest.TestCase):
    def test_server_run(self, fake_flask, fake_flask_restful, fake_cors, fake_jobstore):
        test_config = {
            'elasticsearch': 'foo',
            'webapi': {'debug': True}
        }
        fake_queue = Mock()

        server.run(test_config, fake_queue)

        fake_flask_restful.assert_called_with(fake_flask.return_value, catch_all_404s=True)
        fake_flask_restful.return_value.add_resource.assert_any_call(ecs_scheduler.webapi.home.Home, '/')
        fake_jobstore.assert_called_with(test_config['elasticsearch'])
        fake_flask_restful.return_value.add_resource.assert_any_call(ecs_scheduler.webapi.jobs.Jobs, '/jobs', resource_class_args=(fake_jobstore.return_value, fake_queue))
        fake_flask_restful.return_value.add_resource.assert_any_call(ecs_scheduler.webapi.jobs.Job, '/jobs/<job_id>', resource_class_args=(fake_jobstore.return_value, fake_queue))
        fake_cors.assert_called_with(fake_flask.return_value, allow_headers='Content-Type')
        fake_flask.return_value.run.assert_called_with(debug=test_config['webapi']['debug'], host=None, use_evalex=False)

    def test_server_run_with_debug_off(self, fake_flask, fake_flask_restful, fake_cors, fake_jobstore):
        test_config = {
            'elasticsearch': 'foo',
            'webapi': {'debug': False}
        }
        fake_queue = Mock()

        server.run(test_config, fake_queue)

        fake_flask_restful.assert_called_with(fake_flask.return_value, catch_all_404s=True)
        fake_flask_restful.return_value.add_resource.assert_any_call(ecs_scheduler.webapi.home.Home, '/')
        fake_jobstore.assert_called_with(test_config['elasticsearch'])
        fake_flask_restful.return_value.add_resource.assert_any_call(ecs_scheduler.webapi.jobs.Jobs, '/jobs', resource_class_args=(fake_jobstore.return_value, fake_queue))
        fake_flask_restful.return_value.add_resource.assert_any_call(ecs_scheduler.webapi.jobs.Job, '/jobs/<job_id>', resource_class_args=(fake_jobstore.return_value, fake_queue))
        fake_cors.assert_called_with(fake_flask.return_value, allow_headers='Content-Type')
        fake_flask.return_value.run.assert_called_with(debug=test_config['webapi']['debug'], host='0.0.0.0', use_evalex=False)
