import unittest
from unittest.mock import patch, Mock
from ecs_scheduler.scheduld.app import run


class RunTests(unittest.TestCase):
    @patch('ecs_scheduler.scheduld.app.Scheduler')
    @patch('ecs_scheduler.scheduld.app.dispatch')
    @patch('ecs_scheduler.scheduld.app.JobExecutor')
    @patch('ecs_scheduler.scheduld.app.JobStore')
    def test_run_starts_dispatch(self, fake_store, fake_exec, fake_dispatch, fake_sched):
        test_config = {'elasticsearch': {'bort': 'baz'}, 'aws': {'foo': 'bar'}, 'scheduld': {'blah': 'blah'}}
        test_queue = Mock()
        
        run(test_config, test_queue)

        fake_store.assert_called_with(test_config['elasticsearch'])
        fake_exec.assert_called_with(test_config['aws'])
        fake_sched.assert_called_with(fake_store.return_value, fake_exec.return_value)
        fake_sched.return_value.start.assert_called_with()
        fake_dispatch.run.assert_called_with(test_queue, fake_sched.return_value, fake_store.return_value, test_config['scheduld'])
