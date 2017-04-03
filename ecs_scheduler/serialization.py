"""Serialization schemas for scheduler classes"""
import re
import random
import marshmallow
import apscheduler.triggers.cron
from .models import Job, Pagination, JobOperation


_MIN_TASKS = 1
_MAX_TASKS = 50


def _validate_task_definition_name(value):
    if re.search(':\d*', value):
        raise marshmallow.ValidationError('task definition names cannot contain revision numbers')


class TriggerSchema(marshmallow.Schema):
    """
    Schema of a job schedule trigger.

    Schedule triggers are used to schedule a job based on an AWS event instead of a date/time point.
    An example of a trigger would be when messages are present in an SQS queue.
    Jobs may contain triggers"""
    type = marshmallow.fields.String(required=True)
    queueName = marshmallow.fields.String()
    messagesPerTask = marshmallow.fields.Integer(validate=marshmallow.validate.Range(min=1))

    @marshmallow.validates_schema
    def validate_trigger(self, data):
        if data.get('type') == 'sqs' and 'queueName' not in data:
            raise marshmallow.ValidationError('sqs trigger type requires "queueName" field')


class OverrideSchema(marshmallow.Schema):
    """
    Schema of a list of task overrides.

    Task overrides are passed to ECS when a new task is stared"""
    containerName = marshmallow.fields.String(required=True)
    environment = marshmallow.fields.Dict()


class TaskInfoSchema(marshmallow.Schema):
    """
    Schema of task information

    Task info records information about ECS assets started by the scheduler
    """
    taskId = marshmallow.fields.String()
    hostId = marshmallow.fields.String()


class JobSchema(marshmallow.Schema):
    """
    Schema of a job.

    A job is an ecs scheduler document that defines a run schedule for an ECS task
    """
    _WILD_CARD = '?'

    taskDefinition = marshmallow.fields.String(validate=_validate_task_definition_name)
    schedule = marshmallow.fields.String()
    scheduleStart = marshmallow.fields.DateTime()
    scheduleEnd = marshmallow.fields.DateTime()
    taskCount = marshmallow.fields.Integer(validate=marshmallow.validate.Range(_MIN_TASKS, _MAX_TASKS))
    maxCount = marshmallow.fields.Integer(validate=marshmallow.validate.Range(_MIN_TASKS, _MAX_TASKS))
    trigger = marshmallow.fields.Nested(TriggerSchema)
    suspended = marshmallow.fields.Boolean()
    parsedSchedule = marshmallow.fields.Raw(load_only=True)
    overrides = marshmallow.fields.List(marshmallow.fields.Nested(OverrideSchema))
    lastRun = marshmallow.fields.DateTime()
    lastRunTasks = marshmallow.fields.List(marshmallow.fields.Nested(TaskInfoSchema))
    estimatedNextRun = marshmallow.fields.DateTime()

    @marshmallow.validates('parsedSchedule')
    def validate_parsed_schedule(self, value):
        if not value:
            return
        try:
            apscheduler.triggers.cron.CronTrigger(timezone='UTC', **value)
        except ValueError as ex:
            raise marshmallow.ValidationError(['Invalid schedule syntax: {}'.format(error) for error in ex.args]) from ex

    @marshmallow.pre_load
    def parse_schedule(self, data):
        schedule = data.get('schedule')
        if schedule:
            data['schedule'], data['parsedSchedule'] = self._parse_schedule(schedule)

    @marshmallow.post_load
    def create_job(self, data):
        return Job(**data)

    @marshmallow.pre_dump
    def get_job_data(self, data):
        return data.data

    def _parse_schedule(self, value):
        schedule_parts = value.split()
        # these names come from apscheduler.triggers.cron.CronTrigger
        # see: https://apscheduler.readthedocs.org/en/latest/modules/triggers/cron.html#module-apscheduler.triggers.cron
        # to handle 'xth y' or 'last x' use underscore e.g. 'xth_y', 'last_x'
        params = ['second', 'minute', 'hour', 'day_of_week', 'week', 'day', 'month', 'year']
        schedule_args = dict(zip(params, schedule_parts))
        day = schedule_args.get('day')
        if day:
            schedule_args['day'] = day.replace('_', ' ')
        return self._process_wildcards(zip(params[:3], [range(60), range(60), range(24)]), value, schedule_args)

    def _process_wildcards(self, wc_params, schedule_expression, schedule_args):
        for wc_param in wc_params:
            k = wc_param[0]
            value = schedule_args.get(k)
            if value == self._WILD_CARD:
                new_value = str(random.choice(wc_param[1]))
                schedule_args[k] = new_value
                schedule_expression = schedule_expression.replace(self._WILD_CARD, new_value, 1)
        return schedule_expression, schedule_args


class JobCreateSchema(JobSchema):
    """
    Schema of a job creation request

    This extends JobSchema to define id as a required field and validate input.
    Used by the web api to create jobs
    """
    # use validate param instead of decorator to report 'taskDefinition' as the invalid field instead of 'id'
    id = marshmallow.fields.String(required=True, validate=_validate_task_definition_name, load_from='taskDefinition', load_only=True)
    schedule = marshmallow.fields.String(required=True)
    taskCount = marshmallow.fields.Integer(missing=_MIN_TASKS, validate=marshmallow.validate.Range(_MIN_TASKS, _MAX_TASKS))


class JobResponseSchema(JobSchema):
    """
    Schema of a job response

    This extends JobSchema to parse an elasticsearch job document into a Job object
    and deserialize the object into a REST JSON representation
    """
    id = marshmallow.fields.String(load_from='_id')
    link = marshmallow.fields.Method('link_generator', dump_only=True)
    
    def __init__(self, link_func, **kwargs):
        self._link_func = link_func
        super().__init__(**kwargs)

    @marshmallow.pre_load
    def flatten_source(self, data):
        if '_source' in data:
            d = data.copy()
            d.update(data['_source'])
            return d

    def link_generator(self, obj):
        return self._link_func(obj['id'])


class PaginationSchema(marshmallow.Schema):
    """Schema for pagination arguments"""
    skip = marshmallow.fields.Integer(missing=0)
    count = marshmallow.fields.Integer(missing=10)

    @marshmallow.post_load
    def make_pagination(self, data):
        for field in self.fields.keys():
            data[field] = max(0, data[field])
        return Pagination(**data)

    @marshmallow.pre_dump
    def adjust_page_frame(self, obj):
        if obj.total <= 0 or (obj.skip + obj.count) <= 0 or obj.skip >= obj.total:
            return {}
        obj.skip = max(0, obj.skip)

    @marshmallow.post_dump
    def strip_defaults(self, data):
        return {k: v for k, v in data.items() if v != self._get_field_missing_value(k)}

    def _get_field_missing_value(self, name):
        field = self.fields.get(name)
        return field.missing if field else None


class JobOperationSchema(marshmallow.Schema):
    """
    Schema for a job operation

    This is used to serialize and deserialize Job objects to and from the task queue
    between the web api and the scheduler daemon
    """
    job_id = marshmallow.fields.String(required=True)
    operation = marshmallow.fields.Integer(required=True)

    @marshmallow.post_load
    def create_job_op(self, data):
        return JobOperation(**data)
