import unittest
from unittest.mock import patch

from ecs_scheduler.webapi.spec import Spec


class SpecTests(unittest.TestCase):
    @patch('flask_swagger.swagger')
    @patch('ecs_scheduler.webapi.spec.flask')
    def test_get(self, fake_flask, fake_swagger):
        spec = Spec()

        response = spec.get()

        fake_swagger.assert_called_with(fake_flask.current_app)
        self.assertIs(fake_swagger.return_value, response)
