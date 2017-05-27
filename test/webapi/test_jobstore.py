import unittest
from unittest.mock import patch

import elasticsearch.exceptions

from ecs_scheduler.webapi.jobstore import JobStore, JobExistsException, JobNotFoundException


class JobStoreTests(unittest.TestCase):
    def setUp(self):
        self._test_config = {'client': {'hosts': [{'host': 'test_host', 'port': 20}]}, 'index': 'test_index'}
        with patch('elasticsearch.Elasticsearch'):
            self._store = JobStore(self._test_config)

    def test_ctor_initializes_es(self):
        with patch('elasticsearch.Elasticsearch') as fake_es:
            store = JobStore(self._test_config)
            fake_es.assert_called()
            expected_args = fake_es.call_args[1]
            self.assertEqual(self._test_config['index'], store._index)

        self.assertEqual(self._test_config['client'], expected_args)

    def test_get_jobs_calls_store(self):
        skip = 5
        count = 12

        response = self._store.get_jobs(skip, count)

        self._store._es.search.assert_called_with(index=self._store._index, doc_type=self._store._DOC_TYPE, from_=skip, size=12)
        self.assertIs(self._store._es.search.return_value, response)

    def test_get_jobs_raises_exception(self):
        self._store._es.search.side_effect = Exception

        with self.assertRaises(Exception):
            self._store.get_jobs(3, 32)

    def test_create_calls_store(self):
        job_id = 'foo'
        body = 'bar'

        response = self._store.create(job_id, body)

        self._store._es.create.assert_called_with(index=self._store._index, doc_type=self._store._DOC_TYPE, id=job_id, body=body, refresh='true')
        self.assertIs(self._store._es.create.return_value, response)

    def test_create_raises_if_ConflictError(self):
        job_id = 'foo'
        body = 'bar'
        self._store._es.create.side_effect = elasticsearch.exceptions.ConflictError

        with self.assertRaises(JobExistsException):
            self._store.create(job_id, body)

    def test_create_raises_unknown_exception(self):
        job_id = 'foo'
        body = 'bar'
        self._store._es.create.side_effect = Exception

        with self.assertRaises(Exception):
            self._store.create(job_id, body)

    def test_get_calls_store(self):
        job_id = 'foo'
        
        response = self._store.get(job_id)

        self._store._es.get.assert_called_with(index=self._store._index, doc_type=self._store._DOC_TYPE, id=job_id)
        self.assertIs(self._store._es.get.return_value, response)

    def test_get_raises_if_NotFoundError(self):
        job_id = 'foo'
        self._store._es.get.side_effect = elasticsearch.exceptions.NotFoundError

        with self.assertRaises(JobNotFoundException):
            self._store.get(job_id)

    def test_get_raises_unknown_exception(self):
        job_id = 'foo'
        self._store._es.get.side_effect = Exception

        with self.assertRaises(Exception):
            self._store.get(job_id)

    def test_update_calls_store(self):
        job_id = 'foo'
        body = 'bar'

        response = self._store.update(job_id, body)

        self._store._es.update.assert_called_with(index=self._store._index, doc_type=self._store._DOC_TYPE, id=job_id, body={'doc': body}, retry_on_conflict=3, refresh='true')
        self.assertIs(self._store._es.update.return_value, response)

    def test_update_raises_if_NotFoundError(self):
        job_id = 'foo'
        body = 'bar'
        self._store._es.update.side_effect = elasticsearch.exceptions.NotFoundError

        with self.assertRaises(JobNotFoundException):
            self._store.update(job_id, body)

    def test_update_raises_unknown_exception(self):
        job_id = 'foo'
        body = 'bar'
        self._store._es.update.side_effect = Exception

        with self.assertRaises(Exception):
            self._store.update(job_id, body)

    def test_delete_calls_store(self):
        job_id = 'foo'
        
        response = self._store.delete(job_id)

        self._store._es.delete.assert_called_with(index=self._store._index, doc_type=self._store._DOC_TYPE, id=job_id)
        self.assertIs(self._store._es.delete.return_value, response)

    def test_delete_raises_if_NotFoundError(self):
        job_id = 'foo'
        self._store._es.delete.side_effect = elasticsearch.exceptions.NotFoundError

        with self.assertRaises(JobNotFoundException):
            self._store.delete(job_id)

    def test_delete_raises_unknown_exception(self):
        job_id = 'foo'
        self._store._es.delete.side_effect = Exception

        with self.assertRaises(Exception):
            self._store.delete(job_id)
