"""Main entry for all ecs scheduler services"""
import sys
import logging

# TODO: get this working once the package is deployable
#from setuptools_scm import get_version

import ecs_scheduler.webapi.server
import ecs_scheduler.scheduld.app
from . import init, jobtasks, __version__


_logger = logging.getLogger(__name__)


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
        _logger.info('ECS Scheduler v%s', __version__)
        if component_name == 'webapi':
            ecs_scheduler.webapi.server.run(config, queue)
        elif component_name == 'scheduld':
            ecs_scheduler.scheduld.app.run(config, queue)
        else:
            raise RuntimeError('Unknown component name: ' + str(component_name))
    except Exception:
        _logger.critical('unhandled scheduler exception', exc_info=True)
        raise
