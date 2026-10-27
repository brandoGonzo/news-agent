import time, pendulum
from airflow.sdk import dag, task
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
START = pendulum.datetime(2026,1,1,tz="UTC")

def step(n):
    import json, hashlib
    data=[hashlib.sha256(str(i).encode()).hexdigest() for i in range(20000)]
    time.sleep(15); return n

@dag(schedule=None, start_date=START, catchup=False, max_active_runs=1)
def pipeline():
    prev=None
    for name in ["ingest","process","score","summarize","digest","finalize"]:
        t=task(task_id=name, retries=2)(step)(name)
        if prev: prev>>t
        prev=t
pipeline()

@dag(schedule="* * * * *", start_date=START, catchup=False, max_active_runs=1)
def tick():
    @task.short_circuit
    def due():
        import os; return os.path.exists("/tmp/af_due")
    due() >> TriggerDagRunOperator(task_id="trigger", trigger_dag_id="pipeline")
tick()
