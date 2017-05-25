"""Job REST resources."""
import logging
import functools

import flask
import flask_restful

from ..serialization import PaginationSchema, JobSchema, JobCreateSchema, JobResponseSchema
from ..models import Pagination, JobOperation
from .jobstore import JobExistsException, JobNotFoundException


_logger = logging.getLogger(__name__)


def require_json_content_type(verb):
    """A decorator for enforcing json content-type constraints on http requests."""
    @functools.wraps(verb)
    def ct_checker(*args, **kwargs):
        return verb(*args, **kwargs) \
                if flask.request.headers.get('Content-Type', '').startswith('application/json') \
                else ({'message': 'Request requires Content-Type: application/json'}, 415)
    return ct_checker


def _job_link(job_id):
    return {'rel': 'item', 'title': 'Job for {}'.format(job_id), 'href': flask.url_for(Job.__name__.lower(), job_id=job_id)}


def _job_committed_response(job_id):
    return {
        'id': job_id,
        'link': _job_link(job_id)
    }


def _job_notfound_response(job_id):
    return {'message': 'Job {} does not exist'.format(job_id)}, 404


def _post_operation(job_op, ops_queue, job_response):
    try:
        ops_queue.put(job_op)
    except Exception:
        _logger.exception('Exception when posting job operation to ops queue')
        flask_restful.abort(500,
            item=job_response,
            message='Job update was saved correctly but failed to post update message to scheduler')


def _deserialize_data(data, schema, status_if_failure=400):
    obj, errors = schema.load(data)
    if errors:
        flask_restful.abort(status_if_failure, messages=errors)
    else:
        return obj


_job_response_schema = JobResponseSchema(_job_link)


class Jobs(flask_restful.Resource):
    """
    Jobs REST Resource
    REST operations for a collection of jobs.
    """
    def __init__(self, store, ops_queue):
        """
        Create jobs resource.

        :param store: Document store for updating persistent data
        :param ops_queue: Ops queue to post job operations to after updating document store
        """
        self._store = store
        self._ops_queue = ops_queue
        self._pagination_schema = PaginationSchema()
        self._request_schema = JobCreateSchema()

    def get(self):
        """
        Get jobs
        List of scheduled jobs.
        ---
        tags:
            - jobs
        produces:
            - application/json
        parameters:
            -   name: skip
                in: query
                type: integer
                default: 0
                description: number of jobs to skip
            -   name: count
                in: query
                type: integer
                default: 10
                description: number of jobs to return
        responses:
            200:
                description: Paginated list of scheduled jobs
            400:
                description: Invalid pagination arguments
            default:
                description: Server error
        """
        pagination = _deserialize_data(flask.request.values, self._pagination_schema)
        response = self._store.get_jobs(pagination.skip, pagination.count)
        docs = response['hits']['hits']
        result = {
            'jobs': [_job_response_schema.dump(job_obj).data for job_obj in [_deserialize_data(d, _job_response_schema, status_if_failure=500) for d in docs]]
        }
        self._set_pagination(result, pagination, response['hits']['total'])
        return result

    @require_json_content_type
    def post(self):
        """
        Create job
        Create a new scheduled job.
        ---
        tags:
            - jobs
        consumes:
            - application/json
        produces:
            - application/json
        parameters:
            -   in: body
                name: body
                schema:
                    id: Job
                    required:
                        - taskDefinition
                        - schedule
                    properties:
                        taskDefinition:
                            type: string
                            description: Name of task definition in ECS and used as job id if no id is explicitly specified
                        id:
                            type: string
                            description: >
                                Id of scheduler job. This will be set to taskDefinition if not otherwise specified,
                                and is only necessary if multiple jobs share the same task definition and therefore
                                need a unique id. Generally used in conjuction with overrides
                        schedule:
                            type: string
                            description: >
                                Cron-style description of the job's run schedule.
                                See README.md at https://github.com/drmonkeysee/ecs-scheduler for details
                        taskCount:
                            type: integer
                            default: 1
                            minimum: 1
                            maximum: 50
                            description: Number of tasks to start when the job is run
                        maxCount:
                            type: integer
                            minimum: 1
                            maximum: 50
                            description: Maximum number of tasks to run
                        scheduleStart:
                            type: string
                            description: Start date in ISO-8601 format from which to begin scheduling the job
                        scheduledEnd:
                            type: string
                            description: End date in ISO-8601 format at which to stop scheduling the job
                        suspended:
                            type: boolean
                            default: false
                            description: Tell the scheduler to suspend the job
                        trigger:
                            $ref: '#/definitions/Trigger'
                        overrides:
                            type: array
                            items:
                                $ref: '#/definitions/Override'
        definitions:
            - schema:
                id: Trigger
                required:
                    - type
                properties:
                    type:
                        type: string
                        enum:
                            - sqs
                        description: Trigger type
                    queueName:
                        type: string
                        description: SQS queue name, required if type is 'sqs'
                    messagesPerTask:
                        type: integer
                        description: >
                            Scaling factor for sqs triggers.
                            Will start up number of tasks based on number of messages in queue.
                            If taskCount is larger than the number of tasks calculated based on message count
                            then taskCount tasks will be started instead
            - schema:
                id: Override
                required:
                    - containerName
                properties:
                    containerName:
                        type: string
                        description: The name of the container in the task definition to apply the overrides to
                    environment:
                        type: object
                        description: >
                            Environment variable overrides for the named container as "NAME": "VALUE" pairs
        responses:
            201:
                description: Job created and scheduled
            400:
                description: Invalid body
            409:
                description: Job already exists
            415:
                description: Invalid request media type
            default:
                description: Server error
        """
        job_item = _deserialize_data(flask.request.json, self._request_schema)
        job_doc_body, e = self._request_schema.dump(job_item)
        try:
            response = self._store.create(job_item.id, job_doc_body)
        except JobExistsException:
            return {'message': 'Job {} already exists'.format(job_item.id)}, 409
        web_response = _job_committed_response(job_item.id)
        _post_operation(JobOperation.add(job_item.id), self._ops_queue, web_response)
        return web_response, 201

    def _set_pagination(self, result, pagination, total):
        prev_link = self._pagination_link(Pagination(pagination.skip - pagination.count, pagination.count, total))
        if prev_link:
            result['prev'] = prev_link
        next_link = self._pagination_link(Pagination(pagination.skip + pagination.count, pagination.count, total))
        if next_link:
            result['next'] = next_link

    def _pagination_link(self, page_frame):
        values, e = self._pagination_schema.dump(page_frame)
        return flask.url_for(Jobs.__name__.lower(), **values) if values else None


