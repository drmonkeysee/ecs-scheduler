import unittest
import logging
from unittest.mock import Mock, patch

from ecs_scheduler.jobstore import JobStore


class JobStoreTests(unittest.TestCase):
    def setUp(self):
        self._persistence = Mock()
        self._target = JobStore(self._persistence)

    @patch.object(logging.getLogger('ecs_scheduler.jobstore'), 'warning')
    def test_load_selects_null_source_if_not_specified(self, fake_log):
        result = JobStore.load()

        self.assertEqual([], list(result.get_all()))
        fake_log.assert_called()

    def test_load_fills_store_from_source(self):
        self._persistence.load_all.return_value = {'a': 1, 'b': 2}

        result = JobStore.load(self._persistence)

        self._persistence.load_all.assert_called()
        self.assertCountEqual([1, 2], result.get_all())
