# Environment Configuration

ECS Scheduler configuration is controlled entirely through environment variables which affect behaviors like logging, persistent storage, and operational metadata. All ECS Scheduler environment variables can contain formatting parameters naming other environment variables which will be filled in at runtime. For example if your server's `HOSTNAME` env variable is `prod-server-1234` and you set `ECSS_LOG_FOLDER` to `/var/log/{HOSTNAME}/scheduler` then ECS Scheduler will log to **/var/log/prod-server-1234/scheduler**.

| Name | Required | Example | Description |
| ---- | -------- | ------- | ----------- |
| ECSS_ECS_CLUSTER | Yes | `prod-cluster` | Name of the ECS cluster in which to run tasks |
| ECSS_NAME | No | `my-scheduler` | Name to use in the `startedBy` field of an ECS task started by ECS Scheduler; uses a default name if not specified |
| ECSS_LOG_LEVEL | No | `INFO` | Level of application logging; expected values documented [here](https://docs.python.org/3/library/logging.html#logging-levels); uses Python default level if not specified |
| ECSS_LOG_FOLDER | No | `/var/log/ecs-scheduler` | Folder in which to write application logs; ECS Scheduler will also log to the standard streams whether this is set or not |

## Persistent Storage

ECS Scheduler supports several technologies for persisting scheduled jobs, chosen by setting environment variables. A word of warning: if you specify environment variables for more than one persistence technology at the same time it is implementation-defined which one will be chosen!

If none of these enviroment variables are defined then ECS Scheduler will default to an in-memory store that will not persist anything when the application terminates. This can be useful for quick-and-dirty testing and development but since it's unlikely to be the intended behavior outside of those scenarios ECS Scheduler will always log a warning if the in-memory store is created.

The supported persistence technologies are:

- **SQLite**: local database file; useful to avoid network failures or additional AWS service charges for storage but if used in docker will be destroyed along with the container unless the file is part of a mounted volume
- **S3**: store jobs as objects in an S3 bucket; supports optional key prefix if you do not want to dedicate a bucket to ECS Scheduler
- **DynamoDB**: store jobs as key-value items in a DynamoDB table
- **Elasticsearch**: store jobs in an Elasticsearch index

All the persistent stores will attempt to create the expected artifact (e.g. file, bucket, table, index) with reasonable defaults if not found on startup. If specific settings for the storage artifacts are desired then create them before starting ECS Scheduler.

| Name | Example | Description |
| ---- | ------- | ----------- |
| ECSS_SQLITE_FILE | `/var/opt/ecs-scheduler.db` | Use local SQLite database file using a simple id, JSON data schema |
| ECSS_S3_BUCKET | `my-company-ecs-scheduler` | Use S3 bucket to store jobs as individual serialized JSON S3 objects |
| ECSS_S3_PREFIX | `ecs-scheduler/test/jobs` | Optional S3 key prefix |
| ECSS_DYNAMODB_TABLE | `ecs-scheduler` | DynamoDB table to store jobs as key-value serialized JSON items |
| ECSS_ELASTICSEARCH_INDEX | `ecs-scheduler` | Elasticsearch index to store jobs as JSON documents |
| ECSS_ELASTICSEARCH_HOSTS | `http://my-node-1:9200/, http://my-node-2:9200/, http://my-node-3:9200/` | Comma-delimited Elasticsearch hosts on which the given Elasticsearch index is stored; required if ECSS_ELASTICSEARCH_INDEX is set |

Note that Elasticsearch is the odd-one out; it requires two distinct environment variables in order to function properly. In fact, Elasticsearch potentially requires much more complicated initialization than an index and the hosts. Therefore there is one more environment variable that can used to provide extended initialization parameters to ECS Scheduler. Elasticsearch is currently the only component that takes advantage of extended configuration but future additions to ECS Scheduler may use it as well.

### Extended Storage Configuration

A configuration file path can be given to ECS Scheduler which it can use to provide more complicated persistence initialization that would be awkward to express via simple environment variable strings. The configuration file must be a [YAML file](https://en.wikipedia.org/wiki/YAML) that specifies a top-level key specifying which persistence technology to use and then subkeys describing the initialization arguments for the persistent store.

As with environment variables if the configuration file specifies multiple persistence technologies it is implementation-defined which one will be picked!

| Name | Example | Description |
| ---- | ------- | ----------- |
| ECSS_CONFIG_FILE | `/etc/opt/ecs-scheduler.yaml` | YAML configuration file to provide extended persistence initialization |

#### Elasticsearch Config Example

```yaml
---
elasticsearch:
  index: prod-ecs-scheduler
  client:
    hosts:
      - prod-1.escluster.somedomain
      - prod-2.escluster.somedomain
    sniff_on_start: true
    sniff_on_connection_fail: true
    sniffer_timeout: 600
    sniff_timeout: 10
    timeout: 60
    retry_on_timeout: true
    max_retries: 10
```

`index` specifies the name of the index to use and `client` specifies all keyword arguments to be passed to the underlying [Elasticsearch client](http://elasticsearch-py.readthedocs.io/en/master/api.html#elasticsearch).
