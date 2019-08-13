import unittest
from datetime import datetime, timezone, timedelta

import dateutil

from ecs_scheduler.models import Pagination
from ecs_scheduler.serialization import (TriggerSchema, JobSchema,
                                         JobCreateSchema, JobResponseSchema,
                                         PaginationSchema, OverrideSchema,
                                         TaskInfoSchema)


class TriggerSchemaTests(unittest.TestCase):
    def test_simple_deserialize(self):
        schema = TriggerSchema()
        data = {'type': 'foo'}

        trigger, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertEqual(data, trigger)

    def test_complete_deserialize(self):
        schema = TriggerSchema()
        data = {'type': 'sqs', 'queueName': 'foo', 'messagesPerTask': 10}

        trigger, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertEqual(data, trigger)

    def test_deserialize_fails_if_missing_required_fields(self):
        schema = TriggerSchema()
        data = {}

        trigger, errors = schema.load(data)

        self.assertEqual({'type'}, errors.keys())

    def test_deserialize_fails_if_type_constraints_violated(self):
        schema = TriggerSchema()
        data = {'type': 'sqs'}

        trigger, errors = schema.load(data)

        self.assertEqual({'_schema'}, errors.keys())

    def test_deserialize_fails_if_range_constraints_violated(self):
        schema = TriggerSchema()
        data = {'type': 'sqs', 'queueName': 'foo', 'messagesPerTask': 0}

        trigger, errors = schema.load(data)

        self.assertEqual({'messagesPerTask'}, errors.keys())


class OverrideSchemaTests(unittest.TestCase):
    def test_deserialize(self):
        schema = OverrideSchema()
        data = {
            'containerName': 'test-container',
            'environment': {'foo': 'bar', 'baz': 'bort'},
        }

        override, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertEqual(data, override)

    def test_deserialize_empty_data(self):
        schema = OverrideSchema()
        data = {}

        override, errors = schema.load(data)

        self.assertEqual({'containerName'}, errors.keys())
        self.assertEqual(data, override)

    def test_deserialize_empty_list(self):
        schema = OverrideSchema()
        data = {'containerName': 'test-container', 'environment': {}}

        override, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertEqual(data, override)

    def test_deserialize_fails_if_none_list(self):
        schema = OverrideSchema()
        data = {'containerName': 'test-container', 'environment': None}

        override, errors = schema.load(data)

        self.assertEqual({'environment'}, errors.keys())


class TaskInfoSchemaTests(unittest.TestCase):
    def test_deserialize(self):
        schema = TaskInfoSchema()
        data = {'taskId': 'foo', 'hostId': 'bar'}

        info, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertEqual(data, info)

    def test_deserialize_empty_data(self):
        schema = TaskInfoSchema()
        data = {}

        override, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertEqual(data, override)


