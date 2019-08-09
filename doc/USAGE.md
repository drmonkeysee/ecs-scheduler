# Usage

Presented here is a step-by-step usage guide illustrating several features of ECS Scheduler.

Before creating jobs for ECS Scheduler you will need an existing Amazon ECS cluster and ECS task definitions for the docker containers you wish to run. Consult the Amazon ECS documentation for details.

## Basic Job Creation

Assume we have an existing ECS task named `sleeper-task` that sleeps for 3 seconds then prints that it is done and exits. We want it to run every 5 minutes and will use ECS Scheduler to make that happen. We add a scheduled job to scheduler like so:

```sh
> curl -i http://localhost:5000/jobs -d '{"taskDefinition": "sleeper-task", "schedule": "25 */5"}' -H 'Content-Type: application/json'
HTTP/1.0 201 CREATED
Content-Type: application/json
Content-Length: 142
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 01:19:27 GMT

{
    "id": "sleeper-task",
    "link": {
        "href": "/jobs/sleeper-task",
        "rel": "item",
        "title": "Job for sleeper-task"
    }
}
```

This is a minimal job creation request; `taskDefinition` and `schedule` are the only required fields. Notice the 201 response contains an href pointing at the newly created job. Following this url gives us the following:

```sh
> curl -i http://localhost:5000/jobs/sleeper-task
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 222
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 01:22:33 GMT

{
    "id": "sleeper-task",
    "link": {
        "href": "/jobs/sleeper-task",
        "rel": "item",
        "title": "Job for sleeper-task"
    },
    "schedule": "* */5",
    "taskCount": 1,
    "taskDefinition": "sleeper-task"
}
```

These are the entire details of the scheduled job. It has an id that matches the task definition name, a link describing how to access this resource, the number of tasks that will be launched when this job fires (currently set to 1), and a schedule that will fire on the 25th second of every 5th minute. Why 25? Well we had to pick something for the second field so we picked that. If we had used the wildcard `* */5` we would quickly find that our job executes _every_ second of every 5th minute which is clearly wrong. Is there a way to do this without picking an arbitrary second? Yes! Let's adjust our job's schedule without hard-coding an arbitrary second.

```sh
> curl -i http://localhost:5000/jobs/sleeper-task -XPUT -d '{"schedule": "? */5"}' -H 'Content-Type: application/json'
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 142
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 01:28:40 GMT

{
    "id": "sleeper-task",
    "link": {
        "href": "/jobs/sleeper-task",
        "rel": "item",
        "title": "Job for sleeper-task"
    }
}
```

Notice we use the `PUT` verb instead of `POST` and we only specify the "schedule" field since we're updating an existing job. In addition we're using the "random choice" wildcard character `?` because in this case we don't care which second of every 5th minute this job fires on, just that it fires on some second. Getting the job again we see:

```sh
> curl -i http://localhost:5000/jobs/sleeper-task
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 222
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 01:30:31 GMT

{
    "id": "sleeper-task",
    "link": {
        "href": "/jobs/sleeper-task",
        "rel": "item",
        "title": "Job for sleeper-task"
    },
    "schedule": "9 */5",
    "taskCount": 1,
    "taskDefinition": "sleeper-task"
}
```

In this particular case the server decided to run the job on the 9th second of every 5th minute. Note that this is a stable choice; the `?` resolves to a concrete value at the time the job is created or updated and that value is stored in the job's schedule. It will not change until a user chooses to modify the schedule again.

## Multiple Jobs per Task

Why does a job have both an `id` and a `taskDefinition`? We only specified `taskDefinition` when creating the job and the `id` got set automatically to the same value.

Every scheduled job must know which ECS task to start when it fires. `taskDefinition` is the name of that ECS task (defined in ECS itself) and is therefore a required field. In many cases there is only one scheduled job for a task so the `taskDefinition` is sufficient to uniquely identify a job. But sometimes you may want more than one job per task; for example a task may have multiple execution modes or require different schedules for different inputs.

