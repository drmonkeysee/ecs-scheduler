"""Built-in job data source implementations."""
class MemorySource:
    """
    In memory data source.

    NOTE: as the name implies this is a memory-only
    data source and will not be saved when the application terminates.
    """
    def get_all(self):
        pass

    def get(self, job_id):
        pass

    def create(self, job_id, **job):
        pass

    def update(self, job_id, **job):
        pass

    def delete(self, job_id):
        pass


class FileSource:
    """File system data source."""
    def get_all(self):
        pass

    def get(self, job_id):
        pass

    def create(self, job_id, **job):
        pass

    def update(self, job_id, **job):
        pass

    def delete(self, job_id):
        pass


class S3Source:
    """AWS S3 data source."""
    def get_all(self):
        pass

    def get(self, job_id):
        pass

    def create(self, job_id, **job):
        pass

    def update(self, job_id, **job):
        pass

    def delete(self, job_id):
        pass


class ElasticsearchSource:
    """Elasticsearch data source."""
    def get_all(self):
        pass

    def get(self, job_id):
        pass

    def create(self, job_id, **job):
        pass

    def update(self, job_id, **job):
        pass

    def delete(self, job_id):
        pass
