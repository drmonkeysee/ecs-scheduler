import unittest
import logging
from unittest.mock import patch, Mock

import werkzeug.exceptions

import ecs_scheduler.models
from ecs_scheduler.webapi.jobs import Jobs, Job, require_json_content_type
from ecs_scheduler.webapi.jobstore import JobExistsException, JobNotFoundException


@patch('flask.request')
class RequireJsonContentTypeTests(unittest.TestCase):
    @require_json_content_type
    def fake_verb(self):
        return 'fake verb + ' + type(self).__name__

    def test_defers_to_verb_if_valid_header(self, fake_request):
        fake_request.headers = {'Content-Type': 'application/json'}

        result = self.fake_verb()

        self.assertEqual('fake verb + RequireJsonContentTypeTests', result)
        self.assertIsNotNone(getattr(self.fake_verb, '__wrapped__', None))

    def test_defers_to_verb_if_valid_header_with_more_info(self, fake_request):
        fake_request.headers = {'Content-Type': 'application/json; charset=utf-8'}

        result = self.fake_verb()

        self.assertEqual('fake verb + RequireJsonContentTypeTests', result)
        self.assertIsNotNone(getattr(self.fake_verb, '__wrapped__', None))

    def test_returns_error_if_no_header(self, fake_request):
        fake_request.headers = {}

        result = self.fake_verb()

        self.assertEqual(({'message': 'Request requires Content-Type: application/json'}, 415), result)

    def test_returns_error_if_invalid_header(self, fake_request):
        fake_request.headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        result = self.fake_verb()

        self.assertEqual(({'message': 'Request requires Content-Type: application/json'}, 415), result)


@patch('flask.url_for', side_effect=lambda *args, **kwargs: 'foo/' + args[0] + '/' + kwargs['job_id'] if 'job_id' in kwargs else 'pageLink')
class JobsTests(unittest.TestCase):
    def setUp(self):
        self._fake_es = Mock()
        self._fake_queue = Mock()
        self._jobs = Jobs(self._fake_es, self._fake_queue)

    def test_expected_verbs_are_decorated(self, fake_url):
        self.assertIsNone(getattr(self._jobs.get, '__wrapped__', None))
        self.assertIsNotNone(getattr(self._jobs.post, '__wrapped__', None))

    @patch('flask.request')
    def test_get_returns_all_jobs(self, fake_request, fake_url):
        fake_request.values = {'skip': 1, 'count': 2}
        self._fake_es.get_jobs.return_value = {'hits': {'hits': [{'_id': '1'}, {'_id': '2'}, {'_id': '3'}], 'total': 10}}

        response = self._jobs.get()

        self._fake_es.get_jobs.assert_called_with(1, 2)
        self.assertEqual({
            'jobs': [
                {'id': '1', 'link': {'href': 'foo/job/1', 'rel': 'item', 'title': 'Job for 1'}},
                {'id': '2', 'link': {'href': 'foo/job/2', 'rel': 'item', 'title': 'Job for 2'}},
                {'id': '3', 'link': {'href': 'foo/job/3', 'rel': 'item', 'title': 'Job for 3'}}
            ],
            'prev': 'pageLink',
            'next': 'pageLink'
        }, response)

    @patch('flask.request')
    def test_get_returns_no_jobs(self, fake_request, fake_url):
        fake_request.values = {'skip': 4, 'count': 12}
        self._fake_es.get_jobs.return_value = {'hits': {'hits': [], 'total': 0}}

        response = self._jobs.get()

        self._fake_es.get_jobs.assert_called_with(4, 12)
        self.assertEqual({'jobs': []}, response)

    @patch('flask.request')
    def test_get_returns_bad_request_if_invalid_pagination(self, fake_request, fake_url):
        fake_request.values = {'skip': 'blah', 'count': 12}
        
        with self.assertRaises(werkzeug.exceptions.BadRequest):
            self._jobs.get()

    @patch('flask.request')
    def test_get_returns_server_error_if_docs_are_malformed(self, fake_request, fake_url):
        fake_request.values = {'skip': 4, 'count': 12}
        self._fake_es.get_jobs.return_value = {'hits': {'hits': [{'_id': '1', 'taskCount': 'broken'}], 'total': 10}}
        
        with self.assertRaises(werkzeug.exceptions.InternalServerError):
            self._jobs.get()

    @patch('flask.request')
    def test_post_returns_committed_response_if_success(self, fake_request, fake_url):
        fake_request.json = {'taskDefinition': 'foobar', 'schedule': '*'}
        self._fake_es.create.return_value = 'yay'

        response = self._jobs.post.__wrapped__(self._jobs)

        self._fake_es.create.assert_called_with('foobar', {'taskCount': 1, 'schedule': '*', 'taskDefinition': 'foobar'})
        self._fake_queue.put.assert_called()
        job_op_args, k = self._fake_queue.put.call_args
        self.assertEqual(1, len(job_op_args))
        self.assertEqual(ecs_scheduler.models.JobOperation.ADD, job_op_args[0].operation)
        self.assertEqual('foobar', job_op_args[0].job_id)
        self.assertEqual(({
            'id': 'foobar',
            'link': {'href': 'foo/job/foobar', 'rel': 'item', 'title': 'Job for foobar'}
        }, 201), response)

    @patch.object(logging.getLogger('ecs_scheduler.webapi.jobs'), 'exception')
    @patch('flask_restful.abort')
    @patch('flask.request')
    def test_post_returns_committed_response_error_if_queue_throws(self, fake_request, fake_abort, fake_url, fake_log):
        fake_request.json = {'taskDefinition': 'foobar', 'schedule': '*'}
        self._fake_es.create.return_value = 'yay'
        self._fake_queue.put.side_effect = Exception

        self._jobs.post.__wrapped__(self._jobs)

        self._fake_es.create.assert_called_with('foobar', {'taskCount': 1, 'schedule': '*', 'taskDefinition': 'foobar'})
        fake_abort.assert_called_with(500, item={
            'id': 'foobar',
            'link': {'href': 'foo/job/foobar', 'rel': 'item', 'title': 'Job for foobar'}
        }, message='Job update was saved correctly but failed to post update message to scheduler')

    @patch('flask.request')
    def test_post_returns_conflict_response_if_failure(self, fake_request, fake_url):
        fake_request.json = {'taskDefinition': 'foobar', 'schedule': '*'}
        self._fake_es.create.side_effect = JobExistsException

        response = self._jobs.post.__wrapped__(self._jobs)

        self._fake_es.create.assert_called_with('foobar', {'taskCount': 1, 'schedule': '*', 'taskDefinition': 'foobar'})
        self.assertEqual(({
            'message': 'Job foobar already exists'
        }, 409), response)

    @patch('flask.request')
    def test_post_returns_bad_request_if_body_malformed(self, fake_request, fake_url):
        fake_request.json = {'taskDefinition': 'foobar'}
        self._fake_es.create.side_effect = JobExistsException

        with self.assertRaises(werkzeug.exceptions.BadRequest):
            self._jobs.post.__wrapped__(self._jobs)


