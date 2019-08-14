import logging
import os
import sqlite3
import unittest
from datetime import datetime
from io import BytesIO
from unittest.mock import patch, Mock, call, ANY

import boto3
import botocore.exceptions

from ecs_scheduler.persistence import (resolve, NullStore, SQLiteStore,
                                       S3Store, DynamoDBStore,
                                       ElasticsearchStore)


class ResolveTests(unittest.TestCase):
    @patch('ecs_scheduler.persistence.SQLiteStore')
    @patch.dict(os.environ, {'ECSS_SQLITE_FILE': 'test.db'}, clear=True)
    def test_resolve_sqlite(self, sqlite):
        result = resolve()

        self.assertIs(sqlite.return_value, result)
        sqlite.assert_called_with('test.db')

    @patch('ecs_scheduler.persistence.S3Store')
    @patch.dict(os.environ, {'ECSS_S3_BUCKET': 'test-bucket'}, clear=True)
    def test_resolve_s3(self, s3):
        result = resolve()

        self.assertIs(s3.return_value, result)
        s3.assert_called_with('test-bucket', prefix=None)

    @patch('ecs_scheduler.persistence.S3Store')
    @patch.dict(
        os.environ,
        {'ECSS_S3_BUCKET': 'test-bucket', 'ECSS_S3_PREFIX': 'test/prefix'},
        clear=True
    )
    def test_resolve_s3_with_prefix(self, s3):
        result = resolve()

        self.assertIs(s3.return_value, result)
        s3.assert_called_with('test-bucket', prefix='test/prefix')

    @patch('ecs_scheduler.persistence.DynamoDBStore')
    @patch.dict(os.environ, {'ECSS_DYNAMODB_TABLE': 'test-table'}, clear=True)
    def test_resolve_dynamodb(self, dynamodb):
        result = resolve()

        self.assertIs(dynamodb.return_value, result)
        dynamodb.assert_called_with('test-table')

    @patch('ecs_scheduler.persistence.ElasticsearchStore')
    @patch.dict(
        os.environ,
        {
            'ECSS_ELASTICSEARCH_INDEX': 'test-index',
            'ECSS_ELASTICSEARCH_HOSTS': 'http://test-host:9200/',
        },
        clear=True
    )
    def test_resolve_elasticsearch(self, elasticsearch):
        result = resolve()

        self.assertIs(elasticsearch.return_value, result)
        elasticsearch.assert_called_with(
            'test-index', hosts=['http://test-host:9200/']
        )

    @patch('ecs_scheduler.persistence.ElasticsearchStore')
    @patch.dict(
        os.environ,
        {
            'ECSS_ELASTICSEARCH_INDEX': 'test-index',
            'ECSS_ELASTICSEARCH_HOSTS': 'http://test-host1:9200/,'
                                        ' http://test-host2:9200/,'
                                        'http://test-host3:8080/',
        },
        clear=True
    )
    def test_resolve_elasticsearch_with_multiple_hosts(self, elasticsearch):
        result = resolve()

        self.assertIs(elasticsearch.return_value, result)
        elasticsearch.assert_called_with(
            'test-index',
            hosts=[
                'http://test-host1:9200/',
                'http://test-host2:9200/',
                'http://test-host3:8080/',
            ]
        )

    @patch('builtins.open')
    @patch('ecs_scheduler.persistence.yaml')
    @patch('ecs_scheduler.persistence.ElasticsearchStore')
    @patch.dict(
        os.environ, {'ECSS_CONFIG_FILE': '/etc/opt/test.yaml'}, clear=True
    )
    def test_resolve_elasticsearch_extended(self, elasticsearch, yaml, f_open):
        yaml.safe_load.return_value = {
            'elasticsearch': {
                'index': 'test-index', 'client': {'foo': 'bar', 'a': 1},
            },
        }

        result = resolve()

        self.assertIs(elasticsearch.return_value, result)
        f_open.assert_called_with('/etc/opt/test.yaml')
        elasticsearch.assert_called_with('test-index', foo='bar', a=1)


