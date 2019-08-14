from dataclasses import dataclass
"""
Miscellaneous model classes.

JobOperation communicates updates between the webapi and scheduler.

Pagination is a simple model object for webapi pagination operations.
"""


class JobOperation:
    """
    A job operation used to communicate changes to the scheduler via
    the ops queue between the web api and the scheduler daemon.

    :attribute ADD: Add operation label
    :attribute MODIFY: Modify operation label
    :attribute REMOVE: Remove operation label
    """
    ADD = 1
    MODIFY = 2
    REMOVE = 3

    @classmethod
    def add(cls, job_id):
        """
        Create an add job operation.

        :param job_id: The string id of the job to add to the scheduler
        """
        return cls(cls.ADD, job_id)

    @classmethod
    def modify(cls, job_id):
        """
        Create a modify job operation

        :param job_id: The string id of the job to modify in the scheduler
        """
        return cls(cls.MODIFY, job_id)

    @classmethod
    def remove(cls, job_id):
        """
        Create a remove job operation.

        :param job_id: The string id of the job to remove from the scheduler
        """
        return cls(cls.REMOVE, job_id)

    def __init__(self, operation, job_id):
        """
        Create a job operation.

        Use the factory class methods instead of __init___ directly
        to create an instance.

        :param operation: The operation label
        :param job_id: The string id of the job to apply the operation to
        """
        self.operation = operation
        self.job_id = job_id


@dataclass
class Pagination:
    """
    Job pagination parameters.

    :param skip: The number of jobs to skip
    :param count: The number of jobs to return
    :param total: The total number of jobs across all pages;
                  used to calculate next and prev page links
    """
    skip: int
    count: int
    total: int = 0
