"""Job execution classes."""
import logging
import copy

import boto3

from . import triggers
from .. import env


# see http://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_RunTask.html
_MAX_TASK_COUNT = 10
_logger = logging.getLogger(__name__)


class JobExecutor:
    """
    The executor run by all scheduled jobs.

    :attribute RETVAL_CHECKED_TASKS: The return value of the job executor when it successfully verifies the state of ECS for a job but starts no new tasks
    :attribute RETVAL_STARTED_TASKS: The return value of the job executor when it started new ECS tasks for a job
    :attribute OVERRIDE_TAG: If the job contains task overrides add the job id to the overrides when launching a task so it can be identified later
    """
    RETVAL_CHECKED_TASKS = 0
    RETVAL_STARTED_TASKS = 1
    OVERRIDE_TAG = 'ECS_SCHEDULER_OVERRIDE_TAG'
    
    def __init__(self):
        """Create an executor."""
        self._ecs = boto3.client('ecs')
        self._cluster_name = env.get_var('ECS_CLUSTER', required=True)
        self._my_name = env.get_var('NAME', default='ecs-scheduler')

    def __call__(self, **job_data):
        """
        Call the executor.

        :param job_data: The job data dictionary
        :returns: An executor return value
        """
        task_name = job_data.get('taskDefinition', job_data['id'])
        running_tasks = self._ecs.list_tasks(cluster=self._cluster_name, family=task_name, desiredStatus='RUNNING')
        running_task_count = self._calculate_running_count(job_data, running_tasks['taskArns'])
        expected_task_count = self._calculate_expected_count(job_data)
        needed_task_count = max(0, expected_task_count - running_task_count)

        if needed_task_count:
            task_info = self._launch_tasks(task_name, needed_task_count, job_data)
            _logger.info('Launched %s "%s" tasks for job %s', needed_task_count, task_name, job_data['id'])
            return JobResult(self.RETVAL_STARTED_TASKS, task_info)
        
        _logger.info('Checked status for "%s" and no additional tasks were needed', job_data['id'])
        return JobResult(self.RETVAL_CHECKED_TASKS)

    def _calculate_running_count(self, job_data, task_arns):
        if task_arns and 'overrides' in job_data:
            tasks = self._ecs.describe_tasks(cluster=self._cluster_name, tasks=task_arns)
            overridden_tasks = [task for task in tasks['tasks'] if self._is_overridden_by_job(task, job_data['id'])]
            return len(overridden_tasks)
        else:
            return len(task_arns)

    def _is_overridden_by_job(self, task, job_id):
        return any(env.get('name') == self.OVERRIDE_TAG and env.get('value') == job_id
                    for overrides in task['overrides']['containerOverrides']
                    for env in overrides.get('environment', []))

    def _calculate_expected_count(self, job_data):
        trigger_data = job_data.get('trigger', {})
        trigger = triggers.get(trigger_data.get('type'))
        return trigger.determine_task_count(job_data)

    def _launch_tasks(self, task_def_id, task_count, job_data):
        run_kwargs = {
            'cluster': self._cluster_name,
            'taskDefinition': task_def_id,
            'startedBy': self._my_name
        }

        self._add_overrides(run_kwargs, job_data)
        
        task_info = []
        while task_count > 0:
            run_kwargs['count'] = min(task_count, _MAX_TASK_COUNT)
            response = self._ecs.run_task(**run_kwargs)
            failures = response['failures']
            if failures:
                _logger.warning('Task "%s" start failures: %s', task_def_id, failures)
            task_info.extend({'taskId': t['taskArn'], 'hostId': t['containerInstanceArn']} for t in response['tasks'])
            task_count -= _MAX_TASK_COUNT
        return task_info

    def _add_overrides(self, run_kwargs, job_data):
        overrides = job_data.get('overrides')
        if overrides:
            # APScheduler only gives me a shallow copy of kwargs on each job run so deep copy before manipulating
            tagged_overrides = copy.deepcopy(overrides)
            for override in tagged_overrides:
                override['environment'][self.OVERRIDE_TAG] = job_data['id']
            ecs_overrides = [{
                    'name': override['containerName'],
                    'environment': [{'name': k, 'value': v} for k, v in override['environment'].items()]
                } for override in tagged_overrides]
            run_kwargs['overrides'] = {'containerOverrides': ecs_overrides}


class JobResult:
    """The result of a job run."""
    def __init__(self, return_code, task_info=None):
        """Create a job result with a return code and optional task info."""
        self.return_code = return_code
        self.task_info = task_info