class JobSchemaTests(unittest.TestCase):
    def test_simple_deserialize(self):
        schema = JobSchema()
        data = {}

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertEqual({}, job)

    def test_complete_deserialize(self):
        schema = JobSchema()
        data = {
            'taskDefinition': 'test-task',
            'schedule': '*',
            'scheduleStart': '2015-10-07T13:44:53.123456+00:00',
            'scheduleEnd': '2015-10-10T04:10:03.654321+00:00',
            'timezone': 'UTC',
            'taskCount': 12,
            'maxCount': 20,
            'suspended': True,
            'trigger': {
                'type': 'test-type',
            },
            'overrides': [{
                'containerName': 'test-container',
                'environment': {
                    'foo': 'foo_value',
                    'bar': 'bar_value',
                    'baz': 'baz_value',
                },
            }],
        }

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))

        expected_data = data.copy()
        _parse_datetime_fields(expected_data, 'scheduleStart', 'scheduleEnd')

        self.assertEqual(expected_data, job)

    def test_deserialize_supports_timezone_offsets(self):
        schema = JobSchema()
        data = {
            'scheduleStart': '2015-10-07T13:44:53.123456+10:00',
            'scheduleEnd': '2015-10-10T04:10:03.654321-06:00',
            'timezone': 'US/Pacific',
        }

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))

        expected_data = data.copy()
        _parse_datetime_fields(expected_data, 'scheduleStart', 'scheduleEnd')

        self.assertEqual(expected_data, job)

    def test_deserialize_ignores_parsed_schedule_on_input(self):
        schema = JobSchema()
        data = {
            'schedule': '*',
            'parsedSchedule': 'foobar',
        }

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertEqual({'second': '*'}, job['parsedSchedule'])

    def test_deserialize_parses_full_schedule(self):
        schema = JobSchema()
        data = {
            'schedule': '10 12 22-23 sun 34 last 2 2012-2015',
        }

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        expected_data = {
            'second': '10',
            'minute': '12',
            'hour': '22-23',
            'day_of_week': 'sun',
            'week': '34',
            'day': 'last',
            'month': '2',
            'year': '2012-2015',
        }
        self.assertEqual(expected_data, job['parsedSchedule'])

    def test_deserialize_ignores_extra_schedule_stuff(self):
        schema = JobSchema()
        data = {
            'schedule': '10 12 22-23 sun 34 last 2 2012-2015'
                        ' barf bort blow-up',
        }

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        expected_data = {
            'second': '10',
            'minute': '12',
            'hour': '22-23',
            'day_of_week': 'sun',
            'week': '34',
            'day': 'last',
            'month': '2',
            'year': '2012-2015',
        }
        self.assertEqual(expected_data, job['parsedSchedule'])

    def test_deserialize_uses_underscore_to_denote_spaces(self):
        schema = JobSchema()
        data = {
            'schedule': '0 0 0 * * 2nd_wed'
        }

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        expected_data = {
            'second': '0',
            'minute': '0',
            'hour': '0',
            'day_of_week': '*',
            'week': '*',
            'day': '2nd wed',
        }
        self.assertEqual(expected_data, job['parsedSchedule'])

    def test_deserialize_supports_wildcards_for_secminhour(self):
        schema = JobSchema()
        data = {
            'schedule': '? ? ?',
        }

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertTrue(
            0 <= int(job['parsedSchedule']['second']) < 60,
            'wildcard second not in expected range'
        )
        self.assertTrue(
            0 <= int(job['parsedSchedule']['minute']) < 60,
            'wildcard minute not in expected range'
        )
        self.assertTrue(
            0 <= int(job['parsedSchedule']['hour']) < 24,
            'wildcard hour not in expected range'
        )
        expected_expression = ' '.join((
            job['parsedSchedule']['second'],
            job['parsedSchedule']['minute'],
            job['parsedSchedule']['hour'],
        ))
        self.assertEqual(expected_expression, job['schedule'])

    def test_deserialize_supports_wildcards_combined_with_other_fields(self):
        schema = JobSchema()
        data = {
            'schedule': '? ? ? sun 34 last 2 2012-2015',
        }

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertTrue(
            0 <= int(job['parsedSchedule']['second']) < 60,
            'wildcard second not in expected range'
        )
        self.assertTrue(
            0 <= int(job['parsedSchedule']['minute']) < 60,
            'wildcard minute not in expected range'
        )
        self.assertTrue(
            0 <= int(job['parsedSchedule']['hour']) < 24,
            'wildcard hour not in expected range'
        )
        expected_expression = ' '.join((
            job['parsedSchedule']['second'],
            job['parsedSchedule']['minute'],
            job['parsedSchedule']['hour'],
            'sun 34 last 2 2012-2015',
        ))
        self.assertEqual(expected_expression, job['schedule'])

    def test_deserialize_does_not_support_wildcards_for_other_fields(self):
        schema = JobSchema()
        data = {
            'schedule': '0 0 0 ? ? ? ? ?',
        }

        job, errors = schema.load(data)

        self.assertEqual({'parsedSchedule'}, errors.keys())

    def test_complete_deserialize_fails_if_invalid_schedule(self):
        schema = JobSchema()
        data = {
            'taskDefinition': 'test-task',
            'schedule': 'bad-schedule',
            'scheduleStart': '2015-10-07T13:44:53.123456+00:00',
            'scheduleEnd': '2015-10-10T04:10:03.654321+00:00',
            'taskCount': 12,
            'suspended': True,
            'trigger': {
                'type': 'test-type',
            },
            'overrides': [{
                'containerName': 'test-container',
                'environment': {
                    'foo': 'foo_value',
                    'bar': 'bar_value',
                    'baz': 'baz_value',
                },
            }],
        }

        job, errors = schema.load(data)

        self.assertEqual({'parsedSchedule'}, errors.keys())

    def test_deserialize_fails_if_bad_trigger(self):
        schema = JobSchema()
        data = {
            'schedule': '*',
            'trigger': {},
        }

        job, errors = schema.load(data)

        self.assertEqual({'trigger'}, errors.keys())

    def test_deserialize_fails_if_zero_task_count(self):
        schema = JobSchema()
        data = {'taskCount': 0, 'maxCount': 0}

        job, errors = schema.load(data)

        self.assertEqual({'taskCount', 'maxCount'}, errors.keys())

    def test_deserialize_fails_if_negative_task_count(self):
        schema = JobSchema()
        data = {'taskCount': -1, 'maxCount': -1}

        job, errors = schema.load(data)

        self.assertEqual({'taskCount', 'maxCount'}, errors.keys())

    def test_deserialize_fails_if_above_max_task_count(self):
        schema = JobSchema()
        data = {'taskCount': 51, 'maxCount': 51}

        job, errors = schema.load(data)

        self.assertEqual({'taskCount', 'maxCount'}, errors.keys())

    def test_deserialize_succeeds_if_at_max_task_count(self):
        schema = JobSchema()
        data = {'taskCount': 50, 'maxCount': 50}

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertEqual(50, job['taskCount'])
        self.assertEqual(50, job['maxCount'])

    def test_deserialize_succeeds_if_max_less_than_task_count(self):
        schema = JobSchema()
        data = {'taskCount': 21, 'maxCount': 20}

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertEqual(21, job['taskCount'])
        self.assertEqual(20, job['maxCount'])

    def test_deserialize_succeeds_with_empty_overrides(self):
        schema = JobSchema()
        data = {'overrides': []}

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertEqual({'overrides': []}, job)

    def test_deserialize_fails_if_task_definition_includes_revision(self):
        schema = JobSchema()
        data = {'taskDefinition': 'foo:3', 'schedule': '*'}

        job, errors = schema.load(data)

        self.assertEqual({'taskDefinition'}, errors.keys())

    def test_deserialize_fails_if_task_definition_includes_malformed_revision(
        self
    ):
        schema = JobSchema()
        data = {'taskDefinition': 'foo:', 'schedule': '*'}

        job, errors = schema.load(data)

        self.assertEqual({'taskDefinition'}, errors.keys())

    def test_deserialize_fails_if_task_definition_includes_invalid_characters(
        self
    ):
        schema = JobSchema()
        data = {'taskDefinition': 'foo/bar.baz', 'schedule': '*'}

        job, errors = schema.load(data)

        self.assertEqual({'taskDefinition'}, errors.keys())

    def test_deserialize_fails_if_invalid_timezone(self):
        schema = JobSchema()
        data = {'timezone': 'FOO'}

        job, errors = schema.load(data)

        self.assertEqual({'timezone'}, errors.keys())

    def test_serialize(self):
        schema = JobSchema()
        job_data = {
            'id': 'idIsIgnored',
            'taskDefinition': 'test-task',
            'schedule': 'test-schedule',
            'scheduleStart': datetime(
                2015, 10, 7, 13, 44, 53, 123456, timezone.utc
            ),
            'scheduleEnd': datetime(
                2015, 10, 10, 4, 10, 3, 654321, timezone.utc
            ),
            'timezone': 'UTC',
            'taskCount': 12,
            'suspended': True,
            'trigger': {
                'type': 'test-type',
            },
            'overrides': [{
                'containerName': 'test-container',
                'environment': {
                    'foo': 'foo_value',
                    'bar': 'bar_value',
                    'baz': 'baz_value',
                },
            }],
        }

        doc, errors = schema.dump(job_data)

        self.assertEqual(0, len(errors))
        expected_data = {
            'taskDefinition': 'test-task',
            'schedule': 'test-schedule',
            'scheduleStart': '2015-10-07T13:44:53.123456+00:00',
            'scheduleEnd': '2015-10-10T04:10:03.654321+00:00',
            'timezone': 'UTC',
            'taskCount': 12,
            'suspended': True,
            'trigger': {
                'type': 'test-type',
            },
            'overrides': [{
                'containerName': 'test-container',
                'environment': {
                    'foo': 'foo_value',
                    'bar': 'bar_value',
                    'baz': 'baz_value',
                },
            }],
        }
        self.assertEqual(expected_data, doc)

    def test_serialize_empty_doc(self):
        schema = JobSchema()
        job_data = {}

        doc, errors = schema.dump(job_data)

        self.assertEqual(0, len(errors))
        self.assertEqual({}, doc)

    def test_serialize_timezone_offsets(self):
        schema = JobSchema()
        job_data = {
            'scheduleStart': datetime(
                2015, 10, 7, 13, 44, 53, 123456, timezone(timedelta(hours=10))
            ),
            'scheduleEnd': datetime(
                2015, 10, 10, 4, 10, 3, 654321, timezone(timedelta(hours=-6))
            ),
            'timezone': 'US/Eastern',
        }

        doc, errors = schema.dump(job_data)

        self.assertEqual(0, len(errors))
        expected_data = {
            'scheduleStart': '2015-10-07T13:44:53.123456+10:00',
            'scheduleEnd': '2015-10-10T04:10:03.654321-06:00',
            'timezone': 'US/Eastern',
        }
        self.assertEqual(expected_data, doc)

    def test_serialize_timezone_naive(self):
        schema = JobSchema()
        job_data = {
            'scheduleStart': datetime(2015, 10, 7, 13, 44, 53, 123456),
            'scheduleEnd': datetime(2015, 10, 10, 4, 10, 3, 654321),
        }

        doc, errors = schema.dump(job_data)

        self.assertEqual(0, len(errors))
        expected_data = {
            'scheduleStart': '2015-10-07T13:44:53.123456+00:00',
            'scheduleEnd': '2015-10-10T04:10:03.654321+00:00',
        }
        self.assertEqual(expected_data, doc)


