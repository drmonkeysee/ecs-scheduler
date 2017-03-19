"""Main entry for all ecs scheduler services"""
import sys
import logging
import ecs_scheduler.webapi.server
import ecs_scheduler.scheduld.app
import ecs_scheduler.taskdemo.app
from setuptools_scm import get_version
from ecs_scheduler import init, jobtasks

def main():
    """
    Start ecs scheduler service

    :raises Exception: Unhandled exceptions
    """
    try:
        init.env()
        config = init.config()
        queue = jobtasks.SqsTaskQueue(config['aws'])

        logging.info('ECS Scheduler v%s', get_version())
        if config.get('service_name') == 'webapi':
            ecs_scheduler.webapi.server.run(config, queue)
        elif config.get('service_name') == 'scheduld':
            ecs_scheduler.scheduld.app.run(config, queue)
        else:
            ecs_scheduler.taskdemo.app.run()
    except Exception:
        logging.critical('unhandled scheduler exception', exc_info=True)
        raise
