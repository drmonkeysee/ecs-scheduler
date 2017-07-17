"""Built-in job data store implementations."""


def resolve():
    """
    Resolve a data store from the current execution environment.

    :returns: A data store implementation
    """
    pass


class NullStore:
    """
    Null data store.

    This store loads nothing and saves nothing.
    Effectively makes the JobStore an in-memory store.
    """
    def load_all(self):
        yield from {}.items()

    def create(self, job_id, **job):
        pass

    def update(self, job_id, **job):
        pass

    def delete(self, job_id):
        pass


class FileStore:
    """File system data store."""
    def __init__(self, file_path):
        """
        Create a file-based data store.

        :param file_path: The full path of the file to use for loading and storing jobs
        """
        self.file_path = file_path

    def load_all(self):
        pass

    def create(self, job_id, **job):
        pass

    def update(self, job_id, **job):
        pass

    def delete(self, job_id):
        pass


class S3Store:
    """AWS S3 data store."""
    pass


class ElasticsearchStore:
    """Elasticsearch data store."""
    pass
