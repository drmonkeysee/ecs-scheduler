"""Scheduler daemon subpackage."""
from .execution import JobExecutor
from .scheduler import Scheduler
from .jobstore import JobStore


def create(ops_queue, jobs_datacontext):
    """
    Create the ecs scheduler daemon.

    :param ops_queue: The operations queue from which to process job operations
    :param jobs_datacontext: The jobs data context for loading and saving jobs
    :returns: An initialized scheduler instance
    """
    store = JobStore()
    
    job_exec = JobExecutor()
    
    sched = Scheduler(store, job_exec)
    ops_queue.register(sched)
    return sched
