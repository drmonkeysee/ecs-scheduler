"""Built-in job data source implementations."""
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
    def load_all(self):
        pass

    def create(self, job_id, **job):
        pass

    def update(self, job_id, **job):
        pass

    def delete(self, job_id):
        pass


class ElasticsearchSource:
    """Elasticsearch data source."""
    def load_all(self):
        pass

    def create(self, job_id, **job):
        pass

    def update(self, job_id, **job):
        pass

    def delete(self, job_id):
        pass
