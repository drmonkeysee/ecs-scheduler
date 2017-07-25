import unittest
from unittest.mock import patch, Mock

from ecs_scheduler.scheduld import create


class RunTests(unittest.TestCase):
    @patch('ecs_scheduler.scheduld.Scheduler')
    @patch('ecs_scheduler.scheduld.JobExecutor')
    def test_create_scheduld(self, fake_exec, fake_sched):
        test_queue = Mock()
        dc = Mock()
        
        result = create(test_queue, dc)

        fake_exec.assert_called_with()
        fake_sched.assert_called_with(dc, fake_exec.return_value)
        test_queue.register.assert_called_with(fake_sched.return_value)
        self.assertIsNotNone(result)
