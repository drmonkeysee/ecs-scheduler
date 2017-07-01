import logging

from .persistence import NullSource


_logger = logging.getLogger(__name__)


"""Job storage interface."""
class JobStore:
    """A job storage instance used by the application to load and store jobs."""
    @classmethod
    def load(cls, source=None):
        """
        Create and load a job store from the given job source.

        :param source: The job source from which to load and store jobs;
                        uses null source if not specified
        :returns: A job store attached to the given job data source
        """
        # TODO: rework to pick data source based on config
        if not source:
            source = NullSource()
            _logger.warning('!!! Warning !!!: No registered persistence layer found; falling back to null data source! Jobs will not be saved when the application terminates!')
        store = cls(source)
        store.fill()
        return store

    def __init__(self, source):
        """
        Create a job store.

        Use JobStore.load() instead of creating the object directly to ensure
        a properly initialized job store.

        :param source: The data source to use for loading and storing jobs
        """
        self._source = source
        self._jobs = None

    def fill(self):
        """
        Fill the job store with the contents of the data source.

        get_all() and get() will not return anything until this method is called.
        Use JobStore.load() instead of creating the object directly to ensure
        a properly initialized job store.
        """
        self._jobs = self._source.load_all()

    def get_all(self):
        """
        Get all jobs.

        :returns: A generator that yields all jobs in the job store
        """
        yield from self._jobs.values()

    def get(self, job_id):
        """
        Get a job by id.

        :param job_id: The id of the job to get
        :returns: The job for the given id
        :raises JobNotFound: If job not found
        """
        if job_id in self._jobs:
            return self._jobs[job_id]
        raise JobNotFound(job_id)

    def create(self, job_id, **job):
        """
        Create a new job.

        :param job_id: The id of the job to create
        :param **job: Keyword arguments for the new job
        :raises JobAlreadyExists: If job already exists
        """
        pass

    def update(self, job_id, **job):
        """
        Update a job by id.

        :param job_id: The id of the job to update
        :param **job: Keyword arguments to set on the given job
        :raises JobNotFound: If job not found
        """
        pass

    def annotate(self, job_id, **job):
        """
        Annotate a job by id.

        Annotated fields do not persist into the job data source.
        This is used for storing job fields that are only relevant
        during runtime and do not need to be persisted between application runs.

        :param job_id: The id of the job to annotate
        :param **job: Keyword arguments to set on the given job
        :raises JobNotFound: If job not found
        """
        pass

    def delete(self, job_id):
        """
        Delete a job.

        :param job_id: The id of the job to delete
        :raises JobNotFound: If job not found
        """
        pass


class JobNotFound(Exception):
    """Job not found error."""
    def __init__(self, job_id, *args, **kwargs):
        """
        Create a job not found exception.

        :param job_id: The job id that was not found
        :param *args: Additional exception positional arguments
        :param **kwargs: Additional exception keyword arugments
        """
        super().__init__(*args, **kwargs)
        self.job_id = job_id


class JobAlreadyExists(Exception):
    """Job exists error."""
    pass
