"""Built-in job data store implementations."""
import logging
from datetime import datetime

import elasticsearch
import elasticsearch.helpers

from .configuration import config


_logger = logging.getLogger(__name__)


def resolve():
    """
    Resolve a data store from the current execution environment.

    :returns: A data store implementation
    """
    pass


class NullStore:
    """
    Null data store.

    This store loads nothing and saves nothing.
    Effectively makes the JobStore an in-memory store.
    """
    def load_all(self):
        yield from {}.items()

    def create(self, job_id, job_data):
        pass

    def update(self, job_id, job_data):
        pass

    def delete(self, job_id):
        pass


class FileStore:
    """File system data store."""
    def __init__(self, file_path):
        """
        Create a file-based data store.

        :param file_path: The full path of the file to use for loading and storing jobs
        """
        self.file_path = file_path

    def load_all(self):
        pass

    def create(self, job_id, job_data):
        pass

    def update(self, job_id, job_data):
        pass

    def delete(self, job_id):
        pass


class S3Store:
    """AWS S3 data store."""
    pass


class ElasticsearchStore:
    """Elasticsearch data store."""
    _DOC_TYPE = 'job'
    _SCROLL_PERIOD = '1m'

    def __init__(self):
        """Create store."""
        self._es = elasticsearch.Elasticsearch(**config['elasticsearch']['client'])
        self._index = config['elasticsearch']['index']
        if not self._es.indices.exists(self._index):
            self._create_index()

    def load_all(self):
        """
        Get all job data in the index.

        :returns: Generator yielding job data dictionary for each job
        """
        _logger.info('Loading jobs from elasticsearch index %s...', self._index)
        hits = elasticsearch.helpers.scan(client=self._es,
            index=self._index,
            doc_type=self._DOC_TYPE,
            scroll=self._SCROLL_PERIOD)
        for hit in hits:
            yield {'id': hit['_id'], **hit['_source']}

    def create(self, job_id, job_data):
        """
        Create a new job document.

        :param job_id: Job document id
        :param job_data: Job document body
        """
        self._es.create(index=self._index, doc_type=self._DOC_TYPE, id=job_id, body=job_data)

    def update(self, job_id, job_data):
        """
        Update existing job document.

        :param job_id: Job document id
        :param job_data: Job document body
        """
        self._es.update(index=self._index, doc_type=self._DOC_TYPE, id=job_id, body={'doc': job_data}, retry_on_conflict=3)

    def delete(self, job_id):
        """
        Delete a job document.

        :param job_id: Job document id
        """
        self._es.delete(index=self._index, doc_type=self._DOC_TYPE, id=job_id)

    def _create_index(self):
        index_name = f'{self._index}-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
        index_settings = {
            'settings': {
                'number_of_shards': 3
            },
            'aliases': {
                self._index: {}
            }
        }
        _logger.warning('ECS scheduler index not found; creating index "%s" with alias "%s"', index_name, self._index)
        self._es.indices.create(index=index_name, body=index_settings)
