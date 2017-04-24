import unittest
from unittest.mock import patch, Mock

import ecs_scheduler.webapi.home
import ecs_scheduler.webapi.jobs
from ecs_scheduler.webapi import create


@patch('ecs_scheduler.webapi.JobStore')
@patch('flask_cors.CORS')
@patch('flask_restful.Api')
@patch('flask.Flask')
class CreateTests(unittest.TestCase):
    def test_create_server(self, fake_flask, fake_flask_restful, fake_cors, fake_jobstore):
        test_config = {
            'elasticsearch': 'foo',
            'webapi': {'debug': True}
        }
        fake_queue = Mock()

        result = create(test_config, fake_queue)

        fake_flask_restful.assert_called_with(fake_flask.return_value, catch_all_404s=True)
        fake_flask_restful.return_value.add_resource.assert_any_call(ecs_scheduler.webapi.home.Home, '/')
        fake_jobstore.assert_called_with(test_config['elasticsearch'])
        fake_flask_restful.return_value.add_resource.assert_any_call(ecs_scheduler.webapi.jobs.Jobs, '/jobs', resource_class_args=(fake_jobstore.return_value, fake_queue))
        fake_flask_restful.return_value.add_resource.assert_any_call(ecs_scheduler.webapi.jobs.Job, '/jobs/<job_id>', resource_class_args=(fake_jobstore.return_value, fake_queue))
        fake_cors.assert_called_with(fake_flask.return_value, allow_headers='Content-Type')
        self.assertIsNotNone(result)
