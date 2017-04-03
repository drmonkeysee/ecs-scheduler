# ECS Scheduler

A scheduler for executing ECS docker tasks, controlled via a JSON REST API.

[AWS ECS](http://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html) makes it possible to manage and run docker containers on EC2 instances. Refer to the full AWS documentation to get more details on how ECS works but in short it provides two methods of container execution via tasks (a task is one or more docker containers): services and manually-run tasks. A service is a persistent task; it is intended for containers that run in perpetuity and if a task terminates the ECS service will spin up a new one. Manually-run tasks are tasks started via the ECS dashboard or AWS API; it will run until the docker container exits, at which point the task is terminated.

There is a third execution model in between one-off and persistent tasks: tasks that execute on a scheduled interval or when a certain environmental condition is met. These container tasks may need to perform a few seconds or a few days of work, but they do not need to run indefinitely. This is where ECS scheduler fits in. Docker containers allow you to build a series of loosely-coupled components that can a process as needed and then exit without taking up any idle resources. ECS Scheduler allows you to manage the execution schedules of such ephemeral containers. Think of using ECS and docker in this way as a high-octane version of AWS Lambda!

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

[elasticsearch](https://www.elastic.co/products/elasticsearch) is used as the backing store for persisting job information so an elasticsearch cluster is also required to run ECS scheduler. An index will be created automatically the first time a job is added; however you may want to use a more specific mapping, in which case consult the `JobSchema` and related classes in **serialization.py**. In a later release there will be a static file and a simple S3 storage option as well as hooks to implement your own persistence layer.

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

### Basic Job Creation

Here is a simple example of creating and manipulating a job. Imagine an ECS task named `test-task` that executes a docker container that prints how long it will sleep, sleeps, and then prints that it is finished sleeping and exits.

We can add a scheduled job to scheduler like so:

```sh
> curl -i http://localhost:5000/jobs -d '{"taskDefinition": "test-task", "schedule": "* */5"}' -H 'Content-Type: application/json'
HTTP/1.0 201 CREATED
Content-Type: application/json
Content-Length: 142
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 01:19:27 GMT

{
    "id": "test-task",
    "link": {
        "href": "/jobs/test-task",
        "rel": "item",
        "title": "Job for test-task"
    }
}
```

This is a minimal job creation request; `taskDefinition` and `schedule` are the only required fields. Notice the 201 response contains an href pointing at the newly created job. Following this url gives us the following:

```sh
> curl -i http://localhost:5000/jobs/test-task
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 222
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 01:22:33 GMT

{
    "id": "test-task",
    "link": {
        "href": "/jobs/test-task",
        "rel": "item",
        "title": "Job for test-task"
    },
    "schedule": "* */5",
    "taskCount": 1,
    "taskDefinition": "test-task"
}
```

These are the entire details of the scheduled job. It has an id that matches the task definition name, a link describing how to access this resource, the number of tasks that will be launched when this job fires (currently set to 1), and a schedule that will fire every second of every 5 minutes. Uh... what? Whoops the wildcard `*` doesn't mean _any_ value, it means _every_ value. Clearly we only want to fire once every 5 minutes, not 60 times every 5th minute. Let's fix that:

```sh
> curl -i http://localhost:5000/jobs/test-task -XPUT -d '{"schedule": "? */5"}' -H 'Content-Type: application/json'
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 142
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 01:28:40 GMT

{
    "id": "test-task",
    "link": {
        "href": "/jobs/test-task",
        "rel": "item",
        "title": "Job for test-task"
    }
}
```

Notice we use the `PUT` verb instead of `POST` and we only specify the "schedule" field since we're updating an existing job. In addition we're using the "random choice" wildcard character `?` because in this case we don't care which second of every 5th minute this job fires on, just that it fires on some second. Getting the job again we see:

```sh
> curl -i http://localhost:5000/jobs/test-task
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 222
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 01:30:31 GMT

{
    "id": "test-task",
    "link": {
        "href": "/jobs/test-task",
        "rel": "item",
        "title": "Job for test-task"
    },
    "schedule": "9 */5",
    "taskCount": 1,
    "taskDefinition": "test-task"
}
```

Now the schedule makes a bit more sense. In this particular case the server decided to run the job on the 9th second of every 5th minute.

### Tasks with Multiple Jobs

Why does a job have both an `id` and a `taskDefinition`? We only specified the second one when creating the job and the `id` got set automatically to the same value. The reason both fields exist is to differentiate between ECS Scheduler jobs and AWS ECS tasks.

Every scheduled job must know which ECS task to start when it fires. `taskDefinition` is the name of that ECS task (defined in ECS itself). In many cases there is a one-to-one relationship between scheduled jobs and tasks so the job's `id` can be set to the same value. But sometimes you may want more than one job per task; for example a task may have multiple execution modes or require different schedules for different inputs.

Going back to our original example of `test-task` which sleeps for some amount of time, notice that we didn't tell the task how long to sleep. It must have a default value, but what if we could specify that value via environment variables? And we needed several of these tasks to run on different sleep durations? That's where alternate jobs can come into play.

We already have one job called `test-task` and if we tried creating a new one with the same `id` we'll get an error:

```sh
> curl -i http://localhost:5000/jobs -d '{"taskDefinition": "test-task", ... details omitted}' -H 'Content-Type: application/json'
HTTP/1.0 409 CONFLICT
Content-Type: application/json
Content-Length: 50
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 01:37:16 GMT

{
    "message": "Job test-task already exists"
}
```

This would be a problem if job ids and task definition names were one-to-one but they're not. In our case we just need to explicitly specify `id` when creating the job. Since we want this to sleep for a different duration we'll also specify that as an environment override.

```sh
> curl -i http://localhost:5000/jobs -d '{"taskDefinition": "test-task", "id": "long-sleep-test", "schedule": "? */7", "overrides": [{"containerName": "drmonkeysee-task", "environment": {"SLEEP_SECONDS": "10"}}]}' -H 'Content-Type: application/json'
HTTP/1.0 201 CREATED
Content-Type: application/json
Content-Length: 160
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 01:43:34 GMT

{
    "id": "long-sleep-test",
    "link": {
        "href": "/jobs/long-sleep-test",
        "rel": "item",
        "title": "Job for long-sleep-test"
    }
}
```

Here we specify the `id` explicitly and we set container-specific environment overrides to control how long our test task will sleep before exiting. The `overrides` syntax can be a bit confusing at first due to the fact that an ECS task can contain multiple containers, so overrides must be specified per container. Getting this job looks like:

```sh
> curl -i http://localhost:5000/jobs/long-sleep-test
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 417
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 01:46:20 GMT

{
    "id": "long-sleep-test",
    "link": {
        "href": "/jobs/long-sleep-test",
        "rel": "item",
        "title": "Job for long-sleep-test"
    },
    "overrides": [
        {
            "containerName": "drmonkeysee-task",
            "environment": {
                "SLEEP_SECONDS": "10"
            }
        }
    ],
    "schedule": "22 */7",
    "taskCount": 1,
    "taskDefinition": "test-task"
}
```

To get a sense of what our scheduler state is overall we can get the list of jobs:

```sh
> curl -i http://localhost:5000/jobs
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 904
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 01:47:31 GMT

{
    "jobs": [
        {
            "id": "long-sleep-test",
            "link": {
                "href": "/jobs/long-sleep-test",
                "rel": "item",
                "title": "Job for long-sleep-test"
            },
            "overrides": [
                {
                    "containerName": "drmonkeysee-task",
                    "environment": {
                        "SLEEP_SECONDS": "10"
                    }
                }
            ],
            "schedule": "22 */7",
            "taskCount": 1,
            "taskDefinition": "test-task"
        },
        {
            "id": "test-task",
            "link": {
                "href": "/jobs/test-task",
                "rel": "item",
                "title": "Job for test-task"
            },
            "schedule": "9 */5",
            "taskCount": 1,
            "taskDefinition": "test-task"
        }
    ]
}
```

At this point if we were to fire up the scheduld daemon it would read the jobs store and begin running `test-task` every 5 minutes and `long-sleep-test` every 7 minutes.

### Triggers

There is one final feature of scheduled jobs that merits an example. Often times an ephemeral docker container may not be performing work in isolation of other systems; perhaps a container needs to update several document records or transform and insert data events into a shared log. It may not be all that useful to execute the container on a fixed schedule but instead in response to a signal from another system. ECS Scheduler can handle jobs like this via triggers.

A trigger is an environmental check of some sort that the scheduld daemon can perform on behalf of the task and it will only launch the task if the check passes (i.e. if the trigger fires). The schedule, in the case of a triggered job, is the frequency with which the trigger is checked instead of how often the task itself is executed. Triggers can theoretically be anything though ECS Scheduler currently comes with one built-in trigger: the [SQS](http://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/Welcome.html) trigger. See **execution.py** for how triggers are defined.

Take our test task again. Normally it starts, sleeps, then exits. But let's say it can also run in a mode where it processes SQS messages (in our simple case if the env var `INPUT_QUEUE` is defined it will pull the message from the queue named by that var, print its contents, then remove it from the queue). Running the task every 5 minutes or every 20 minutes or once a day isn't very useful. There would be many times when our task would launch only to be faced with an empty queue. At other times the queue might be very active but the task isn't scheduled to start for another 6 hours, delaying our processing time. To avoid these issues we'll use an SQS trigger in the scheduled job.

```sh
> curl -i http://localhost:5000/jobs -d '{"taskDefinition": "test-task", "id": "queue-test", "schedule": "? */3", "overrides": [{"containerName": "drmonkeysee-task", "environment": {"INPUT_QUEUE": "test-task-queue"}}], "trigger": {"type": "sqs", "queueName": "test-task-queue", "messagesPerTask": 100}}' -H 'Content-Type: application/json'
HTTP/1.0 201 CREATED
Content-Type: application/json
Content-Length: 145
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 02:01:06 GMT

{
    "id": "queue-test",
    "link": {
        "href": "/jobs/queue-test",
        "rel": "item",
        "title": "Job for queue-test"
    }
}
```

The environment override allows us to tell our test-task to perform queue processing instead of sleeping (in practice you would likely have a different task definition and docker image as opposed to using env modes like this but this is just an example). The important point here is the `trigger` field. A trigger _must_ specify a `type`, other fields are specific to the type and will be consumed by the trigger implementaton in scheduld.

```sh
> curl -i http://localhost:5000/jobs/queue-test
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 530
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 02:04:26 GMT

{
    "id": "queue-test",
    "link": {
        "href": "/jobs/queue-test",
        "rel": "item",
        "title": "Job for queue-test"
    },
    "overrides": [
        {
            "containerName": "drmonkeysee-task",
            "environment": {
                "INPUT_QUEUE": "test-task-queue"
            }
        }
    ],
    "schedule": "43 */3",
    "taskCount": 1,
    "taskDefinition": "test-task",
    "trigger": {
        "messagesPerTask": 100,
        "queueName": "test-task-queue",
        "type": "sqs"
    }
}
```

The full job gives a clearer picture of the trigger. An SQS trigger requires the `queueName` so scheduld knows what queue to check and it also includes a scaling factor `messagesPerTask`. The `taskCount` tells the job to start _at least_ that many tasks; in most cases 1 is sufficient and is the default value. But for SQS message processing you may need several tasks to clear the queue in a reasonable time. We can set `taskCount` to a higher value but we run into the same issue as when we tried to guess a good schedule for processing the queue: a minimum of, say, 7 tasks may be sufficient when the queue is particularly busy but there may be many situations where that is overkill or insufficient.

`messagesPerTask` instead scales the task count to the queue size. There's still some measure of guesswork involved, in our case we decided that a single task can process 100 messages in a reasonable amount of time, but it allows us to achieve a better ratio of tasks to queue size and the scale factor can always be tweaked if it turns out we got it wrong. In this case at 100 messages per task, scheduld will spin up 1 task if the queue size is 1 - 100 messages, 2 tasks if the queue size is 101 - 200 messages, 3 tasks for 201 - 300 messages, etc.

Note that if the queue size is 0 it will not spin up _any_ tasks. That's the power of the trigger, it only launches tasks if it needs to. The `schedule` field in our case is not how often the tasks will be launched but how often the queue will be checked. This is a cheap operation so checking once every 3 minutes seems fair. This gives us a maximum slack time of 3 minutes between when messages arrive in the queue and our `queue-test` tasks start launching and processing the queue.

Finally, it's possible the queue becomes extremely full. While you want to process all the messages in a reasonable time you also don't want to spin up hundreds or thousands of tasks and run up a massive AWS bill. The `maxCount` field will limit how many tasks a scheduled job will launch. This field can be used for any scheduled job, not just triggered jobs, but its most common use case is limiting the scaling factor for SQS-triggered jobs. We set it the same way as any other field:

```sh
> curl -i http://localhost:5000/jobs/queue-test -XPUT -d '{"maxCount": 10}' -H 'Content-Type: application/json'
HTTP/1.0 200 OK
```

Here we limit the number of tasks processing our queue to 10.

For all the other scheduled jobs fields that can be set or read from webapi consult the Swagger documentation or **serialization.py**. 

## Local Setup

If you want to build or develop against ECS Scheduler then use the following instructions.

### System Requirements

- [Python 3](https://www.python.org)
- [make](https://www.gnu.org/software/make/)

Technically you can get by without make by just reading the Makefile and performing the individual build targets manually.

### Build Package

If you want to build the package yourself but do not need a development environment run `make` or `make build` to create the package wheel. Run `make check` to run the unit tests. Currently building the package will not get you much since ECS Scheduler is designed to run as an application script but in the future this will be the primary way to get and run the application.

### Development Environment

Run `make test` and follow the displayed instructions. Once your development environment is set up `make test` will run the unit tests.

## Credits

This application is adapted from an internal [Openmail](https://github.com/Openmail) project. Special thanks to the following people for their contributions during its development:

- [Michael Green](https://github.com/mgreen)
- [Michael Schaffer](https://github.com/mtschaffer)

And very special thanks to Michael Schaffer for the original idea back in 2015.
