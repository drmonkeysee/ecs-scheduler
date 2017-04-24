import unittest
from unittest.mock import patch, Mock

from ecs_scheduler.scheduld import create


class RunTests(unittest.TestCase):
    @patch('ecs_scheduler.scheduld.Scheduler')
    @patch('ecs_scheduler.scheduld.JobExecutor')
    @patch('ecs_scheduler.scheduld.JobStore')
    def test_create_scheduld(self, fake_store, fake_exec, fake_sched):
        test_config = {'elasticsearch': {'bort': 'baz'}, 'aws': {'foo': 'bar'}, 'scheduld': {'blah': 'blah'}}
        test_queue = Mock()
        
        result = create(test_config)

        fake_store.assert_called_with(test_config['elasticsearch'])
        fake_exec.assert_called_with(test_config['aws'])
        fake_sched.assert_called_with(fake_store.return_value, fake_exec.return_value)
        self.assertIsNotNone(result)
