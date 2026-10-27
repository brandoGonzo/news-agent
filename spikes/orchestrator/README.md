# Orchestrator spike: Airflow vs Dagster footprint and scheduling

Throwaway test code supporting [ADR-0006](../../docs/adr/0006-orchestrator-selection.md).
Not production code. The `spike` database user and password are test-only.

Run on 2026-10-27 in a Linux sandbox (2 vCPU, 8 GB RAM), Python 3.12, PostgreSQL 18
installed from the distribution packages.

## What was tested

The same 6-step sequential pipeline (ingest, process, score, summarize, digest, finalize),
each step doing a little CPU work and sleeping 15 seconds, started by a one-minute tick that
checks whether a run is due (a marker file stands in for the scheduling library).

| | Airflow 3.3.2 | Dagster 1.13.27 |
|---|---|---|
| Tick | `tick` DAG, `* * * * *`, short-circuit task then `TriggerDagRunOperator` | Sensor, `minimum_interval_seconds=60`, `RunRequest` with `run_key` |
| Pipeline | `pipeline` DAG, `schedule=None`, `max_active_runs=1`, retries 2 | Job with 6 ops, `RetryPolicy(max_retries=2)` |
| Executor | LocalExecutor, `parallelism=4` | QueuedRunCoordinator (`max_concurrent_runs: 1`), DefaultRunLauncher, default multiprocess executor |
| Processes | api-server, scheduler, dag-processor, triggerer (+ workers, log server) | code-server, webserver, daemon |
| Metadata DB | PostgreSQL 18, database `airflow` | PostgreSQL 18, database `dagster` |

Memory was sampled every 2 seconds for 330 seconds with `mem.py` (sum of PSS for the
tool's processes): about 150 seconds idle with the tick running, then one pipeline run.

## Results

| | Airflow | Dagster |
|---|---|---|
| Idle with tick running | ~790 MB | ~427 MB |
| Peak during a pipeline run | ~790 MB | ~609 MB |
| Pipeline run | Succeeded | Succeeded |
| Records left by the tick | 8 DAG runs in ~8 minutes (~1,440/day) | 21 tick records in ~20 minutes |
| PostgreSQL (either tool) | ~60 MB | ~60 MB |

Raw samples are in `results/`.

## Findings

- Airflow's published 4 to 8 GB Docker guidance is for the full Celery-based compose stack.
  With LocalExecutor the orchestrator used about 10% of the NFR-020 budget.
- Airflow pre-forks its LocalExecutor workers, so memory stays flat during a run. Fewer
  workers and no triggerer were not tested.
- Dagster's peak comes from one process per op in the default multiprocess executor.
- `airflow db clean --dag-ids tick --tables dag_run --skip-archive` removed 7 of 8 tick runs
  and their task instances, kept the latest tick run, and left the pipeline DAG untouched.
  Its output showed rows being moved to an `_airflow_deleted__dag_run__*` table even with
  `--skip-archive`; whether that table is dropped is still to be confirmed.
- `db clean` does not remove task log files on disk (9 tick log files after this test).
- Dagster setup issue: with psycopg 3 installed, SQLAlchemy 2.1 uses it as the default
  `postgresql://` driver, which dagster-postgres does not support (`NOTIFY` with a bound
  parameter failed). Forcing `postgresql+psycopg2://` fixed it.

## Reproducing

```bash
# PostgreSQL 18 running locally with user spike/spike and databases airflow, dagster
uv venv -p 3.12 af && VIRTUAL_ENV=af uv pip install "apache-airflow==3.3.2" psycopg2-binary psutil \
  --constraint https://raw.githubusercontent.com/apache/airflow/constraints-3.3.2/constraints-3.12.txt
cd spikes/orchestrator && . airflow/env.sh && airflow db migrate
# start: airflow api-server | scheduler | dag-processor | triggerer
python mem.py airflow 330 results/airflow-mem.json   # touch /tmp/af_due at ~150 s

uv venv -p 3.12 dg && VIRTUAL_ENV=dg uv pip install dagster dagster-webserver dagster-postgres psycopg2-binary psutil
export DAGSTER_HOME=$(pwd)/dagster
dagster code-server start -f dagster/defs.py -p 4000
dagster-webserver -w dagster/workspace.yaml -p 3000
dagster-daemon run -w dagster/workspace.yaml
dagster sensor start tick -w dagster/workspace.yaml
python mem.py dg/bin 330 results/dagster-mem.json    # echo run1 > /tmp/dg_due at ~150 s
```
