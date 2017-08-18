# Component Overview

ECS Scheduler is organized as two components:

- **webapi**: a REST web application providing the scheduler UI; used to create, modify, and remove scheduled jobs
- **scheduld**: the scheduler daemon that runs scheduled jobs and talks to ECS to start tasks

The components are packaged together into a single [Flask](http://flask.pocoo.org) application.

## Webapi

The webapi component is used to interact with ECS scheduler. It provides a REST interface for getting, creating, updating, and removing jobs from the scheduler.

The home url `/` returns the list of available endpoints.

webapi runs as a self-hosted Flask server. The usage pattern of webapi makes it unlikely you will need a more sophisticated application server container but if necessary [uWSGI](https://uwsgi-docs.readthedocs.org/en/latest/) can provide multi-process/multi-threading request dispatching and more robust web server hosting.

webapi provides a swagger spec at `/spec`. This spec can be read by [Swagger UI](https://github.com/swagger-api/swagger-ui). You can either build [Swagger UI](https://github.com/swagger-api/swagger-ui) yourself or point the official [Swagger test site](http://petstore.swagger.io/) at it. For full documentation of the webapi interface consult the swagger spec.

If you find yourself needing to modify the swagger spec and it appears to be erroring out in [Swagger UI](https://github.com/swagger-api/swagger-ui) I recommend using the node package [swagger-tools](https://www.npmjs.com/package/swagger-tools) to find issues with the spec format.

The purpose of webapi is to provide a REST api to the ECS scheduler for creating, reading, updating, and deleting scheduled jobs. Jobs are exposed as a single resource with the following operations:

```
/jobs
GET - list the current jobs with pagination
POST - create a new job

/jobs/{job-id}
GET - return the current job
PUT - update the current job
DELETE - delete the current job
```

### Scheduled Jobs

The unit of ECS scheduler that controls tasks is the scheduled job. See the Swagger spec for full documentation on scheduled jobs but a job field summary is listed below:

```
taskDefinition - required field; name of the ECS task to control via this job
schedule - required field; CRON-style schedule describing when this job fires (all times in UTC)
id - id of the job; set to taskDefinition if not specified explicitly
scheduleStart - start date for when the job should begin its schedule; if not set schedule begins immediately
scheduleEnd - end date for when the job should end its schedule; if not set schedule never ends
taskCount - the minimum number of tasks to start when the job fires
maxCount - the maximum number of tasks to start when the job fires; ECS Scheduler also has a hard-coded limit of 50 tasks per job
trigger - additional conditions for whether the job should start any tasks when its schedule fires
suspended - whether the job is currently suspended or not
overrides - docker container overrides for the ECS task (currently only supports environment variable overrides)
```

There are also a few fields managed by scheduld automatically but are not set by the end-user when creating or updating a job:

```
lastRun - the last date/time the job fired
lastRunTasks - the list of ECS tasks launched the last time the job fired
estimatedNextRun - an estimate of the next time the job will fire
```

### Schedule Format

The primary field of a scheduler job is its schedule. The schedule follows a cron-like syntax but it's not exactly cron due to differences between actual cron and the underlying implementation of the ECS scheduler implementation.

The structure of a schedule is an 8-tuple delimited by spaces:

`second minute hour day_of_week week day month year`

Any fields to the right can be omitted, any fields to the left are required. For example setting a job to run every 15 minutes on the minute would be `0 */15` but running every September would require specifying a point in time for all the fields to the left such as `0 0 0 * * 1 9` which specifies midnight on the first of September.

The syntax follows the expected argument formats defined by the [Python APScheduler package](https://apscheduler.readthedocs.org/en/latest/modules/triggers/cron.html#module-apscheduler.triggers.cron). All times are in UTC.

#### APScheduler Expressions with Spaces

The elements of the schedule syntax are delimited by spaces, which APScheduler also uses for certain day expressions. Therefore an expression like `xth y` is expressed in webapi requests using underscores like `xth_y`.

#### Wildcard Expressions

The second, minute, and hour elements of the schedule expression support a special wildcard character, `?`, which will tell webapi to choose a random integer in the expected range of that field before storing it in the job definition and sending it to the scheduler. For example if a job should be run once an hour but the specific minute and second don't matter then `? ? 4` will run the job every day in the 4 AM hour with the minute and second chosen by webapi.

## Scheduld

As mentioned previously Scheduld uses the APScheduler package to do all the real work of managing job schedules. Since webapi is the primary interface to ECS Scheduler there is not much to say about scheduld; APScheduler docs and the ECS API documentation cover most of what it does.