Returning to our original example of `sleeper-task`, let's say it was designed to read the sleep duration from an environment variable and defaults to 3 seconds only if the variable is not set. Now what do we do if we want to schedule several tasks with different sleep duration inputs? Our original job will only launch sleeper tasks that use the default. That's where alternate jobs come into play.

We already have one job called `sleeper-task` and if we tried creating a new one we'll get an error:

```sh
> curl -i http://localhost:5000/jobs -d '{"taskDefinition": "sleeper-task", ... details omitted}' -H 'Content-Type: application/json'
HTTP/1.0 409 CONFLICT
Content-Type: application/json
Content-Length: 50
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 01:37:16 GMT

{
    "message": "Job sleeper-task already exists"
}
```

This would be a problem if job ids and task definition names were one-to-one but they're not. We can explicitly specify `id` and uniquely name a job that uses the same `taskDefinition` as other jobs. In addition since we want this to sleep for a different duration we'll also specify that as an environment override.

```sh
> curl -i http://localhost:5000/jobs -d '{"taskDefinition": "sleeper-task", "id": "long-sleep-task", "schedule": "? */7", "overrides": [{"containerName": "drmonkeysee-task", "environment": {"SLEEP_SECONDS": "10"}}]}' -H 'Content-Type: application/json'
HTTP/1.0 201 CREATED
Content-Type: application/json
Content-Length: 160
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 01:43:34 GMT

{
    "id": "long-sleep-task",
    "link": {
        "href": "/jobs/long-sleep-task",
        "rel": "item",
        "title": "Job for long-sleep-task"
    }
}
```

The `overrides` syntax can be a bit confusing; ECS tasks can contain multiple docker containers so the overrides must be specified per container.

```sh
> curl -i http://localhost:5000/jobs/long-sleep-task
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 417
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 01:46:20 GMT

{
    "id": "long-sleep-task",
    "link": {
        "href": "/jobs/long-sleep-task",
        "rel": "item",
        "title": "Job for long-sleep-task"
    },
    "overrides": [
        {
            "containerName": "sleeper-container",
            "environment": {
                "SLEEP_SECONDS": "10"
            }
        }
    ],
    "schedule": "22 */7",
    "taskCount": 1,
    "taskDefinition": "sleeper-task"
}
```

Now we have a second job that also launches the `sleeper-task` task but with the environment variable `SLEEP_SECONDS` set to 10. To get a sense of what our scheduler state is overall we can get the list of jobs:

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
            "id": "long-sleep-task",
            "link": {
                "href": "/jobs/long-sleep-task",
                "rel": "item",
                "title": "Job for long-sleep-task"
            },
            "overrides": [
                {
                    "containerName": "sleeper-container",
                    "environment": {
                        "SLEEP_SECONDS": "10"
                    }
                }
            ],
            "schedule": "22 */7",
            "taskCount": 1,
            "taskDefinition": "sleeper-task"
        },
        {
            "id": "sleeper-task",
            "link": {
                "href": "/jobs/sleeper-task",
                "rel": "item",
                "title": "Job for sleeper-task"
            },
            "schedule": "9 */5",
            "taskCount": 1,
            "taskDefinition": "sleeper-task"
        }
    ]
}
```

At this point if we were to fire up the scheduld daemon it would read the jobs store and begin running `sleeper-task` every 5 minutes and `long-sleep-task` every 7 minutes.

## Triggers

There is one final feature of scheduled jobs that merits an extended example. Often times an ephemeral docker container may not be performing work in isolation of other systems; perhaps a container needs to update several document records or transform and insert data events into a shared log. It may not be all that useful to execute the container on a fixed schedule but instead in response to a signal from another system. ECS Scheduler can handle jobs like this via triggers.

A trigger is an environmental check of some sort that the scheduld daemon can perform on behalf of the task and it will only launch the task if the check passes (i.e. if the trigger fires). A triggered job's schedule is the frequency with which the trigger is checked instead of how often the task is executed. ECS Scheduler currently comes with one built-in trigger: the [SQS](http://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/Welcome.html) trigger. In a future release it will be easier to add custom triggers but for now see **execution.py** for how triggers are defined and used.

Let's say we have another task that consumes messages from an SQS queue: `consumer-task`. Running the task every 5 minutes or every 20 minutes or once a day isn't very useful. Frequently it may be the case that our task would launch only to be faced with an empty queue. At other times the queue might be very active but the task isn't scheduled to start for another 6 hours, delaying our processing time. To avoid these issues we'll use an SQS trigger in the scheduled job.

```sh
> curl -i http://localhost:5000/jobs -d '{"taskDefinition": "consumer-task", "schedule": "? */3", "trigger": {"type": "sqs", "queueName": "consumer-task-queue", "messagesPerTask": 100}}' -H 'Content-Type: application/json'
HTTP/1.0 201 CREATED
Content-Type: application/json
Content-Length: 145
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 02:01:06 GMT

