import unittest
import logging
from unittest.mock import patch, Mock

from ecs_scheduler.scheduld.execution import JobExecutor, NoOpTrigger, SqsTrigger, get_trigger, JobResult


@patch('ecs_scheduler.scheduld.execution.get_trigger')
class JobExecutorTests(unittest.TestCase):
    def setUp(self):
        with patch('boto3.client'):
            self._exec = JobExecutor({'ecs_cluster_name': 'testCluster', 'ecs_scheduler_name': 'testName'})

    def test_call_does_nothing_if_zero_task_count(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 0
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': []}

        result = self._exec(id='foo')

        self.assertEqual(JobExecutor.RETVAL_CHECKED_TASKS, result.return_code)
        self._exec._ecs.run_task.assert_not_called()
        fake_get_trigger.assert_called_with(None)

    def test_call_passes_trigger_type_if_available(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 0
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': []}

        result = self._exec(id='foo', trigger={'type': 'bar'})

        self.assertEqual(JobExecutor.RETVAL_CHECKED_TASKS, result.return_code)
        fake_get_trigger.assert_called_with('bar')

    def test_call_does_nothing_if_at_expected_task_count(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 3
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': ['a', 'b', 'c']}

        result = self._exec(id='foo')

        self.assertEqual(JobExecutor.RETVAL_CHECKED_TASKS, result.return_code)
        self._exec._ecs.run_task.assert_not_called()
        fake_get_trigger.assert_called_with(None)

    def test_call_does_nothing_if_more_than_expected_task_count(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 3
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': ['a', 'b', 'c', 'd', 'e']}

        result = self._exec(id='foo')

        self.assertEqual(JobExecutor.RETVAL_CHECKED_TASKS, result.return_code)
        self._exec._ecs.run_task.assert_not_called()
        fake_get_trigger.assert_called_with(None)

    def test_call_launches_tasks_if_none_running(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 3
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': []}
        self._exec._ecs.run_task.return_value = {'tasks':[{'taskArn': 'foo1', 'containerInstanceArn': 'bar1'}, {'taskArn': 'foo2', 'containerInstanceArn': 'bar2'}], 'failures': []}

        result = self._exec(id='foo')

        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([{'taskId': 'foo1', 'hostId': 'bar1'}, {'taskId': 'foo2', 'hostId': 'bar2'}], result.task_info)
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster', taskDefinition='foo', count=3, startedBy='testName')
        fake_get_trigger.assert_called_with(None)

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.execution'), 'warning')
    def test_call_logs_warning_if_some_tasks_fail(self, fake_log, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 3
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': []}
        self._exec._ecs.run_task.return_value = {'tasks':[{'taskArn': 'foo1', 'containerInstanceArn': 'bar1'}, {'taskArn': 'foo2', 'containerInstanceArn': 'bar2'}],
                                                    'failures': [{'arn': 'failedTask', 'reason': 'poop'}]}

        result = self._exec(id='foo')

        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([{'taskId': 'foo1', 'hostId': 'bar1'}, {'taskId': 'foo2', 'hostId': 'bar2'}], result.task_info)
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster', taskDefinition='foo', count=3, startedBy='testName')
        fake_get_trigger.assert_called_with(None)
        fake_log.assert_called()

    @patch.object(logging.getLogger('ecs_scheduler.scheduld.execution'), 'warning')
    def test_call_logs_warning_if_all_tasks_fail(self, fake_log, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 3
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': []}
        self._exec._ecs.run_task.return_value = {'tasks':[], 'failures': [{'arn': 'failedTask', 'reason': 'poop'}, {'arn': 'failedTask2', 'reason': 'poop'}, {'arn': 'failedTask3', 'reason': 'poop'}]}

        result = self._exec(id='foo')

        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([], result.task_info)
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster', taskDefinition='foo', count=3, startedBy='testName')
        fake_get_trigger.assert_called_with(None)
        fake_log.assert_called()

    def test_call_launches_tasks_if_some_running(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 5
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': ['a', 'b', 'c']}
        self._exec._ecs.run_task.return_value = {'tasks':[{'taskArn': 'foo1', 'containerInstanceArn': 'bar1'}, {'taskArn': 'foo2', 'containerInstanceArn': 'bar2'}], 'failures': []}

        result = self._exec(id='foo')

        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([{'taskId': 'foo1', 'hostId': 'bar1'}, {'taskId': 'foo2', 'hostId': 'bar2'}], result.task_info)
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster', taskDefinition='foo', count=2, startedBy='testName')
        fake_get_trigger.assert_called_with(None)

    def test_call_launches_max_single_batch_tasks(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 10
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': []}
        self._exec._ecs.run_task.return_value = {'tasks':[{'taskArn': 'foo1', 'containerInstanceArn': 'bar1'}, {'taskArn': 'foo2', 'containerInstanceArn': 'bar2'}], 'failures': []}

        result = self._exec(id='foo')

        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([{'taskId': 'foo1', 'hostId': 'bar1'}, {'taskId': 'foo2', 'hostId': 'bar2'}], result.task_info)
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster', taskDefinition='foo', count=10, startedBy='testName')
        self.assertEqual(1, self._exec._ecs.run_task.call_count)

    def test_call_launches_multiple_task_batches(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 13
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': []}
        self._exec._ecs.run_task.side_effect = ({'tasks':[{'taskArn': 'foo1', 'containerInstanceArn': 'bar1'}, {'taskArn': 'foo2', 'containerInstanceArn': 'bar2'}], 'failures': []},
            {'tasks':[{'taskArn': 'faz1', 'containerInstanceArn': 'baz1'}, {'taskArn': 'faz2', 'containerInstanceArn': 'baz2'}], 'failures': []})

        result = self._exec(id='foo')

        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([{'taskId': 'foo1', 'hostId': 'bar1'}, {'taskId': 'foo2', 'hostId': 'bar2'}, {'taskId': 'faz1', 'hostId': 'baz1'}, {'taskId': 'faz2', 'hostId': 'baz2'}],
                            result.task_info)
        self._exec._ecs.run_task.assert_any_call(cluster='testCluster', taskDefinition='foo', count=10, startedBy='testName')
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster', taskDefinition='foo', count=3, startedBy='testName')
        self.assertEqual(2, self._exec._ecs.run_task.call_count)

    def test_call_launches_single_batch_if_running_count_reduces_expected_count_to_one_batch(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 13
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': ['a', 'b', 'c', 'd']}
        self._exec._ecs.run_task.return_value = {'tasks':[], 'failures': []}

        result = self._exec(id='foo')

        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([], result.task_info)
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster', taskDefinition='foo', count=9, startedBy='testName')
        self.assertEqual(1, self._exec._ecs.run_task.call_count)

    def test_call_launches_override_tasks_if_none_running(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 3
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': []}
        self._exec._ecs.run_task.return_value = {'tasks':[], 'failures': []}
        job_overrides = [{'containerName': 'test-container', 'environment': {'foo': 'bar', 'baz': 'bort'}}]

        result = self._exec(id='job-id', overrides=job_overrides)

        expected_overrides = [{'name': 'test-container', 'environment': [{'name': 'foo', 'value': 'bar'}, {'name': 'baz', 'value': 'bort'}, {'name': self._exec.OVERRIDE_TAG, 'value': 'job-id'}]}]
        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([], result.task_info)
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster',
            taskDefinition='job-id',
            count=3,
            startedBy='testName',
            overrides=unittest.mock.ANY)
        self._assert_equal_overrides(expected_overrides, self._exec._ecs.run_task.call_args[1]['overrides'])
        fake_get_trigger.assert_called_with(None)

    def test_call_checks_override_tags_for_running_count(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 5
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': ['a', 'b', 'c', 'd', 'e', 'f', 'g']}
        self._exec._ecs.run_task.return_value = {'tasks':[], 'failures': []}
        self._exec._ecs.describe_tasks.return_value = {
            'tasks': [
                {'overrides': {'containerOverrides': [
                    {'name': 'a'}
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'b', 'environment': [{'name': self._exec.OVERRIDE_TAG, 'value': 'job-id'}]},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'c'},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'd', 'environment': [{'name': self._exec.OVERRIDE_TAG, 'value': 'job-id'}]},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'e', 'environment': [{'name': self._exec.OVERRIDE_TAG, 'value': 'job-id'}]},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'f'},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'g'},
                ]}}
            ]
        }
        job_overrides = [{'containerName': 'test-container', 'environment': {'foo': 'bar', 'baz': 'bort'}}]

        result = self._exec(id='job-id', overrides=job_overrides)

        expected_overrides = [{'name': 'test-container', 'environment': [{'name': 'foo', 'value': 'bar'}, {'name': 'baz', 'value': 'bort'}, {'name': self._exec.OVERRIDE_TAG, 'value': 'job-id'}]}]
        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([], result.task_info)
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster',
            taskDefinition='job-id',
            count=2,
            startedBy='testName',
            overrides=unittest.mock.ANY)
        self._assert_equal_overrides(expected_overrides, self._exec._ecs.run_task.call_args[1]['overrides'])
        fake_get_trigger.assert_called_with(None)

    def test_call_checks_override_tags_with_unrelated_values(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 5
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': ['a', 'b', 'c', 'd', 'e', 'f', 'g']}
        self._exec._ecs.run_task.return_value = {'tasks':[], 'failures': []}
        self._exec._ecs.describe_tasks.return_value = {
            'tasks': [
                {'overrides': {'containerOverrides': [
                    {'name': 'a'}
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'b', 'environment': [{'name': self._exec.OVERRIDE_TAG, 'value': 'job-id'}, {'name': 'bar', 'value': 'baz'}]},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'c'},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'd'},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'e', 'environment': [{'name': 'bort', 'value': 'bart'}, {'name': self._exec.OVERRIDE_TAG, 'value': 'job-id'}]},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'f'},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'g'},
                ]}}
            ]
        }
        job_overrides = [{'containerName': 'test-container', 'environment': {'foo': 'bar', 'baz': 'bort'}}]

        result = self._exec(id='job-id', overrides=job_overrides)

        expected_overrides = [{'name': 'test-container', 'environment': [{'name': 'foo', 'value': 'bar'}, {'name': 'baz', 'value': 'bort'}, {'name': self._exec.OVERRIDE_TAG, 'value': 'job-id'}]}]
        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([], result.task_info)
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster',
            taskDefinition='job-id',
            count=3,
            startedBy='testName',
            overrides=unittest.mock.ANY)
        self._assert_equal_overrides(expected_overrides, self._exec._ecs.run_task.call_args[1]['overrides'])
        fake_get_trigger.assert_called_with(None)

    def test_call_checks_override_tags_with_over_container_sections(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 5
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': ['a', 'b', 'c', 'd', 'e', 'f', 'g']}
        self._exec._ecs.run_task.return_value = {'tasks':[], 'failures': []}
        self._exec._ecs.describe_tasks.return_value = {
            'tasks': [
                {'overrides': {'containerOverrides': [
                    {'name': 'a'}
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'b', 'environment': [{'name': 'bort', 'value': 'blarg'}]},
                    {'name': 'b-2', 'environment': [{'name': self._exec.OVERRIDE_TAG, 'value': 'job-id'}]}
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'c'},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'd'},
                    {'name': 'd-2', 'environment': [{'name': self._exec.OVERRIDE_TAG, 'value': 'job-id'}]}
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'e', 'environment': [{'name': self._exec.OVERRIDE_TAG, 'value': 'job-id'}]},
                    {'name': 'e-2', 'environment': [{'name': 'baz', 'value': 'bort'}]},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'f', 'environment': [{'name': 'foo', 'value': 'bar'}]},
                    {'name': 'f-2', 'environment': [{'name': self._exec.OVERRIDE_TAG, 'value': 'job-id'}]},
                    {'name': 'f-3', 'environment': [{'name': 'baz', 'value': 'bort'}]}
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'g'},
                ]}}
            ]
        }
        job_overrides = [{'containerName': 'test-container', 'environment': {'foo': 'bar', 'baz': 'bort'}}]

        result = self._exec(id='job-id', overrides=job_overrides)

        expected_overrides = [{'name': 'test-container', 'environment': [{'name': 'foo', 'value': 'bar'}, {'name': 'baz', 'value': 'bort'}, {'name': self._exec.OVERRIDE_TAG, 'value': 'job-id'}]}]
        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([], result.task_info)
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster',
            taskDefinition='job-id',
            count=1,
            startedBy='testName',
            overrides=unittest.mock.ANY)
        self._assert_equal_overrides(expected_overrides, self._exec._ecs.run_task.call_args[1]['overrides'])
        fake_get_trigger.assert_called_with(None)

    def test_call_does_not_match_other_id_in_override_tag(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 5
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': ['a', 'b', 'c', 'd', 'e', 'f', 'g']}
        self._exec._ecs.run_task.return_value = {'tasks':[], 'failures': []}
        self._exec._ecs.describe_tasks.return_value = {
            'tasks': [
                {'overrides': {'containerOverrides': [
                    {'name': 'a'}
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'b', 'environment': [{'name': self._exec.OVERRIDE_TAG, 'value': 'notme'}]},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'c'},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'd', 'environment': [{'name': self._exec.OVERRIDE_TAG, 'value': 'somethingelse'}]},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'e', 'environment': [{'name': self._exec.OVERRIDE_TAG, 'value': 'boobar'}]},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'f'},
                ]}},
                {'overrides': {'containerOverrides': [
                    {'name': 'g'},
                ]}}
            ]
        }
        job_overrides = [{'containerName': 'test-container', 'environment': {'foo': 'bar', 'baz': 'bort'}}]

        result = self._exec(id='job-id', overrides=job_overrides)

        expected_overrides = [{'name': 'test-container', 'environment': [{'name': 'foo', 'value': 'bar'}, {'name': 'baz', 'value': 'bort'}, {'name': self._exec.OVERRIDE_TAG, 'value': 'job-id'}]}]
        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([], result.task_info)
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster',
            taskDefinition='job-id',
            count=5,
            startedBy='testName',
            overrides=unittest.mock.ANY)
        self._assert_equal_overrides(expected_overrides, self._exec._ecs.run_task.call_args[1]['overrides'])
        fake_get_trigger.assert_called_with(None)

    def test_call_uses_task_description_instead_of_id_if_present(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 3
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': []}
        self._exec._ecs.run_task.return_value = {'tasks':[], 'failures': []}

        result = self._exec(id='foo', taskDefinition='bar')

        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([], result.task_info)
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster', taskDefinition='bar', count=3, startedBy='testName')
        fake_get_trigger.assert_called_with(None)

    def test_call_uses_passes_overrides_to_ecs(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 3
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': []}
        self._exec._ecs.run_task.return_value = {'tasks':[], 'failures': []}
        overrides = [{'containerName': 'test-container', 'environment': {'foo': 'bar'}}]

        result = self._exec(id='test-id', overrides=overrides)

        expected_overrides = [{'name': 'test-container', 'environment': [{'name': 'foo', 'value': 'bar'}, {'name': self._exec.OVERRIDE_TAG, 'value': 'test-id'}]}]
        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([], result.task_info)
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster',
            taskDefinition='test-id',
            count=3,
            startedBy='testName',
            overrides=unittest.mock.ANY)
        self._exec._ecs.describe_tasks.assert_not_called()
        self._assert_equal_overrides(expected_overrides, self._exec._ecs.run_task.call_args[1]['overrides'])
        fake_get_trigger.assert_called_with(None)

    def test_call_uses_passes_overrides_with_multiple_entries_to_ecs(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 3
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': []}
        self._exec._ecs.run_task.return_value = {'tasks':[], 'failures': []}
        overrides = [{'containerName': 'test-container1', 'environment': {'foo': 'bar'}}, {'containerName': 'test-container2', 'environment': {'boo': 'baz'}}]

        result = self._exec(id='test-id', overrides=overrides)

        expected_overrides = [
            {'name': 'test-container1', 'environment': [{'name': 'foo', 'value': 'bar'}, {'name': self._exec.OVERRIDE_TAG, 'value': 'test-id'}]},
            {'name': 'test-container2', 'environment': [{'name': 'boo', 'value': 'baz'}, {'name': self._exec.OVERRIDE_TAG, 'value': 'test-id'}]}
        ]
        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([], result.task_info)
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster',
            taskDefinition='test-id',
            count=3,
            startedBy='testName',
            overrides=unittest.mock.ANY)
        self._exec._ecs.describe_tasks.assert_not_called()
        self._assert_equal_overrides(expected_overrides, self._exec._ecs.run_task.call_args[1]['overrides'])
        fake_get_trigger.assert_called_with(None)

    def test_call_uses_a_copy_of_overrides_to_ecs(self, fake_get_trigger):
        fake_trigger = Mock()
        fake_trigger.determine_task_count.return_value = 3
        fake_get_trigger.return_value = fake_trigger
        self._exec._ecs.list_tasks.return_value = {'taskArns': []}
        self._exec._ecs.run_task.return_value = {'tasks':[], 'failures': []}
        overrides = [{'containerName': 'test-container', 'environment': {'foo': 'bar'}}]

        result = self._exec(id='test-id', overrides=overrides)

        expected_overrides = [{'name': 'test-container', 'environment': [{'name': 'foo', 'value': 'bar'}, {'name': self._exec.OVERRIDE_TAG, 'value': 'test-id'}]}]
        self.assertEqual(JobExecutor.RETVAL_STARTED_TASKS, result.return_code)
        self.assertEqual([], result.task_info)
        self._exec._ecs.run_task.assert_called_with(cluster='testCluster',
            taskDefinition='test-id',
            count=3,
            startedBy='testName',
            overrides=unittest.mock.ANY)
        self._assert_equal_overrides(expected_overrides, self._exec._ecs.run_task.call_args[1]['overrides'])
        self.assertEqual([{'containerName': 'test-container', 'environment': {'foo': 'bar'}}], overrides)

    def _assert_equal_overrides(self, expected, actual):
        unwrapped_actual = actual['containerOverrides']
        self.assertEqual(len(expected), len(unwrapped_actual))
        for i in range(len(expected)):
            expected_override = expected[i]
            actual_override = unwrapped_actual[i]
            self.assertEqual(len(expected_override), len(actual_override), msg=f'Unexpected override length for index {i}')

            self.assertEqual(expected_override['name'], actual_override['name'], msg=f'Unexpected container name for index {i}')

            expected_env = expected_override['environment']
            actual_env = actual_override['environment']
            self.assertCountEqual(expected_env, actual_env, msg=f'Unexpected environment values for index {i}')


class JobResultTests(unittest.TestCase):
    def test_set_default_attributes(self):
        result = JobResult(12)

        self.assertEqual(12, result.return_code)
        self.assertIsNone(result.task_info)

    def test_set_all_attributes(self):
        info = []
        result = JobResult(12, info)

        self.assertEqual(12, result.return_code)
        self.assertIs(info, result.task_info)


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

    def test_determine_task_count_returns_task_count_if_no_scaling_factor(self):
        test_data = {'taskCount': 10, 'trigger': {'queueName': 'testQueue'}}
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 1})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(10, count)

    def test_determine_task_count_returns_max_count_if_no_scaling_factor_and_task_greater_than_max(self):
        test_data = {'taskCount': 10, 'trigger': {'queueName': 'testQueue'}, 'maxCount': 7}
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 1})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(7, count)

    def test_determine_task_count_returns_calculated_count_based_on_factor(self):
        test_data = {'taskCount': 1, 'trigger': {'queueName': 'testQueue', 'messagesPerTask': 10}}
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 40})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(4, count)

    def test_determine_task_count_returns_max_count_if_calculated_count_greater_than_max(self):
        test_data = {'taskCount': 1, 'trigger': {'queueName': 'testQueue', 'messagesPerTask': 10}, 'maxCount': 2}
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 40})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(2, count)

    def test_determine_task_count_returns_calculated_count_with_remainder_based_on_factor(self):
        test_data = {'taskCount': 1, 'trigger': {'queueName': 'testQueue', 'messagesPerTask': 10}}
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 41})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(5, count)

    def test_determine_task_count_returns_calculated_count_if_equal_messages_to_factor(self):
        test_data = {'taskCount': 1, 'trigger': {'queueName': 'testQueue', 'messagesPerTask': 10}}
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 10})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(1, count)

    def test_determine_task_count_returns_calculated_count_if_less_messages_than_factor(self):
        test_data = {'taskCount': 1, 'trigger': {'queueName': 'testQueue', 'messagesPerTask': 10}}
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 2})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(1, count)

    def test_determine_task_count_returns_task_count_if_calculated_value_lower(self):
        test_data = {'taskCount': 3, 'trigger': {'queueName': 'testQueue', 'messagesPerTask': 10}}
        fake_queue = Mock(attributes={'ApproximateNumberOfMessages': 10})
        self._trigger._sqs.get_queue_by_name.return_value = fake_queue

        count = self._trigger.determine_task_count(test_data)

        self.assertEqual(3, count)


@patch('boto3.resource')
class GetTriggerTests(unittest.TestCase):
    def test_get_sqs_trigger(self, fake_resource):
        trigger = get_trigger('sqs')

        self.assertIsInstance(trigger, SqsTrigger)

    def test_get_noop_trigger(self, fake_resource):
        trigger = get_trigger('noop')

        self.assertIsInstance(trigger, NoOpTrigger)

    def test_get_unknown_trigger(self, fake_resource):
        trigger = get_trigger('who knows')

        self.assertIsInstance(trigger, NoOpTrigger)
