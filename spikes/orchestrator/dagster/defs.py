import time, os, hashlib
import dagster as dg
names=["ingest","process","score","summarize","digest","finalize"]
def mk(n):
    @dg.op(name=n, ins={"x": dg.In(dg.Nothing)} if n!="ingest" else None, retry_policy=dg.RetryPolicy(max_retries=2))
    def _op():
        [hashlib.sha256(str(i).encode()).hexdigest() for i in range(20000)]; time.sleep(15)
    return _op
ops=[mk(n) for n in names]
@dg.job
def pipeline():
    prev=None
    for o in ops:
        prev = o(x=prev) if prev is not None else o()
@dg.sensor(job=pipeline, minimum_interval_seconds=60)
def tick(context):
    if os.path.exists("/tmp/dg_due"):
        return dg.RunRequest(run_key=open("/tmp/dg_due").read().strip())
    return dg.SkipReason("nothing due")
defs=dg.Definitions(jobs=[pipeline], sensors=[tick])