class Job(flask_restful.Resource):
    """
    Job REST Resource
    REST operations for a single job.
    """
    def __init__(self, store, ops_queue):
        """
        Create job resource.

        :param store: Document store for updating persistent data
        :param ops_queue: Ops queue to post job operations to after updating document store
        """
        self._store = store
        self._ops_queue = ops_queue
        self._request_schema = JobSchema()

    def get(self, job_id):
        """
        Get a job
        The job for the given id.
        ---
        tags:
            - jobs
        produces:
            - application/json
        parameters:
            -   name: job_id
                in: path
                type: string
                required: true
                description: the job id
        responses:
            200:
                description: The job for job id
            404:
                description: Job not found
            default:
                description: Server error
        """
        try:
            response = self._store.get(job_id)
        except JobNotFoundException:
            return _job_notfound_response(job_id)
        job = _deserialize_data(response, _job_response_schema, status_if_failure=500)
        return _job_response_schema.dump(job).data

    @require_json_content_type
    def put(self, job_id):
        """
        Update job
        Update the specified job.
        ---
        tags:
            - jobs
        consumes:
            - application/json
        produces:
            - application/json
        parameters:
            -   name: job_id
                in: path
                type: string
                required: true
                description: the job id
            -   in: body
                name: body
                schema:
                    id: JobUpdate
                    properties:
                        taskDefinition:
                            type: string
                            description: Name of task definition in ECS
                        schedule:
                            type: string
                            description: Cron-style description of the job's run schedule
                        taskCount:
                            type: integer
                            default: 1
                            minimum: 1
                            maximum: 50
                            description: Number of tasks to start when the job is run
                        maxCount:
                            type: integer
                            minimum: 1
                            maximum: 50
                            description: Maximum number of tasks to run
                        scheduleStart:
                            type: string
                            description: Start date in ISO-8601 format from which to begin scheduling the job
                        scheduledEnd:
                            type: string
                            description: End date in ISO-8601 format at which to stop scheduling the job
                        suspended:
                            type: boolean
                            default: false
                            description: Tell the scheduler to suspend the job
                        trigger:
                            $ref: '#/definitions/Trigger'
                        overrides:
                            type: array
                            items:
                                $ref: '#/definitions/Override'
        responses:
            200:
                description: Job updated and rescheduled
            400:
                description: Invalid body
            404:
                description: Job not found
            415:
                description: Invalid request media type
            default:
                description: Server error
        """
        job_update = _deserialize_data(flask.request.json, self._request_schema)
        job_doc, e = self._request_schema.dump(job_update)
        try:
            response = self._store.update(job_id, job_doc)
        except JobNotFoundException:
            return _job_notfound_response(job_id)
        web_response = _job_committed_response(job_id)
        _post_operation(JobOperation.modify(job_id), self._ops_queue, web_response)
        return web_response

    def delete(self, job_id):
        """
        Delete job
        Delete and unschedule the specified job.
        ---
        tags:
            - jobs
        produces:
            - application/json
        parameters:
            -   name: job_id
                in: path
                type: string
                required: true
                description: the job id
        responses:
            200:
                description: Job deleted
            404:
                description: Job not found
            default:
                description: Server error
        """
        try:
            response = self._store.delete(job_id)
        except JobNotFoundException:
            return _job_notfound_response(job_id)
        web_response = {'id': job_id}
        _post_operation(JobOperation.remove(job_id), self._ops_queue, web_response)
        return web_response
