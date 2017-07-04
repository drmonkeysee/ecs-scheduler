"""
Model classes.

Most of these classes are intended for indirect use via the serialization module.
"""
import logging
import functools
from threading import RLock

from .persistence import NullSource


_logger = logging.getLogger(__name__)


def _sync(f):
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return f(self, *args, **kwargs)
    return wrapper


def _sync_yield(f):
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            yield from f(self, *args, **kwargs)
    return wrapper


# TODO: figure out schema usage
"""Job storage interface."""
class Jobs:
    """A job storage instance used by the application to load and store jobs."""
    @classmethod
    def load(cls, source=None):
        """
        Create and load a jobs from the given job source.

        :param source: The job source from which to load and store jobs;
                        uses null source if not specified
        :returns: A jobs storage resource attached to the given job data source
        """
        # TODO: rework to pick data source based on config
        if not source:
            source = NullSource()
            _logger.warning('!!! Warning !!!: No registered persistence layer found; falling back to null data source! Jobs will not be saved when the application terminates!')
        store = cls(source)
        store._fill()
        return store

    def __init__(self, source):
        """
        Create a job store.

        Use Jobs.load() instead of creating the object directly to ensure
        a properly initialized job store.

        :param source: The data source to use for loading and storing jobs
        """
        self._source = source
        self._lock = RLock()
        self._jobs = None

    @_sync
    def total(self):
        """
        Get the total number of jobs.

        :returns: The total job count
        """
        return len(self._jobs)

    @_sync_yield
    def get_all(self):
        """
        Get all jobs.

        :returns: A generator that yields all jobs in the job store
        """
        yield from self._jobs.values()

    @_sync
    def get(self, job_id):
        """
        Get a job by id.

        :param job_id: The id of the job to get
        :returns: The job for the given id
        :raises JobNotFound: If job not found
        """
        if job_id not in self._jobs:
            raise JobNotFound(job_id)
        return self._jobs[job_id]

    @_sync
    def create(self, job_id, job):
        """
        Create a new job.

        :param job_id: The id of the job to create
        :param **job: Keyword arguments for the new job
        :raises JobAlreadyExists: If job already exists
        """
        if job_id in self._jobs:
            raise JobAlreadyExists(job_id)
        self._source.create(job_id, job)
        self._jobs[job_id] = job

    @_sync
    def delete(self, job_id):
        """
        Delete a job.

        :param job_id: The id of the job to delete
        :raises JobNotFound: If job not found
        """
        if job_id not in self._jobs:
            raise JobNotFound(job_id)
        self._source.delete(job_id)
        del self._jobs[job_id]

    def _fill(self):
        self._jobs = self._source.load_all()


class Job:
    """A scheduled job for an ECS task."""
    def __init__(self, data, lock, source):
        """
        Create a job.

        Use Jobs.create() instead of creating the object directly to ensure
        a properly initialized job.

        :param data: The job data from the persistent store.
            The expected fields are determined by the ecs_scheduler.serialization.JobSchema class
            and its subclasses
        :param lock: The data source synchronization lock, provided by the Jobs instance
        :param source: The data source to use for persistence, provided by the Jobs instance

        :attribute data: The job data used to construct this job, as a dictionary
        """
        self.data = data
        self._lock = lock
        self._source = source

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

    @_sync
    def update(self, **fields):
        """
        Update the job.

        :param **fields: Fields to update on the given job
        """
        self._source.update(self.id, fields)
        self.annotate(**fields)

    @_sync
    def annotate(self, **fields):
        """
        Annotate the job.

        Annotated fields do not persist into the job data source.
        This is used for storing job fields that are only relevant
        during runtime and do not need to be persisted between application runs.

        :param **fields: Fields to set on the given job
        """
        self.data.update(fields)


class JobError(Exception):
    """General job error."""
    def __init__(self, job_id, *args, **kwargs):
        """
        Create a job error.

        :param job_id: The job id related to the failed jobs call
        :param *args: Additional exception positional arguments
        :param **kwargs: Additional exception keyword arugments
        """
        super().__init__(*args, **kwargs)
        self.job_id = job_id


class JobNotFound(JobError):
    """Job not found error."""
    pass


class JobAlreadyExists(JobError):
    """Job exists error."""
    pass


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
