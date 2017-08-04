import unittest
import logging
from unittest.mock import patch, Mock, call
from datetime import datetime
from io import BytesIO

import boto3
import botocore.exceptions

from ecs_scheduler.persistence import NullStore, SQLiteStore, S3Store, DynamoDBStore, ElasticsearchStore


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


class S3StoreTests(unittest.TestCase):
    def setUp(self):
        with patch('boto3.resource') as self._res:
            bn = 'test-bucket'
            self._target = S3Store(bn)
            self._bucket = self._res.return_value.Bucket.return_value
            self._bucket.name = bn

    def test_init(self):
        self._res.return_value.Bucket.assert_called_with('test-bucket')
        self._bucket.load.assert_called_with()
        self._bucket.create.assert_not_called()

    @patch.object(logging.getLogger('ecs_scheduler.persistence'), 'warning')
    def test_init_creates_bucket_if_not_found(self, warning):
        with patch('boto3.resource') as res, \
                patch('boto3.session.Session') as s:
            bucket = res.return_value.Bucket.return_value
            bucket.load.side_effect = botocore.exceptions.ClientError({'Error': {'Code': '404'}}, 'fake_operation')
            session = s.return_value
            session.region_name = 'test-region'
            target = S3Store('test-bucket', 'test-prefix')

        bucket.create.assert_called_with(CreateBucketConfiguration={'LocationConstraint': 'test-region'})
        bucket.wait_until_exists.assert_called_with()
        warning.assert_called()

    @patch.object(logging.getLogger('ecs_scheduler.persistence'), 'warning')
    def test_init_raises_unknown_errors(self, warning):
        with patch('boto3.resource') as res:
            bucket = res.return_value.Bucket.return_value
            bucket.load.side_effect = botocore.exceptions.ClientError({'Error': {'Code': '500'}}, 'fake_operation')
            with self.assertRaises(botocore.exceptions.ClientError):
                target = S3Store('test-bucket', 'test-prefix')

        bucket.create.assert_not_called()
        warning.assert_not_called()

    def test_load_all_yields_nothing_if_empty(self):
        self._bucket.objects.filter.return_value = []

        results = list(self._target.load_all())

        self.assertEqual([], results)
        self._bucket.objects.filter.assert_called_with(Prefix='')

    def test_load_all_yields_json_objects_from_root_bucket(self):
        self._bucket.objects.filter.return_value = [
            Mock(key='foo.json', get=lambda: {'Body': BytesIO(b'{"a": 1}')}),
            Mock(key='bar.json', get=lambda: {'Body': BytesIO(b'{"b": 2}')}),
            Mock(key='baz.json', get=lambda: {'Body': BytesIO(b'{"c": 3}')})
        ]

        results = list(self._target.load_all())

        expected = [
            {'id': 'foo', 'a': 1},
            {'id': 'bar', 'b': 2},
            {'id': 'baz', 'c': 3}
        ]
        self.assertCountEqual(expected, results)
        self._bucket.objects.filter.assert_called_with(Prefix='')

    def test_load_all_ignores_other_bucket_contents(self):
        self._bucket.objects.filter.return_value = [
            Mock(key='foo.json', get=lambda: {'Body': BytesIO(b'{"a": 1}')}),
            Mock(key='a-prefix/'),
            Mock(key='bar.json', get=lambda: {'Body': BytesIO(b'{"b": 2}')}),
            Mock(key='another-prefix/'),
            Mock(key='baz.json', get=lambda: {'Body': BytesIO(b'{"c": 3}')}),
            Mock(key='another-prefix/foo.json'),
            Mock(key='bort.txt'),
            Mock(key='a-file'),
        ]

        results = list(self._target.load_all())

        expected = [
            {'id': 'foo', 'a': 1},
            {'id': 'bar', 'b': 2},
            {'id': 'baz', 'c': 3}
        ]
        self.assertCountEqual(expected, results)
        self._bucket.objects.filter.assert_called_with(Prefix='')

    def test_load_all_prefix_yields_nothing_if_empty(self):
        self._target._prefix = 'test-prefix'

        results = list(self._target.load_all())

        self.assertEqual([], results)
        self._bucket.objects.filter.assert_called_with(Prefix='test-prefix')

    def test_load_all_prefix_yields_json_objects(self):
        self._target._prefix = 'test-prefix'
        self._bucket.objects.filter.return_value = [
            Mock(key='test-prefix/foo.json', get=lambda: {'Body': BytesIO(b'{"a": 1}')}),
            Mock(key='test-prefix/bar.json', get=lambda: {'Body': BytesIO(b'{"b": 2}')}),
            Mock(key='test-prefix/baz.json', get=lambda: {'Body': BytesIO(b'{"c": 3}')})
        ]

        results = list(self._target.load_all())

        expected = [
            {'id': 'foo', 'a': 1},
            {'id': 'bar', 'b': 2},
            {'id': 'baz', 'c': 3}
        ]
        self.assertCountEqual(expected, results)
        self._bucket.objects.filter.assert_called_with(Prefix='test-prefix')

    def test_load_all_prefix_works_if_prefix_contains_slash(self):
        self._target._prefix = 'test-prefix/'
        self._bucket.objects.filter.return_value = [
            Mock(key='test-prefix/foo.json', get=lambda: {'Body': BytesIO(b'{"a": 1}')}),
            Mock(key='test-prefix/bar.json', get=lambda: {'Body': BytesIO(b'{"b": 2}')}),
            Mock(key='test-prefix/baz.json', get=lambda: {'Body': BytesIO(b'{"c": 3}')})
        ]

        results = list(self._target.load_all())

        expected = [
            {'id': 'foo', 'a': 1},
            {'id': 'bar', 'b': 2},
            {'id': 'baz', 'c': 3}
        ]
        self.assertCountEqual(expected, results)
        self._bucket.objects.filter.assert_called_with(Prefix='test-prefix/')

    def test_load_all_prefix_ignores_subfolders(self):
        self._target._prefix = 'test-prefix'
        self._bucket.objects.filter.return_value = [
            Mock(key='test-prefix/foo.json', get=lambda: {'Body': BytesIO(b'{"a": 1}')}),
            Mock(key='a-prefix/'),
            Mock(key='test-prefix/bar.json', get=lambda: {'Body': BytesIO(b'{"b": 2}')}),
            Mock(key='another-prefix/'),
            Mock(key='test-prefix/baz.json', get=lambda: {'Body': BytesIO(b'{"c": 3}')}),
            Mock(key='another-prefix/foo.json'),
            Mock(key='bort.txt'),
            Mock(key='a-file'),
        ]

        results = list(self._target.load_all())

        expected = [
            {'id': 'foo', 'a': 1},
            {'id': 'bar', 'b': 2},
            {'id': 'baz', 'c': 3}
        ]
        self.assertCountEqual(expected, results)
        self._bucket.objects.filter.assert_called_with(Prefix='test-prefix')

    def test_create(self):
        new_obj = self._res.return_value.Object.return_value
        data = {'a': 1}

        self._target.create('test-id', data)

        self._res.return_value.Object.assert_called_with('test-bucket', 'test-id.json')
        new_obj.put(Body=b'{"a": 1, "id": "test-id"}')

    def test_create_with_prefix(self):
        self._target._prefix = 'test-prefix'
        new_obj = self._res.return_value.Object.return_value
        data = {'a': 1}

        self._target.create('test-id', data)

        self._res.return_value.Object.assert_called_with('test-bucket', 'test-prefix/test-id.json')
        new_obj.put(Body=b'{"a": 1, "id": "test-id"}')

    def test_create_with_slashed_prefix(self):
        self._target._prefix = 'test-prefix/'
        new_obj = self._res.return_value.Object.return_value
        data = {'a': 1}

        self._target.create('test-id', data)

        self._res.return_value.Object.assert_called_with('test-bucket', 'test-prefix/test-id.json')
        new_obj.put(Body=b'{"a": 1, "id": "test-id"}')

    def test_update_adds_fields(self):
        up_obj = self._res.return_value.Object.return_value
        up_obj.get.return_value = {'Body': BytesIO(b'{"a": 1}')}
        updated_data = {'b': 2}

        self._target.update('test-id', updated_data)

        self._res.return_value.Object.assert_called_with('test-bucket', 'test-id.json')
        up_obj.put(Body=b'{"a": 1, "b": 2, "id": "test-id"}')

    def test_update_replace_fields(self):
        up_obj = self._res.return_value.Object.return_value
        up_obj.get.return_value = {'Body': BytesIO(b'{"a": 1}')}
        updated_data = {'a': 3}

        self._target.update('test-id', updated_data)

        self._res.return_value.Object.assert_called_with('test-bucket', 'test-id.json')
        up_obj.put(Body=b'{"a": 3 "id": "test-id"}')

    def test_update_with_prefix(self):
        self._target._prefix = 'test-prefix'
        up_obj = self._res.return_value.Object.return_value
        up_obj.get.return_value = {'Body': BytesIO(b'{"a": 1, "b": 2}')}
        updated_data = {'b': 4, 'w': 'foo'}

        self._target.update('test-id', updated_data)

        self._res.return_value.Object.assert_called_with('test-bucket', 'test-prefix/test-id.json')
        up_obj.put(Body=b'{"a": 1, "b": 4, "id": "test-id", "w": "foo"}')

    def test_update_with_slashed_prefix(self):
        self._target._prefix = 'test-prefix/'
        up_obj = self._res.return_value.Object.return_value
        up_obj.get.return_value = {'Body': BytesIO(b'{"a": 1, "b": 2}')}
        updated_data = {'b': 4, 'w': 'foo'}

        self._target.update('test-id', updated_data)

        self._res.return_value.Object.assert_called_with('test-bucket', 'test-prefix/test-id.json')
        up_obj.put(Body=b'{"a": 1, "b": 4, "id": "test-id", "w": "foo"}')

    def test_delete(self):
        del_obj = self._res.return_value.Object.return_value

        self._target.delete('test-id')

        self._res.return_value.Object.assert_called_with('test-bucket', 'test-id.json')
        del_obj.delete()

    def test_delete_with_prefix(self):
        self._target._prefix = 'test-prefix'
        del_obj = self._res.return_value.Object.return_value

        self._target.delete('test-id')

        self._res.return_value.Object.assert_called_with('test-bucket', 'test-prefix/test-id.json')
        del_obj.delete()

    def test_delete_with_slashed_prefix(self):
        self._target._prefix = 'test-prefix/'
        del_obj = self._res.return_value.Object.return_value

        self._target.delete('test-id')

        self._res.return_value.Object.assert_called_with('test-bucket', 'test-prefix/test-id.json')
        del_obj.delete()


