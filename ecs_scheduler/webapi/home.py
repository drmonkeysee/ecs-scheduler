"""Root url REST resources."""
import flask
import flask_restful

from .jobs import Jobs
from .spec import Spec


class Home(flask_restful.Resource):
    """Home url REST resource."""

    def get(self):
        """
        Home
        Available endpoints for the web api.
        ---
        tags:
            - docs
        produces:
            - application/json
        responses:
            200:
                description: List of available endpoints
        """
        return {
            'resources': [
                {
                    'link': {
                        'rel': 'jobs',
                        'title': 'Jobs',
                        'href': flask.url_for(Jobs.__name__.lower()),
                    },
                },
                {
                    'link': {
                        'rel': 'spec',
                        'title': 'Spec',
                        'href': flask.url_for(Spec.__name__.lower()),
                    },
                }
            ],
        }