class NullStoreTests(unittest.TestCase):
    def setUp(self):
        logger = logging.getLogger('ecs_scheduler.persistence')
        with patch.object(logger, 'warning') as self._log:
            self._target = NullStore()

    def test_init_logs_warning(self):
        self._log.assert_called()

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
    def setUp(self):
        conn_patch = patch('sqlite3.connect')
        self._connect = conn_patch.start()
        self.addCleanup(conn_patch.stop)
        self._conn = self._connect.return_value.__enter__.return_value
        with patch('sqlite3.register_adapter') as self._adapt, \
                patch('sqlite3.register_converter') as self._conv, \
                patch('os.makedirs') as self._mkdirs, \
                patch('os.path.abspath') as self._abspath:
            self._target = SQLiteStore('test-file')

    def test_init_registers_handers(self):
        self._adapt.assert_called_with(dict, ANY)
        self._conv.assert_called_with('JSONTEXT', ANY)

    def test_init_creates_file_folder_if_present(self):
        with patch('sqlite3.register_adapter'), \
            patch('sqlite3.register_converter'), \
            patch('os.makedirs') as mkdirs, \
            patch(
                'os.path.abspath', side_effect=lambda p: '/abs/path/' + p
        ):
            SQLiteStore('foo/bar/test-file')
        mkdirs.assert_called_with('/abs/path/foo/bar', exist_ok=True)

    def test_init_creates_table(self):
        self._connect.assert_called_with(
            'test-file',
            isolation_level=None,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        args = self._conn.execute.call_args[0]
        self.assertEqual(1, self._connect.call_count)
        self.assertEqual(
            """
                CREATE TABLE IF NOT EXISTS
                jobs(id TEXT PRIMARY KEY NOT NULL,
                data JSONTEXT NOT NULL)
                """,
            args[0]
        )
        self._mkdirs.assert_not_called()
        self._abspath.assert_not_called()

    def test_load_all_yields_nothing_if_empty(self):
        self._conn.execute.return_value = []

        results = list(self._target.load_all())

        self.assertEqual([], results)
        self.assertEqual(2, self._connect.call_count)
        self._connect.assert_called_with(
            'test-file',
            isolation_level=None,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        self._conn.execute.assert_called_with('SELECT * FROM jobs')

    def test_load_all_rows(self):
        self._conn.execute.return_value = [
            ('foo', {'a': 1}),
            ('bar', {'b': 2}),
            ('baz', {'c': 3}),
        ]

        results = list(self._target.load_all())

        self.assertEqual([
            {'id': 'foo', 'a': 1},
            {'id': 'bar', 'b': 2},
            {'id': 'baz', 'c': 3},
        ], results)
        self.assertEqual(2, self._connect.call_count)
        self._connect.assert_called_with(
            'test-file',
            isolation_level=None,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        self._conn.execute.assert_called_with('SELECT * FROM jobs')

    def test_create(self):
        data = {'a': 1}

        self._target.create('test-id', data)

        self.assertEqual(2, self._connect.call_count)
        self._connect.assert_called_with(
            'test-file',
            isolation_level=None,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        self._conn.execute.assert_called_with(
            'INSERT INTO jobs VALUES (?, ?)', ('test-id', data)
        )

    def test_update_adds_new_values(self):
        self._conn.execute.return_value.fetchone.return_value = (
            'test-id',
            {'a': 1},
        )
        data = {'b': 2}

        self._target.update('test-id', data)

        self.assertEqual(2, self._connect.call_count)
        self._connect.assert_called_with(
            'test-file',
            isolation_level=None,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        execute_calls = [
            call('SELECT * FROM jobs WHERE id = ?', ('test-id',)),
            call(
                """
                UPDATE jobs SET data = ?
                WHERE id = ?
                """,
                ({'a': 1, 'b': 2}, 'test-id')
            ),
        ]
        # NOTE: skip asserting create table call from __init__
        self.assertEqual(execute_calls, self._conn.execute.call_args_list[1:])

    def test_update_replaces_values(self):
        self._conn.execute.return_value.fetchone.return_value = (
            'test-id',
            {'a': 1, 'b': 2},
        )
        data = {'a': 4}

        self._target.update('test-id', data)

        self.assertEqual(2, self._connect.call_count)
        self._connect.assert_called_with(
            'test-file',
            isolation_level=None,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        execute_calls = [
            call('SELECT * FROM jobs WHERE id = ?', ('test-id',)),
            call(
                """
                UPDATE jobs SET data = ?
                WHERE id = ?
                """,
                ({'a': 4, 'b': 2}, 'test-id')
            ),
        ]
        # NOTE: skip asserting create table call from __init__
        self.assertEqual(execute_calls, self._conn.execute.call_args_list[1:])

    def test_delete(self):
        self._target.delete('test-id')

        self.assertEqual(2, self._connect.call_count)
        self._connect.assert_called_with(
            'test-file',
            isolation_level=None,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        self._conn.execute.assert_called_with(
            'DELETE FROM jobs WHERE id = ?', ('test-id',)
        )


class S3StoreTests(unittest.TestCase):
    def setUp(self):
        with patch('boto3.resource') as self._res, \
                patch('boto3.client') as self._client:
            bn = 'test-bucket'
            self._bucket = self._res.return_value.Bucket.return_value
            self._bucket.name = bn
            self._target = S3Store(bn)

    def test_init(self):
        self._res.return_value.Bucket.assert_called_with('test-bucket')
        self._client.return_value.head_bucket.assert_called_with(
            Bucket='test-bucket'
        )
        self._bucket.create.assert_not_called()

    @patch.object(logging.getLogger('ecs_scheduler.persistence'), 'warning')
    def test_init_creates_bucket_if_not_found(self, warning):
        with patch('boto3.resource') as res, \
                patch('boto3.client') as c, \
                patch('boto3.session.Session') as s:
            bucket = res.return_value.Bucket.return_value
            c.return_value.head_bucket.side_effect = \
                botocore.exceptions.ClientError(
                    {'Error': {'Code': '404'}}, 'fake_operation'
                )
            session = s.return_value
            session.region_name = 'test-region'
            S3Store('test-bucket', 'test-prefix')

        bucket.create.assert_called_with(
            CreateBucketConfiguration={'LocationConstraint': 'test-region'}
        )
        bucket.wait_until_exists.assert_called_with()
        warning.assert_called()

    @patch.object(logging.getLogger('ecs_scheduler.persistence'), 'warning')
    def test_init_raises_unknown_errors(self, warning):
        with patch('boto3.resource') as res, \
                patch('boto3.client') as c:
            bucket = res.return_value.Bucket.return_value
            c.return_value.head_bucket.side_effect = \
                botocore.exceptions.ClientError(
                    {'Error': {'Code': '500'}}, 'fake_operation'
                )
            with self.assertRaises(botocore.exceptions.ClientError):
                S3Store('test-bucket', 'test-prefix')

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
            Mock(key='baz.json', get=lambda: {'Body': BytesIO(b'{"c": 3}')}),
        ]

        results = list(self._target.load_all())

        expected = [
            {'id': 'foo', 'a': 1},
            {'id': 'bar', 'b': 2},
            {'id': 'baz', 'c': 3},
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
            {'id': 'baz', 'c': 3},
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
            Mock(
                key='test-prefix/foo.json',
                get=lambda: {'Body': BytesIO(b'{"a": 1}')}
            ),
            Mock(
                key='test-prefix/bar.json',
                get=lambda: {'Body': BytesIO(b'{"b": 2}')}
            ),
            Mock(
                key='test-prefix/baz.json',
                get=lambda: {'Body': BytesIO(b'{"c": 3}')}
            ),
        ]

        results = list(self._target.load_all())

        expected = [
            {'id': 'foo', 'a': 1},
            {'id': 'bar', 'b': 2},
            {'id': 'baz', 'c': 3},
        ]
        self.assertCountEqual(expected, results)
        self._bucket.objects.filter.assert_called_with(Prefix='test-prefix')

    def test_load_all_prefix_works_if_prefix_contains_slash(self):
        self._target._prefix = 'test-prefix/'
        self._bucket.objects.filter.return_value = [
            Mock(
                key='test-prefix/foo.json',
                get=lambda: {'Body': BytesIO(b'{"a": 1}')}
            ),
            Mock(
                key='test-prefix/bar.json',
                get=lambda: {'Body': BytesIO(b'{"b": 2}')}
            ),
            Mock(
                key='test-prefix/baz.json',
                get=lambda: {'Body': BytesIO(b'{"c": 3}')}
            ),
        ]

        results = list(self._target.load_all())

        expected = [
            {'id': 'foo', 'a': 1},
            {'id': 'bar', 'b': 2},
            {'id': 'baz', 'c': 3},
        ]
        self.assertCountEqual(expected, results)
        self._bucket.objects.filter.assert_called_with(Prefix='test-prefix/')

    def test_load_all_prefix_ignores_subfolders(self):
        self._target._prefix = 'test-prefix'
        self._bucket.objects.filter.return_value = [
            Mock(
                key='test-prefix/foo.json',
                get=lambda: {'Body': BytesIO(b'{"a": 1}')}
            ),
            Mock(key='a-prefix/'),
            Mock(
                key='test-prefix/bar.json',
                get=lambda: {'Body': BytesIO(b'{"b": 2}')}
            ),
            Mock(key='another-prefix/'),
            Mock(
                key='test-prefix/baz.json',
                get=lambda: {'Body': BytesIO(b'{"c": 3}')}
            ),
            Mock(key='another-prefix/foo.json'),
            Mock(key='bort.txt'),
            Mock(key='a-file'),
        ]

        results = list(self._target.load_all())

        expected = [
            {'id': 'foo', 'a': 1},
            {'id': 'bar', 'b': 2},
            {'id': 'baz', 'c': 3},
        ]
        self.assertCountEqual(expected, results)
        self._bucket.objects.filter.assert_called_with(Prefix='test-prefix')

    def test_create(self):
        new_obj = self._res.return_value.Object.return_value
        data = {'a': 1}

        self._target.create('test-id', data)

        self._res.return_value.Object.assert_called_with(
            'test-bucket', 'test-id.json'
        )
        new_obj.put.assert_called_with(Body=b'{"a": 1}')

    def test_create_with_prefix(self):
        self._target._prefix = 'test-prefix'
        new_obj = self._res.return_value.Object.return_value
        data = {'a': 1}

        self._target.create('test-id', data)

        self._res.return_value.Object.assert_called_with(
            'test-bucket', 'test-prefix/test-id.json'
        )
        new_obj.put.assert_called_with(Body=b'{"a": 1}')

    def test_create_with_slashed_prefix(self):
        self._target._prefix = 'test-prefix/'
        new_obj = self._res.return_value.Object.return_value
        data = {'a': 1}

        self._target.create('test-id', data)

        self._res.return_value.Object.assert_called_with(
            'test-bucket', 'test-prefix/test-id.json'
        )
        new_obj.put.assert_called_with(Body=b'{"a": 1}')

    def test_update_adds_fields(self):
        up_obj = self._res.return_value.Object.return_value
        up_obj.get.return_value = {'Body': BytesIO(b'{"a": 1}')}
        updated_data = {'b': 2}

        self._target.update('test-id', updated_data)

        self._res.return_value.Object.assert_called_with(
            'test-bucket', 'test-id.json'
        )
        up_obj.put.assert_called_with(Body=b'{"a": 1, "b": 2}')

    def test_update_replace_fields(self):
        up_obj = self._res.return_value.Object.return_value
        up_obj.get.return_value = {'Body': BytesIO(b'{"a": 1}')}
        updated_data = {'a': 3}

        self._target.update('test-id', updated_data)

        self._res.return_value.Object.assert_called_with(
            'test-bucket', 'test-id.json'
        )
        up_obj.put.assert_called_with(Body=b'{"a": 3}')

    def test_update_with_prefix(self):
        self._target._prefix = 'test-prefix'
        up_obj = self._res.return_value.Object.return_value
        up_obj.get.return_value = {'Body': BytesIO(b'{"a": 1, "b": 2}')}
        updated_data = {'b': 4, 'w': 'foo'}

        self._target.update('test-id', updated_data)

        self._res.return_value.Object.assert_called_with(
            'test-bucket', 'test-prefix/test-id.json'
        )
        up_obj.put.assert_called_with(Body=b'{"a": 1, "b": 4, "w": "foo"}')

    def test_update_with_slashed_prefix(self):
        self._target._prefix = 'test-prefix/'
        up_obj = self._res.return_value.Object.return_value
        up_obj.get.return_value = {'Body': BytesIO(b'{"a": 1, "b": 2}')}
        updated_data = {'b': 4, 'w': 'foo'}

        self._target.update('test-id', updated_data)

        self._res.return_value.Object.assert_called_with(
            'test-bucket', 'test-prefix/test-id.json'
        )
        up_obj.put.assert_called_with(Body=b'{"a": 1, "b": 4, "w": "foo"}')

    def test_delete(self):
        del_obj = self._res.return_value.Object.return_value

        self._target.delete('test-id')

        self._res.return_value.Object.assert_called_with(
            'test-bucket', 'test-id.json'
        )
        del_obj.delete.assert_called_with()

    def test_delete_with_prefix(self):
        self._target._prefix = 'test-prefix'
        del_obj = self._res.return_value.Object.return_value

        self._target.delete('test-id')

        self._res.return_value.Object.assert_called_with(
            'test-bucket', 'test-prefix/test-id.json'
        )
        del_obj.delete.assert_called_with()

    def test_delete_with_slashed_prefix(self):
        self._target._prefix = 'test-prefix/'
        del_obj = self._res.return_value.Object.return_value

        self._target.delete('test-id')

        self._res.return_value.Object.assert_called_with(
            'test-bucket', 'test-prefix/test-id.json'
        )
        del_obj.delete.assert_called_with()


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
        self._dyn_client.describe_table.assert_called_with(
            TableName='test-table'
        )
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
            dyn_c.describe_table.side_effect = ex_type(
                {'Error': {'Code': '404'}}, 'fake_operation'
            )
            DynamoDBStore('test-table')

        dyn_c.create_table.assert_called_with(
            AttributeDefinitions=[
                {'AttributeName': 'job-id', 'AttributeType': 'S'},
            ],
            TableName=self._table.name,
            KeySchema=[{'AttributeName': 'job-id', 'KeyType': 'HASH'}],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5,
            }
        )
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
                {'job-id': 'foo1', 'json-data': '{"a": 1}'},
                {'job-id': 'foo2', 'json-data': '{"b": 2}'},
                {'job-id': 'foo3', 'json-data': '{"c": 3}'},
            ]},)

        results = list(self._target.load_all())

        expected_results = [
            {'id': 'foo1', 'a': 1},
            {'id': 'foo2', 'b': 2},
            {'id': 'foo3', 'c': 3},
        ]
        self.assertEqual(expected_results, results)
        self.assertEqual([call()], self._table.scan.call_args_list)

    def test_load_all_yields_all_batches(self):
        self._table.scan.side_effect = (
            {'Items': [
                {'job-id': 'foo1', 'json-data': '{"a": 1}'},
                {'job-id': 'foo2', 'json-data': '{"b": 2}'},
                {'job-id': 'foo3', 'json-data': '{"c": 3}'},
            ], 'LastEvaluatedKey': 'foo'},
            {'Items': [
                {'job-id': 'bar1', 'json-data': '{"d": 4}'},
            ], 'LastEvaluatedKey': 'bar'},
            {'Items': [
                {'job-id': 'baz1', 'json-data': '{"e": 5}'},
                {'job-id': 'baz2', 'json-data': '{"f": 6}'},
            ]},
        )

        results = list(self._target.load_all())

        expected_results = [
            {'id': 'foo1', 'a': 1},
            {'id': 'foo2', 'b': 2},
            {'id': 'foo3', 'c': 3},
            {'id': 'bar1', 'd': 4},
            {'id': 'baz1', 'e': 5},
            {'id': 'baz2', 'f': 6},
        ]
        self.assertEqual(expected_results, results)
        self.assertEqual([
            call(),
            call(ExclusiveStartKey='foo'),
            call(ExclusiveStartKey='bar'),
        ], self._table.scan.call_args_list)

    def test_create(self):
        data = {'a': 1, 'b': 2}

        self._target.create('test-id', data)

        self._table.put_item.assert_called_with(
            Item={'job-id': 'test-id', 'json-data': '{"a": 1, "b": 2}'}
        )

    def test_update_adds_fields(self):
        self._table.get_item.return_value = {
            'Item': {'job-id': 'test-id', 'json-data': '{"a": 1}'},
        }
        new_data = {'b': 2}

        self._target.update('test-id', new_data)

        self._table.get_item.assert_called_with(Key={'job-id': 'test-id'})
        self._table.put_item.assert_called_with(
            Item={'job-id': 'test-id', 'json-data': '{"a": 1, "b": 2}'}
        )

    def test_update_replaces_fields(self):
        self._table.get_item.return_value = {
            'Item': {'job-id': 'test-id', 'json-data': '{"a": 1, "b": 2}'},
        }
        new_data = {'a': 4}

        self._target.update('test-id', new_data)

        self._table.get_item.assert_called_with(Key={'job-id': 'test-id'})
        self._table.put_item.assert_called_with(
            Item={'job-id': 'test-id', 'json-data': '{"a": 4, "b": 2}'}
        )

    def test_delete(self):
        self._target.delete('test-id')

        self._table.delete_item.assert_called_with(Key={'job-id': 'test-id'})


class ElasticsearchStoreTests(unittest.TestCase):
    def setUp(self):
        with patch('elasticsearch.Elasticsearch') as es_cls:
            self._target = ElasticsearchStore('test_index', foo='bar')
            self._es = es_cls.return_value

    @patch('elasticsearch.Elasticsearch')
    def test_init_does_not_create_index_if_present(self, es_cls):
        es = es_cls.return_value
        es.indices.exists.return_value = True

        ElasticsearchStore('test_index', foo='bar')

        es.indices.create.assert_not_called()

    @patch('ecs_scheduler.persistence.datetime')
    @patch('elasticsearch.Elasticsearch')
    @patch.object(logging.getLogger('ecs_scheduler.persistence'), 'warning')
    def test_init_does_creates_index_if_not_found(self, warning, es_cls, dt):
        es = es_cls.return_value
        es.indices.exists.return_value = False
        dt.now.return_value = datetime(
            year=2017, month=6, day=14, hour=13, minute=43, second=54
        )

        ElasticsearchStore('test_index', foo='bar')

        expected_body = {
            'settings': {
                'number_of_shards': 3,
            },
            'aliases': {
                'test_index': {},
            }
        }
        es.indices.create.assert_called_with(
            index='test_index-20170614-134354', body=expected_body
        )
        warning.assert_called()

    @patch('elasticsearch.helpers.scan')
    @patch.object(logging.getLogger('ecs_scheduler.persistence'), 'info')
    def test_load_all_returns_empty_if_no_documents(self, info, scan):
        scan.return_value = []

        results = list(self._target.load_all())

        self.assertEqual([], results)
        info.assert_called()
        scan.assert_called_with(
            client=self._es, index='test_index', scroll='1m'
        )

    @patch('elasticsearch.helpers.scan')
    @patch.object(logging.getLogger('ecs_scheduler.persistence'), 'info')
    def test_load_all_returns_all_documents(self, info, scan):
        scan.return_value = [
            {
                '_id': 1,
                '_source': {'a': 'foo'},
            },
            {
                '_id': 4,
                '_source': {'a': 'bar'},
            },
            {
                '_id': 8,
                '_source': {'a': 'baz'},
            },
        ]

        results = list(self._target.load_all())

        expected = [
            {
                'id': 1,
                'a': 'foo',
            },
            {
                'id': 4,
                'a': 'bar',
            },
            {
                'id': 8,
                'a': 'baz',
            },
        ]
        self.assertCountEqual(expected, results)
        info.assert_called()
        scan.assert_called_with(
            client=self._es, index='test_index', scroll='1m'
        )

    def test_create(self):
        data = {'a': 1, 'b': 2}

        self._target.create(12, data)

        self._es.create.assert_called_with(
            index='test_index', id=12, body=data
        )

    def test_update(self):
        data = {'a': 1, 'b': 2}

        self._target.update(12, data)

        self._es.update.assert_called_with(
            index='test_index', id=12, body={'doc': data}, retry_on_conflict=3
        )

    def test_delete(self):
        self._target.delete(12)

        self._es.delete.assert_called_with(index='test_index', id=12)
