import unittest
from unittest.mock import patch, Mock

import marshmallow.exceptions

from ecs_scheduler.operations import DirectQueue


class DirectQueueTests(unittest.TestCase):
    def setUp(self):
        self._target = DirectQueue()

    def test_does_nothing_if_no_consumer(self):
        try:
            self._target.post('foo')
        except Exception:
            self.fail('post should not have raised an error')

    def test_sends_message_to_consumer(self):
        consumer = Mock()

        self._target.register(consumer)
        self._target.post('foo')

        consumer.notify.assert_called_with('foo')
