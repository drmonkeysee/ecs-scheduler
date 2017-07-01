"""Built-in job data source implementations."""
from abc import ABCMeta, abstractmethod


# TODO: use ABCMeta to allow alternate registrations and pick implementation automatically
class JobSource(metaclass=ABCMeta):
    """
    Abstract base class for Job Source implementations.

    Register a new job source implementation either by inheriting from JobStore
    or calling JobSource.register(MyJobSourceClass).
    """
    @abstractmethod
    def load_all(self):
        raise NotImplementedError()

    @abstractmethod
    def create(self, job_id, **job):
        raise NotImplementedError()

    @abstractmethod
    def update(self, job_id, **job):
        raise NotImplementedError()

    @abstractmethod
    def delete(self, job_id):
        raise NotImplementedError()


class NullSource(JobSource):
    """
    Null data source.

    This source loads nothing and saves nothing.
    Effectively makes the JobStore an in-memory store.
    """
    def load_all(self):
        return {}

    def create(self, job_id, **job):
        pass

    def update(self, job_id, **job):
        pass

    def delete(self, job_id):
        pass


class FileSource(JobSource):
    """File system data source."""
    pass


class S3Source(JobSource):
    """AWS S3 data source."""
    pass


class ElasticsearchSource(JobSource):
    """Elasticsearch data source."""
    pass