@patch('flask.url_for', side_effect=lambda *args, **kwargs: 'foo/' + args[0] + '/' + kwargs['job_id'])
class JobTests(unittest.TestCase):
    def setUp(self):
        self._fake_es = Mock()
        self._fake_queue = Mock()
        self._job = Job(self._fake_es, self._fake_queue)

    def test_expected_verbs_are_decorated(self, fake_url):
        self.assertIsNone(getattr(self._job.get, '__wrapped__', None))
        self.assertIsNotNone(getattr(self._job.put, '__wrapped__', None))
        self.assertIsNone(getattr(self._job.delete, '__wrapped__', None))

    def test_get_returns_found_job(self, fake_url):
        self._fake_es.get.return_value = {'_id': 'foobar'}

        response = self._job.get('foobar')

        self._fake_es.get.assert_called_with('foobar')
        self.assertEqual({
            'id': 'foobar',
            'link': {'href': 'foo/job/foobar', 'rel': 'item', 'title': 'Job for foobar'}
        }, response)

    def test_get_returns_notfound(self, fake_url):
        self._fake_es.get.side_effect = JobNotFoundException

        response = self._job.get('foobar')

        self._fake_es.get.assert_called_with('foobar')
        self.assertEqual(({'message': 'Job foobar does not exist'}, 404), response)

    def test_get_returns_server_error_if_malformed_doc(self, fake_url):
        self._fake_es.get.return_value = {'_id': 'foobar', 'taskCount': 'broken'}

        with self.assertRaises(werkzeug.exceptions.InternalServerError):
            self._job.get('foobar')

    @patch('flask.request')
    def test_put_returns_committed_response_if_success(self, fake_request, fake_url):
        fake_request.json = {'taskCount': 30}
        self._fake_es.update.return_value = 'yay'

        response = self._job.put.__wrapped__(self._job, 'foobar')

        self._fake_es.update.assert_called_with('foobar', {'taskCount': 30})
        self._fake_queue.put.assert_called()
        job_op_args, k = self._fake_queue.put.call_args
        self.assertEqual(1, len(job_op_args))
        self.assertEqual(ecs_scheduler.models.JobOperation.MODIFY, job_op_args[0].operation)
        self.assertEqual('foobar', job_op_args[0].job_id)
        self.assertEqual({
            'id': 'foobar',
            'link': {'href': 'foo/job/foobar', 'rel': 'item', 'title': 'Job for foobar'}
        }, response)

    @patch('flask.request')
    def test_put_omits_parsed_schedule_if_schedule_provided(self, fake_request, fake_url):
        fake_request.json = {'taskCount': 30, 'schedule': '*'}
        self._fake_es.update.return_value = 'yay'

        response = self._job.put.__wrapped__(self._job, 'foobar')

        self._fake_es.update.assert_called_with('foobar', {'taskCount': 30, 'schedule': '*'})
        self._fake_queue.put.assert_called()
        job_op_args, k = self._fake_queue.put.call_args
        self.assertEqual(1, len(job_op_args))
        self.assertEqual(ecs_scheduler.models.JobOperation.MODIFY, job_op_args[0].operation)
        self.assertEqual('foobar', job_op_args[0].job_id)
        self.assertEqual({
            'id': 'foobar',
            'link': {'href': 'foo/job/foobar', 'rel': 'item', 'title': 'Job for foobar'}
        }, response)

    @patch.object(logging.getLogger('ecs_scheduler.webapi.jobs'), 'exception')
    @patch('flask_restful.abort')
    @patch('flask.request')
    def test_put_returns_committed_response_error_if_queue_throws(self, fake_request, fake_abort, fake_url, fake_log):
        fake_request.json = {'taskCount': 30}
        self._fake_es.update.return_value = 'yay'
        self._fake_queue.put.side_effect = Exception

        response = self._job.put.__wrapped__(self._job, 'foobar')

        self._fake_es.update.assert_called_with('foobar', {'taskCount': 30})
        fake_abort.assert_called_with(500, item={
            'id': 'foobar',
            'link': {'href': 'foo/job/foobar', 'rel': 'item', 'title': 'Job for foobar'}
        }, message='Job update was saved correctly but failed to post update message to scheduler')

    @patch('flask.request')
    def test_put_returns_notfound(self, fake_request, fake_url):
        fake_request.json = {'taskCount': 30}
        self._fake_es.update.side_effect = JobNotFoundException

        response = self._job.put.__wrapped__(self._job, 'foobar')

        self._fake_es.update.assert_called_with('foobar', {'taskCount': 30})
        self.assertEqual(({'message': 'Job foobar does not exist'}, 404), response)

    @patch('flask.request')
    def test_put_returns_bad_request_if_malformed_body(self, fake_request, fake_url):
        fake_request.json = {'taskCount': 'broken'}
        
        with self.assertRaises(werkzeug.exceptions.BadRequest):
            self._job.put.__wrapped__(self._job, 'foobar')

    def test_delete_returns_job_id(self, fake_url):
        self._fake_es.delete.return_value = 'yay'

        response = self._job.delete('foobar')

        self._fake_es.delete.assert_called_with('foobar')
        self._fake_queue.put.assert_called()
        job_op_args, k = self._fake_queue.put.call_args
        self.assertEqual(1, len(job_op_args))
        self.assertEqual(ecs_scheduler.models.JobOperation.REMOVE, job_op_args[0].operation)
        self.assertEqual('foobar', job_op_args[0].job_id)
        self.assertEqual({'id': 'foobar'}, response)

    @patch.object(logging.getLogger('ecs_scheduler.webapi.jobs'), 'exception')
    @patch('flask_restful.abort')
    @patch('flask.request')
    def test_delete_returns_committed_response_error_if_queue_throws(self, fake_request, fake_abort, fake_url, fake_log):
        self._fake_es.delete.return_value = 'yay'
        self._fake_queue.put.side_effect = Exception

        response = self._job.delete('foobar')

        self._fake_es.delete.assert_called_with('foobar')
        fake_abort.assert_called_with(500, item={
            'id': 'foobar'
        }, message='Job update was saved correctly but failed to post update message to scheduler')

    def test_delete_returns_notfound(self, fake_url):
        self._fake_es.delete.side_effect = JobNotFoundException

        response = self._job.delete('foobar')

        self._fake_es.delete.assert_called_with('foobar')
        self.assertEqual(({'message': 'Job foobar does not exist'}, 404), response)
