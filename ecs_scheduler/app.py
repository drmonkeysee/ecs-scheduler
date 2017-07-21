"""Main entry for the ECS Scheduler application."""
import os
import logging
import atexit

from setuptools_scm import get_version
import werkzeug.serving

from . import webapi, scheduld, startup, operations, datacontext


_logger = logging.getLogger(__name__)


def create():
    """
    Start the ECS scheduler daemon and create the flask server.

    :returns: The flask server instance
    """
    try:
        startup.init()

        _logger.info('ECS Scheduler v%s', get_version())
        ops_queue = operations.DirectQueue()
        jobs_dc = datacontext.Jobs.load()

        _logger.info('Creating webapi...')
        app = webapi.create(ops_queue, jobs_dc)

        # NOTE: Flask in debug mode will restart after initial startup
        # so only launch scheduler in the main Flask process to avoid duplicate daemons
        # see: https://github.com/pallets/werkzeug/blob/master/werkzeug/_reloader.py
        if werkzeug.serving.is_running_from_reloader() or not app.debug:
            _launch_scheduld(ops_queue, jobs_dc)

        return app
    except Exception:
        _logger.critical('unhandled startup exception', exc_info=True)
        raise


def _launch_scheduld(ops_queue, jobs_dc):
    _logger.info('Starting scheduld...')
    scheduler = scheduld.create(ops_queue, jobs_dc)
    scheduler.start()
    atexit.register(_on_exit, scheduler)


def _on_exit(scheduler):
    scheduler.stop()
