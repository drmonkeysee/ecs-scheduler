from .persistence import MemoryStore


"""Job storage interface."""
class JobStore:
    """A job storage instance used by the application to load and store jobs."""
    @classmethod
    def load(cls, source=None):
        """
        Create and load a job store from the given job source.

        :param source: The job source from which to load and store jobs;
                        uses empty in-memory source if not specified
        :returns: A job store attached to the given job data source
        """
        source = source or MemoryStore()
        pass

    def __init__(self, source):
        """
        Create a job store.

        :param source: The data source to use for loading and storing jobs
        """
        self._source = source
        self._jobs = {}

    def get_all(self):
        """
        Get all jobs.

        :returns: A generator that yields all jobs in the job store
        """
        pass

    def get(self, job_id):
        """
        Get a job by id.

        :param job_id: The id of the job to get
        :returns: The job for the given id
        :raises JobNotFound: If job not found
        """
        pass

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
    pass


class JobAlreadyExists(Exception):
    """Job exists error."""
    pass
