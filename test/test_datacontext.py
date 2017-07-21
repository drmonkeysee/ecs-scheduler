import unittest
import logging
from unittest.mock import Mock, patch

from ecs_scheduler.datacontext import (Jobs, Job, JobDataMapping,
                                        JobNotFound, InvalidJobData,
                                        JobAlreadyExists, JobPersistenceError,
                                        JobFieldsRequirePersistence)


class JobsTests(unittest.TestCase):
    def setUp(self):
        self._store = Mock()
        self._store.load_all.return_value = {'id': 1}, {'id': 2}
        with patch('ecs_scheduler.datacontext.JobCreateSchema') as sp, \
                patch('ecs_scheduler.datacontext.RLock') as rp:
            self._schema = sp.return_value
            self._schema.load.side_effect = lambda d: (d, {})
            self._schema.dump.side_effect = lambda d: Mock(data={'validated': True, **d})
            self._lock = rp.return_value
            self._target = Jobs.load(self._store)

    @patch.object(logging.getLogger('ecs_scheduler.datacontext'), 'warning')
    def test_load_selects_null_source_if_not_specified(self, fake_log):
        result = Jobs.load()

        self.assertEqual([], list(result.get_all()))
        fake_log.assert_called()

    def test_get_all_returns_all(self):
        self._store.load_all.assert_called()
        self.assertCountEqual([1, 2], [j.id for j in self._target.get_all()])
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_len_gets_jobs_length(self):
        self.assertEqual(2, self._target.total())
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_get_retrieves_job(self):
        result = self._target.get(2)

        self.assertIsInstance(result, Job)
        self.assertEqual(2, result.id)
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_get_raises_error(self):
        with self.assertRaises(JobNotFound) as cm:
            result = self._target.get(3)

        self.assertEqual(3, cm.exception.job_id)
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_create_new_job(self):
        data = {'id': 4, 'foo': 'bar'}

        result = self._target.create(data)

        self.assertIsInstance(result, Job)
        self.assertEqual(4, result.id)
        self.assertIs(result, self._target.get(4))
        self.assertEqual(3, self._target.total())
        self._store.create.assert_called_with(4, {'validated': True, **data})
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_create_raises_if_invalid_data(self):
        self._schema.load.side_effect = lambda d: (d, {'error': 'bad'})
        data = {'id': 4, 'foo': 'bar'}

        with self.assertRaises(InvalidJobData) as cm:
            self._target.create(data)

        self.assertEqual(4, cm.exception.job_id)
        self.assertEqual({'error': 'bad'}, cm.exception.errors)
        self.assertEqual(2, self._target.total())
        self._store.create.assert_not_called()
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_create_raises_with_missing_id(self):
        self._schema.load.side_effect = lambda d: (d, {'error': 'noid'})
        data = {'foo': 'bar'}

        with self.assertRaises(InvalidJobData) as cm:
            self._target.create(data)

        self.assertIsNone(cm.exception.job_id)
        self.assertEqual({'error': 'noid'}, cm.exception.errors)
        self.assertEqual(2, self._target.total())
        self._store.create.assert_not_called()
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_create_raises_if_duplicate_job(self):
        data = {'id': 1, 'foo': 'bar'}

        with self.assertRaises(JobAlreadyExists) as cm:
            self._target.create(data)

        self.assertEqual(1, cm.exception.job_id)
        self.assertEqual(2, self._target.total())
        self._store.create.assert_not_called()
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_create_raises_if_store_fails(self):
        self._store.create.side_effect = RuntimeError
        data = {'id': 4, 'foo': 'bar'}

        with self.assertRaises(JobPersistenceError) as cm:
            self._target.create(data)

        self.assertEqual(4, cm.exception.job_id)
        self.assertEqual(2, self._target.total())
        self._store.create.assert_called_with(4, {'validated': True, **data})
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_delete_job(self):
        self._target.delete(1)

        self.assertEqual(1, self._target.total())
        with self.assertRaises(JobNotFound):
            self._target.get(1)
        self._store.delete.assert_called_with(1)
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_delete_raises_if_no_job(self):
        with self.assertRaises(JobNotFound) as cm:
            self._target.delete(3)

        self.assertEqual(3, cm.exception.job_id)
        self.assertEqual(2, self._target.total())
        self._store.delete.assert_not_called()
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_delete_raises_if_store_error(self):
        self._store.delete.side_effect = RuntimeError

        with self.assertRaises(JobPersistenceError) as cm:
            self._target.delete(2)

        self.assertEqual(2, cm.exception.job_id)
        self.assertEqual(2, self._target.total())
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()


