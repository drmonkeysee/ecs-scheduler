import unittest
from unittest.mock import patch

import marshmallow.exceptions

import ecs_scheduler.models
from ecs_scheduler.scheduld.jobstore import JobStore


class JobStoreTests(unittest.TestCase):
    def setUp(self):
        with patch('elasticsearch.Elasticsearch'), \
                patch.dict('ecs_scheduler.configuration.config', {'client': {'hosts': [{'host': 'foo', 'port': 9000}]}, 'index': 'test_index'}):
            self._store = JobStore()

    @patch('elasticsearch.helpers.scan')
    def test_get_all_returns_empty_if_no_hits(self, fake_scan):
        fake_scan.return_value = []

        iteration_count = 0
        for batch in self._store.get_all():
            iteration_count += 1

        self.assertEqual(0, iteration_count)

    @patch('elasticsearch.helpers.scan')
    def test_get_all_returns_jobs_until_empty(self, fake_scan):
        test_results = [{'_id': '1', '_source':{'schedule': '*'}}, {'_id': '2', '_source':{'schedule': '*'}}, {'_id': '3', '_source':{'schedule': '*'}}]
        fake_scan.return_value = test_results

        iteration_count = 0
        for i, job in enumerate(self._store.get_all()):
            self.assertEqual(test_results[i]['_id'], job.id)
            iteration_count += 1

        self.assertEqual(len(test_results), iteration_count)
        fake_scan.assert_called_with(self._store._es, index=self._store._index, doc_type=self._store._DOC_TYPE,
                                                    scroll=self._store._SCROLL_PERIOD)

    @patch('elasticsearch.helpers.scan')
    def test_get_all_raises_error_for_malformed_job(self, fake_scan):
        test_results = [{'_id': '1', '_source':{'schedule': '*'}}, {'_id': '2', '_source':{'schedule': 'bad-schedule'}}, {'_id': '3', '_source':{'schedule': '*'}}]
        fake_scan.return_value = test_results

        iteration_count = 0
        with self.assertRaises(marshmallow.exceptions.ValidationError):
            for i, job in enumerate(self._store.get_all()):
                self.assertEqual(test_results[i]['_id'], job.id)
                iteration_count += 1

        self.assertEqual(1, iteration_count)

    def test_get_returns_job(self):
        job_id = 'foo'
        self._store._es.get.return_value = {'_id': 'foo', '_source':{'schedule': '*'}}

        job = self._store.get(job_id)

        self.assertIsInstance(job, ecs_scheduler.models.Job)
        self.assertEqual(job_id, job.id)
        self._store._es.get.assert_called_with(index=self._store._index, doc_type=self._store._DOC_TYPE, id=job_id)

    def test_get_raises_error_if_malformed_job(self):
        job_id = 'foo'
        self._store._es.get.return_value = {'_id': '1', '_source':{'schedule': 'bad-schedule'}}

        with self.assertRaises(marshmallow.exceptions.ValidationError):
            self._store.get(job_id)

    def test_update_sends_data_to_store(self):
        job_id = 'foo'
        job_data = {'schedule': '*'}

        self._store.update(job_id, job_data)

        self._store._es.update.assert_called_with(index=self._store._index, doc_type=self._store._DOC_TYPE,
            id=job_id, body={'doc': {'schedule': '*'}}, retry_on_conflict=3)
