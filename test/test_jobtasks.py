import unittest
import marshmallow.exceptions
from unittest.mock import patch, Mock
from ecs_scheduler.jobtasks import SqsTaskQueue, MsgTask, InvalidMessageException
from ecs_scheduler.models import JobOperation
from ecs_scheduler.serialization import JobOperationSchema


class SqsTaskQueueTests(unittest.TestCase):
    def setUp(self):
        with patch('boto3.resource') as fake_boto:
            self._test_queue = SqsTaskQueue({'task_queue_name': 'foobar'})

    def test_ctor_gets_queue_by_name(self):
        with patch('boto3.resource') as fake_boto:
            queue = SqsTaskQueue({'task_queue_name': 'foobar'})
            fake_boto.assert_called_with('sqs')
            fake_boto.return_value.get_queue_by_name.assert_called_with(QueueName='foobar')
            self.assertIs(fake_boto.return_value.get_queue_by_name.return_value, queue._q)

    def test_put_posts_message_to_sqs(self):
        job_op = JobOperation.add('testId')

        self._test_queue.put(job_op)

        expected_body = JobOperationSchema().dumps(job_op).data
        self._test_queue._q.send_message.assert_called_with(MessageBody=expected_body)

    def test_put_throws_exception_if_unserializable(self):
        job_op = JobOperation('bad_op', 'testId')

        with self.assertRaises(marshmallow.exceptions.ValidationError):
            self._test_queue.put(job_op)

    def test_get_returns_task_with_message(self):
        self._test_queue._q.receive_messages.return_value = [Mock()]

        task = self._test_queue.get()

        self._test_queue._q.receive_messages.assert_called_with(WaitTimeSeconds=20, MaxNumberOfMessages=1)
        self.assertIsNotNone(task)
        self.assertIs(self._test_queue._q.receive_messages.return_value[0], task._context)

    def test_get_returns_none_if_no_message(self):
        self._test_queue._q.receive_messages.return_value = []

        task = self._test_queue.get()

        self._test_queue._q.receive_messages.assert_called_with(WaitTimeSeconds=20, MaxNumberOfMessages=1)
        self.assertIsNone(task)


class MsgTaskTests(unittest.TestCase):
    def test_task_id_returns_message_id(self):
        fake_msg = Mock(body='{"job_id": "testId", "operation": 1}', message_id='foo')
        task = MsgTask(fake_msg)

        self.assertEqual('foo', task.task_id)
        
    def test_get_job_operation_returns_job_op_instance(self):
        fake_msg = Mock(body='{"job_id": "testId", "operation": 1}', message_id='foo')
        task = MsgTask(fake_msg)

        job_op = task.get_job_operation()

        self.assertIsInstance(job_op, JobOperation)
        self.assertEqual('testId', job_op.job_id)
        self.assertEqual(1, job_op.operation)

    def test_get_job_operation_raises_error_if_unserializable(self):
        fake_msg = Mock(body='{"job_id": "testId", "operation": "notANum"}', message_id='foo')
        task = MsgTask(fake_msg)

        self.assertRaises(InvalidMessageException, task.get_job_operation)

    def test_complete_deletes_message(self):
        fake_msg = Mock(body='{"job_id": "testId", "operation": 1}', message_id='foo')
        task = MsgTask(fake_msg)
        task.get_job_operation()

        task.complete()

        fake_msg.delete.assert_called_with()

    def test_complete_does_not_delete_message_if_get_not_called(self):
        fake_msg = Mock()
        task = MsgTask(fake_msg)

        task.complete()

        fake_msg.delete.assert_not_called()

    def test_complete_does_not_delete_message_if_get_failed(self):
        fake_msg = Mock(body='{"job_id": "testId", "operation": "notANum"}', message_id='foo')
        task = MsgTask(fake_msg)
        saw_exception = False
        try:
            task.get_job_operation()
        except InvalidMessageException:
            saw_exception = True

        task.complete()

        self.assertTrue(saw_exception)
        fake_msg.delete.assert_not_called()
