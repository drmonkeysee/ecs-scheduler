"""Scheduler daemon subpackage."""
from .execution import JobExecutor
from .scheduler import Scheduler


def create(ops_queue, datacontext):
    """
    Create the ecs scheduler daemon.

    :param ops_queue: The operations queue from which to process job operations
    :param datacontext: The jobs data context for loading and saving jobs
    :returns: An initialized scheduler instance
    """
    job_exec = JobExecutor()
    
    sched = Scheduler(datacontext, job_exec)
    ops_queue.register(sched)
    return sched
