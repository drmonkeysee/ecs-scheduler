"""ECS Scheduler web api subpackage."""
import logging

import flask
import flask_restful
import flask_cors

from .home import Home
from .spec import Spec
from .jobs import Jobs, Job
from .jobstore import JobStore


def create(ops_queue, jobs_datacontext):
    """
    Create the web server.

    :param ops_queue: Job ops queue for sending job operations to the scheduler daemon
    :param jobs_datacontext: The jobs data context for loading and saving jobs
    :returns: A flask application instance
    """
    app = flask.Flask(__name__)
    flask_cors.CORS(app, allow_headers='Content-Type')
    api = flask_restful.Api(app, catch_all_404s=True)

    api.add_resource(Home, '/')

    api.add_resource(Spec, '/spec')

    job_store = JobStore()
    api.add_resource(Jobs, '/jobs', resource_class_args=(job_store, ops_queue))
    api.add_resource(Job, '/jobs/<job_id>', resource_class_args=(job_store, ops_queue))

    _update_logger(app)

    return app


def _update_logger(app):
    try:
        file_handler = next(h for h in logging.getLogger().handlers if isinstance(h, logging.handlers.RotatingFileHandler))
    except StopIteration:
        pass
    else:
        app.logger.addHandler(file_handler)