class JobCreateSchemaTests(unittest.TestCase):
    def test_simple_deserialize(self):
        schema = JobCreateSchema()
        data = {'taskDefinition': 'foo', 'schedule': '*'}

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        expected_data = {
            'id': data['taskDefinition'],
            'taskDefinition': data['taskDefinition'],
            'taskCount': 1,
            'schedule': '*',
            'parsedSchedule': {'second': '*'},
        }
        self.assertEqual(expected_data, job)

    def test_deserialize_fails_if_missing_required_fields(self):
        schema = JobCreateSchema()
        data = {}

        job, errors = schema.load(data)

        self.assertEqual({'taskDefinition', 'schedule'}, errors.keys())

    def test_deserialize_fails_if_id_includes_revision(self):
        schema = JobCreateSchema()
        data = {'taskDefinition': 'foo:3', 'schedule': '*'}

        job, errors = schema.load(data)

        self.assertEqual({'taskDefinition'}, errors.keys())

    def test_deserialize_fails_if_id_includes_malformed_revision(self):
        schema = JobCreateSchema()
        data = {'taskDefinition': 'foo:', 'schedule': '*'}

        job, errors = schema.load(data)

        self.assertEqual({'taskDefinition'}, errors.keys())

    def test_deserialize_fails_if_zero_task_count(self):
        schema = JobCreateSchema()
        data = {'taskDefinition': 'foo', 'schedule': '*', 'taskCount': 0}

        job, errors = schema.load(data)

        self.assertEqual({'taskCount'}, errors.keys())

    def test_deserialize_fails_if_negative_task_count(self):
        schema = JobCreateSchema()
        data = {'taskDefinition': 'foo', 'schedule': '*', 'taskCount': -1}

        job, errors = schema.load(data)

        self.assertEqual({'taskCount'}, errors.keys())

    def test_deserialize_fails_if_above_max_task_count(self):
        schema = JobCreateSchema()
        data = {'taskDefinition': 'foo', 'schedule': '*', 'taskCount': 51}

        job, errors = schema.load(data)

        self.assertEqual({'taskCount'}, errors.keys())

    def test_deserialize_succeeds_if_at_max_task_count(self):
        schema = JobCreateSchema()
        data = {'taskDefinition': 'foo', 'schedule': '*', 'taskCount': 50}

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertEqual(50, job['taskCount'])

    def test_deserialize_sets_id_if_given_explicitly(self):
        schema = JobCreateSchema()
        data = {'id': 'foo', 'schedule': '*', 'taskCount': 1}

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertEqual(data, job)

    def test_deserialize_sets_id_and_task_definition(self):
        schema = JobCreateSchema()
        data = {
            'id': 'foo',
            'taskDefinition': 'bar',
            'schedule': '*',
            'taskCount': 1,
        }

        job, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertEqual(data, job)

    def test_deserialize_fails_if_id_includes_invalid_characters(self):
        schema = JobCreateSchema()
        data = {'taskDefinition': 'foo/bar.baz', 'schedule': '*'}

        job, errors = schema.load(data)

        self.assertEqual({'taskDefinition'}, errors.keys())


