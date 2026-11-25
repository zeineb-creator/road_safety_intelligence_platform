import argparse
import json
import os
import time

import psycopg
from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()

ap = argparse.ArgumentParser()
ap.add_argument("--speed", type=float, default=0,
                help="simulated seconds per real second (86400 = one day per second); 0 = no delay")
ap.add_argument("--deps", default="75,92,93,94")
ap.add_argument("--from-year", type=int, default=2019)
ap.add_argument("--to-year", type=int, default=2025)
ap.add_argument("--limit", type=int, default=0, help="stop after N events (0 = all)")
args = ap.parse_args()

SQL = """
SELECT accident_id, occurred_at, dep, com, adr, lat, lon, lum, atm, col, agg,
       intersection, n_vehicles, n_users, n_killed, n_hospitalized, n_slight, n_unhurt
FROM crashes
WHERE exclusion_reason IS NULL AND dep = ANY(%s) AND year BETWEEN %s AND %s
ORDER BY occurred_at, accident_id
"""

conn = psycopg.connect(
    host="localhost", port=int(os.environ.get("POSTGRES_PORT", "5432")),
    dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)
with conn.cursor() as cur:
    cur.execute(SQL, (args.deps.split(","), args.from_year, args.to_year))
    cols = [d.name for d in cur.description]
    rows = cur.fetchall()
if args.limit:
    rows = rows[: args.limit]

producer = Producer({"bootstrap.servers": "localhost:9092"})
errors = 0


def on_delivery(err, msg):
    global errors
    if err is not None:
        errors += 1
        print("delivery failed:", err)


print(f"replaying {len(rows)} events, speed={args.speed}")
first_sim = rows[0][1]
start = time.monotonic()
for i, row in enumerate(rows, 1):
    event = dict(zip(cols, row))
    event["schema_version"] = 1
    event["occurred_at"] = event["occurred_at"].isoformat()
    event["accident_id"] = int(event["accident_id"])
    if args.speed > 0:
        due = (row[1] - first_sim).total_seconds() / args.speed
        wait = due - (time.monotonic() - start)
        if wait > 0:
            time.sleep(wait)
    producer.produce("crashes.raw", key=str(event["accident_id"]),
                     value=json.dumps(event), on_delivery=on_delivery)
    producer.poll(0)
    if i % 5000 == 0:
        print(f"{i} events sent")

producer.flush()
print(f"done: {len(rows)} events, {errors} delivery errors")