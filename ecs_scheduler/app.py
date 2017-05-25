"""Main entry for the ECS Scheduler application."""
import os
import logging
import atexit

# TODO: get this working once the package is deployable
#from setuptools_scm import get_version
import werkzeug.serving

import ecs_scheduler.webapi
import ecs_scheduler.scheduld
from . import init, joboperations, __version__


_logger = logging.getLogger(__name__)


def create():
    """
    Start the ECS scheduler daemon and create the flask server.

    :returns: The flask server instance
    """
    try:
        init.env()
        config = init.config()

        component_name = config.get('component_name')
        _logger.info('ECS Scheduler v%s', __version__)
        ops_queue = joboperations.DirectQueue()

        _logger.info('Creating webapi...')
        # TODO: need to refresh es updates immediately until we have a proper jobs store layer
        # also need to add universal config
        app = ecs_scheduler.webapi.create(config, ops_queue)

        # NOTE: Flask in debug mode will restart after initial startup
        # so only launch scheduler in the main Flask process to avoid duplicate daemons
        # see: https://github.com/pallets/werkzeug/blob/master/werkzeug/_reloader.py
        if werkzeug.serving.is_running_from_reloader() or not app.debug:
            _launch_scheduld(config, ops_queue)

        return app
    except Exception:
        _logger.critical('unhandled startup exception', exc_info=True)
        raise


def _launch_scheduld(config, ops_queue):
    _logger.info('Starting scheduld...')
    scheduler = ecs_scheduler.scheduld.create(config, ops_queue)
    scheduler.start()
    atexit.register(_on_exit, scheduler)


def _on_exit(scheduler):
    scheduler.stop()
