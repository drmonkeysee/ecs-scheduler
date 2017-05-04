import unittest
import logging
import datetime
from unittest.mock import patch, Mock

import apscheduler.jobstores.base
import apscheduler.events

from ecs_scheduler.scheduld.scheduler import Scheduler, ScheduleEventHandler
from ecs_scheduler.models import Job, JobOperation
from ecs_scheduler.scheduld.execution import JobExecutor, JobResult


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        with patch('ecs_scheduler.scheduld.scheduler.BackgroundScheduler') as self._bg_sched_cls:
            self._bg_sched = self._bg_sched_cls.return_value
            self._bg_sched.get_job.return_value = None
            self._test_exec = lambda: None
            self._store = Mock()
            self._target = Scheduler(self._store, self._test_exec)

    def test_init_sets_up_scheduler(self):
        self._bg_sched_cls.assert_called_with(timezone='UTC',
            job_defaults={'coalesce': True, 'max_instances': 1, 'misfire_grace_time': 60 * 60})
        self._bg_sched.add_listener.assert_called_with(self._target._handler,
            apscheduler.events.EVENT_JOB_ADDED | apscheduler.events.EVENT_JOB_MODIFIED
            | apscheduler.events.EVENT_JOB_EXECUTED | apscheduler.events.EVENT_JOB_ERROR
            | apscheduler.events.EVENT_JOB_MISSED)
        self.assertIsInstance(self._target._handler, ScheduleEventHandler)
        self.assertIs(self._bg_sched, self._target._handler._sched)
        self.assertIs(self._store, self._target._handler._store)

    def test_start(self):
        self._store.get_all.return_value = (Job(id='job1', parsedSchedule={'second': '10'}),
                                                    Job(id='job2', parsedSchedule={'day_of_week': 'fri'}),
                                                    Job(id='job3', parsedSchedule={'year': '2013', 'month': '3'}))

        self._target.start()

        self.assertEqual(3, self._bg_sched.add_job.call_count)
        self._bg_sched.start.assert_called_with()

    def test_start_with_no_existing_jobs(self):
        self._store.get_all.return_value = []

        self._target.start()

        self.assertEqual(0, self._bg_sched.add_job.call_count)
        self._bg_sched.start.assert_called_with()

    def test_stop(self):
        self._target.stop()

        self._bg_sched.shutdown.assert_called_with()

    def test_add_job_creates_new_job(self):
        job = Job(id='job4', parsedSchedule={'day': '23'})
        self._store.get.return_value = job

        self._target.notify(JobOperation.add('job4'))

        self._store.get.assert_called_with('job4')
        self._bg_sched.add_job.assert_called_with(self._test_exec, 'cron',
            kwargs=job.data, id=job.id, replace_existing=True, day='23')

    def test_add_job_creates_new_job_as_paused_if_suspended(self):
        job = Job(id='job4', parsedSchedule={'day': '23'}, suspended=True)
        self._store.get.return_value = job

        self._target.notify(JobOperation.add('job4'))

        self._store.get.assert_called_with('job4')
        self._bg_sched.add_job.assert_called_with(self._test_exec, 'cron',
            kwargs=job.data, id=job.id, replace_existing=True, next_run_time=None, day='23')

    def test_add_job_sets_end_date_if_given(self):
        test_date = datetime.datetime.now()
        job = Job(id='job4', parsedSchedule={'day': '23'}, scheduleEnd=test_date)
        self._store.get.return_value = job

        self._target.notify(JobOperation.add('job4'))

        self._store.get.assert_called_with('job4')
        self._bg_sched.add_job.assert_called_with(self._test_exec, 'cron',
            kwargs=job.data, id=job.id, replace_existing=True, day='23', end_date=test_date)

    def test_add_job_sets_start_date_if_given(self):
        test_date = datetime.datetime.now()
        job = Job(id='job4', parsedSchedule={'day': '23'}, scheduleStart=test_date)
        self._store.get.return_value = job

        self._target.notify(JobOperation.add('job4'))

        self._store.get.assert_called_with('job4')
        self._bg_sched.add_job.assert_called_with(self._test_exec, 'cron',
            kwargs=job.data, id=job.id, replace_existing=True, day='23', start_date=test_date)

    def test_add_job_sets_start_date_as_last_run_if_given(self):
        schedule_start = datetime.datetime(2013, 2, 28)
        last_run = datetime.datetime.now()
        job = Job(id='job4', parsedSchedule={'day': '23'}, scheduleStart=schedule_start, lastRun=last_run)
        self._store.get.return_value = job

        self._target.notify(JobOperation.add('job4'))

        self._store.get.assert_called_with('job4')
        self._bg_sched.add_job.assert_called_with(self._test_exec, 'cron',
            kwargs=job.data, id=job.id, replace_existing=True, day='23', start_date=last_run)

    def test_modify_job_adds_job_to_scheduler(self):
        job = Job(id='job4', parsedSchedule={'day': '23'})
        self._store.get.return_value = job

        self._target.notify(JobOperation.modify('job4'))

        self._store.get.assert_called_with('job4')
        self._bg_sched.add_job.assert_called_with(self._test_exec, 'cron',
            kwargs=job.data, id=job.id, replace_existing=True, day='23')

    def test_modify_job_adds_job_as_paused_if_suspended(self):
        job = Job(id='job4', parsedSchedule={'day': '23'}, suspended=True)
        self._store.get.return_value = job

        self._target.notify(JobOperation.modify('job4'))

        self._store.get.assert_called_with('job4')
        self._bg_sched.add_job.assert_called_with(self._test_exec, 'cron',
            kwargs=job.data, id=job.id, replace_existing=True, next_run_time=None, day='23')

    def test_remove_job(self):
        job_id = 'job3'

        self._target.notify(JobOperation.remove(job_id))

        self._store.get_job.assert_not_called()
        self._bg_sched.remove_job.assert_called_with(job_id)

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'exception')
    def test_remove_job_catches_job_not_found(self, fake_log):
        job_id = 'job3'
        self._bg_sched.remove_job.side_effect = apscheduler.jobstores.base.JobLookupError(job_id)
        
        self._target.notify(JobOperation.remove(job_id))

        fake_log.assert_called()


