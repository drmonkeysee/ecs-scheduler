"""Main entry for all ecs scheduler services"""
import sys
import logging
import ecs_scheduler.webapi.server
import ecs_scheduler.scheduld.app
# TODO: get this working once the package is deployable
#from setuptools_scm import get_version
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

        component_name = config.get('component_name')
        logging.info('ECS Scheduler v%s', 'test_version')
        if component_name == 'webapi':
            ecs_scheduler.webapi.server.run(config, queue)
        elif component_name == 'scheduld':
            ecs_scheduler.scheduld.app.run(config, queue)
        else:
            raise RuntimeError('Unknown component name: ' + str(component_name))
    except Exception:
        logging.critical('unhandled scheduler exception', exc_info=True)
        raise
