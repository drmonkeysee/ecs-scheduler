"""ECS Scheduler web api subpackage."""
import flask
import flask_restful
import flask_cors

from .home import Home
from .spec import Spec
from .jobs import Jobs, Job
from .jobstore import JobStore


def create(config, task_queue):
    """
    Create the web server.

    :param config: The application configuration dictionary
    :param task_queue: Job task queue for sending job operations to the scheduler daemon
    :returns: A flask application instance
    """
    app = flask.Flask(__name__)
    flask_cors.CORS(app, allow_headers='Content-Type')
    api = flask_restful.Api(app, catch_all_404s=True)

    api.add_resource(Home, '/')

    api.add_resource(Spec, '/spec')

    job_store = JobStore(config['elasticsearch'])
    api.add_resource(Jobs, '/jobs', resource_class_args=(job_store, task_queue))
    api.add_resource(Job, '/jobs/<job_id>', resource_class_args=(job_store, task_queue))
    
    return app
