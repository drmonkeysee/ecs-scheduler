"""
Data context classes.

Model classes that handle persistence and storage.

Jobs and Job represent job storage and individual jobs, respectively.
Job data is controlled by the schemas in ecs_scheduler.serialization module.
All job loading and storing exceptions inherit from JobError.
"""
import logging
import functools
import collections.abc
from threading import RLock

from .persistence import NullStore
from .serialization import JobSchema, JobCreateSchema


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


"""Job data context."""
class Jobs:
    """A job data context used by the application to load and store jobs."""
    @classmethod
    def load(cls, store=None):
        """
        Create and load jobs from the given job store.

        :param store: The job store from which to load and store jobs;
                        uses null store if not specified
        :returns: A jobs storage resource attached to the given job data store
        :raises: InvalidJobData if job fields fail validation
        :raises: JobPersistenceError if job loading fails
        """
        # TODO: rework to pick data store based on config
        instance = cls(store or NullStore())
        instance._fill()
        return instance

    def __init__(self, store):
        """
        Create a job data context.

        Use Jobs.load() instead of creating the object directly to ensure
        a properly initialized job context.

        :param store: The data store to use for loading and storing jobs
        """
        self._schema = JobCreateSchema()
        self._store = store
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
    def create(self, job_data):
        """
        Create a new job.

        :param job_data: Data dictionary for the new job
        :returns: The newly created job
        :raises: JobAlreadyExists if job already exists
        :raises: InvalidJobData if job fields fail validation
        :raises: JobPersistenceError if job creation fails
        """
        job = self._create_job(job_data)
        if job.id in self._jobs:
            raise JobAlreadyExists(job.id)
        try:
            self._store.create(job.id, self._schema.dump(job.data).data)
        except Exception as ex:
            # TODO: inner exception not printed in flask logs :(
            raise JobPersistenceError(job.id) from ex
        self._jobs[job.id] = job
        return job

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
            self._store.delete(job_id)
        except Exception as ex:
            raise JobPersistenceError(job_id) from ex
        del self._jobs[job_id]

    def _fill(self):
        parsed_jobs = (self._create_job(raw_data) for raw_data in self._store.load_all())
        self._jobs = {job.id: job for job in parsed_jobs}

    def _create_job(self, raw_data):
        job_data, errors = self._schema.load(raw_data)
        if errors:
            raise InvalidJobData(job_data.get('id'), errors)
        return Job(job_data, self._store)


class Job:
    """
    A persistent job representing an ECS scheduled task.

    Stored and retrieved by a Jobs data context.
    """
    _RESERVED_FIELDS = {'id'}

    def __init__(self, data, store):
        """
        Create a persistent job.

        Use Jobs.create() instead of creating the object directly to ensure
        a properly initialized and persisted job.

        :param data: The job fields that make up the job
        :param store: The data store to use for persistence, provided by the Jobs instance
        """
        self._schema = JobSchema()
        self._data = data
        self._mapping = JobDataMapping(self._data)
        self._lock = RLock()
        self._store = store

    @property
    def id(self):
        """
        Get the job id.

        :returns: The job id string
        """
        return self._data['id']

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
    def update(self, fields):
        """
        Update the job.

        :param fields: Fields to update on the given job
        :raises: InvalidJobData if job data fails field validation
        :raises: JobPersistenceError if job update fails
        """
        validated_fields, errors = self._schema.load(fields)
        if errors:
            raise InvalidJobData(self.id, errors)
        try:
            self._store.update(self.id, self._schema.dump(validated_fields).data)
        except Exception as ex:
            raise JobPersistenceError(self.id) from ex
        self._update_data(validated_fields)

    @_sync
    def annotate(self, fields):
        """
        Annotate the job.

        Annotated fields do not persist into the job data store.
        This is used for storing job fields that are only relevant
        during runtime and do not need to be persisted between application runs.

        :param fields: Fields to set on the given job
        :raises: JobFieldsRequirePersistence if attempting to set persistent fields
        :raises: ImmutableJobFields if attempting to set immutable fields
        """
        persisted_data, errors = self._schema.load(fields)
        persisted_fields = persisted_data.keys() | errors.keys()
        if persisted_fields:
            raise JobFieldsRequirePersistence(self.id, persisted_fields)

        reserved_fields = self._RESERVED_FIELDS & fields.keys()
        if reserved_fields:
            raise ImmutableJobFields(self.id, reserved_fields)

        self._update_data(fields)

    def _update_data(self, fields):
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
    """
    General error for job persistence failures.

    Used to wrap lower-level persistence errors.
    """
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


class JobFieldsError(JobError):
    """General error for modifying invalid fields."""
    def __init__(self, job_id, fields, *args, **kwargs):
        """
        Create a job error.

        :param job_id: The job id related to the failed jobs call
        :param fields: The fields that caused an invalid modification error
        :param *args: Additional exception positional arguments
        :param **kwargs: Additional exception keyword arugments
        """
        super().__init__(job_id, *args, **kwargs)
        self.fields = fields


class JobFieldsRequirePersistence(JobFieldsError):
    """Error for attempting to annotate instead of update persistent job fields."""
    pass


class ImmutableJobFields(JobFieldsError):
    """Error for attempting to modify a field that cannot be changed."""
    pass
