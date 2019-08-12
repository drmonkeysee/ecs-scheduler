# ECS Scheduler

A scheduler for executing Amazon ECS docker tasks, controlled via a JSON REST API.

[Amazon ECS](http://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html) makes it possible to manage and run docker containers on EC2 instances. An ECS task, consisting of one or more docker containers, can be run indefinitely as a service or can be launched manually as a standalone task.

However there is a third execution model in between one-off and persistent tasks: tasks that execute on a scheduled interval or when a certain environmental condition is met. These container tasks may need to perform a few seconds or a few days of work, but they do not need to run indefinitely. Amazon ECS does not support this natively so ECS Scheduler was created to fill that gap. ECS Scheduler allows you to manage the execution schedules of such ephemeral containers turning ECS and docker into a high-octane version of AWS Lambda!

## Getting Started

ECS Scheduler is designed to be run as a standalone application rather than an installable Python package. Docker is the preferred means to host it using the provided Dockerfile. It is written in [Flask](https://flask.palletsprojects.com/) and uses the [APScheduler](https://apscheduler.readthedocs.io/en/latest/) package for job scheduling.

[boto3](https://github.com/boto/boto3) is the package used to communicate to AWS services. You will need AWS credentials to access, at a minimum, ECS. To learn how to pass your AWS credentials to an application using boto3 consult the [boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html).

The environment variables in the following examples are described in more detail in a [later section](#environment-configuration).

### System Requirements

- [Python 3.6+](https://www.python.org)
- [make](https://www.gnu.org/software/make/)

### Development

Run `make check` and follow the displayed instructions. Once your development environment is set up `make check` will run the unit tests.

Run `make` or `make debug` to launch ECS Scheduler in debug mode.

### Docker and Deployment

If you want to run ECS Scheduler in docker use `make docker` to build the image. The docker image is the recommended way to deploy and run ECS Scheduler outside of a local development environment. The docker container hosts ECS Scheduler within [uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/) behind an [nginx](http://nginx.org) server, making it more robust than a standalone Flask application.

The following example runs an instance of the ECS Scheduler container using an on-image SQLite database as the persistent store and passes your AWS credentials to the container via an environment file named **docker-env**:

```sh
> docker run --name ecs-scheduler -p 8080:80 -e ECSS_ECS_CLUSTER=test-cluster -e ECSS_SQLITE_FILE=/var/opt/ecss/ecs-scheduler.db --env-file ~/.aws/docker-env -d ecs-scheduler
```

`make docker-clean` will delete all stopped ECS Scheduler containers and remove the image.

## [Environment Configuration](doc/ENVIRONMENT.md)

## [Component Overview](doc/COMPONENTS.md)

## [Usage](doc/USAGE.md)

## Credits

This application is adapted from an internal [Openmail](https://github.com/Openmail) project. Thanks to the following people for their contributions during its development:

- [Michael Green](https://github.com/mgreen)
- [Michael Schaffer](https://github.com/mtschaffer)

And very special thanks to Michael Schaffer for the original idea back in 2015.
