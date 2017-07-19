import unittest
import logging
from unittest.mock import Mock, patch

from ecs_scheduler.datacontext import (Jobs, Job, JobDataMapping,
                                        JobNotFound, InvalidJobData,
                                        JobAlreadyExists, JobPersistenceError)


class JobsTests(unittest.TestCase):
    def setUp(self):
        schema_patch = patch('ecs_scheduler.datacontext.JobCreateSchema')
        self._schema = schema_patch.start().return_value
        self.addCleanup(schema_patch.stop)
        lock_patch = patch('ecs_scheduler.datacontext.RLock')
        self._lock = lock_patch.start().return_value
        self.addCleanup(lock_patch.stop)
        self._store = Mock()
        self._store.load_all.return_value = {'id': 1}, {'id': 2}
        self._schema.load.side_effect = lambda d: (d, {})
        self._schema.dump.side_effect = lambda d: Mock(data=d)
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
        self._store.create.assert_called_with(4, data)
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

    def test_create_raises_if_missing_id(self):
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
        self._store.create.assert_called_with(4, data)
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
    def test_ctor_sets_data(self):
        data = {'foo': 'bar', 'baz': 5, 'bort': {'named': 'bart'}}
        job = Job(**data)

        self.assertEqual(data, job.data)

    def test_id_property_returns_id(self):
        job = Job(id='test')

        self.assertEqual('test', job.id)

        job.id = 'foo'

        self.assertEqual('foo', job.id)

    def test_suspended_property_returns_suspended_true(self):
        job = Job(suspended=True)

        self.assertTrue(job.suspended)

    def test_suspended_property_returns_suspended_false(self):
        job = Job(suspended=False)

        self.assertFalse(job.suspended)

    def test_suspended_property_returns_suspended_false_if_missing(self):
        job = Job()

        self.assertFalse(job.suspended)

    def test_parsed_schedule_property_gets_value(self):
        job = Job(parsedSchedule='foo')

        self.assertEqual('foo', job.parsed_schedule)
