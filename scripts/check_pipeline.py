import os
import sys

import psycopg
from dotenv import load_dotenv

load_dotenv()
DEPS = ["75", "92", "93", "94"]
SNAP_MAX = 50  # must match the consumer's --snap-max-m

conn = psycopg.connect(
    host="localhost", port=int(os.environ.get("POSTGRES_PORT", "5432")),
    dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)
results = []


def one(sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
    results.append(ok)


src = one("""SELECT count(*), sum(n_killed), sum(n_hospitalized), sum(n_slight), sum(n_unhurt)
             FROM crashes WHERE exclusion_reason IS NULL AND dep = ANY(%s)""", (DEPS,))
evt = one("""SELECT count(*), sum(n_killed), sum(n_hospitalized), sum(n_slight), sum(n_unhurt)
             FROM crash_events""")
distinct = one("SELECT count(DISTINCT accident_id) FROM crash_events")[0]

check("row count equals source", evt[0] == src[0], f"events={evt[0]} source={src[0]}")
check("no duplicate accident ids", distinct == evt[0], f"distinct={distinct}")
check("severity totals equal source", evt[1:] == src[1:], f"events={evt[1:]} source={src[1:]}")

missing = one("""SELECT count(*) FROM crashes c
    WHERE c.exclusion_reason IS NULL AND c.dep = ANY(%s)
    AND NOT EXISTS (SELECT 1 FROM crash_events e WHERE e.accident_id = c.accident_id)""", (DEPS,))[0]
extra = one("""SELECT count(*) FROM crash_events e
    WHERE NOT EXISTS (SELECT 1 FROM crashes c WHERE c.accident_id = e.accident_id
    AND c.exclusion_reason IS NULL AND c.dep = ANY(%s))""", (DEPS,))[0]
check("no source accident missing", missing == 0, f"missing={missing}")
check("no unexpected extra accident", extra == 0, f"extra={extra}")

diff = one("""SELECT count(*) FROM crash_events e JOIN crashes c USING (accident_id)
    WHERE e.occurred_at <> c.occurred_at OR e.dep <> c.dep
       OR e.lat <> c.lat OR e.lon <> c.lon
       OR e.n_killed <> c.n_killed OR e.n_hospitalized <> c.n_hospitalized
       OR e.n_slight <> c.n_slight OR e.n_unhurt <> c.n_unhurt""")[0]
check("every row matches its source row", diff == 0, f"differing rows={diff}")

bad_status = one("""SELECT count(*) FROM crash_events
    WHERE snap_status IS NULL OR snap_status NOT IN ('snapped','far','no_road')""")[0]
bad_snapped = one("""SELECT count(*) FROM crash_events WHERE snap_status = 'snapped'
    AND (segment_id IS NULL OR snap_distance_m > %s)""", (SNAP_MAX,))[0]
bad_far = one("""SELECT count(*) FROM crash_events WHERE snap_status = 'far'
    AND (segment_id IS NOT NULL OR snap_distance_m <= %s)""", (SNAP_MAX,))[0]
check("snap status values valid", bad_status == 0, f"bad={bad_status}")
check("snapped rows within threshold", bad_snapped == 0, f"bad={bad_snapped}")
check("far rows have no road and exceed threshold", bad_far == 0, f"bad={bad_far}")

no_h3 = one("SELECT count(*) FROM crash_events WHERE h3_cell IS NULL")[0]
bad_weight = one("""SELECT count(*) FROM crash_events
    WHERE severity_weight <> 10*n_killed + 3*n_hospitalized + n_slight""")[0]
check("every row has an H3 cell", no_h3 == 0, f"missing={no_h3}")
check("severity weight matches the formula", bad_weight == 0, f"bad={bad_weight}")

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)