class JobResponseSchemaTests(unittest.TestCase):
    def test_serialize(self):
        def link_gen(job_id):
            return {
                'rel': 'foo',
                'href': 'link/' + job_id,
                'title': 'test-title',
            }

        schema = JobResponseSchema(link_gen)
        job_data = {
            'id': 'testid',
            'taskDefinition': 'test-task',
            'schedule': '*',
            'parsedSchedule': {'second': '*'},
            'scheduleStart': datetime(
                2015, 10, 7, 13, 44, 53, 123456, timezone.utc
            ),
            'scheduleEnd': datetime(
                2015, 10, 10, 4, 10, 3, 654321, timezone.utc
            ),
            'lastRun': datetime(
                2015, 10, 8, 4, 2, 56, 777777, timezone.utc
            ),
            'lastRunTasks': [
                {'taskId': 'foo1', 'hostId': 'bar1'},
                {'taskId': 'foo2', 'hostId': 'bar2'},
            ],
            'estimatedNextRun': datetime(
                2015, 10, 12, 6, 12, 44, 980027, timezone.utc
            ),
            'taskCount': 5,
            'suspended': True,
            'trigger': {
                'type': 'test-type',
            },
            'overrides': [{
                'containerName': 'test-container',
                'environment': {
                    'foo': 'foo_value',
                    'bar': 'bar_value',
                    'baz': 'baz_value',
                },
            }],
        }

        data, errors = schema.dump(job_data)

        self.assertEqual(0, len(errors))
        expected_data = job_data.copy()
        del expected_data['parsedSchedule']
        expected_data['scheduleStart'] = '2015-10-07T13:44:53.123456+00:00'
        expected_data['scheduleEnd'] = '2015-10-10T04:10:03.654321+00:00'
        expected_data['lastRun'] = '2015-10-08T04:02:56.777777+00:00'
        expected_data['estimatedNextRun'] = '2015-10-12T06:12:44.980027+00:00'
        expected_data['link'] = {
            'rel': 'foo',
            'href': 'link/testid',
            'title': 'test-title',
        }
        self.assertEqual(expected_data, data)

    def test_serialize_supports_timezone_offsets(self):
        def link_gen(job_id):
            return {
                'rel': 'foo',
                'href': 'link/' + job_id,
                'title': 'test-title',
            }

        schema = JobResponseSchema(link_gen)
        job_data = {
            'id': 'testid',
            'lastRun': datetime(
                2015, 10, 8, 4, 2, 56, 777777, timezone(timedelta(hours=12))
            ),
            'estimatedNextRun': datetime(
                2015, 10, 12, 6, 12, 44, 980027, timezone(timedelta(hours=-4))
            ),
        }

        data, errors = schema.dump(job_data)

        self.assertEqual(0, len(errors))
        expected_data = {
            'id': 'testid',
            'lastRun': '2015-10-08T04:02:56.777777+12:00',
            'estimatedNextRun': '2015-10-12T06:12:44.980027-04:00',
            'link': {
                'rel': 'foo',
                'href': 'link/testid',
                'title': 'test-title',
            },
        }
        self.assertEqual(expected_data, data)


