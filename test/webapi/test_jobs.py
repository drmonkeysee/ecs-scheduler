import logging
import unittest
from unittest.mock import patch, Mock

import werkzeug.exceptions

import ecs_scheduler.models
from ecs_scheduler.datacontext import (JobAlreadyExists, JobNotFound,
                                       InvalidJobData)
from ecs_scheduler.webapi.jobs import Jobs, Job, require_json_content_type


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
        fake_request.headers = {
            'Content-Type': 'application/json; charset=utf-8',
        }

        result = self.fake_verb()

        self.assertEqual('fake verb + RequireJsonContentTypeTests', result)
        self.assertIsNotNone(getattr(self.fake_verb, '__wrapped__', None))

    def test_returns_error_if_no_header(self, fake_request):
        fake_request.headers = {}

        result = self.fake_verb()

        self.assertEqual(
            (
                {'message': 'Header Content-Type: application/json required to send a request body.'},
                415,
            ),
            result
        )

    def test_returns_error_if_invalid_header(self, fake_request):
        fake_request.headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        result = self.fake_verb()

        self.assertEqual(
            (
                {'message': 'Header Content-Type: application/json required to send a request body.'},
                415,
            ),
            result
        )


@patch(
    'flask.url_for',
    side_effect=lambda *args, **kwargs: 'foo/' + args[0] + '/' + kwargs['job_id'] if 'job_id' in kwargs else 'pageLink'
)
@patch('flask.request')
class JobsTests(unittest.TestCase):
    def setUp(self):
        self._queue = Mock()
        self._dc = Mock()
        self._jobs = Jobs(self._queue, self._dc)

    def test_expected_verbs_are_decorated(self, fake_request, fake_url):
        self.assertIsNone(getattr(self._jobs.get, '__wrapped__', None))
        self.assertIsNotNone(getattr(self._jobs.post, '__wrapped__', None))

    def test_get_returns_all_jobs(self, fake_request, fake_url):
        fake_request.values = {}
        self._dc.get_all.return_value = [
            Mock(id='1', data={'id': '1'}),
            Mock(id='2', data={'id': '2'}),
            Mock(id='3', data={'id': '3'}),
        ]
        self._dc.total.return_value = 10

        response = self._jobs.get()

        self.assertEqual({
            'jobs': [
                {
                    'id': '1',
                    'link': {
                        'href': 'foo/job/1',
                        'rel': 'item',
                        'title': 'Job for 1',
                    },
                },
                {
                    'id': '2',
                    'link': {
                        'href': 'foo/job/2',
                        'rel': 'item',
                        'title': 'Job for 2',
                    },
                },
                {
                    'id': '3',
                    'link': {
                        'href': 'foo/job/3',
                        'rel': 'item',
                        'title': 'Job for 3',
                    },
                },
            ],
        }, response)

    def test_get_returns_paginated_jobs(self, fake_request, fake_url):
        fake_request.values = {'skip': 1, 'count': 2}
        self._dc.get_all.return_value = [
            Mock(id='1', data={'id': '1'}),
            Mock(id='2', data={'id': '2'}),
            Mock(id='3', data={'id': '3'}),
            Mock(id='4', data={'id': '4'}),
        ]
        self._dc.total.return_value = 10

        response = self._jobs.get()

        self.assertEqual({
            'jobs': [
                {
                    'id': '2',
                    'link': {
                        'href': 'foo/job/2',
                        'rel': 'item',
                        'title': 'Job for 2',
                    },
                },
                {
                    'id': '3',
                    'link': {
                        'href': 'foo/job/3',
                        'rel': 'item',
                        'title': 'Job for 3',
                    },
                },
            ],
            'prev': 'pageLink',
            'next': 'pageLink',
        }, response)

    def test_get_returns_no_jobs(self, fake_request, fake_url):
        fake_request.values = {'skip': 4, 'count': 12}
        self._dc.get_all.return_value = []
        self._dc.total.return_value = 0

        response = self._jobs.get()

        self.assertEqual({'jobs': []}, response)

    def test_get_returns_bad_request_if_invalid_pagination(self, fake_request, fake_url):
        fake_request.values = {'skip': 'blah', 'count': 12}

        with self.assertRaises(werkzeug.exceptions.BadRequest):
            self._jobs.get()

    def test_post_returns_committed_response_if_success(self, fake_request, fake_url):
        fake_request.json = {'taskDefinition': 'foobar', 'schedule': '*'}
        self._dc.create.return_value = Mock(id='foobar', data={'id': 'foobar'})

        response = self._jobs.post.__wrapped__(self._jobs)

        self._dc.create.assert_called_with(
            {'schedule': '*', 'taskDefinition': 'foobar'}
        )
        self._queue.post.assert_called()
        job_op_args, k = self._queue.post.call_args
        self.assertEqual(1, len(job_op_args))
        self.assertEqual(
            ecs_scheduler.models.JobOperation.ADD, job_op_args[0].operation
        )
        self.assertEqual('foobar', job_op_args[0].job_id)
        self.assertEqual(({
            'id': 'foobar',
            'link': {
                'href': 'foo/job/foobar',
                'rel': 'item',
                'title': 'Job for foobar',
            },
        }, 201), response)

    @patch.object(logging.getLogger('ecs_scheduler.webapi.jobs'), 'exception')
    @patch('flask_restful.abort')
    def test_post_returns_committed_response_error_if_queue_throws(self, fake_abort, fake_log, fake_request, fake_url):
        fake_request.json = {'taskDefinition': 'foobar', 'schedule': '*'}
        self._dc.create.return_value = Mock(id='foobar', data={'id': 'foobar'})
        self._queue.post.side_effect = Exception

        self._jobs.post.__wrapped__(self._jobs)

        self._dc.create.assert_called_with(
            {'schedule': '*', 'taskDefinition': 'foobar'}
        )
        fake_abort.assert_called_with(
            500,
            item={
                'id': 'foobar',
                'link': {
                    'href': 'foo/job/foobar',
                    'rel': 'item',
                    'title': 'Job for foobar',
                },
            },
            message='Job update was saved correctly but failed to post update message to scheduler.'
        )

    def test_post_returns_conflict_response_if_failure(self, fake_request, fake_url):
        fake_request.json = {'taskDefinition': 'foobar', 'schedule': '*'}
        self._dc.create.side_effect = JobAlreadyExists('foobar')

        with self.assertRaises(werkzeug.exceptions.Conflict):
            self._jobs.post.__wrapped__(self._jobs)

    def test_post_returns_bad_request_if_body_malformed(self, fake_request, fake_url):
        fake_request.json = {'taskDefinition': 'foobar'}
        self._dc.create.side_effect = InvalidJobData('foobar', {})

        with self.assertRaises(werkzeug.exceptions.BadRequest):
            self._jobs.post.__wrapped__(self._jobs)


