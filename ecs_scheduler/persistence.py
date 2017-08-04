"""Built-in job data store implementations."""
import logging
import posixpath
import collections
import json
from datetime import datetime

import boto3
import botocore.exceptions
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


class SQLiteStore:
    """SQLite data store."""
    pass
    # TODO:
    # - multithreaded connection
    # - create table ID JSON
    # - write json adapter
    # - replace NullStore with in-memory sqlite
    # separate locks for Jobs and Job sufficient?


class S3Store:
    """AWS S3 data store."""
    _JobObject = collections.namedtuple('JobObject', ['summary', 'prefix', 'job_id', 'ext'])
    _JOB_EXT = '.json'
    _ENCODING = 'utf-8'

    def __init__(self, bucket, prefix=None):
        """
        Create store.

        :param bucket: Name of the S3 bucket to use
        :param prefix: Key prefix to use for job objects
        """
        self._s3 = boto3.resource('s3')
        self._bucket = self._s3.Bucket(bucket)
        self._prefix = prefix or ''
        self._ensure_bucket()

    def load_all(self):
        """
        Get all job objects from the S3 location.

        :returns: Generator yielding job data dictionary for each job
        """
        msg = f'Loading jobs from S3 bucket {self._bucket.name}'
        if self._prefix:
            msg += f', prefix {self._prefix}'
        msg += '...'
        _logger.info(msg)
        job_objects = self._get_objects()
        for jo in job_objects:
            job_data = self._load_obj_contents(jo.summary)
            yield {'id': jo.job_id, **job_data}

    def create(self, job_id, job_data):
        """
        Create a new job S3 object.

        :param job_id: Job object id
        :param job_data: Job object contents
        """
        new_obj = self._make_object(job_id)
        self._store_obj(new_obj, job_data)

    def update(self, job_id, job_data):
        """
        Update existing job object.

        :param job_id: Job object id
        :param job_data: Job object body
        """
        updated_obj = self._make_object(job_id)
        current_data = self._load_obj_contents(updated_obj)
        current_data.update(job_data)
        self._store_obj(updated_obj, current_data)

    def delete(self, job_id):
        """
        Delete a job object.

        :param job_id: Job object id
        """
        deleted_obj = self._make_object(job_id)
        deleted_obj.delete()

    def _ensure_bucket(self):
        try:
            self._bucket.load()
        except botocore.exceptions.ClientError as ex:
            if ex.response['Error']['Code'] == '404':
                _logger.warning('S3 bucket not found; creating bucket "%s"', self._bucket.name)
                current_region = boto3.session.Session().region_name
                self._bucket.create(CreateBucketConfiguration={'LocationConstraint': current_region})
                _logger.info('Waiting for bucket to exist...')
                self._bucket.wait_until_exists()
            else:
                raise

    def _get_objects(self):
        objects = self._bucket.objects.filter(Prefix=self._prefix)
        job_objects = (self._make_job_object(o) for o in objects)
        return (j for j in job_objects if self._valid_job(j))

    def _make_job_object(self, s3_obj_summary):
        prefix, name = posixpath.split(s3_obj_summary.key)
        job_id, extension = posixpath.splitext(name)
        return self._JobObject(s3_obj_summary, prefix, job_id, extension)

    def _valid_job(self, job_object):
        prefix_check = self._prefix[:-1] \
                        if self._prefix and self._prefix[-1] == '/' \
                        else self._prefix
        return job_object.prefix == prefix_check and job_object.ext == self._JOB_EXT

    def _make_object(self, job_id):
        key = posixpath.join(self._prefix, job_id) + self._JOB_EXT
        return self._s3.Object(self._bucket.name, key)

    def _load_obj_contents(self, obj_handle):
        job_bytes = obj_handle.get()['Body'].read()
        return json.loads(job_bytes, encoding=self._ENCODING)

    def _store_obj(self, obj_handle, data):
        obj_handle.put(Body=json.dumps(data, sort_keys=True).encode(self._ENCODING))


class DynamoDBStore:
    """DynamoDB data store."""
    _KEY_NAME = 'job-id'

    def __init__(self, table):
        """
        Create store.

        :param table: Name of the dynamodb table to use
        """
        self._table = boto3.resource('dynamodb').Table(table)
        self._ensure_table()

    def load_all(self):
        """
        Get all job items from the DynamoDB table.

        :returns: Generator yielding job data dictionary for each job
        """
        _logger.info('Loading jobs from DynamoDB table %s...', self._table.name)
        batch = None
        while True:
            if batch:
                if 'LastEvaluatedKey' in batch:
                    batch = self._table.scan(ExclusiveStartKey=batch['LastEvaluatedKey'])
                else:
                    break
            else:
                batch = self._table.scan()
            items = batch['Items']
            for item in items:
                job_id = item[self._KEY_NAME]
                contents = item['value']
                job_data = json.loads(contents)
                yield {'id': job_id, **job_data}

    # TODO: write these
    def create(self, job_id, job_data):
        """
        Create a new job DynamoDB item.

        :param job_id: Job item id
        :param job_data: Job item contents
        """
        new_obj = self._make_object(job_id)
        self._store_obj(new_obj, job_data)

    def update(self, job_id, job_data):
        """
        Update existing job item.

        :param job_id: Job item id
        :param job_data: Job item body
        """
        updated_obj = self._make_object(job_id)
        current_data = self._load_obj_contents(updated_obj)
        current_data.update(job_data)
        self._store_obj(updated_obj, current_data)

    def delete(self, job_id):
        """
        Delete a job item.

        :param job_id: Job item id
        """
        deleted_obj = self._make_object(job_id)
        deleted_obj.delete()

    def _ensure_table(self):
        dyn_client = boto3.client('dynamodb')
        try:
            dyn_client.describe_table(TableName=self._table.name)
        except dyn_client.exceptions.ResourceNotFoundException:
            _logger.warning('DynamoDB table not found; creating table "%s"', self._table.name)
            dyn_client.create_table(
                AttributeDefinitions=[{'AttributeName': self._KEY_NAME, 'AttributeType': 'S'}],
                TableName=self._table.name,
                KeySchema=[{'AttributeName': self._KEY_NAME, 'KeyType': 'HASH'}],
                ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5})
            _logger.info('Waiting for table to exist...')
            self._table.wait_until_exists()


class ElasticsearchStore:
    """Elasticsearch data store."""
    _DOC_TYPE = 'job'
    _SCROLL_PERIOD = '1m'

    def __init__(self):
        """Create store."""
        self._es = elasticsearch.Elasticsearch(**config['elasticsearch']['client'])
        self._index = config['elasticsearch']['index']
        self._ensure_index()

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

    def _ensure_index(self):
        if self._es.indices.exists(self._index):
            return
        index_name = f'{self._index}-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
        index_settings = {
            'settings': {
                'number_of_shards': 3
            },
            'aliases': {
                self._index: {}
            }
        }
        _logger.warning('Elasticsearch index not found; creating index "%s" with alias "%s"', index_name, self._index)
        self._es.indices.create(index=index_name, body=index_settings)
