import unittest
from unittest.mock import Mock

from ecs_scheduler.jobstore import JobStore


class JobStoreTests(unittest.TestCase):
    def setUp(self):
        self._persistence = Mock()
        self._target = JobStore(self._persistence)
