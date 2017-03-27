# ECS Scheduler

A scheduler for executing ECS docker tasks, controlled via a JSON REST API; adapted from an internal [Openmail](https://github.com/Openmail) project.

[AWS ECS](http://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html) makes it possible to manage and run docker containers on EC2 instances. Refer to the full AWS documentation to get more details on how ECS works but in short it provides two methods of container execution via tasks (a task is one or more docker containers): services and manually-run tasks. A service is a persistent task; it is intended for containers that run in perpetuity and if a task terminates the ECS service will spin up a new one. Manually-run tasks are tasks started via the ECS dashboard or AWS API; it will run until the docker container exists, at which point the task is terminated.

There is a third execution model in between one-off and persistent tasks: tasks that execute on a scheduled interval or when a certain environmental condition is met. This is where ECS scheduler fits in. Docker containers allow you to build a series of loosely-coupled components that can be run when they need to do work then exit without taking up any idle resources. ECS Scheduler allows you to manage the execution schedules of such ephemeral containers. Think of using ECS and docker in this way as a high-octane version of AWS Lambda!

ECS Scheduler is organized as two components:

- **webapi**: a REST web application providing the scheduler UI. this is used to create, modify, and remove scheduled jobs
- **scheduld**: the scheduler daemon that runs scheduled jobs and talks to ECS to start tasks

## Getting Started (PROVISIONAL)

This particular version of ECS Scheduler is a nearly direct rip from the internal Openmail project and as such is designed to be run as a standalone application directly from the git repository (or rather, from the repository copied into a docker image). Later releases of this project will expose it as a pip-installable package with greater flexibility in hosting and running the scheduler components. In the meantime this can be run as an application script directly from the repo contents. A Dockerfile is also provided that sets the repository up to host in docker.

ECS Scheduler startup is controlled through a combination of configuration files and environment variables and depends on some minimal AWS infrastructure to operate.

Primary configuration is controlled via the contents of YAML files in the **config/** directory. It begins by loading the contents of **config_default.yaml** and then overlaying the contents of one of the environment-specific config files based on the `RUN_ENV` environment variable. For example if `RUN_ENV=test` then **config_test.yaml** and **config_default.yaml** will be combined.

ECS Scheduler is composed of two independent components: webapi and scheduld. They are run as seperate processes, which one is started is controlled via the `COMPONENT_NAME` environment variable (set to either `webapi` or `scheduld`). In the future these will be hostable in a single process and not required to run seperately. In the meantime they communicate to each other via an SQS queue, named under the appropriate key in one of the configuration files (see the files in **config/** for details).

See [this link](http://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/SQSDeadLetterQueue.html) for more info on creating dead letter queues.

[boto3](https://github.com/boto/boto3) is the package used to communicate to AWS. To set up credentials and default AWS configuration see the details in the [boto3 docs](https://boto3.readthedocs.io/en/latest/guide/configuration.html).

[elasticsearch](https://www.elastic.co/products/elasticsearch) is used as the backing store for persisting job information so an elasticsearch cluster is also required to run ECS scheduler. In a later release there will be a static file and a simple S3 storage option as well as hooks to implement your own persistence layer.

Finally the log level can be controlled via the `LOG_LEVEL` env variable, set to one of the values defined in the [`logging` Python module](https://docs.python.org/3/library/logging.html#logging-levels).

So for example to start the webapi component of ECS Scheduler for testing and logging at the info level would be:

```sh
> LOG_LEVEL=INFO RUN_ENV=test COMPONENT_NAME=webapi ./ecsscheduler
```

### SQS Setup

ECS Scheduler uses an SQS queue to communicate between the web api and the scheduler daemon. If the queue is not already set up then:

1. Create the dead letter sqs queue
2. Create the primary scheduler queue
3. Add the dead letter queue to the scheduler queue
4. Make sure the queue name is correct in the corresponding config file

### Application Configuration

ECS Scheduler looks for configuration files automatically in the **config/** directory. This repository comes with sample configuration files (both default and environment-specific) that contain sample values. Configuration controls the following aspects of the application:

- Flask debug mode
- elasticsearch cluster connectivity
- elasticsearch index name in which to store jobs
- SNS queue name used to communicate job updates between webapi and scheduld
- ECS cluster name in which to start tasks
- name used to tag tasks in ECS so they can be identified as being started by scheduld
- SQS polling frequency in seconds for scheduld

## Webapi

The webapi component is used to interact with ECS scheduler. It provides a REST interface to provide getting, creating, updating, and removing jobs from the scheduler.

The home url `/` returns the list of available endpoints.

webapi runs as a self-hosted Flask server. The usage pattern of webapi makes it unlikely you will need a more sophisticated application server container but if necessary [uWSGI](https://uwsgi-docs.readthedocs.org/en/latest/) can provide multi-process/multi-threading request dispatching and more robust web server hosting.

webapi provides a swagger spec at `/spec`. This spec can be read by [Swagger UI](https://github.com/swagger-api/swagger-ui). You can either build [Swagger UI](https://github.com/swagger-api/swagger-ui) yourself or point official [Swagger test site](http://petstore.swagger.io/) at it. For full documentation of the webapi interface consult the swagger spec.

If you find yourself needing to modify the swagger spec and it appears to be erroring out in [Swagger UI](https://github.com/swagger-api/swagger-ui) I recommend using the node package [swagger-tools](https://www.npmjs.com/package/swagger-tools) to find issues with the spec format.

The purpose of webapi is to provide a REST api to the ECS scheduler allowing the creation, reading, updating, and deletion of scheduled jobs. Jobs are exposed as a single resource with the following operations:

```/jobs
GET - list the current jobs with pagination
POST - create a new job

/jobs/{job-id}
GET - return the current job
PUT - update the current job
DELETE - delete the current job
```

### Schedule Format

The primary field of a scheduler job is its schedule. The schedule follows a cron-like syntax but it's not exactly cron due to differences between actual cron and the underlying implementation of the ECS scheduler implementation.

The structure of a schedule is an 8-tuple delimited by spaces:

`second minute hour day_of_week week day month year`

Any fields to the right can be omitted, any fields to the left are required. For example setting a job to run every 15 minutes on the minute would be `0 */15` but running every September would require specifying a point in time for all the fields to the left such as `0 0 0 * * 1 9` which specifies midnight on the first of September.

The syntax follows the expected argument formats defined by the [Python APScheduler package](https://apscheduler.readthedocs.org/en/latest/modules/triggers/cron.html#module-apscheduler.triggers.cron).

#### APScheduler Expressions with Spaces

The elements of the schedule syntax is delimited by spaces, which APScheduler also uses for certain day expressions. Thus an expression like `xth y` must be given to webapi using underscores like `xth_y`.

#### Wildcard Expressions

The second, minute, and hour elements of the schedule expression support a special wildcard character, `?`, which will tell webapi to choose a random integer in the expected range of that field before storing it in the job definition and sending it to the scheduler. For example if a job should be run once an hour but the specific minute and second don't matter then `? ? 4` will run the job every day in the 4 AM hour with the minute and second chosen by webapi.

## Scheduld

As mentioned previously Scheduld uses the APScheduler package to do all the real work of managing job schedules. Since webapi is the primary interface to ECS Scheduler there is not much to say about scheduld; APScheduler docs and the ECS API documentation covers most of what it does.

The only thing to note here is when scheduld launches a new task when a scheduled job fires it will automatically update the job with the last run time and the list of ECS tasks that were started when the job last fired.

## Usage

EXAMPLES
- basic example
- overriding environment (one task -> multiple jobs)
- triggers

## Local Setup

If you want to build or develop against ECS then use the following instructions.

### System Requirements

- [Python 3](https://www.python.org)
- [make](https://www.gnu.org/software/make/)

Technically you can get by without make by just reading the Makefile and performing the individual build targets manually.

### Build Package

If you want to build the package yourself but do not need a development environment run `make` or `make build` to create the package wheel. Run `make check` to run the unit tests. Currently building the package will not get you much since ECS Scheduler is designed to run as an application script but in the future this will be the primary way to get and run the application.

### Development Environment

Run `make test` and follow the displayed instructions. Once your development environment is set up `make test` will run the unit tests.
