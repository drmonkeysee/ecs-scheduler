import datetime
import logging
import unittest
from unittest.mock import patch, Mock

import apscheduler.events
import apscheduler.jobstores.base

from ecs_scheduler.datacontext import JobNotFound
from ecs_scheduler.models import JobOperation
from ecs_scheduler.scheduld.execution import JobExecutor, JobResult
from ecs_scheduler.scheduld.scheduler import Scheduler, ScheduleEventHandler


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        with patch('ecs_scheduler.scheduld.scheduler.BackgroundScheduler') \
                as self._bg_sched_cls:
            self._bg_sched = self._bg_sched_cls.return_value
            self._bg_sched.get_job.return_value = None
            self._test_exec = lambda: None
            self._dc = Mock()
            self._target = Scheduler(self._dc, self._test_exec)

    def test_init_sets_up_scheduler(self):
        self._bg_sched_cls.assert_called_with(
            timezone='UTC',
            job_defaults={
                'coalesce': True,
                'max_instances': 1,
                'misfire_grace_time': 60 * 60,
            }
        )
        self._bg_sched.add_listener.assert_called_with(
            self._target._handler,
            apscheduler.events.EVENT_JOB_ADDED
            | apscheduler.events.EVENT_JOB_MODIFIED
            | apscheduler.events.EVENT_JOB_EXECUTED
            | apscheduler.events.EVENT_JOB_ERROR
            | apscheduler.events.EVENT_JOB_MISSED
        )
        self.assertIsInstance(self._target._handler, ScheduleEventHandler)
        self.assertIs(self._bg_sched, self._target._handler._sched)
        self.assertIs(self._dc, self._target._handler._dc)

    def test_start(self):
        self._dc.get_all.return_value = (
            Mock(id='job1', parsed_schedule={'second': '10'}),
            Mock(id='job2', parsed_schedule={'day_of_week': 'fri'}),
            Mock(id='job3', parsed_schedule={'year': '2013', 'month': '3'}),
        )

        self._target.start()

        self.assertEqual(3, self._bg_sched.add_job.call_count)
        self._bg_sched.start.assert_called_with()

    def test_start_with_no_existing_jobs(self):
        self._dc.get_all.return_value = []

        self._target.start()

        self.assertEqual(0, self._bg_sched.add_job.call_count)
        self._bg_sched.start.assert_called_with()

    def test_stop(self):
        self._target.stop()

        self._bg_sched.shutdown.assert_called_with()

    def test_add_job_creates_new_job(self):
        job = Mock(
            id='job4', parsed_schedule={'day': '23'}, suspended=False, data={}
        )
        self._dc.get.return_value = job

        self._target.notify(JobOperation.add('job4'))

        self._dc.get.assert_called_with('job4')
        self._bg_sched.add_job.assert_called_with(
            self._test_exec,
            'cron',
            kwargs=job.data,
            id=job.id,
            replace_existing=True,
            day='23'
        )

    def test_add_job_creates_new_job_as_paused_if_suspended(self):
        job = Mock(
            id='job4', parsed_schedule={'day': '23'}, suspended=True, data={}
        )
        self._dc.get.return_value = job

        self._target.notify(JobOperation.add('job4'))

        self._dc.get.assert_called_with('job4')
        self._bg_sched.add_job.assert_called_with(
            self._test_exec,
            'cron',
            kwargs=job.data,
            id=job.id,
            replace_existing=True,
            next_run_time=None,
            day='23'
        )

    def test_add_job_sets_end_date_if_given(self):
        test_date = datetime.datetime.now()
        job = Mock(
            id='job4',
            parsed_schedule={'day': '23'},
            suspended=False,
            data={'scheduleEnd': test_date}
        )
        self._dc.get.return_value = job

        self._target.notify(JobOperation.add('job4'))

        self._dc.get.assert_called_with('job4')
        self._bg_sched.add_job.assert_called_with(
            self._test_exec,
            'cron',
            kwargs=job.data,
            id=job.id,
            replace_existing=True,
            day='23',
            end_date=test_date
        )

    def test_add_job_sets_start_date_if_given(self):
        test_date = datetime.datetime.now()
        job = Mock(
            id='job4',
            parsed_schedule={'day': '23'},
            suspended=False,
            data={'scheduleStart': test_date}
        )
        self._dc.get.return_value = job

        self._target.notify(JobOperation.add('job4'))

        self._dc.get.assert_called_with('job4')
        self._bg_sched.add_job.assert_called_with(
            self._test_exec,
            'cron',
            kwargs=job.data,
            id=job.id,
            replace_existing=True,
            day='23',
            start_date=test_date
        )

    def test_add_job_sets_timezone_if_given(self):
        job = Mock(
            id='job4',
            parsed_schedule={'day': '23'},
            suspended=False,
            data={'timezone': 'US/Pacific'}
        )
        self._dc.get.return_value = job

        self._target.notify(JobOperation.add('job4'))

        self._dc.get.assert_called_with('job4')
        self._bg_sched.add_job.assert_called_with(
            self._test_exec,
            'cron',
            kwargs=job.data,
            id=job.id,
            replace_existing=True,
            day='23',
            timezone='US/Pacific'
        )

    def test_add_job_sets_start_date_as_last_run_if_given(self):
        schedule_start = datetime.datetime(2013, 2, 28)
        last_run = datetime.datetime.now()
        job = Mock(
            id='job4',
            parsed_schedule={'day': '23'},
            suspended=False,
            data={'scheduleStart': schedule_start, 'lastRun': last_run}
        )
        self._dc.get.return_value = job

        self._target.notify(JobOperation.add('job4'))

        self._dc.get.assert_called_with('job4')
        self._bg_sched.add_job.assert_called_with(
            self._test_exec,
            'cron',
            kwargs=job.data,
            id=job.id,
            replace_existing=True,
            day='23',
            start_date=last_run
        )

    def test_modify_job_adds_job_to_scheduler(self):
        job = Mock(
            id='job4', parsed_schedule={'day': '23'}, suspended=False, data={}
        )
        self._dc.get.return_value = job

        self._target.notify(JobOperation.modify('job4'))

        self._dc.get.assert_called_with('job4')
        self._bg_sched.add_job.assert_called_with(
            self._test_exec,
            'cron',
            kwargs=job.data,
            id=job.id,
            replace_existing=True,
            day='23'
        )

    def test_modify_job_adds_job_as_paused_if_suspended(self):
        job = Mock(
            id='job4', parsed_schedule={'day': '23'}, suspended=True, data={}
        )
        self._dc.get.return_value = job

        self._target.notify(JobOperation.modify('job4'))

        self._dc.get.assert_called_with('job4')
        self._bg_sched.add_job.assert_called_with(
            self._test_exec,
            'cron',
            kwargs=job.data,
            id=job.id,
            replace_existing=True,
            next_run_time=None,
            day='23'
        )

    def test_remove_job(self):
        job_id = 'job3'

        self._target.notify(JobOperation.remove(job_id))

        self._dc.get.assert_not_called()
        self._bg_sched.remove_job.assert_called_with(job_id)

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'exception'
    )
    def test_remove_job_catches_job_not_found(self, fake_log):
        job_id = 'job3'
        self._bg_sched.remove_job.side_effect = \
            apscheduler.jobstores.base.JobLookupError(job_id)

        self._target.notify(JobOperation.remove(job_id))

        fake_log.assert_called()

    def test_notify_raises_error_if_unknown_job_operation(self):
        with self.assertRaises(RuntimeError):
            self._target.notify(JobOperation(-1, 'job4'))

        self._dc.get.assert_not_called()
        self._bg_sched.add_job.assert_not_called()
        self._bg_sched.remove_job.assert_not_called()


