import unittest
import logging
from unittest.mock import patch
from datetime import datetime

from ecs_scheduler.persistence import NullStore, SQLiteStore, ElasticsearchStore


class NullStoreTests(unittest.TestCase):
    def setUp(self):
        self._target = NullStore()

    def test_load_all_returns_empty(self):
        result = list(self._target.load_all())

        self.assertEqual([], result)

    def test_other_ops_do_nothing(self):
        try:
            self._target.create('id', {'a': 1, 'b': 2})
            self._target.update('id', {'a': 1, 'b': 2})
            self._target.delete('id')
        except Exception as ex:
            self.fail('Unexpected error raised: {}'.format(ex))


class SQLiteStoreTests(unittest.TestCase):
    pass


class ElasticsearchStoreTests(unittest.TestCase):
    def setUp(self):
        with patch('elasticsearch.Elasticsearch') as es_cls, \
                patch.dict('ecs_scheduler.configuration.config',
                            {'elasticsearch': {'client': {'foo': 'bar'}, 'index': 'test_index'}}):
            self._target = ElasticsearchStore()
            self._es = es_cls.return_value

    @patch('elasticsearch.Elasticsearch')
    @patch.dict('ecs_scheduler.configuration.config', {'elasticsearch': {'client': {'foo': 'bar'}, 'index': 'test_index'}})
    def test_init_does_not_create_index_if_present(self, es_cls):
        es = es_cls.return_value
        es.indices.exists.return_value = True

        target = ElasticsearchStore()

        es.indices.create.assert_not_called()

    @patch('ecs_scheduler.persistence.datetime')
    @patch('elasticsearch.Elasticsearch')
    @patch.object(logging.getLogger('ecs_scheduler.persistence'), 'warning')
    @patch.dict('ecs_scheduler.configuration.config', {'elasticsearch': {'client': {'foo': 'bar'}, 'index': 'test_index'}})
    def test_init_does_creates_index_if_not_found(self, warning, es_cls, dt):
        es = es_cls.return_value
        es.indices.exists.return_value = False
        dt.now.return_value = datetime(year=2017, month=6, day=14, hour=13, minute=43, second=54)

        target = ElasticsearchStore()

        expected_body = {
            'settings': {
                'number_of_shards': 3
            },
            'aliases': {
                'test_index': {}
            }
        }
        es.indices.create.assert_called_with(index='test_index-20170614-134354', body=expected_body)
        warning.assert_called()

    @patch('elasticsearch.helpers.scan')
    @patch.object(logging.getLogger('ecs_scheduler.persistence'), 'info')
    def test_load_all_returns_empty_if_no_documents(self, info, scan):
        scan.return_value = []

        results = list(self._target.load_all())

        self.assertEqual([], results)
        info.assert_called()
        scan.assert_called_with(client=self._es, index='test_index', doc_type='job', scroll='1m')

    @patch('elasticsearch.helpers.scan')
    @patch.object(logging.getLogger('ecs_scheduler.persistence'), 'info')
    def test_load_all_returns_all_documents(self, info, scan):
        scan.return_value = [
            {
                '_id': 1,
                '_source': {'a': 'foo'}
            },
            {
                '_id': 4,
                '_source': {'a': 'bar'}
            },
            {
                '_id': 8,
                '_source': {'a': 'baz'}
            }
        ]

        results = list(self._target.load_all())

        expected = [
            {
                'id': 1,
                'a': 'foo'
            },
            {
                'id': 4,
                'a': 'bar'
            },
            {
                'id': 8,
                'a': 'baz'
            }
        ]
        self.assertCountEqual(expected, results)
        info.assert_called()
        scan.assert_called_with(client=self._es, index='test_index', doc_type='job', scroll='1m')

    def test_create(self):
        data = {'a': 1, 'b': 2}

        self._target.create(12, data)

        self._es.create.assert_called_with(index='test_index', doc_type='job', id=12, body=data)

    def test_update(self):
        data = {'a': 1, 'b': 2}

        self._target.update(12, data)

        self._es.update.assert_called_with(index='test_index', doc_type='job', id=12, body={'doc': data}, retry_on_conflict=3)

    def test_delete(self):
        self._target.delete(12)

        self._es.delete.assert_called_with(index='test_index', doc_type='job', id=12)
