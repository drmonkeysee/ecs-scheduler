"""
Model classes.

Most of these classes are intended for indirect use via the serialization module.
"""
class Job:
    """A scheduled job for an ECS task."""
    def __init__(self, **kwargs):
        """
        Create a job.

        :param **kwargs: The job data from the persistent store.
            The expected fields are determined by the ecs_scheduler.serialization.JobSchema class
            and its subclasses

        :attribute data: The job data used to construct this job, as a dictionary
        """
        self.data = kwargs

    @property
    def id(self):
        """
        Get or set the job id.

        :returns: The job id string
        """
        return self.data['id']

    @id.setter
    def id(self, value):
        self.data['id'] = value

    @property
    def suspended(self):
        """
        Get the job suspended flag.

        :returns: The job suspended flag or False if not set
        """
        return self.data.get('suspended', False)

    @property
    def parsed_schedule(self):
        """
        Get the parsed schedule.

        :returns: A dictionary representation of the schedule
            mapped to the expected arguments of the scheduler trigger.
        """
        return self.data['parsedSchedule']


class JobOperation:
    """
    A job operation used to communicate changes to the scheduler via the ops queue
    between the web api and the scheduler daemon.

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

        Use the factory class methods instead of __init___ directly to create an instance.

        :param operation: The operation label
        :param job_id: The string id of the job to apply the operation to
        """
        self.operation = operation
        self.job_id = job_id


class Pagination:
    """Job pagination parameters."""
    def __init__(self, skip, count, total=0):
        """
        Create a pagination object.

        :param skip: The number of jobs to skip
        :param count: The number of jobs to return
        :param total: The total number of jobs across all pages.
            Used to calculate next and prev page links
        """
        self.skip = skip
        self.count = count
        self.total = total
