import psutil, sys, time, json
pat=sys.argv[1]; dur=int(sys.argv[2]); out=sys.argv[3]
samples=[]
end=time.time()+dur
while time.time()<end:
    tot=0; pg=0; n=0
    for p in psutil.process_iter(['cmdline','name']):
        try:
            cl=' '.join(p.info['cmdline'] or [])
            if 'postgres' in (p.info['name'] or ''): pg+=p.memory_full_info().pss
            elif pat in cl and 'mem.py' not in cl: tot+=p.memory_full_info().pss; n+=1
        except Exception: pass
    samples.append((time.time(),tot/2**20,pg/2**20,n)); time.sleep(2)
json.dump(samples,open(out,'w'))
o=[s[1] for s in samples]; print(f"{pat}: min {min(o):.0f} MB  max {max(o):.0f} MB  avg {sum(o)/len(o):.0f} MB  pg max {max(s[2] for s in samples):.0f} MB  procs max {max(s[3] for s in samples)}")
