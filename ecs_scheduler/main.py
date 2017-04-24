"""Main entry for the ECS Scheduler application."""
import os
import logging

# TODO: get this working once the package is deployable
#from setuptools_scm import get_version

import ecs_scheduler.webapi
import ecs_scheduler.scheduld
from . import init, jobtasks, __version__


_logger = logging.getLogger(__name__)


def main():
    """
    Start ECS Scheduler application.

    :raises Exception: Unhandled exceptions
    """
    try:
        init.env()
        config = init.config()
        queue = jobtasks.SqsTaskQueue(config['aws'])

        component_name = config.get('component_name')
        _logger.info('ECS Scheduler v%s', __version__)

        # NOTE: Flask in debug mode will restart the process
        # so only launch scheduler in the initial startup to avoid duplicate daemons
        # see: https://github.com/pallets/werkzeug/blob/master/werkzeug/_reloader.py
        if not os.getenv('WERKZEUG_RUN_MAIN'):
            _logger.info('Starting scheduld...')
            scheduler = ecs_scheduler.scheduld.create(config)
            scheduler.start()

        _logger.info('Starting webapi...')
        is_debug = config['webapi']['debug']
        server = ecs_scheduler.webapi.create(config, queue)
        server.run(debug=is_debug, host=None if is_debug else '0.0.0.0', use_evalex=False)
    except Exception:
        _logger.critical('unhandled scheduler exception', exc_info=True)
        raise
