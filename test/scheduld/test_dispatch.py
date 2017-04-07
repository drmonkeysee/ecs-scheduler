import unittest
import logging
import ecs_scheduler.jobtasks
from unittest.mock import patch, Mock
from ecs_scheduler.scheduld.dispatch import run
from ecs_scheduler.models import JobOperation


@patch('time.sleep')
@patch.object(logging.getLogger('ecs_scheduler.scheduld.dispatch'), 'exception')
@patch.object(logging.getLogger('ecs_scheduler.scheduld.dispatch'), 'critical')
class RunTests(unittest.TestCase):
    def setUp(self):
        self._fake_queue = Mock()
        self._fake_sched = Mock()
        self._fake_store = Mock()
        self._config = {'sleep_in_seconds': 10}

    def test_run_terminates_when_exception_raised_by_queue(self, fake_critlog, fake_exlog, fake_sleep):
        self._fake_queue.get.side_effect = RunTestException

        with self.assertRaises(RunTestException):
            run(self._fake_queue, self._fake_sched, self._fake_store, self._config)

        fake_critlog.assert_called()
        fake_exlog.assert_called()
        self._fake_sched.stop.assert_called_with()
        fake_sleep.assert_not_called()

    def test_run_does_nothing_if_no_tasks(self, fake_critlog, fake_exlog, fake_sleep):
        self._fake_queue.get.side_effect = None, RunTestException

        with self.assertRaises(RunTestException):
            run(self._fake_queue, self._fake_sched, self._fake_store, self._config)

        self._fake_sched.add_job.assert_not_called()
        self._fake_sched.modify_job.assert_not_called()
        self._fake_sched.remove_job.assert_not_called()
        fake_sleep.assert_called_with(10)

    def test_run_does_not_complete_task_if_job_op_malformed(self, fake_critlog, fake_exlog, fake_sleep):
        fake_task = Mock(task_id='foo')
        fake_task.get_job_operation.side_effect = ecs_scheduler.jobtasks.InvalidMessageException
        self._fake_queue.get.side_effect = fake_task, RunTestException

        with self.assertRaises(RunTestException):
            run(self._fake_queue, self._fake_sched, self._fake_store, self._config)

        fake_task.complete.assert_not_called()
        fake_sleep.assert_called_with(10)

    def test_run_dispatches_add_job(self, fake_critlog, fake_exlog, fake_sleep):
        add_job = JobOperation.add('test_job')
        fake_task = Mock(task_id='foo')
        fake_task.get_job_operation.return_value = add_job
        self._fake_queue.get.side_effect = fake_task, RunTestException

        with self.assertRaises(RunTestException):
            run(self._fake_queue, self._fake_sched, self._fake_store, self._config)

        self._fake_store.get.assert_called_with('test_job')
        self._fake_sched.add_job.assert_called_with(self._fake_store.get.return_value)
        fake_task.complete.assert_called_with()
        fake_sleep.assert_called_with(10)

    def test_run_dispatches_modify_job(self, fake_critlog, fake_exlog, fake_sleep):
        modify_job = JobOperation.modify('test_job')
        fake_task = Mock(task_id='foo')
        fake_task.get_job_operation.return_value = modify_job
        self._fake_queue.get.side_effect = fake_task, RunTestException

        with self.assertRaises(RunTestException):
            run(self._fake_queue, self._fake_sched, self._fake_store, self._config)

        self._fake_store.get.assert_called_with('test_job')
        self._fake_sched.modify_job.assert_called_with(self._fake_store.get.return_value)
        fake_task.complete.assert_called_with()
        fake_sleep.assert_called_with(10)

    def test_run_dispatches_remove_job(self, fake_critlog, fake_exlog, fake_sleep):
        remove_job = JobOperation.remove('test_job')
        fake_task = Mock(task_id='foo')
        fake_task.get_job_operation.return_value = remove_job
        self._fake_queue.get.side_effect = fake_task, RunTestException

        with self.assertRaises(RunTestException):
            run(self._fake_queue, self._fake_sched, self._fake_store, self._config)

        self._fake_store.get.assert_not_called()
        self._fake_sched.remove_job.assert_called_with('test_job')
        fake_task.complete.assert_called_with()
        fake_sleep.assert_called_with(10)

    def test_run_does_not_complete_task_if_dispatch_fails(self, fake_critlog, fake_exlog, fake_sleep):
        add_job = JobOperation.add('test_job')
        fake_task = Mock(task_id='foo')
        fake_task.get_job_operation.return_value = add_job
        self._fake_queue.get.side_effect = fake_task, RunTestException
        self._fake_store.get.side_effect = Exception

        with self.assertRaises(RunTestException):
            run(self._fake_queue, self._fake_sched, self._fake_store, self._config)

        self._fake_store.get.assert_called_with('test_job')
        self._fake_sched.add_job.assert_not_called()
        fake_task.complete.assert_not_called()
        fake_sleep.assert_called_with(10)

    def test_run_does_not_complete_task_if_unknown_job_operation(self, fake_critlog, fake_exlog, fake_sleep):
        bad_job = JobOperation(9999, 'test_job')
        fake_task = Mock(task_id='foo')
        fake_task.get_job_operation.return_value = bad_job
        self._fake_queue.get.side_effect = fake_task, RunTestException
        self._fake_store.get.side_effect = Exception

        with self.assertRaises(RunTestException):
            run(self._fake_queue, self._fake_sched, self._fake_store, self._config)

        self._fake_store.get.assert_not_called()
        self._fake_sched.add_job.assert_not_called()
        self._fake_sched.modify_job.assert_not_called()
        self._fake_sched.remove_job.assert_not_called()
        fake_task.complete.assert_not_called()
        fake_sleep.assert_called_with(10)


class RunTestException(Exception):
    """Test exception to terminate infinite loop in dispatch."""
    pass
