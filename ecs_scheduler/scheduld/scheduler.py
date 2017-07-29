"""Job scheduler classes."""
import logging

import apscheduler.events
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import JobLookupError

from .execution import JobExecutor
from ..models import JobOperation
from ..datacontext import JobNotFound


_logger = logging.getLogger(__name__)


class Scheduler:
    """The job scheduler."""
    def __init__(self, datacontext, job_func):
        """
        Create the job scheduler.

        :param datacontext: The jobs data context for loading and saving jobs
        :param job_func: The function to invoke when a scheduled job runs
        """
        self._dc = datacontext
        self._exec = job_func
        job_defaults = {
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 60 * 60 # 1 hour
        }
        self._sched = BackgroundScheduler(timezone='UTC', job_defaults=job_defaults)
        self._handler = ScheduleEventHandler(self._sched, datacontext)
        self._sched.add_listener(self._handler,
            apscheduler.events.EVENT_JOB_ADDED
            | apscheduler.events.EVENT_JOB_MODIFIED
            | apscheduler.events.EVENT_JOB_EXECUTED
            | apscheduler.events.EVENT_JOB_ERROR
            | apscheduler.events.EVENT_JOB_MISSED)

    def start(self):
        """Start the scheduler."""
        job_count = 0
        for job in self._dc.get_all():
            self._insert_job(job)
            job_count += 1
        self._sched.start()
        _logger.info('Scheduler started with %s initial jobs', job_count)

    def stop(self):
        """
        Stop the scheduler.

        After stopping the scheduler a new scheduler must be created to start again.
        """
        self._sched.shutdown()

    def notify(self, job_op):
        """
        Implementation of ops queue consumer interface.

        :param job_op: The operation sent to this queue consumer
        :raises: RuntimeError if received an unknown job operation
        """
        if job_op.operation == JobOperation.ADD or job_op.operation == JobOperation.MODIFY:
            self._insert_job_from_id(job_op.job_id)
        elif job_op.operation == JobOperation.REMOVE:
            self._remove_job(job_op.job_id)
        else:
            raise RuntimeError(f'Received unknown job operation {job_op.job_id} {{{job_op.operation}}}')

    def _insert_job_from_id(self, job_id):
        job = self._dc.get(job_id)
        self._insert_job(job)

    def _insert_job(self, job):
        job_kwargs = {
            'kwargs': job.data,
            'id': job.id,
            'replace_existing': True
        }
        # NOTE: None means pause the job after add
        # see: https://apscheduler.readthedocs.org/en/latest/modules/schedulers/base.html#apscheduler.schedulers.base.BaseScheduler.add_job
        if job.suspended:
            job_kwargs['next_run_time'] = None
        self._sched.add_job(self._exec, 'cron', **job_kwargs, **self._build_trigger_kwargs(job))

    def _build_trigger_kwargs(self, job):
        kwargs = job.parsed_schedule.copy()
        start_date = job.data.get('lastRun', job.data.get('scheduleStart'))
        if start_date:
            kwargs['start_date'] = start_date
        end_date = job.data.get('scheduleEnd')
        if end_date:
            kwargs['end_date'] = end_date
        tz = job.data.get('timezone')
        if tz:
            kwargs['timezone'] = tz
        return kwargs

    def _remove_job(self, job_id):
        try:
            self._sched.remove_job(job_id)
        except JobLookupError:
            _logger.exception('Unable to find job %s for removal', job_id)


class ScheduleEventHandler:
    """
    Handler for scheduler events.

    Intended for internal use by the Scheduler, the handler
    updates the run date stats in the persistent job store whenever a job
    executes or its state is modified in the schedule.
    It also logs errors that bubble out of job runs or if jobs were missed.
    """
    def __init__(self, schedule, datacontext):
        """
        Create a handler.

        :param schedule: The internal schedule implementation of the Scheduler object
        :param datacontext: The jobs data context for loading and saving jobs
        """
        self._sched = schedule
        self._dc = datacontext

    def __call__(self, event):
        """
        Call the event handler.

        :param event: The schedule event that was raised to this handler
        """
        if event.code == apscheduler.events.EVENT_JOB_ADDED or event.code == apscheduler.events.EVENT_JOB_MODIFIED:
            self._handle_update_event(event)
        elif event.code == apscheduler.events.EVENT_JOB_EXECUTED:
            self._handle_execute_event(event)
        elif event.code == apscheduler.events.EVENT_JOB_ERROR:
            self._handle_error_event(event)
        elif event.code == apscheduler.events.EVENT_JOB_MISSED:
            self._handle_missed_event(event)
        else:
            self._handle_unknown_event(event)

    def _handle_update_event(self, event):
        self._update_job_doc(event.job_id)

    def _handle_execute_event(self, event):
        if event.retval.return_code == JobExecutor.RETVAL_CHECKED_TASKS:
            self._update_job_doc(event.job_id)
        elif event.retval.return_code == JobExecutor.RETVAL_STARTED_TASKS:
            self._update_job_doc(event.job_id, {'lastRun': event.scheduled_run_time, 'lastRunTasks': event.retval.task_info})
        else:
            _logger.warning('Unexpected job event return value for job %s: %s', event.job_id, event.retval.return_code)

    def _handle_error_event(self, event):
        if event.exception:
            try:
                raise event.exception
            except Exception:
                _logger.exception('Job %s failed with exception', event.job_id)
        else:
            _logger.error('Job %s failed but no exception was recorded', event.job_id)

    def _handle_missed_event(self, event):
        _logger.error('Job %s was supposed to run at %s but was missed', event.job_id, event.scheduled_run_time)

    def _handle_unknown_event(self, event):
        _logger.warning('Unexpected job event raised for job %s: %s', event.job_id, event.code)

    def _update_job_doc(self, job_id, job_data=None):
        scheduled_job = self._sched.get_job(job_id)
        if not scheduled_job:
            _logger.warning('Job %s not found in scheduler from which to get updated stats', job_id)
            return

        job_data = job_data if job_data else {}
        if scheduled_job.next_run_time:
            job_data['estimatedNextRun'] = scheduled_job.next_run_time
        
        if job_data:
            try:
                stored_job = self._dc.get(job_id)
            except JobNotFound:
                _logger.warning('Stored job %s not found to update stats', job_id)
                return
            try:
                stored_job.annotate(job_data)
            except Exception:
                _logger.exception('Unable to annotate job stats for %s', job_id)
        else:
            _logger.info('No job updates needed')
