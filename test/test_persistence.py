import unittest

from ecs_scheduler.persistence import NullSource, FileSource


class NullSourceTests(unittest.TestCase):
    def setUp(self):
        self._target = NullSource()

    def test_load_all_returns_empty(self):
        result = self._target.load_all()

        self.assertEqual({}, result)

    def test_other_ops_do_nothing(self):
        try:
            self._target.create('id', a=1, b=2)
            self._target.update('id', a=1, b=2)
            self._target.delete('id')
        except Exception as ex:
            self.fail('Unexpected error raised: {}'.format(ex))


class FileSourceTests(unittest.TestCase):
    def setUp(self):
        self._target = FileSource()

    def test(self):
        self._target.get_all()
