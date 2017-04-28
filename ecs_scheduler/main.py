"""Main entry for the ECS Scheduler application."""
import os
import logging
import atexit

# TODO: get this working once the package is deployable
#from setuptools_scm import get_version
import werkzeug.serving

import ecs_scheduler.webapi
import ecs_scheduler.scheduld
from . import init, jobtasks, __version__


_logger = logging.getLogger(__name__)


def create_app():
    """
    Start the ECS scheduler daemon and create the flask server.

    :returns: The flask server instance
    """
    try:
        init.env()
        config = init.config()

        component_name = config.get('component_name')
        _logger.info('ECS Scheduler v%s', __version__)

        _logger.info('Creating webapi...')
        app = ecs_scheduler.webapi.create(config, jobtasks.SqsTaskQueue(config['aws']))

        # NOTE: Flask in debug mode will restart after initial startup
        # so only launch scheduler in the main Flask process to avoid duplicate daemons
        # see: https://github.com/pallets/werkzeug/blob/master/werkzeug/_reloader.py
        if werkzeug.serving.is_running_from_reloader() or not app.debug:
            _launch_scheduld(config)

        return app
    except Exception:
        _logger.critical('unhandled scheduler exception', exc_info=True)
        raise


def _launch_scheduld(config):
    _logger.info('Starting scheduld...')
    scheduler = ecs_scheduler.scheduld.create(config)
    scheduler.start()
    atexit.register(_on_exit, scheduler)


def _on_exit(scheduler):
    scheduler.stop()
