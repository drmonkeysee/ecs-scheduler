"""Web API main server"""
import logging
import flask
import flask_restful
import flask.ext.cors
from .home import Home
from .spec import Spec
from .jobs import Jobs, Job
from .jobstore import JobStore


_app = None
_api = None


def run(config, task_queue):
    """
    Start web server

    :param config: The application configuration dictionary
    :param task_queue: Job task queue for sending job operations to the scheduler daemon
    """
    _app = flask.Flask(__name__)
    flask.ext.cors.CORS(_app, allow_headers='Content-Type')
    _api = flask_restful.Api(_app, catch_all_404s=True)

    _api.add_resource(Home, '/')

    _api.add_resource(Spec, '/spec')

    job_store = JobStore(config['elasticsearch'])
    _api.add_resource(Jobs, '/jobs', resource_class_args=(job_store, task_queue))
    _api.add_resource(Job, '/jobs/<job_id>', resource_class_args=(job_store, task_queue))
    
    logging.info('Starting webapi...')
    is_debug = config['webapi']['debug']
    _app.run(debug=is_debug, host=None if is_debug else '0.0.0.0', use_evalex=False)