class ScheduleEventHandlerTests(unittest.TestCase):
    def setUp(self):
        self._sched = Mock()
        self._store = Mock()
        self._target = ScheduleEventHandler(self._sched, self._store)

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'exception')
    def test_exception_gets_logged(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_ERROR,
            'test_id', 'default', datetime.datetime.now(), exception=Exception('oh no'))

        self._target(event)

        fake_log.assert_called()

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'error')
    def test_error_with_no_exception_gets_logged(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_ERROR,
            'test_id', 'default', datetime.datetime.now())

        self._target(event)

        fake_log.assert_called()

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'error')
    def test_missed_job_gets_logged(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_MISSED,
            'test_id', 'default', datetime.datetime.now(), retval=0)

        self._target(event)

        fake_log.assert_called()

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning')
    def test_non_exception_gets_logged(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_REMOVED,
            'test_id', 'default', datetime.datetime.now(), retval=0)

        self._target(event)

        fake_log.assert_called()

    def test_checked_tasks_updates_estimated_next_run(self):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id', 'default', datetime.datetime.now(), retval=JobResult(JobExecutor.RETVAL_CHECKED_TASKS))
        test_scheduled_job = Mock(next_run_time=datetime.datetime(2013, 12, 12))
        self._sched.get_job.return_value = test_scheduled_job

        self._target(event)

        self._store.update.assert_called_with('test_id', {'estimatedNextRun': test_scheduled_job.next_run_time})

    def test_checked_tasks_does_not_call_store_if_no_next_run(self):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id', 'default', datetime.datetime.now(), retval=JobResult(JobExecutor.RETVAL_CHECKED_TASKS))
        test_scheduled_job = Mock(next_run_time=None)
        self._sched.get_job.return_value = test_scheduled_job

        self._target(event)

        self._store.update.assert_not_called()

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'exception')
    def test_checked_tasks_records_exception_if_update_fails(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id', 'default', datetime.datetime.now(), retval=JobResult(JobExecutor.RETVAL_CHECKED_TASKS))
        test_scheduled_job = Mock(next_run_time=datetime.datetime(2013, 12, 12))
        self._sched.get_job.return_value = test_scheduled_job
        self._store.update.side_effect = Exception

        self._target(event)

        self._store.update.assert_called_with('test_id', {'estimatedNextRun': test_scheduled_job.next_run_time})
        fake_log.assert_called()

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning')
    def test_checked_tasks_logs_warning_if_job_not_found(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id', 'default', datetime.datetime.now(), retval=JobResult(JobExecutor.RETVAL_CHECKED_TASKS))
        self._sched.get_job.return_value = None
        
        self._target(event)

        self._store.update.assert_not_called()
        fake_log.assert_called()

    def test_started_tasks_updates_dates(self):
        expected_last_run_time = datetime.datetime(2013, 11, 11)
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id', 'default', expected_last_run_time, retval=JobResult(JobExecutor.RETVAL_STARTED_TASKS, ['foo', 'bar']))
        test_scheduled_job = Mock(next_run_time=datetime.datetime(2013, 12, 12))
        self._sched.get_job.return_value = test_scheduled_job

        self._target(event)

        self._store.update.assert_called_with('test_id', {'estimatedNextRun': test_scheduled_job.next_run_time, 'lastRun': expected_last_run_time, 'lastRunTasks': ['foo', 'bar']})

    def test_started_tasks_omits_next_run_if_none(self):
        expected_last_run_time = datetime.datetime(2013, 11, 11)
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id', 'default', expected_last_run_time, retval=JobResult(JobExecutor.RETVAL_STARTED_TASKS, ['foo', 'bar']))
        test_scheduled_job = Mock(next_run_time=None)
        self._sched.get_job.return_value = test_scheduled_job

        self._target(event)

        self._store.update.assert_called_with('test_id', {'lastRun': expected_last_run_time, 'lastRunTasks': ['foo', 'bar']})

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'exception')
    def test_started_tasks_records_exception_if_update_fails(self, fake_log):
        expected_last_run_time = datetime.datetime(2013, 11, 11)
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id', 'default', expected_last_run_time, retval=JobResult(JobExecutor.RETVAL_STARTED_TASKS, ['foo', 'bar']))
        test_scheduled_job = Mock(next_run_time=datetime.datetime(2013, 12, 12))
        self._sched.get_job.return_value = test_scheduled_job
        self._store.update.side_effect = Exception

        self._target(event)

        self._store.update.assert_called_with('test_id', {'estimatedNextRun': test_scheduled_job.next_run_time, 'lastRun': expected_last_run_time, 'lastRunTasks': ['foo', 'bar']})
        fake_log.assert_called()

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning')
    def test_started_tasks_logs_warning_if_job_not_found(self, fake_log):
        expected_last_run_time = datetime.datetime(2013, 11, 11)
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id', 'default', expected_last_run_time, retval=JobResult(JobExecutor.RETVAL_STARTED_TASKS))
        self._sched.get_job.return_value = None
        
        self._target(event)

        self._store.update.assert_not_called()
        fake_log.assert_called()

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning')
    def test_successful_execute_logs_warning_if_unknown_retval(self, fake_log):
        expected_last_run_time = datetime.datetime(2013, 11, 11)
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id', 'default', expected_last_run_time, retval=JobResult(9999))
        
        self._target(event)

        self._store.update.assert_not_called()
        fake_log.assert_called()

    def test_add_job_updates_estimated_next_run(self):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_ADDED,
            'test_id', 'default', datetime.datetime.now())
        test_scheduled_job = Mock(next_run_time=datetime.datetime(2013, 12, 12))
        self._sched.get_job.return_value = test_scheduled_job

        self._target(event)

        self._store.update.assert_called_with('test_id', {'estimatedNextRun': test_scheduled_job.next_run_time})

    def test_add_job_updates_nothing_if_no_next_run(self):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_ADDED,
            'test_id', 'default', datetime.datetime.now())
        test_scheduled_job = Mock(next_run_time=None)
        self._sched.get_job.return_value = test_scheduled_job

        self._target(event)

        self._store.update.assert_not_called()

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'exception')
    def test_add_job_records_exception_if_update_fails(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_ADDED,
            'test_id', 'default', datetime.datetime.now())
        test_scheduled_job = Mock(next_run_time=datetime.datetime(2013, 12, 12))
        self._sched.get_job.return_value = test_scheduled_job
        self._store.update.side_effect = Exception

        self._target(event)

        self._store.update.assert_called_with('test_id', {'estimatedNextRun': test_scheduled_job.next_run_time})
        fake_log.assert_called()

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning')
    def test_add_job_logs_warning_if_job_not_found(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_ADDED,
            'test_id', 'default', datetime.datetime.now())
        self._sched.get_job.return_value = None
        
        self._target(event)

        self._store.update.assert_not_called()
        fake_log.assert_called()

    def test_modify_job_updates_estimated_next_run(self):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_MODIFIED,
            'test_id', 'default', datetime.datetime.now())
        test_scheduled_job = Mock(next_run_time=datetime.datetime(2013, 12, 12))
        self._sched.get_job.return_value = test_scheduled_job

        self._target(event)

        self._store.update.assert_called_with('test_id', {'estimatedNextRun': test_scheduled_job.next_run_time})

    def test_modify_job_updates_nothing_if_no_next_run(self):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_MODIFIED,
            'test_id', 'default', datetime.datetime.now())
        test_scheduled_job = Mock(next_run_time=None)
        self._sched.get_job.return_value = test_scheduled_job

        self._target(event)

        self._store.update.assert_not_called()

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'exception')
    def test_modify_job_records_exception_if_update_fails(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_MODIFIED,
            'test_id', 'default', datetime.datetime.now())
        test_scheduled_job = Mock(next_run_time=datetime.datetime(2013, 12, 12))
        self._sched.get_job.return_value = test_scheduled_job
        self._store.update.side_effect = Exception

        self._target(event)

        self._store.update.assert_called_with('test_id', {'estimatedNextRun': test_scheduled_job.next_run_time})
        fake_log.assert_called()

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning')
    def test_modify_job_logs_warning_if_job_not_found(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(apscheduler.events.EVENT_JOB_MODIFIED,
            'test_id', 'default', datetime.datetime.now())
        self._sched.get_job.return_value = None
        
        self._target(event)

        self._store.update.assert_not_called()
        fake_log.assert_called()
