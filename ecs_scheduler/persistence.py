"""Built-in job data source implementations."""


def resolve():
    """
    Resolve a data source from the current execution environment.

    :returns: A data source implementation
    """
    pass


class NullSource:
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


class FileSource:
    """File system data source."""
    def __init__(self, file_path):
        """
        Create a file-based data source.

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


class S3Source:
    """AWS S3 data source."""
    pass


class ElasticsearchSource:
    """Elasticsearch data source."""
    pass
