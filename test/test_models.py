import unittest
import logging
from unittest.mock import Mock, patch

from ecs_scheduler.models import Jobs, Job, Pagination, JobOperation


class JobsTests(unittest.TestCase):
    def setUp(self):
        self._persistence = Mock()
        self._target = Jobs(self._persistence)

    @patch.object(logging.getLogger('ecs_scheduler.models'), 'warning')
    def test_load_selects_null_source_if_not_specified(self, fake_log):
        result = Jobs.load()

        self.assertEqual([], list(result.get_all()))
        fake_log.assert_called()

    def test_load_fills_store_from_source(self):
        self._persistence.load_all.return_value = {'a': 1, 'b': 2}

        result = Jobs.load(self._persistence)

        self._persistence.load_all.assert_called()
        self.assertCountEqual([1, 2], result.get_all())


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


class JobOperationTests(unittest.TestCase):
    def test_ctor(self):
        operation = 5
        job_id = 'foo'
        
        op = JobOperation(operation, job_id)

        self.assertEqual(operation, op.operation)
        self.assertIs(job_id, op.job_id)

    def test_add_creates_op(self):
        job_id = 'foo'

        op = JobOperation.add(job_id)

        self.assertEqual(JobOperation.ADD, op.operation)
        self.assertIs(job_id, op.job_id)

    def test_modify_creates_op(self):
        job_id = 'foo'

        op = JobOperation.modify(job_id)

        self.assertEqual(JobOperation.MODIFY, op.operation)
        self.assertIs(job_id, op.job_id)

    def test_remove_creates_op(self):
        job_id = 'foo'

        op = JobOperation.remove(job_id)

        self.assertEqual(JobOperation.REMOVE, op.operation)
        self.assertIs(job_id, op.job_id)


class PaginationTests(unittest.TestCase):
    def test_ctor_sets_attributes(self):
        page = Pagination(12, 42)

        self.assertEqual(12, page.skip)
        self.assertEqual(42, page.count)
        self.assertEqual(0, page.total)
    
    def test_ctor_sets_all_attributes(self):
        page = Pagination(33, 44, 55)

        self.assertEqual(33, page.skip)
        self.assertEqual(44, page.count)
        self.assertEqual(55, page.total)
        