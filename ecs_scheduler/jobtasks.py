"""Classes for operating on job tasks."""
import logging

import boto3

from .serialization import JobOperationSchema


_logger = logging.getLogger(__name__)


class DirectQueue:
    """
    An operations queue directly wired to the scheduler daemon.
    """
    def __init__(self):
        """
        Create a notifier queue.
        """
        self._consumer = None

    def register(self, consumer):
        """
        Register a consumer for the operations queue.

        Only supports a single consumer at a time; the existing consumer will be
        overridden by the new one when this method is called.

        :consumer: An instance of a queue consumer, implementing a notify(job_op) method
        """
        self._consumer = consumer

    def post(self, job_op):
        """
        Post a job operation to operations queue.

        :param job_op: The job operation to post
        """
        if self._consumer:
            self._consumer.notify(job_op)


class SqsTaskQueue:
    """
    A task queue backed by SQS

    The task queue is used to communicate creation, modification, and removal
    of scheduled jobs between the web api and the scheduler daemon via 'job operations'.
    A task wraps a job operation which tells the scheduler what to do with a particular job
    """
    def __init__(self, config):
        """
        Create a task queue

        :param config: AWS configuration from app config
        """
        self._q = boto3.resource('sqs').get_queue_by_name(QueueName=config['task_queue_name'])
        self._schema = JobOperationSchema(strict=True)

    def put(self, job_op):
        """
        Put a job operation on the task queue

        :param job_op: The job operation to place on the queue
        """
        body, e = self._schema.dumps(job_op)
        self._q.send_message(MessageBody=body)

    def get(self):
        """
        Get a task off the queue

        :returns: A task wrapping an sqs message for a job operation
        """
        messages = self._q.receive_messages(WaitTimeSeconds=20, MaxNumberOfMessages=1)
        return MsgTask(messages[0]) if messages else None


class MsgTask:
    """A job task that wraps an SQS message"""
    def __init__(self, sqs_message):
        """Create a message task

        :param sqs_message: The sqs message to wrap
        """
        self._context = sqs_message
        self._schema = JobOperationSchema()
        self._got_valid_job = False

    @property
    def task_id(self):
        """
        Get the task id of the message

        :returns: Return the message id string
        """
        return self._context.message_id

    def get_job_operation(self):
        """
        Extract the job operation object from the task

        :returns: A job operation object
        :raises InvalidMessageException: If the message body cannot be parsed into a job operation
        """
        body = self._context.body
        obj, errors = self._schema.loads(body)
        if errors:
            raise InvalidMessageException('Errors encountered when parsing task message "{}": {}'.format(self._context.message_id, errors))
        self._got_valid_job = True
        return obj

    def complete(self):
        """Mark the task as completed"""
        if self._got_valid_job:
            self._context.delete()
            _logger.info('Processed task message "%s"', self.task_id)


class InvalidMessageException(Exception):
    """Exception for invalid message body"""
    pass
