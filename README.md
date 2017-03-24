# ECS Scheduler

A scheduler for executing ECS docker tasks, controlled via a JSON REST API. Adapted from an internal [Openmail](https://github.com/Openmail) project. It is composed of two components:

- **webapi**: a REST web application providing the scheduler UI. this is used to create, modify, and remove scheduled jobs
- **scheduld**: the scheduler daemon that actually runs scheduled jobs and talks to ECS to start tasks

DESCRIBE WHY HERE

## PROVISIONAL RELEASE

This particular version of ECS Scheduler is a nearly direct rip from the internal Openmail project and as such is designed to be run as a standalone application. Later release of this project will expose it as a pip-installable package with greater flexibility in hosting and running the scheduler components.

## Local Setup

### System Requirements

- [Python 3](https://www.python.org)
- [make](https://www.gnu.org/software/make/)

Technically you can get by without make by just reading the Makefile and performing the individual build targets manually.

### Build Package 

If you want to build the package yourself but do not need a development environment run `make` or `make build` to create the package wheel. Run `make check` to run the unit tests.

### Development Environment

Run `make test` and follow the displayed instructions. Once your development environment is set up `make test` will run the unit tests.

### AWS Setup (PROVISIONAL)

ECS Scheduler uses an SQS queue to communicate between the web api and the scheduler daemon. If the queue is not already set up then:

1. Create the dead letter sqs queue
2. Create the primary scheduler queue
3. Add the dead letter queue to the scheduler queue
4. Make sure the queue name is correct in the corresponding config file

See [this link](http://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/SQSDeadLetterQueue.html) for more info on creating dead letter queues.

## webapi

The webapi application is used to interact with ECS scheduler. It provides a REST interface to provide getting, creating, updating, and removing jobs from the scheduler.

The home url `/` returns the list of available endpoints.

webapi runs as a self-hosted Flask server. The usage pattern of webapi makes it unlikely you will need a more sophisticated application server container but if necessary [uWSGI](https://uwsgi-docs.readthedocs.org/en/latest/) can provide multi-process/multi-threading request dispatching and more robust web server hosting.

### Swagger

webapi provides a swagger spec at `/spec`. This spec can be read by [Swagger UI](https://github.com/swagger-api/swagger-ui). You can either build [Swagger UI](https://github.com/swagger-api/swagger-ui) yourself or point official [Swagger test site](http://petstore.swagger.io/) at it. For full documentation of the webapi interface consult the swagger spec. What follows is a brief overview.

The purpose of webapi is to provide a REST api to the ECS scheduler allowing the creation, reading, updating, and deletion of scheduled jobs. Jobs are exposed as a single resource with the following operations:

```/jobs
GET - list the current jobs with pagination
POST - create a new job

/jobs/{job-id}
GET - return the current job
PUT - update the current job
DELETE - delete the current job
```

Note that when creating or modifying a job nearly all top-level fields are optional. When updating a nested field (e.g. a trigger) all fields are required in the nested field. A minimal JSON request to create a job is:

```
curl http://webapi.domain/jobs -d '{
	"taskDefinition": "foobar",
	"schedule": "*"
}'
```

This will schedule an ECS task named foobar to run every second.

If you find yourself needing to modify the swagger spec and it appears to be erroring out in [Swagger UI](https://github.com/swagger-api/swagger-ui) I recommend using the node package [swagger-tools](https://www.npmjs.com/package/swagger-tools) to find issues with the spec format.

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
