"""ECS Scheduler web api subpackage."""
import logging
import logging.handlers

import flask
import flask_restful

from .home import Home
from .spec import Spec
from .jobs import Jobs, Job


def create():
    """
    Create the initial web server instance.

    This instance has no application-specific behaviors registered.

    :returns: An unadorned Flask instance
    """
    return flask.Flask(__name__)


def setup(app, ops_queue, datacontext):
    """
    Set up the web server with application behaviors.

    :param app: The flask app instance to set up
    :param ops_queue: Job ops queue for sending job operations to the scheduler daemon
    :param datacontext: The jobs data context for loading and saving jobs
    :returns: A flask application instance
    """
    api = flask_restful.Api(app, catch_all_404s=True)
    app.config['ERROR_404_HELP'] = False

    api.add_resource(Home, '/')

    api.add_resource(Spec, '/spec')

    api.add_resource(Jobs, '/jobs', resource_class_args=(ops_queue, datacontext))
    api.add_resource(Job, '/jobs/<job_id>', resource_class_args=(ops_queue, datacontext))

    app.after_request(_add_etag)

    _update_logger(app)

    return app


def _update_logger(app):
    try:
        file_handler = next(h for h in logging.getLogger().handlers if isinstance(h, logging.handlers.RotatingFileHandler))
    except StopIteration:
        pass
    else:
        app.logger.addHandler(file_handler)


def _add_etag(response):
    response.add_etag()
    return response