@patch(
    'flask.url_for',
    side_effect=lambda *args, **kwargs: 'foo/' + args[0] + '/' + kwargs['job_id']
)
class JobTests(unittest.TestCase):
    def setUp(self):
        self._queue = Mock()
        self._dc = Mock()
        self._job = Job(self._queue, self._dc)

    def test_expected_verbs_are_decorated(self, fake_url):
        self.assertIsNone(getattr(self._job.get, '__wrapped__', None))
        self.assertIsNotNone(getattr(self._job.put, '__wrapped__', None))
        self.assertIsNone(getattr(self._job.delete, '__wrapped__', None))

    def test_get_returns_found_job(self, fake_url):
        self._dc.get.return_value = Mock(id='foobar', data={'id': 'foobar'})

        response = self._job.get('foobar')

        self._dc.get.assert_called_with('foobar')
        self.assertEqual({
            'id': 'foobar',
            'link': {
                'href': 'foo/job/foobar',
                'rel': 'item',
                'title': 'Job for foobar',
            },
        }, response)

    def test_get_returns_notfound(self, fake_url):
        self._dc.get.side_effect = JobNotFound('foobar')

        with self.assertRaises(werkzeug.exceptions.NotFound):
            self._job.get('foobar')

        self._dc.get.assert_called_with('foobar')

    @patch('flask.request')
    def test_put_returns_committed_response_if_success(self, fake_request, fake_url):
        fake_request.json = {'taskCount': 30}
        update_job = Mock(id='foobar')
        self._dc.get.return_value = update_job

        response = self._job.put.__wrapped__(self._job, 'foobar')

        update_job.update.assert_called_with({'taskCount': 30})
        self._queue.post.assert_called()
        job_op_args, k = self._queue.post.call_args
        self.assertEqual(1, len(job_op_args))
        self.assertEqual(
            ecs_scheduler.models.JobOperation.MODIFY, job_op_args[0].operation
        )
        self.assertEqual('foobar', job_op_args[0].job_id)
        self.assertEqual({
            'id': 'foobar',
            'link': {
                'href': 'foo/job/foobar',
                'rel': 'item',
                'title': 'Job for foobar',
            },
        }, response)

    @patch.object(logging.getLogger('ecs_scheduler.webapi.jobs'), 'exception')
    @patch('flask_restful.abort')
    @patch('flask.request')
    def test_put_returns_committed_response_error_if_queue_throws(self, fake_request, fake_abort, fake_url, fake_log):
        fake_request.json = {'taskCount': 30}
        update_job = Mock(id='foobar')
        self._dc.get.return_value = update_job
        self._queue.post.side_effect = Exception

        self._job.put.__wrapped__(self._job, 'foobar')

        update_job.update.assert_called_with({'taskCount': 30})
        fake_abort.assert_called_with(
            500,
            item={
                'id': 'foobar',
                'link': {
                    'href': 'foo/job/foobar',
                    'rel': 'item',
                    'title': 'Job for foobar',
                },
            },
            message='Job update was saved correctly but failed to post update message to scheduler.'
        )

    @patch('flask.request')
    def test_put_returns_notfound(self, fake_request, fake_url):
        fake_request.json = {'taskCount': 30}
        self._dc.get.side_effect = JobNotFound('foobar')

        with self.assertRaises(werkzeug.exceptions.NotFound):
            self._job.put.__wrapped__(self._job, 'foobar')

    @patch('flask.request')
    def test_put_returns_bad_request_if_invalid_data(self, fake_request, fake_url):
        fake_request.json = {'taskCount': 'broken'}
        update_job = Mock(id='foobar')
        self._dc.get.return_value = update_job
        update_job.update.side_effect = InvalidJobData('foobar', {})

        with self.assertRaises(werkzeug.exceptions.BadRequest):
            self._job.put.__wrapped__(self._job, 'foobar')

    def test_delete_returns_job_id(self, fake_url):
        response = self._job.delete('foobar')

        self._dc.delete.assert_called_with('foobar')
        self._queue.post.assert_called()
        job_op_args, k = self._queue.post.call_args
        self.assertEqual(1, len(job_op_args))
        self.assertEqual(
            ecs_scheduler.models.JobOperation.REMOVE, job_op_args[0].operation
        )
        self.assertEqual('foobar', job_op_args[0].job_id)
        self.assertEqual({'id': 'foobar'}, response)

    @patch.object(logging.getLogger('ecs_scheduler.webapi.jobs'), 'exception')
    @patch('flask_restful.abort')
    @patch('flask.request')
    def test_delete_returns_committed_response_error_if_queue_throws(self, fake_request, fake_abort, fake_url, fake_log):
        self._queue.post.side_effect = Exception

        self._job.delete('foobar')

        self._dc.delete.assert_called_with('foobar')
        fake_abort.assert_called_with(
            500,
            item={
                'id': 'foobar',
            },
            message='Job update was saved correctly but failed to post update message to scheduler.'
        )

    def test_delete_returns_notfound(self, fake_url):
        self._dc.delete.side_effect = JobNotFound('foobar')

        with self.assertRaises(werkzeug.exceptions.NotFound):
            self._job.delete('foobar')

        self._dc.delete.assert_called_with('foobar')
