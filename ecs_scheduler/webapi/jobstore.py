"""Persistent job store operations."""
import elasticsearch

from ..configuration import config


class JobStore:
    """Persistent job store."""
    _DOC_TYPE = 'job'

    def __init__(self):
        """Create job store."""
        self._es = elasticsearch.Elasticsearch(**config['client'])
        self._index = config['index']

    def get_jobs(self, skip, count):
        """
        Get page of jobs from store.

        :param skip: Number of jobs to skip
        :param count: Number of jobs to return
        :returns: The elasticsearch response
        """
        return self._es.search(index=self._index, doc_type=self._DOC_TYPE, from_=skip, size=count)

    def create(self, job_id, body):
        """
        Create a new job.

        :param job_id: New job's id
        :param body: JSON document body for new job
        :returns: The elasticsearch response
        :raises JobExistsException: If job already exists
        """
        # TODO: refresh is temporary until we have a proper in-memory data layer
        try:
            return self._es.create(index=self._index, doc_type=self._DOC_TYPE, id=job_id, body=body, refresh='true')
        except elasticsearch.exceptions.ConflictError as ex:
            raise JobExistsException() from ex

    def get(self, job_id):
        """
        Get a job.

        :param job_id: The job's id
        :returns: The elasticsearch response
        :raises JobNotFoundException: If job not found
        """
        try:
            return self._es.get(index=self._index, doc_type=self._DOC_TYPE, id=job_id)
        except elasticsearch.exceptions.NotFoundError as ex:
            raise JobNotFoundException() from ex

    def update(self, job_id, body):
        """
        Update a job.

        :param job_id: The job's id
        :param body: JSON document body for updated job fields
        :returns: The elasticsearch response
        :raises JobNotFoundException: If job not found
        """
        # TODO: refresh is temporary until we have a proper in-memory data layer
        try:
            return self._es.update(index=self._index, doc_type=self._DOC_TYPE, id=job_id, body={'doc': body}, retry_on_conflict=3, refresh='true')
        except elasticsearch.exceptions.NotFoundError as ex:
            raise JobNotFoundException() from ex

    def delete(self, job_id):
        """
        Delete a job.

        :param job_id: The job's id
        :returns: The elasticsearch response
        :raises JobNotFoundException: If job not found
        """
        try:
            return self._es.delete(index=self._index, doc_type=self._DOC_TYPE, id=job_id)
        except elasticsearch.exceptions.NotFoundError as ex:
            raise JobNotFoundException() from ex


class JobExistsException(Exception):
    """Exception for job already exists."""
    pass


class JobNotFoundException(Exception):
    """Exception for job not found."""
    pass