class JobTests(unittest.TestCase):
    def setUp(self):
        self._store = Mock()
        self._job_data = {'foo': 'bar'}
        with patch('ecs_scheduler.datacontext.JobSchema') as sp, \
                patch('ecs_scheduler.datacontext.RLock') as rp:
            self._schema = sp.return_value
            self._lock = rp.return_value
            self._target = Job(32, self._job_data, self._store)
        self._schema.load.side_effect = lambda d: (d, {})
        self._schema.dump.side_effect = lambda d: Mock(data={'validated': True, **d})

    def test_data_returns_all_data(self):
        self.assertEqual(self._job_data, self._target.data)

    def test_data_is_read_only(self):
        with self.assertRaises(TypeError):
            self._target.data['baz'] = 'bort'

    def test_id_property_returns_id(self):
        self.assertEqual(32, self._target.id)

    def test_id_property_cannot_be_set(self):
        with self.assertRaises(AttributeError):
            self._target.id = 77

    def test_suspended_property_missing(self):
        self.assertFalse(self._target.suspended)

    def test_suspended_property_field(self):
        self._job_data['suspended'] = True

        self.assertTrue(self._target.suspended)

    def test_parsed_schedule_field(self):
        self._job_data['parsedSchedule'] = 'parsed'

        self.assertEqual('parsed', self._target.parsed_schedule)

    def test_update(self):
        new_data = {'a': 1, 'b': 2}

        self._target.update(new_data)

        self.assertEqual(1, self._target.data['a'])
        self.assertEqual(2, self._target.data['b'])
        self._store.update.assert_called_with(32, {'validated': True, **new_data})
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_update_changes_existing_fields(self):
        new_data = {'a': 1, 'foo': 'baz'}

        self._target.update(new_data)

        self.assertEqual(1, self._target.data['a'])
        self.assertEqual('baz', self._target.data['foo'])
        self._store.update.assert_called_with(32, {'validated': True, **new_data})
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_update_does_not_allow_id_override(self):
        job_with_real_schema = Job(44, {'foo': 'bar'}, self._store)
        new_data = {'id': 77, 'taskCount': 4}
        
        job_with_real_schema.update(new_data)

        self.assertEqual(44, job_with_real_schema.id)
        self._store.update.assert_called_with(44, {'taskCount': 4})

    def test_update_raises_if_invalid_data(self):
        self._schema.load.side_effect = lambda d: (d, {'error': 'bad'})
        new_data = {'a': 1, 'b': 2}

        with self.assertRaises(InvalidJobData) as cm:
            self._target.update(new_data)

        self.assertEqual(32, cm.exception.job_id)
        self.assertEqual({'error': 'bad'}, cm.exception.errors)
        self.assertNotIn('a', self._target.data)
        self.assertNotIn('b', self._target.data)
        self._store.update.assert_not_called()
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_update_raises_if_store_error(self):
        self._store.update.side_effect = RuntimeError
        new_data = {'a': 1, 'b': 2}

        with self.assertRaises(JobPersistenceError) as cm:
            self._target.update(new_data)

        self.assertEqual(32, cm.exception.job_id)
        self.assertNotIn('a', self._target.data)
        self.assertNotIn('b', self._target.data)
        self._store.update.assert_called_with(32, {'validated': True, **new_data})
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_annotate(self):
        self._schema.load.side_effect = lambda d: ({}, {})
        new_data = {'a': 1, 'b': 2}

        self._target.annotate(new_data)

        self.assertEqual(1, self._target.data['a'])
        self.assertEqual(2, self._target.data['b'])
        self._store.update.assert_not_called()
        self._lock.__enter__.assert_called()
        self._lock.__exit__.assert_called()

    def test_annotate_ignores_id_override(self):
        job_with_real_schema = Job(44, {'foo': 'bar'}, self._store)
        new_data = {'id': 77, 'b': 2}

        job_with_real_schema.annotate(new_data)

        self.assertEqual(44, job_with_real_schema.id)
        self.assertEqual(2, job_with_real_schema.data['b'])
        self._store.update.assert_not_called()

    def test_annotate_does_not_allow_setting_persistent_fields(self):
        job_with_real_schema = Job(44, {'foo': 'bar'}, self._store)
        new_data = {'taskCount': 4, 'schedule': '* *', 'b': 2}

        with self.assertRaises(JobFieldsRequirePersistence) as cm:
            job_with_real_schema.annotate(new_data)

        self.assertEqual(44, cm.exception.job_id)
        self.assertCountEqual({'taskCount', 'schedule', 'parsedSchedule'}, cm.exception.fields)
        self.assertNotIn('taskCount', job_with_real_schema.data)
        self.assertNotIn('schedule', job_with_real_schema.data)
        self.assertNotIn('b', job_with_real_schema.data)
        self._store.update.assert_not_called()


class JobDataMappingTests(unittest.TestCase):
    def setUp(self):
        self._data = {'a': 1, 'b': 2}
        self._target = JobDataMapping(self._data)

    def test_get(self):
        self.assertEqual(self._data['a'], self._target['a'])

    def test_set_unsupported(self):
        with self.assertRaises(TypeError):
            self._target['c'] = 3

    def test_iterate(self):
        expected = list(iter(self._data))
        actual = list(iter(self._target))

        self.assertCountEqual(expected, actual)

    def test_length(self):
        self.assertEqual(len(self._data), len(self._target))
