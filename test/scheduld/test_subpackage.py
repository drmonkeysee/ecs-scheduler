import unittest
from unittest.mock import patch, Mock

from ecs_scheduler.scheduld import create


class RunTests(unittest.TestCase):
    @patch('ecs_scheduler.scheduld.Scheduler')
    @patch('ecs_scheduler.scheduld.JobExecutor')
    @patch('ecs_scheduler.scheduld.JobStore')
    def test_create_scheduld(self, fake_store, fake_exec, fake_sched):
        test_queue = Mock()
        
        result = create(test_queue)

        fake_store.assert_called_with()
        fake_exec.assert_called_with()
        fake_sched.assert_called_with(fake_store.return_value, fake_exec.return_value)
        test_queue.register.assert_called_with(fake_sched.return_value)
        self.assertIsNotNone(result)
