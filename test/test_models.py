import unittest

from ecs_scheduler.models import Pagination, JobOperation


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
        