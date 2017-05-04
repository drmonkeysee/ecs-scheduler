"""Scheduler daemon subpackage."""
from .execution import JobExecutor
from .scheduler import Scheduler
from .jobstore import JobStore


def create(config, ops_queue):
    """
    Create the ecs scheduler daemon.

    :param config: The application configuration dictionary
    :param ops_queue: The operations queue from which to process job operations
    :returns: An initialized scheduler instance
    """
    store = JobStore(config['elasticsearch'])
    
    job_exec = JobExecutor(config['aws'])
    
    sched = Scheduler(store, job_exec)
    ops_queue.register(sched)
    return sched
