# ECS Scheduler

A scheduler for executing Amazon ECS docker tasks, controlled via a JSON REST API.

[Amazon ECS](http://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html) makes it possible to manage and run docker containers on EC2 instances. An ECS task, consisting of one or more docker containers, can be run indefinitely as a service or can be launched manually as a standalone task.

However there is a third execution model in between one-off and persistent tasks: tasks that execute on a scheduled interval or when a certain environmental condition is met. These container tasks may need to perform a few seconds or a few days of work, but they do not need to run indefinitely. Amazon ECS does not support this natively so ECS Scheduler was created to fill that gap. ECS Scheduler allows you to manage the execution schedules of such ephemeral containers turning ECS and docker into a high-octane version of AWS Lambda!

ECS Scheduler is organized as two components:

- **webapi**: a REST web application providing the scheduler UI; used to create, modify, and remove scheduled jobs
- **scheduld**: the scheduler daemon that runs scheduled jobs and talks to ECS to start tasks

The components are packaged together into a single [Flask](http://flask.pocoo.org) application.

## Getting Started

ECS Scheduler is designed to be run as a standalone application. Docker is the preferred means to host it using the provided Dockerfile, though it can be launched directly as an application script. Later releases of this project will expose it as a pip-installable package as well.

[boto3](https://github.com/boto/boto3) is the package used to communicate to AWS services. You will need AWS credentials to access, at a minimum, ECS. To learn how to pass your AWS credentials to an application using boto3 consult the [boto3 docs](https://boto3.readthedocs.io/en/latest/guide/configuration.html).

The environment variables in the following examples are described in more detail in a [later section](#environment-configuration).

### System Requirements

- [Python 3.6+](https://www.python.org)
- [make](https://www.gnu.org/software/make/)

### Development

Run `make test` and follow the displayed instructions. Once your development environment is set up `make test` will run the unit tests.

Run `make` or `make debug` to launch ECS Scheduler in debug mode.

### Docker

If you want to run ECS Scheduler in docker use `make docker` to build the image. The following example runs an instance of the ECS Scheduler container using an on-image SQLite database as the persistent store and passes your AWS credentials to the container via an environment file named **docker-env**:

```sh
> docker run --name ecs-scheduler -p 5000:5000 -e ECSS_ECS_CLUSTER=test-cluster -e ECSS_SQLITE_FILE=/var/opt/ecs-scheduler.db --env-file ~/.aws/docker-env -d ecs-scheduler
```

`make docker-clean` will delete all stopped ECS Scheduler containers and remove the image.

### Application Script

To run ECS Scheduler in release mode directly use the **ecsscheduler.py** script. The example below will run ECS Scheduler using a test database log at the info level. 

```sh
> ECSS_LOG_LEVEL=INFO ECSS_ECS_CLUSTER=test-cluster ECSS_SQLITE_FILE=data/test.db python ecsscheduler.py
```

### Build Package (Unfinished)

If you want to build the package yourself but do not need a development environment run `make build` to create the package wheel. Run `make check` to run the unit tests. Currently building the package will not get you much since ECS Scheduler is designed to run as an application script but in the future this will be the primary way to get and run the application.

[##](#environment-configuration) [Environment Configuration](doc/ENVIRONMENT.md)

## [Component Overview](doc/COMPONENTS.md)

## [Usage](doc/USAGE.md)

## Credits

This application is adapted from an internal [Openmail](https://github.com/Openmail) project. Thanks to the following people for their contributions during its development:

- [Michael Green](https://github.com/mgreen)
- [Michael Schaffer](https://github.com/mtschaffer)

And very special thanks to Michael Schaffer for the original idea back in 2015.
