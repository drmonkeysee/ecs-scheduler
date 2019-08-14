"""Classes for operating on job operations."""


class DirectQueue:
    """An operations queue directly wired to the scheduler daemon."""

    def __init__(self):
        """Create a notifier queue."""
        self._consumer = None

    def register(self, consumer):
        """
        Register a consumer for the operations queue.

        Only supports a single consumer at a time; the existing consumer
        will be overridden by the new one when this method is called.

        :consumer: An instance of a queue consumer,
                   implementing a notify(job_op) method
        """
        self._consumer = consumer

    def post(self, job_op):
        """
        Post a job operation to operations queue.

        :param job_op: The job operation to post
        """
        if self._consumer:
            self._consumer.notify(job_op)
