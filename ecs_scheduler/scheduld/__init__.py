"""Scheduler daemon subpackage."""
from .execution import JobExecutor
from .scheduler import Scheduler
from .jobstore import JobStore


def create(config):
    """
    Create the ecs scheduler daemon.

    :param config: The application configuration dictionary
    :returns: An initialized scheduler instance
    """
    store = JobStore(config['elasticsearch'])
    
    job_exec = JobExecutor(config['aws'])
    
    return Scheduler(store, job_exec)
