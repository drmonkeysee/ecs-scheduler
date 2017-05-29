"""Persistent job store operations."""
import elasticsearch
import elasticsearch.helpers

from .. import models
from ..serialization import JobSchema, JobResponseSchema
from ..configuration import config


class JobStore:
    """Persistent job store."""
    _DOC_TYPE = 'job'
    _SCROLL_PERIOD = '1m'

    def __init__(self):
        """Create job store."""
        self._es = elasticsearch.Elasticsearch(**config['elasticsearch']['client'])
        self._index = config['elasticsearch']['index']
        self._read_schema = JobResponseSchema(lambda obj: None, strict=True)
        self._write_schema = JobSchema()

    def get_all(self):
        """
        Get all jobs in the persistent store.

        :returns: A generator that yields batches of documents
        """
        hits = elasticsearch.helpers.scan(self._es, index=self._index, doc_type=self._DOC_TYPE, scroll=self._SCROLL_PERIOD)
        for hit in hits:
            yield self._read_schema.load(hit).data

    def get(self, job_id):
        """
        Get a job.

        :param job_id: The job's id
        :returns: The parsed job
        """
        response = self._es.get(index=self._index, doc_type=self._DOC_TYPE, id=job_id)
        return self._read_schema.load(response).data

    def update(self, job_id, job_data):
        """
        Update a job.

        :param job_id: The job's id
        :param job_data: The job fields to update as an elasticsearch JSON document
        """
        job_update, e = self._write_schema.dump(models.Job(**job_data))
        self._es.update(index=self._index, doc_type=self._DOC_TYPE, id=job_id, body={'doc': job_update}, retry_on_conflict=3)
