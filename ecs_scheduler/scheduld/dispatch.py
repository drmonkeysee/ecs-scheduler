"""Job dispatch operations"""
import logging
import time
from ..jobtasks import InvalidMessageException
from ..models import JobOperation


_logger = logging.getLogger(__name__)


def run(task_queue, scheduler, store, config):
    """
    Run the scheduler dispatch loop

    :param task_queue: The job task queue to read from
    :param scheduler: The job scheduler object
    :param store: The persistent job store
    :param config: The scheduld config section of app config
    :raises Exception: Unhandled exceptions
    """
    _logger.info('scheduld job dispatch is online')
    try:
        sleep_period = config['sleep_in_seconds']
        while True:
            task = task_queue.get()
            if task:
                _process_task(task, scheduler, store)
            _logger.info('Sleeping dispatch for %s seconds...', sleep_period)
            time.sleep(sleep_period)
    except Exception:
        _logger.critical('scheduld job dispatcher has died! scheduler will be stopped')
        _logger.exception('unhandled scheduld exception')
        scheduler.stop()
        raise


def _process_task(task, scheduler, store):
    try:
        job_op = task.get_job_operation()
    except InvalidMessageException:
        _logger.exception('Invalid task message for task %s', task.task_id)
    else:
        try:
            _dispatch_job(job_op, scheduler, store)
            _logger.info('Dispatched job operation %s {%s}', job_op.job_id, job_op.operation)
        except Exception:
            _logger.exception('Error dispatching job %s {%s} from task %s',
                job_op.job_id, job_op.operation, task.task_id)
        else:
            task.complete()


def _dispatch_job(job_op, scheduler, store):
    if job_op.operation == JobOperation.ADD:
        job = store.get(job_op.job_id)
        scheduler.add_job(job)
    elif job_op.operation == JobOperation.MODIFY:
        job = store.get(job_op.job_id)
        scheduler.modify_job(job)
    elif job_op.operation == JobOperation.REMOVE:
        scheduler.remove_job(job_op.job_id)
    else:
        raise RuntimeError('Received unknown job operation {} {{{}}}'.format(job_op.job_id, job_op.operation))
