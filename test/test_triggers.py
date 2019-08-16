import unittest
from unittest.mock import patch, Mock

from ecs_scheduler.triggers import (NoOpTrigger, SqsTrigger, get, init,
                                    _triggers)


class NoOpTriggerTests(unittest.TestCase):
    def test_determine_task_count_returns_task_count(self):
        test_data = {'taskCount': 10}
        trigger = NoOpTrigger()

        count = trigger.determine_task_count(test_data)

        self.assertEqual(10, count)

    def test_determine_task_count_returns_task_count_if_less_than_max(self):
        test_data = {'taskCount': 10, 'maxCount': 20}
        trigger = NoOpTrigger()

        count = trigger.determine_task_count(test_data)

        self.assertEqual(10, count)

    def test_determine_task_count_returns_max_count_if_greater_than_max(self):
        test_data = {'taskCount': 30, 'maxCount': 20}
        trigger = NoOpTrigger()

        count = trigger.determine_task_count(test_data)

        self.assertEqual(20, count)


class SqsTriggerTests(unittest.TestCase):
    def setUp(self):
        with patch('boto3.resource'):
            self._trigger = SqsTrigger()

    def test_determine_task_count_returns_zero_if_no_messages(self):
        test_data = {'taskCount': 10, 'trigger': {'queueName': 'testQueue'}}
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 0})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(0, count)

    def test_determine_task_count_returns_task_count_if_no_scaling_factor(
            self):
        test_data = {'taskCount': 10, 'trigger': {'queueName': 'testQueue'}}
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 1})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(10, count)

    def test_determine_task_count_returns_max_count_if_no_scaling_factor_and_task_greater_than_max(self):
        test_data = {
            'taskCount': 10,
            'trigger': {'queueName': 'testQueue'},
            'maxCount': 7,
        }
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 1})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(7, count)

    def test_determine_task_count_returns_calculated_count_based_on_factor(
            self):
        test_data = {
            'taskCount': 1,
            'trigger': {'queueName': 'testQueue', 'messagesPerTask': 10},
        }
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 40})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(4, count)

    def test_determine_task_count_returns_max_count_if_calculated_count_greater_than_max(self):
        test_data = {
            'taskCount': 1,
            'trigger': {'queueName': 'testQueue', 'messagesPerTask': 10},
            'maxCount': 2,
        }
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 40})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(2, count)

    def test_determine_task_count_returns_calculated_count_with_remainder_based_on_factor(self):
        test_data = {
            'taskCount': 1,
            'trigger': {'queueName': 'testQueue', 'messagesPerTask': 10},
        }
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 41})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(5, count)

    def test_determine_task_count_returns_calculated_count_if_equal_messages_to_factor(self):
        test_data = {
            'taskCount': 1,
            'trigger': {'queueName': 'testQueue', 'messagesPerTask': 10},
        }
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 10})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(1, count)

    def test_determine_task_count_returns_calculated_count_if_less_messages_than_factor(self):
        test_data = {
            'taskCount': 1,
            'trigger': {'queueName': 'testQueue', 'messagesPerTask': 10},
        }
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 2})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(1, count)

    def test_determine_task_count_returns_task_count_if_calculated_value_lower(
            self):
        test_data = {
            'taskCount': 3,
            'trigger': {'queueName': 'testQueue', 'messagesPerTask': 10},
        }
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 10})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(3, count)


@patch('boto3.resource')
@patch.dict('ecs_scheduler.triggers._triggers', {})
class InitTests(unittest.TestCase):
    def test(self, fake_resource):
        init()

        self.assertEqual(2, len(_triggers))
        self.assertIsInstance(_triggers['sqs'], SqsTrigger)
        self.assertIsInstance(_triggers['noop'], NoOpTrigger)


class TestTrigger():
    pass


@patch.dict('ecs_scheduler.triggers._triggers',
            {'test': TestTrigger(), 'noop': NoOpTrigger()})
class GetTests(unittest.TestCase):
    def test_get_named_trigger(self):
        trigger = get('test')

        self.assertIsInstance(trigger, TestTrigger)

    def test_get_unknown_trigger(self):
        trigger = get('who knows')

        self.assertIsInstance(trigger, NoOpTrigger)
