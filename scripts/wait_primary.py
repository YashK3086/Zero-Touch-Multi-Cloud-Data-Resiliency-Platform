"""Retry the primary health probe until a freshly created account becomes reachable."""
import time

import sf_dr_controller.config as c
import sf_dr_controller.connection as conn
import sf_dr_controller.health as h

s = c.Settings()
p = h.HealthProber(conn.SnowflakeSqlRunner(15))

for i in range(10):
    res = p.probe(s.primary)
    print(i, res.healthy, (res.error or "")[:90], flush=True)
    if res.healthy:
        break
    time.sleep(30)