class PaginationSchemaTests(unittest.TestCase):
    def test_deserialize_emptydata(self):
        schema = PaginationSchema()
        data = {}

        page, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertIsInstance(page, Pagination)
        self.assertEqual(0, page.skip)
        self.assertEqual(10, page.count)

    def test_deserialize_validdata(self):
        schema = PaginationSchema()
        data = {'skip': 22, 'count': 46}

        page, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertIsInstance(page, Pagination)
        self.assertEqual(data['skip'], page.skip)
        self.assertEqual(data['count'], page.count)

    def test_deserialize_negative_values(self):
        schema = PaginationSchema()
        data = {'skip': -4, 'count': -90}

        page, errors = schema.load(data)

        self.assertEqual(0, len(errors))
        self.assertIsInstance(page, Pagination)
        self.assertEqual(0, page.skip)
        self.assertEqual(0, page.count)

    def test_deserialize_invaliddata_raiseserror(self):
        schema = PaginationSchema()
        data = {'skip': 'foo', 'count': 'bar'}

        page, errors = schema.load(data)

        self.assertEqual({'count', 'skip'}, errors.keys())

    def test_serialize(self):
        schema = PaginationSchema()
        page = Pagination(78, 34, 100)

        data, errors = schema.dump(page)

        self.assertEqual(0, len(errors))
        expected_data = {'skip': 78, 'count': 34}
        self.assertEqual(expected_data, data)

    def test_serialize_omits_defaults(self):
        schema = PaginationSchema()
        page = Pagination(0, 10, 100)

        data, errors = schema.dump(page)

        self.assertEqual(0, len(errors))
        self.assertEqual({}, data)

    def test_serialize_returns_empty_if_default_total(self):
        schema = PaginationSchema()
        page = Pagination(0, 10)

        data, errors = schema.dump(page)

        self.assertEqual(0, len(errors))
        self.assertEqual({}, data)

    def test_serialize_returns_empty_if_skip_and_count_is_less_than_zero(self):
        schema = PaginationSchema()
        page = Pagination(-5, 3)

        data, errors = schema.dump(page)

        self.assertEqual(0, len(errors))
        self.assertEqual({}, data)

    def test_serialize_returns_empty_if_skip_and_count_is_equal_to_zero(self):
        schema = PaginationSchema()
        page = Pagination(-5, 5)

        data, errors = schema.dump(page)

        self.assertEqual(0, len(errors))
        self.assertEqual({}, data)

    def test_serialize_returns_empty_if_skip_is_greater_than_total(self):
        schema = PaginationSchema()
        page = Pagination(120, 10, 100)

        data, errors = schema.dump(page)

        self.assertEqual(0, len(errors))
        self.assertEqual({}, data)

    def test_serialize_returns_empty_if_skip_is_equal_to_total(self):
        schema = PaginationSchema()
        page = Pagination(100, 10, 100)

        data, errors = schema.dump(page)

        self.assertEqual(0, len(errors))
        self.assertEqual({}, data)

    def test_serialize_caps_skip(self):
        schema = PaginationSchema()
        page = Pagination(-5, 8, 100)

        data, errors = schema.dump(page)

        self.assertEqual(0, len(errors))
        self.assertEqual({'count': 8}, data)


def _parse_datetime_fields(data, *fields):
    for field in fields:
        data[field] = dateutil.parser.parse(data[field])