{
    "id": "consumer-task",
    "link": {
        "href": "/jobs/consumer-task",
        "rel": "item",
        "title": "Job for consumer-task"
    }
}
```

The important detail here is the `trigger` field. A trigger _must_ specify a `type` so scheduld knows what implementation to dispatch to, the rest of the fields are specific to the trigger implementation.

```sh
> curl -i http://localhost:5000/jobs/consumer-task
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 530
Access-Control-Allow-Origin: *
Server: Werkzeug/0.12.1 Python/3.6.0
Date: Mon, 03 Apr 2017 02:04:26 GMT

{
    "id": "consumer-task",
    "link": {
        "href": "/jobs/consumer-task",
        "rel": "item",
        "title": "Job for consumer-task"
    },
    "schedule": "43 */3",
    "taskCount": 1,
    "taskDefinition": "consumer-task",
    "trigger": {
        "messagesPerTask": 100,
        "queueName": "consumer-task-queue",
        "type": "sqs"
    }
}
```

The full job gives a clearer picture of the trigger. An SQS trigger requires the `queueName` so scheduld knows what queue to check and it also includes a scaling factor `messagesPerTask`. Normally the `taskCount` tells a job to start _at least_ that number of tasks. For SQS message processing you may need several tasks to clear the queue in a reasonable time so we can set `taskCount` to a higher value. But we run into the same issue as when we tried to guess a good schedule for processing the queue: a minimum of, say, 7 tasks may be sufficient when the queue is particularly busy but there may be many situations where that is over- or under-provisioned.

`messagesPerTask` instead scales the task count to the queue size. There's still some measure of guesswork involved, in our case we decided that a single task can process 100 messages in a reasonable amount of time, but it allows us to achieve a better ratio of tasks to queue size and the scale factor can always be tweaked if it turns out we got it wrong. In this case at 100 messages per task, scheduld will spin up 1 task if the queue size is 1 - 100 messages, 2 tasks if the queue size is 101 - 200 messages, 3 tasks for 201 - 300 messages, etc.

Note that if the queue size is 0 it will not spin up _any_ tasks. That's the power of the trigger, it only launches tasks if it needs to. The `schedule` field in our case is not how often the tasks will be launched but how often the queue will be checked. This is a cheap operation so checking once every 3 minutes seems fair. This gives us a maximum slack time of 3 minutes between when messages arrive in the queue and when tasks start launching and processing the queue.

Finally, it's possible the queue becomes extremely full. While you want to process all the messages in a reasonable time you also don't want to spin up hundreds or thousands of tasks and run up a massive AWS bill. The `maxCount` field will limit how many tasks a scheduled job will launch. This field can be used for any scheduled job, not just triggered jobs, but its most common use case is limiting the scaling factor for SQS-triggered jobs. We set it the same way as any other field:

```sh
> curl -i http://localhost:5000/jobs/consumer-task -XPUT -d '{"maxCount": 10}' -H 'Content-Type: application/json'
HTTP/1.0 200 OK
```

Here we limit the number of tasks processing our queue to 10.
