import unittest
from unittest.mock import patch
from ecs_scheduler.webapi.spec import Spec


class SpecTests(unittest.TestCase):
    @patch('flask_swagger.swagger')
    @patch('flask.current_app')
    def test_get(self, fake_flask_app, fake_swagger):
        spec = Spec()

        response = spec.get()

        fake_swagger.assert_called_with(fake_flask_app)
        self.assertIs(fake_swagger.return_value, response)
