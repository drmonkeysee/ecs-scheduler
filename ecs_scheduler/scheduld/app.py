"""Scheduler daemon main entry"""
import logging
from . import dispatch
from .execution import JobExecutor
from .scheduler import Scheduler
from .jobstore import JobStore


def run(config, task_queue):
    """
    Run the ecs scheduler daemon

    :param config: The application configuration dictionary
    :param task_queue: Job task queue for reading job operations from the web api
    """
    logging.info('Starting scheduld...')

    store = JobStore(config['elasticsearch'])
    
    job_exec = JobExecutor(config['aws'])
    
    scheduler = Scheduler(store, job_exec)
    scheduler.start()

    dispatch.run(task_queue, scheduler, store, config['scheduld'])