class ScheduleEventHandlerTests(unittest.TestCase):
    def setUp(self):
        self._sched = Mock()
        self._dc = Mock()
        self._target = ScheduleEventHandler(self._sched, self._dc)

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'exception'
    )
    def test_exception_gets_logged(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_ERROR,
            'test_id',
            'default',
            datetime.datetime.now(),
            exception=Exception('oh no')
        )

        self._target(event)

        fake_log.assert_called()

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'error'
    )
    def test_error_with_no_exception_gets_logged(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_ERROR,
            'test_id',
            'default',
            datetime.datetime.now()
        )

        self._target(event)

        fake_log.assert_called()

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'error'
    )
    def test_missed_job_gets_logged(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_MISSED,
            'test_id',
            'default',
            datetime.datetime.now(),
            retval=0
        )

        self._target(event)

        fake_log.assert_called()

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning'
    )
    def test_non_exception_gets_logged(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_REMOVED,
            'test_id',
            'default',
            datetime.datetime.now(),
            retval=0)

        self._target(event)

        fake_log.assert_called()

    def test_checked_tasks_updates_estimated_next_run(self):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id',
            'default',
            datetime.datetime.now(),
            retval=JobResult(JobExecutor.RETVAL_CHECKED_TASKS)
        )
        test_scheduled_job = Mock(
            next_run_time=datetime.datetime(2013, 12, 12)
        )
        self._sched.get_job.return_value = test_scheduled_job
        stored_job = Mock(id='test_id')
        self._dc.get.return_value = stored_job

        self._target(event)

        stored_job.annotate.assert_called_with(
            {'estimatedNextRun': test_scheduled_job.next_run_time}
        )

    def test_checked_tasks_does_not_call_store_if_no_next_run(self):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id',
            'default',
            datetime.datetime.now(),
            retval=JobResult(JobExecutor.RETVAL_CHECKED_TASKS)
        )
        test_scheduled_job = Mock(next_run_time=None)
        self._sched.get_job.return_value = test_scheduled_job
        stored_job = Mock(id='test_id')
        self._dc.get.return_value = stored_job

        self._target(event)

        stored_job.annotate.assert_not_called()

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'exception'
    )
    def test_checked_tasks_records_exception_if_update_fails(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id',
            'default',
            datetime.datetime.now(),
            retval=JobResult(JobExecutor.RETVAL_CHECKED_TASKS)
        )
        test_scheduled_job = Mock(
            next_run_time=datetime.datetime(2013, 12, 12)
        )
        self._sched.get_job.return_value = test_scheduled_job
        stored_job = Mock(id='test_id')
        self._dc.get.return_value = stored_job
        stored_job.annotate.side_effect = Exception

        self._target(event)

        stored_job.annotate.assert_called_with(
            {'estimatedNextRun': test_scheduled_job.next_run_time}
        )
        fake_log.assert_called()

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning'
    )
    def test_checked_tasks_logs_warning_if_scheduled_job_not_found(
        self, fake_log
    ):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id',
            'default',
            datetime.datetime.now(),
            retval=JobResult(JobExecutor.RETVAL_CHECKED_TASKS)
        )
        self._sched.get_job.return_value = None

        self._target(event)

        self._dc.get.assert_not_called()
        fake_log.assert_called()

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning'
    )
    def test_checked_tasks_logs_warning_if_stored_job_not_found(
        self, fake_log
    ):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id',
            'default',
            datetime.datetime.now(),
            retval=JobResult(JobExecutor.RETVAL_CHECKED_TASKS)
        )
        test_scheduled_job = Mock(
            next_run_time=datetime.datetime(2013, 12, 12)
        )
        self._sched.get_job.return_value = test_scheduled_job
        self._dc.get.side_effect = JobNotFound('test_id')

        self._target(event)

        fake_log.assert_called()

    def test_started_tasks_updates_dates(self):
        expected_last_run_time = datetime.datetime(2013, 11, 11)
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id',
            'default',
            expected_last_run_time,
            retval=JobResult(JobExecutor.RETVAL_STARTED_TASKS, ['foo', 'bar'])
        )
        test_scheduled_job = Mock(
            next_run_time=datetime.datetime(2013, 12, 12)
        )
        self._sched.get_job.return_value = test_scheduled_job
        stored_job = Mock(id='test_id')
        self._dc.get.return_value = stored_job

        self._target(event)

        stored_job.annotate.assert_called_with({
            'estimatedNextRun': test_scheduled_job.next_run_time,
            'lastRun': expected_last_run_time,
            'lastRunTasks': ['foo', 'bar'],
        })

    def test_started_tasks_omits_next_run_if_none(self):
        expected_last_run_time = datetime.datetime(2013, 11, 11)
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id',
            'default',
            expected_last_run_time,
            retval=JobResult(JobExecutor.RETVAL_STARTED_TASKS, ['foo', 'bar'])
        )
        test_scheduled_job = Mock(next_run_time=None)
        self._sched.get_job.return_value = test_scheduled_job
        stored_job = Mock(id='test_id')
        self._dc.get.return_value = stored_job

        self._target(event)

        stored_job.annotate.assert_called_with({
            'lastRun': expected_last_run_time,
            'lastRunTasks': ['foo', 'bar'],
        })

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'exception'
    )
    def test_started_tasks_records_exception_if_update_fails(self, fake_log):
        expected_last_run_time = datetime.datetime(2013, 11, 11)
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id',
            'default',
            expected_last_run_time,
            retval=JobResult(JobExecutor.RETVAL_STARTED_TASKS, ['foo', 'bar'])
        )
        test_scheduled_job = Mock(
            next_run_time=datetime.datetime(2013, 12, 12)
        )
        self._sched.get_job.return_value = test_scheduled_job
        stored_job = Mock(id='test_id')
        self._dc.get.return_value = stored_job
        stored_job.annotate.side_effect = Exception

        self._target(event)

        stored_job.annotate.assert_called_with({
            'estimatedNextRun': test_scheduled_job.next_run_time,
            'lastRun': expected_last_run_time,
            'lastRunTasks': ['foo', 'bar'],
        })
        fake_log.assert_called()

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning'
    )
    def test_started_tasks_logs_warning_if_scheduled_job_not_found(
        self, fake_log
    ):
        expected_last_run_time = datetime.datetime(2013, 11, 11)
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id',
            'default',
            expected_last_run_time,
            retval=JobResult(JobExecutor.RETVAL_STARTED_TASKS)
        )
        self._sched.get_job.return_value = None

        self._target(event)

        self._dc.get.assert_not_called()
        fake_log.assert_called()

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning'
    )
    def test_started_tasks_logs_warning_if_stored_job_not_found(
        self, fake_log
    ):
        expected_last_run_time = datetime.datetime(2013, 11, 11)
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id',
            'default',
            expected_last_run_time,
            retval=JobResult(JobExecutor.RETVAL_STARTED_TASKS)
        )
        test_scheduled_job = Mock(
            next_run_time=datetime.datetime(2013, 12, 12)
        )
        self._sched.get_job.return_value = test_scheduled_job
        self._dc.get.side_effect = JobNotFound('test_id')

        self._target(event)

        fake_log.assert_called()

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning'
    )
    def test_successful_execute_logs_warning_if_unknown_retval(self, fake_log):
        expected_last_run_time = datetime.datetime(2013, 11, 11)
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_EXECUTED,
            'test_id',
            'default',
            expected_last_run_time,
            retval=JobResult(9999)
        )

        self._target(event)

        self._dc.get.assert_not_called()
        fake_log.assert_called()

    def test_add_job_updates_estimated_next_run(self):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_ADDED,
            'test_id',
            'default',
            datetime.datetime.now()
        )
        test_scheduled_job = Mock(
            next_run_time=datetime.datetime(2013, 12, 12)
        )
        self._sched.get_job.return_value = test_scheduled_job
        stored_job = Mock(id='test_id')
        self._dc.get.return_value = stored_job

        self._target(event)

        stored_job.annotate.assert_called_with({
            'estimatedNextRun': test_scheduled_job.next_run_time,
        })

    def test_add_job_updates_nothing_if_no_next_run(self):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_ADDED,
            'test_id',
            'default',
            datetime.datetime.now()
        )
        test_scheduled_job = Mock(next_run_time=None)
        self._sched.get_job.return_value = test_scheduled_job
        stored_job = Mock(id='test_id')
        self._dc.get.return_value = stored_job

        self._target(event)

        stored_job.annotate.assert_not_called()

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'exception'
    )
    def test_add_job_records_exception_if_update_fails(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_ADDED,
            'test_id',
            'default',
            datetime.datetime.now()
        )
        test_scheduled_job = Mock(
            next_run_time=datetime.datetime(2013, 12, 12)
        )
        self._sched.get_job.return_value = test_scheduled_job
        stored_job = Mock(id='test_id')
        self._dc.get.return_value = stored_job
        stored_job.annotate.side_effect = Exception

        self._target(event)

        stored_job.annotate.assert_called_with({
            'estimatedNextRun': test_scheduled_job.next_run_time,
        })
        fake_log.assert_called()

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning'
    )
    def test_add_job_logs_warning_if_scheduled_job_not_found(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_ADDED,
            'test_id',
            'default',
            datetime.datetime.now()
        )
        self._sched.get_job.return_value = None

        self._target(event)

        self._dc.get.assert_not_called()
        fake_log.assert_called()

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning'
    )
    def test_add_job_logs_warning_if_stored_job_not_found(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_ADDED,
            'test_id',
            'default',
            datetime.datetime.now()
        )
        test_scheduled_job = Mock(
            next_run_time=datetime.datetime(2013, 12, 12))
        self._sched.get_job.return_value = test_scheduled_job
        self._dc.get.side_effect = JobNotFound('test_id')

        self._target(event)

        fake_log.assert_called()

    def test_modify_job_updates_estimated_next_run(self):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_MODIFIED,
            'test_id',
            'default',
            datetime.datetime.now()
        )
        test_scheduled_job = Mock(
            next_run_time=datetime.datetime(2013, 12, 12)
        )
        self._sched.get_job.return_value = test_scheduled_job
        stored_job = Mock(id='test_id')
        self._dc.get.return_value = stored_job

        self._target(event)

        stored_job.annotate.assert_called_with({
            'estimatedNextRun': test_scheduled_job.next_run_time,
        })

    def test_modify_job_updates_nothing_if_no_next_run(self):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_MODIFIED,
            'test_id',
            'default',
            datetime.datetime.now()
        )
        test_scheduled_job = Mock(next_run_time=None)
        self._sched.get_job.return_value = test_scheduled_job
        stored_job = Mock(id='test_id')
        self._dc.get.return_value = stored_job

        self._target(event)

        stored_job.annotate.assert_not_called()

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'exception'
    )
    def test_modify_job_records_exception_if_update_fails(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_MODIFIED,
            'test_id',
            'default',
            datetime.datetime.now()
        )
        test_scheduled_job = Mock(
            next_run_time=datetime.datetime(2013, 12, 12)
        )
        self._sched.get_job.return_value = test_scheduled_job
        stored_job = Mock(id='test_id')
        self._dc.get.return_value = stored_job
        stored_job.annotate.side_effect = Exception

        self._target(event)

        stored_job.annotate.assert_called_with({
            'estimatedNextRun': test_scheduled_job.next_run_time,
        })
        fake_log.assert_called()

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning'
    )
    def test_modify_job_logs_warning_if_scheduled_job_not_found(
        self, fake_log
    ):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_MODIFIED,
            'test_id',
            'default',
            datetime.datetime.now()
        )
        self._sched.get_job.return_value = None

        self._target(event)

        self._dc.get.assert_not_called()
        fake_log.assert_called()

    @patch.object(
        logging.getLogger('ecs_scheduler.scheduld.scheduler'), 'warning'
    )
    def test_modify_job_logs_warning_if_stored_job_not_found(self, fake_log):
        event = apscheduler.events.JobExecutionEvent(
            apscheduler.events.EVENT_JOB_MODIFIED,
            'test_id',
            'default',
            datetime.datetime.now()
        )
        test_scheduled_job = Mock(
            next_run_time=datetime.datetime(2013, 12, 12)
        )
        self._sched.get_job.return_value = test_scheduled_job
        self._dc.get.side_effect = JobNotFound('test_id')

        self._target(event)

        fake_log.assert_called()
