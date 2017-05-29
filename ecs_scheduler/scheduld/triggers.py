"""Job triggers."""
import math

import boto3


_triggers = {}


def init():
    """Initialize built-in triggers."""
    global _triggers
    _triggers.update(sqs=SqsTrigger(), noop=NoOpTrigger())


def get(trigger_name):
    """
    Get a trigger by its name.

    :param trigger_name: The string name of the trigger to get
    :returns: The trigger for the given name or the NoOpTrigger if no such trigger is found
    """
    return _triggers.get(trigger_name, _triggers['noop'])


class NoOpTrigger:
    """The no-op trigger, used for jobs with no explicit trigger set."""
    def determine_task_count(self, job_data):
        """
        Determine the number of tasks that should be running.

        :param job_data: The job data dictionary
        :returns: The job's task count value
        """
        return min(job_data.get('maxCount', float('inf')), job_data['taskCount'])


class SqsTrigger:
    """An SQS trigger for a job."""
    def __init__(self):
        """Create a trigger."""
        self._sqs = boto3.resource('sqs')

    def determine_task_count(self, job_data):
        """
        Determine the number of tasks that should be running.

        :param job_data: The job data dictionary
        :returns: The desired ECS task count based on the number of messages
            in the queue and the desired scale factor in the job definition.
            At a minimum will return the task count of the job
        """
        queue = self._sqs.get_queue_by_name(QueueName=job_data['trigger']['queueName'])
        message_count = int(queue.attributes['ApproximateNumberOfMessages'])
        if message_count > 0:
            return self._calculate_task_count(message_count, job_data)
        return 0

    def _calculate_task_count(self, message_count, job_data):
        scaling_factor = job_data['trigger'].get('messagesPerTask')
        scaled_task_count = math.ceil(message_count / scaling_factor) if scaling_factor else 0
        return min(job_data.get('maxCount', float('inf')), max(scaled_task_count, job_data['taskCount']))
