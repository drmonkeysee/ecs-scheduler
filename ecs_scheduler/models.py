"""
Model classes.

Jobs and Job represent job storage and individual jobs, respectively.
Job data is controlled by the schemas in ecs_scheduler.serialization module.
All job loading and storing exceptions inherit from JobError.

JobOperation communicates updates between the webapi and scheduler.

Pagination is a simple model object for webapi pagination operations.
"""
import logging
import functools
import collections.abc
from threading import RLock

from .persistence import NullSource
from .serialization import JobSchema


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


"""Job storage."""
class Jobs:
    """A job storage instance used by the application to load and store jobs."""
    @classmethod
    def load(cls, source=None):
        """
        Create and load jobs from the given job source.

        :param source: The job source from which to load and store jobs;
                        uses null source if not specified
        :returns: A jobs storage resource attached to the given job data source
        :raises: InvalidJobData if job fields fail validation
        :raises: JobPersistenceError if job loading fails
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
        :raises: JobNotFound if job not found
        """
        if job_id not in self._jobs:
            raise JobNotFound(job_id)
        return self._jobs[job_id]

    @_sync
    def create(self, job_id, job_data):
        """
        Create a new job.

        :param job_id: The id of the job to create
        :param job_data: Data dictionary for the new job
        :raises: JobAlreadyExists if job already exists
        :raises: InvalidJobData if job fields fail validation
        :raises: JobPersistenceError if job creation fails
        """
        if job_id in self._jobs:
            raise JobAlreadyExists(job_id)
        self._jobs[job_id] = self._create_job(job_id, job_data)

    @_sync
    def delete(self, job_id):
        """
        Delete a job.

        :param job_id: The id of the job to delete
        :raises: JobNotFound if job not found
        :raises: JobPersistenceError if job deletion fails
        """
        if job_id not in self._jobs:
            raise JobNotFound(job_id)
        try:
            self._source.delete(job_id)
        except Exception as ex:
            raise JobPersistenceError(self.id) from ex
        del self._jobs[job_id]

    def _fill(self):
        parsed_jobs = (self._create_job(job_id, raw_data) for job_id, raw_data in self._source.load_all())
        return {job.id: job for job in parsed_jobs}

    def _create_job(job_id, job_data):
        return Job(job_id, job_data, self._lock, self._source)


class Job:
    """
    A persistent job representing an ECS scheduled task.

    Stored and retrieved by a Jobs job store.
    """
    def __init__(self, job_id, data, lock, source):
        """
        Create a persistent job.

        Use Jobs.create() instead of creating the object directly to ensure
        a properly initialized and persisted job.

        :param data: The job fields that make up the job
        :param lock: The data source synchronization lock, provided by the Jobs instance
        :param source: The data source to use for persistence, provided by the Jobs instance
        :raises: InvalidJobData if job data fails field validation
        :raises: JobPersistenceError if job creation fails
        """
        self._id = job_id
        self._schema = JobSchema()
        self._data, errors = self._schema.load(data)
        if errors:
            raise InvalidJobData(job_id, errors)
        self._mapping = JobDataMapping(self._data)
        self._lock = lock
        self._source = source
        try:
            self._source.create(self.id, self._schema.dump(self._data).data)
        except Exception as ex:
            raise JobPersistenceError(self.id) from ex

    @property
    def id(self):
        """
        Get or set the job id.

        :returns: The job id string
        """
        return self._id

    @property
    def data(self):
        """
        Get a read-only view of the job data.

        :returns: The job data read-only dict
        """
        return self._mapping

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
        :raises: InvalidJobData if job data fails field validation
        :raises: JobPersistenceError if job update fails
        """
        validated_fields, errors = self._schema.load(fields)
        if errors:
            raise InvalidJobData(self.id, errors)
        try:
            self._source.update(self.id, self._schema.dump(validated_fields).data)
        except Exception as ex:
            raise JobPersistenceError(self.id) from ex
        self.annotate(fields)

    @_sync
    def annotate(self, **fields):
        """
        Annotate the job.

        Annotated fields do not persist into the job data source.
        This is used for storing job fields that are only relevant
        during runtime and do not need to be persisted between application runs.

        :param **fields: Fields to set on the given job
        """
        self._data.update(fields)


class JobDataMapping(collections.abc.Mapping):
    """A read-only dictionary wrapper for job data."""
    def __init__(self, data):
        """
        Create a mapping for the given dictionary.

        :param data: The data dictionary to wrap
        """
        self._data = data

    def __getitem__(self, key):
        """
        Get a value for the given key.

        :param key: The key for the value to get
        :returns: The value for the given key
        """
        return self._data[key]

    def __iter__(self):
        """
        Iterate the underlying data.

        :returns: An iterator for the underlying data
        """
        return iter(self._data)

    def __len__(self):
        """
        The length of the data.

        :returns: Length of the underlying data
        """
        return len(self._data)


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


class JobPersistenceError(JobError):
    """General error for job persistence failures."""
    pass


class InvalidJobData(JobError):
    """Invalid job data error."""
    def __init__(self, job_id, errors, *args, **kwargs):
        """
        Create a job error.

        :param job_id: The job id related to the failed jobs call
        :param errors: Job validation errors
        :param *args: Additional exception positional arguments
        :param **kwargs: Additional exception keyword arugments
        """
        super().__init__(job_id, *args, **kwargs)
        self.errors = errors


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
