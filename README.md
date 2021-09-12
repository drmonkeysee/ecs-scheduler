# ECS Scheduler

## NOTE (August 2021)

ECS Scheduler was created in 2015 for a specific need we had when running much of our infrastructure on Amazon ECS and is no longer under active development. Since then, Amazon has advanced the ECS product to the point where it natively handles most or all of what this service does. In addition Lambda, Serverless, and other AWS products provide more powerful alternatives for running medium-to-heavy tasks. I would advise you to review your options among AWS's product offerings before using this service.

## Summary

A scheduler for executing Amazon ECS docker tasks, controlled via a JSON REST API.

[Amazon ECS](http://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html) makes it possible to manage and run docker containers on EC2 instances. An ECS task, consisting of one or more docker containers, can be run indefinitely as a service or can be launched manually as a standalone task.

However there is a third execution model in between one-off and persistent tasks: tasks that execute on a scheduled interval or when a certain environmental condition is met. These container tasks may need to perform a few seconds or a few days of work, but they do not need to run indefinitely. Amazon ECS does not support this natively so ECS Scheduler was created to fill that gap. ECS Scheduler allows you to manage the execution schedules of such ephemeral containers turning ECS and docker into a high-octane version of AWS Lambda!

## Getting Started

ECS Scheduler is designed to be run as a standalone application rather than an installable Python package. Docker is the preferred means to host it using the provided Dockerfile. It is written in [Flask](https://flask.palletsprojects.com/) and uses the [APScheduler](https://apscheduler.readthedocs.io/en/latest/) package for job scheduling.

[boto3](https://github.com/boto/boto3) ([documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)) is the package used to communicate to AWS services. You will need AWS credentials to access, at a minimum, ECS. In addition boto3 clients require some basic configuration such as default AWS region. How to specify AWS credentials and configuration can be found in the [boto3 developer guide](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html#configuring-credentials). Specifically, all boto3 clients created in ecs-scheduler rely on passing credentials and configuration indirectly (i.e. all credential locations listed in the developer guide from point 3 on down). For local development it's easiest to use environment variables or home directory files; for production consult with your DevOps team, though the most robust approach is probably to rely on appropriate IAM roles.

### System Requirements

- [Python 3.7+](https://www.python.org)
- [make](https://www.gnu.org/software/make/)

### Development

Run `make check` to execute the unit tests.

Run `make` or `make debug` to launch ECS Scheduler in debug mode.

Either make target will set up a virtual environment automatically if it does not already exist.

### Docker and Deployment

If you want to run ECS Scheduler in docker use `make docker` to build the image. The docker image is the recommended way to deploy and run ECS Scheduler outside of a local development environment. The docker container hosts ECS Scheduler within [uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/) behind an [nginx](http://nginx.org) server, making it more robust than a standalone Flask application.

The following example runs an instance of the ECS Scheduler container using an on-image SQLite database as the persistent store and passes your AWS credentials to the container via an environment file named **docker-env**:

```sh
> docker run --name ecs-scheduler -p 8080:80 -e ECSS_ECS_CLUSTER=test-cluster -e ECSS_SQLITE_FILE=/var/opt/ecss/ecs-scheduler.db --env-file ~/.aws/docker-env -d ecs-scheduler
```

For reference **docker-env** would look something like:

```sh
AWS_DEFAULT_REGION=<my_region>
AWS_ACCESS_KEY_ID=<my_key>
AWS_SECRET_ACCESS_KEY=<my_secret>
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
