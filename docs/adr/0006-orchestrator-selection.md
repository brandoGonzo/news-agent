# ADR-0006: Orchestrator selection

- **Status:** Accepted
- **Date:** 2026-10-27
- **Phase:** Logical Design (step 5, stack selection)
- **Requirements addressed:** FR-004, FR-006, FR-009, FR-014, FR-015, FR-036, FR-042, NFR-001, NFR-002, NFR-005, NFR-018, NFR-019, NFR-020, NFR-023, SEC-003, SEC-014
- **Supersedes:** none. Confirms the `airflow` database left conditional in [ADR-0005](0005-database-selection.md).

## Context

C3 Scheduler and the pipeline components (C4 to C9) need an orchestrator that can:

| Need | Requirements |
|---|---|
| Start runs from user settings stored in our database that change at runtime | FR-004, FR-006, D7 in [ADR-0004](0004-logical-architecture.md) |
| Allow one run at a time; queue a manual run that arrives during a scheduled one | FR-042 |
| Resume a failed run from the failed step without repeating paid calls | NFR-002 |
| Retry with backoff; isolate a failing source | FR-015 |
| Trigger delivery at a set time with a grace period | FR-036, NFR-001 |
| Record per-step duration | NFR-005 |
| Protect the admin UI with a login, bound to localhost | SEC-003 |
| Run locally from one command within 8 GB RAM, and on AWS | NFR-018, NFR-019, NFR-020 |

The FR-004 schedule (run window, update interval, skip rule within 30 minutes of the
final run, final run that ends the window, delivery time, timezone and DST safety, all
editable at runtime) is not a built-in schedule type in any orchestrator evaluated. The
scheduling rules are therefore our own code in every option; the choice is which tool
executes runs best and how our code starts them.

An Airflow custom timetable was ruled out: timetables are serialized with the DAG
([Airflow timetables](https://airflow.apache.org/docs/apache-airflow/stable/howto/timetable.html)),
and Airflow advises against database access in top-level DAG code
([Airflow best practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html)).

Airflow and Dagster were compared directly in a spike
([spikes/orchestrator](../../spikes/orchestrator/README.md)): same 6-step pipeline, one-minute
tick, PostgreSQL 18 metadata database.

| Measured | Airflow 3.3.2 (LocalExecutor) | Dagster 1.13.27 |
|---|---|---|
| Idle with tick running | ~790 MB | ~427 MB |
| Peak during a run | ~790 MB | ~609 MB |
| Tick records | ~1,440 DAG runs/day | Lightweight tick records, skipped ticks purged after 7 days by default |

Airflow's Docker guidance of at least 4 GB and ideally 8 GB
([Airflow in Docker](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/index.html))
applies to the Celery-based compose stack, not to LocalExecutor.

## Decision

1. **Airflow 3.3 with LocalExecutor**, using the `airflow` database on the PostgreSQL 18
   server from ADR-0005. Airflow 3.3 is tested with PostgreSQL 14 to 18
   ([prerequisites](https://airflow.apache.org/docs/apache-airflow/stable/installation/prerequisites.html)).
2. **Scheduling library.** The FR-004 rules live in a plain Python library with no Airflow
   imports. It answers "what is due now?" and produces the schedule preview. It is fully
   unit-tested, including DST transitions and the skip rule.
3. **Tick DAG.** A DAG on a one-minute schedule calls the library and triggers the pipeline
   DAG (update run or final run) or the delivery DAG. Each trigger carries a deterministic
   run ID (window and slot) so a slot is never started twice.
4. **Pipeline DAG.** No schedule of its own; `max_active_runs=1`, so a manual run waits in
   the queue (FR-042). A PostgreSQL advisory lock inside the pipeline enforces one run at a
   time independently of Airflow settings. Steps are idempotent and keep their state in
   PostgreSQL so clearing a failed task resumes the run (NFR-002).
5. **Delivery DAG.** Separate from the pipeline, triggered at the delivery time, with the
   FR-036 grace-period behavior.
6. **Maintenance DAG (NFR-023).** Runs daily after delivery. It:
   - runs `airflow db clean --dag-ids tick` for tick runs older than 2 days, with a dry run
     first;
   - deletes tick task log files older than 2 days;
   - applies NFR-023 retention to pipeline and delivery run history;
   - records what it deleted in the `ops` schema.
   A maintenance DAG is used instead of host cron so cleanup gets the same retries, run
   history, alerting (C12), and portability as the pipeline.
7. **Login (SEC-003).** The FAB auth manager. The default Simple auth manager is intended
   for development and testing
   ([Airflow Simple auth manager](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/auth-manager/simple/index.html)).
   The Airflow UI is bound to localhost; the Execution API used by task workers stays on the
   internal container network.
8. **Run launcher interface.** The application (for example "Run now" in C1/C2) starts runs
   through a launcher interface backed by the Airflow REST API. On AWS, a different trigger
   could start AWS Step Functions without changing the scheduling library (NFR-019).

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Dagster | Strong fit: sensors read external state, built-in run keys, lower memory. Not chosen because the open-source UI has no login, so SEC-003 would need a separately secured reverse proxy covering the web UI and its GraphQL API; telemetry is on by default and must be disabled (SEC-014); and the spike hit a driver issue (SQLAlchemy 2.1 defaulting to psycopg 3, unsupported by dagster-postgres). Airflow also serves the project's learning goal. |
| Prefect 3 | Updatable schedules and queued concurrency limits, but login is a single shared basic-auth string and resume from a failed step depends on result caching |
| Temporal | Best durable execution, but adds a server and its own databases (default compose includes Elasticsearch) and strict workflow determinism rules; a general workflow engine, not a data pipeline tool |
| App-native (APScheduler plus a PostgreSQL job table) | Lightest, but rebuilds retries, resume, run history UI, and per-step timing |
| AWS Step Functions | Cloud-only; fails NFR-018 local setup in v1. Kept as a possible AWS backend behind the run launcher interface |
| Airflow custom timetable | Timetable is serialized with the DAG; reading runtime settings from our database there is discouraged |
| App-owned scheduler process calling the Airflow REST API | Clean separation, but adds an always-on process we must operate; the tick DAG gives the same result inside Airflow |
| Host cron for cleanup | Outside the system's monitoring and retries; not portable to AWS |

## Consequences

- Airflow adds roughly 790 MB at idle with the tested settings, well within NFR-020.
- The tick creates about 1,440 short DAG runs a day; the maintenance DAG keeps only 2 days.
- Scheduling correctness depends on the library's tests, not on Airflow configuration.
- Run-start latency is up to about one minute after the scheduled time, which is
  acceptable for FR-004 and NFR-001.
- Follow-ups:
  - Housekeeping testing: confirm `db clean --skip-archive` leaves no `_airflow_deleted__*`
    tables.
  - Platform phase: measure with fewer LocalExecutor workers and without the triggerer.
  - Security Review: FAB auth manager setup, secret key handling, and network exposure of
    the API server and Execution API.
  - API framework ADR: define the run launcher interface used by "Run now".