class DynamoDBStoreTests(unittest.TestCase):
    def setUp(self):
        with patch('boto3.resource') as self._res, \
                patch('boto3.client') as client:
            tablename = 'test-table'
            self._table = self._res.return_value.Table.return_value
            self._table.name = tablename
            self._dyn_client = client.return_value
            self._target = DynamoDBStore(tablename)

    def test_init(self):
        self._res.return_value.Table.assert_called_with('test-table')
        self._dyn_client.describe_table.assert_called_with(TableName='test-table')
        self._dyn_client.create_table.assert_not_called()

    @patch.object(logging.getLogger('ecs_scheduler.persistence'), 'warning')
    def test_init_creates_bucket_if_not_found(self, warning):
        # NOTE: this exception type can only be found on a client instance
        ex_type = boto3.client('dynamodb').exceptions.ResourceNotFoundException
        with patch('boto3.resource') as res, \
                patch('boto3.client') as c:
            dyn_c = c.return_value
            dyn_c.exceptions.ResourceNotFoundException = ex_type
            table = res.return_value.Table.return_value
            table.name = 'test-table'
            dyn_c.describe_table.side_effect = ex_type({'Error': {'Code': '404'}}, 'fake_operation')
            target = DynamoDBStore('test-table')

        dyn_c.create_table.assert_called_with(AttributeDefinitions=[{'AttributeName': 'job-id', 'AttributeType': 'S'}],
                TableName=self._table.name,
                KeySchema=[{'AttributeName': 'job-id', 'KeyType': 'HASH'}],
                ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5})
        table.wait_until_exists.assert_called_with()
        warning.assert_called()

    def test_load_all_yields_nothing_if_empty(self):
        self._table.scan.side_effect = ({'Items': []},)

        results = list(self._target.load_all())

        self.assertEqual([], results)
        self._table.scan.assert_called_with()

    def test_load_all_yields_one_batch(self):
        self._table.scan.side_effect = (
            {'Items': [
                {'job-id': 'foo1', 'value': '{"a": 1}'},
                {'job-id': 'foo2', 'value': '{"b": 2}'},
                {'job-id': 'foo3', 'value': '{"c": 3}'}
            ]},)

        results = list(self._target.load_all())

        expected_results = [
            {'id': 'foo1', 'a': 1},
            {'id': 'foo2', 'b': 2},
            {'id': 'foo3', 'c': 3}
        ]
        self.assertEqual(expected_results, results)
        self.assertEqual([call()], self._table.scan.call_args_list)

    def test_load_all_yields_all_batches(self):
        self._table.scan.side_effect = (
            {'Items': [
                {'job-id': 'foo1', 'value': '{"a": 1}'},
                {'job-id': 'foo2', 'value': '{"b": 2}'},
                {'job-id': 'foo3', 'value': '{"c": 3}'}
            ], 'LastEvaluatedKey': 'foo'},
            {'Items': [
                {'job-id': 'bar1', 'value': '{"d": 4}'}
            ], 'LastEvaluatedKey': 'bar'},
            {'Items': [
                {'job-id': 'baz1', 'value': '{"e": 5}'},
                {'job-id': 'baz2', 'value': '{"f": 6}'}
            ]},)

        results = list(self._target.load_all())

        expected_results = [
            {'id': 'foo1', 'a': 1},
            {'id': 'foo2', 'b': 2},
            {'id': 'foo3', 'c': 3},
            {'id': 'bar1', 'd': 4},
            {'id': 'baz1', 'e': 5},
            {'id': 'baz2', 'f': 6}
        ]
        self.assertEqual(expected_results, results)
        self.assertEqual([call(), call(ExclusiveStartKey='foo'), call(ExclusiveStartKey='bar')], self._table.scan.call_args_list)


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
