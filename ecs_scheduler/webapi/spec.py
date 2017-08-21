"""Documentation REST resources."""
import flask
import flask_restful
import flask_swagger

from .. import env


class Spec(flask_restful.Resource):
    """Swagger spec REST resource."""
    def get(self):
        """
        API spec
        Return the swagger api specification.
        ---
        tags:
            - docs
        produces:
            - application/json
        responses:
            200:
                description: API spec documentation
        """
        swag = flask_swagger.swagger(flask.current_app)
        swag['info']['version'] = env.get_version()
        swag['info']['title'] = 'ECS Scheduler Web Api (webapi)'
        swag['basePath'] = '/'
        return swag
