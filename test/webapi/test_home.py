import unittest
from unittest.mock import patch

from ecs_scheduler.webapi.home import Home


class HomeTests(unittest.TestCase):
    @patch('flask.url_for', side_effect=lambda name: 'foo/' + name)
    def test_get(self, fake_url):
        home = Home()

        response = home.get()

        self.assertEqual({
            'resources': [
                {'link': {'rel': 'jobs', 'title': 'Jobs', 'href': 'foo/jobs'}},
                {'link': {'rel': 'spec', 'title': 'Spec', 'href': 'foo/spec'}}
            ]    
        }, response)
