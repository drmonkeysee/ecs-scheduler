"""Job REST resources."""
import functools
import logging
from itertools import islice

import flask
import flask_restful

from ..datacontext import JobAlreadyExists, JobNotFound, InvalidJobData
from ..models import Pagination, JobOperation
from ..serialization import PaginationSchema, JobResponseSchema


_logger = logging.getLogger(__name__)


def require_json_content_type(verb):
    """
    A decorator for enforcing json content-type constraints on http requests.
    """
    @functools.wraps(verb)
    def ct_checker(*args, **kwargs):
        return (verb(*args, **kwargs)
                if flask.request.headers.get('Content-Type', '')
                .startswith('application/json')
                else ({
                    'message': 'Header Content-Type: application/json'
                               ' required to send a request body.',
                }, 415))
    return ct_checker


def _job_link(job_id):
    return {
        'rel': 'item',
        'title': f'Job for {job_id}',
        'href': flask.url_for(Job.__name__.lower(), job_id=job_id),
    }


def _job_committed_response(job_id):
    return {
        'id': job_id,
        'link': _job_link(job_id),
    }


def _post_operation(job_op, ops_queue, job_response):
    try:
        ops_queue.post(job_op)
    except Exception:
        _logger.exception('Exception when posting job operation to ops queue.')
        flask_restful.abort(500,
                            item=job_response,
                            message='Job update was saved correctly but failed'
                            ' to post update message to scheduler.')


_job_response_schema = JobResponseSchema(_job_link, strict=True)


class Jobs(flask_restful.Resource):
    """
    Jobs REST Resource
    REST operations for a collection of jobs.
    """

    def __init__(self, ops_queue, datacontext):
        """
        Create jobs resource.

        :param ops_queue: Ops queue to post job operations to after
                          updating document store
        :param datacontext: The jobs data context for loading and saving jobs
        """
        self._ops_queue = ops_queue
        self._dc = datacontext
        self._pagination_schema = PaginationSchema()

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
        pagination = self._parse_pagination(flask.request.values)
        jobs_page = islice(self._dc.get_all(), pagination.skip,
                           pagination.skip + pagination.count)
        result = {
            'jobs': [
                _job_response_schema.dump(j.data).data
                for j in jobs_page
            ],
        }
        self._set_pagination(result, pagination, self._dc.total())
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
                            description: Name of task definition in ECS and
                                         used as job id if no id is explicitly
                                         specified
                        id:
                            type: string
                            description: >
                                Id of scheduler job. This will be set to
                                taskDefinition if not otherwise specified, and
                                is only necessary if multiple jobs share the
                                same task definition and therefore need a
                                unique id. Generally used in conjuction with
                                overrides
                        schedule:
                            type: string
                            description: >
                                Cron-style description of the job's run
                                schedule.
                                See README.md at
                                https://github.com/drmonkeysee/ecs-scheduler
                                for details
                        taskCount:
                            type: integer
                            default: 1
                            minimum: 1
                            maximum: 50
                            description: Number of tasks to start when the
                                         job is run
                        maxCount:
                            type: integer
                            minimum: 1
                            maximum: 50
                            description: Maximum number of tasks to run
                        scheduleStart:
                            type: string
                            description: >
                                Start date in ISO-8601 format from which to
                                begin scheduling the job; if timezone offset
                                is omitted it will default to UTC
                        scheduledEnd:
                            type: string
                            description: >
                                End date in ISO-8601 format at which to stop
                                scheduling the job; if timezone offset is
                                omitted it will default to UTC
                        timezone:
                            type: string
                            description: >
                                Timezone used for interpreting the schedule;
                                if omitted the scheduler will use UTC;
                                see pytz documentation for valid values
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
                            Will start up number of tasks based on number of
                            messages in queue; if taskCount is larger than the
                            number of tasks calculated based on message count
                            then taskCount tasks will be started instead
            - schema:
                id: Override
                required:
                    - containerName
                properties:
                    containerName:
                        type: string
                        description: The name of the container in the task
                                     definition to apply the overrides to
                    environment:
                        type: object
                        description: >
                            Environment variable overrides for the named
                            container as "NAME": "VALUE" pairs
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
        job_data = flask.request.json
        try:
            new_job = self._dc.create(job_data)
        except InvalidJobData as ex:
            flask_restful.abort(400, messages=ex.errors)
        except JobAlreadyExists as ex:
            flask_restful.abort(409,
                                message=f'Job {ex.job_id} already exists.')
        web_response = _job_committed_response(new_job.id)
        _post_operation(JobOperation.add(new_job.id), self._ops_queue,
                        web_response)
        return web_response, 201

    def _parse_pagination(self, data):
        obj, errors = self._pagination_schema.load(data)
        if errors:
            flask_restful.abort(400, messages=errors)
        else:
            return obj

    def _set_pagination(self, result, pagination, total):
        prev_link = self._pagination_link(
            Pagination(pagination.skip - pagination.count,
                       pagination.count, total))
        if prev_link:
            result['prev'] = prev_link
        next_link = self._pagination_link(
            Pagination(pagination.skip + pagination.count,
                       pagination.count, total))
        if next_link:
            result['next'] = next_link

    def _pagination_link(self, page_frame):
        values, e = self._pagination_schema.dump(page_frame)
        return (flask.url_for(Jobs.__name__.lower(), **values)
                if values
                else None)


class Job(flask_restful.Resource):
    """
    Job REST Resource
    REST operations for a single job.
    """

    def __init__(self, ops_queue, datacontext):
        """
        Create job resource.

        :param store: Document store for updating persistent data
        :param ops_queue: Ops queue to post job operations to after updating
                          document store
        :param datacontext: The jobs data context for loading and saving jobs
        """
        self._ops_queue = ops_queue
        self._dc = datacontext

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
            job = self._dc.get(job_id)
        except JobNotFound:
            self._raise_job_notfound(job_id)
        return _job_response_schema.dump(job.data).data

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
                            description: Cron-style description of the job's
                                         run schedule
                        taskCount:
                            type: integer
                            default: 1
                            minimum: 1
                            maximum: 50
                            description: Number of tasks to start when the job
                                         is run
                        maxCount:
                            type: integer
                            minimum: 1
                            maximum: 50
                            description: Maximum number of tasks to run
                        scheduleStart:
                            type: string
                            description: >
                                Start date in ISO-8601 format from which to
                                begin scheduling the job; if timezone offset
                                is omitted it will default to UTC
                        scheduledEnd:
                            type: string
                            description: >
                                End date in ISO-8601 format at which to stop
                                scheduling the job; if timezone offset is
                                omitted it will default to UTC
                        timezone:
                            type: string
                            description: >
                                Timezone used for interpreting the schedule;
                                if omitted the scheduler will use UTC;
                                see pytz documentation for valid values
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
        try:
            current_job = self._dc.get(job_id)
        except JobNotFound:
            self._raise_job_notfound(job_id)
        job_update = flask.request.json
        try:
            current_job.update(job_update)
        except InvalidJobData as ex:
            flask_restful.abort(400, messages=ex.errors)
        web_response = _job_committed_response(job_id)
        _post_operation(JobOperation.modify(job_id),
                        self._ops_queue, web_response)
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
            self._dc.delete(job_id)
        except JobNotFound:
            self._raise_job_notfound(job_id)
        web_response = {'id': job_id}
        _post_operation(JobOperation.remove(job_id),
                        self._ops_queue, web_response)
        return web_response

    def _raise_job_notfound(self, job_id):
        flask_restful.abort(404, message=f'Job {job_id} does not exist.')
