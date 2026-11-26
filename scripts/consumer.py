import argparse
import json
import os
import time
from datetime import datetime

import h3
import psycopg
from confluent_kafka import Consumer, Producer
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

ap = argparse.ArgumentParser()
ap.add_argument("--snap-max-m", type=float, default=50)
ap.add_argument("--h3-res", type=int, default=9)
ap.add_argument("--batch", type=int, default=500)
ap.add_argument("--group", default="crash-enricher")
ap.add_argument("--exit-when-idle", type=float, default=0,
                help="stop after N seconds without messages (0 = run forever)")
ap.add_argument("--crash-after", type=int, default=0,
                help="TEST ONLY: hard-exit after this many events are saved in the database, before committing offsets")
args = ap.parse_args()

# Illustrative severity weights: a design choice to justify or compare in Week 3
W_KILLED, W_HOSPITALIZED, W_SLIGHT = 10, 3, 1


class CrashEvent(BaseModel):
    schema_version: int = Field(ge=1, le=1)
    accident_id: int = Field(gt=0)
    occurred_at: datetime
    dep: str
    lat: float = Field(ge=41, le=52)
    lon: float = Field(ge=-5.5, le=10)
    n_vehicles: int = Field(ge=0)
    n_users: int = Field(ge=0)
    n_killed: int = Field(ge=0)
    n_hospitalized: int = Field(ge=0)
    n_slight: int = Field(ge=0)
    n_unhurt: int = Field(ge=0)


DDL = """
CREATE TABLE IF NOT EXISTS crash_events (
    accident_id     bigint PRIMARY KEY,
    occurred_at     timestamp NOT NULL,
    dep             text,
    lat             double precision,
    lon             double precision,
    geom            geometry(Point, 4326),
    segment_id      integer,
    snap_distance_m real,
    snap_status     text,
    h3_cell         text,
    severity_weight real,
    n_killed        integer,
    n_hospitalized  integer,
    n_slight        integer,
    n_unhurt        integer,
    processed_at    timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS crash_events_geom_idx ON crash_events USING GIST (geom);
CREATE INDEX IF NOT EXISTS crash_events_h3_idx ON crash_events (h3_cell);
"""

# Take the 5 nearest segments by index, then pick the closest in real meters
SNAP_SQL = """
WITH p AS (SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326) AS g)
SELECT s.segment_id, ST_Distance(s.geom::geography, p.g::geography) AS dist
FROM p, LATERAL (
    SELECT segment_id, geom FROM road_segments ORDER BY geom <-> p.g LIMIT 5
) s
ORDER BY dist LIMIT 1
"""

UPSERT_SQL = """
INSERT INTO crash_events (accident_id, occurred_at, dep, lat, lon, geom, segment_id,
    snap_distance_m, snap_status, h3_cell, severity_weight,
    n_killed, n_hospitalized, n_slight, n_unhurt)
VALUES (%(accident_id)s, %(occurred_at)s, %(dep)s, %(lat)s, %(lon)s,
    ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326), %(segment_id)s,
    %(snap_distance_m)s, %(snap_status)s, %(h3_cell)s, %(severity_weight)s,
    %(n_killed)s, %(n_hospitalized)s, %(n_slight)s, %(n_unhurt)s)
ON CONFLICT (accident_id) DO UPDATE SET
    occurred_at = EXCLUDED.occurred_at, dep = EXCLUDED.dep,
    lat = EXCLUDED.lat, lon = EXCLUDED.lon, geom = EXCLUDED.geom,
    segment_id = EXCLUDED.segment_id, snap_distance_m = EXCLUDED.snap_distance_m,
    snap_status = EXCLUDED.snap_status, h3_cell = EXCLUDED.h3_cell,
    severity_weight = EXCLUDED.severity_weight, n_killed = EXCLUDED.n_killed,
    n_hospitalized = EXCLUDED.n_hospitalized, n_slight = EXCLUDED.n_slight,
    n_unhurt = EXCLUDED.n_unhurt, processed_at = now()
"""

conn = psycopg.connect(
    host="localhost", port=int(os.environ.get("POSTGRES_PORT", "5432")),
    dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)
with conn.cursor() as cur:
    cur.execute(DDL)
conn.commit()

consumer = Consumer({
    "bootstrap.servers": "localhost:9092",
    "group.id": args.group,
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,
    "session.timeout.ms": 10000,
})
consumer.subscribe(["crashes.raw"])
producer = Producer({"bootstrap.servers": "localhost:9092"})


def dead_letter(msg, error):
    payload = {"error": error, "topic": msg.topic(), "partition": msg.partition(),
               "offset": msg.offset(), "value": msg.value().decode("utf-8", "replace")}
    producer.produce("crashes.dead-letter", key=msg.key(), value=json.dumps(payload))


saved = rejected = 0
t_first = t_work = None
last_message = time.monotonic()
print(f"consumer started (group={args.group}, snap<={args.snap_max_m} m, h3 res {args.h3_res})")
try:
    while True:
        msgs = consumer.consume(num_messages=args.batch, timeout=1.0)
        if not msgs:
            if args.exit_when_idle and time.monotonic() - last_message > args.exit_when_idle:
                break
            continue
        last_message = time.monotonic()
        if t_first is None:
            t_first = last_message

        events = []
        for m in msgs:
            if m.error():
                print("kafka error:", m.error())
                continue
            try:
                events.append(CrashEvent.model_validate_json(m.value()))
            except ValidationError as e:
                dead_letter(m, str(e)[:500])
                rejected += 1

        with conn.cursor() as cur:
            for ev in events:
                cur.execute(SNAP_SQL, {"lat": ev.lat, "lon": ev.lon})
                hit = cur.fetchone()
                if hit is None:
                    seg, dist, status = None, None, "no_road"
                elif hit[1] <= args.snap_max_m:
                    seg, dist, status = hit[0], hit[1], "snapped"
                else:
                    seg, dist, status = None, hit[1], "far"
                cur.execute(UPSERT_SQL, {
                    "accident_id": ev.accident_id, "occurred_at": ev.occurred_at,
                    "dep": ev.dep, "lat": ev.lat, "lon": ev.lon,
                    "segment_id": seg, "snap_distance_m": dist, "snap_status": status,
                    "h3_cell": h3.latlng_to_cell(ev.lat, ev.lon, args.h3_res),
                    "severity_weight": (W_KILLED * ev.n_killed
                                        + W_HOSPITALIZED * ev.n_hospitalized
                                        + W_SLIGHT * ev.n_slight),
                    "n_killed": ev.n_killed, "n_hospitalized": ev.n_hospitalized,
                    "n_slight": ev.n_slight, "n_unhurt": ev.n_unhurt,
                })
        conn.commit()                      # 1. data is safe in the database
        producer.flush()
        if args.crash_after and saved + len(events) >= args.crash_after:
            print("simulated crash: data committed, offsets NOT committed")
            os._exit(1)                   # 2. dead-letter messages are delivered
        consumer.commit(asynchronous=False)  # 3. only now move the bookmark
        saved += len(events)
        t_work = time.monotonic()
        print(f"saved {saved} | rejected {rejected}")
except KeyboardInterrupt:
    print("stopping")
finally:
    consumer.close()
    conn.close()
    print(f"final: saved {saved}, rejected {rejected}")
    if t_first and t_work and saved:
        print(f"throughput: {saved / max(t_work - t_first, 0.001):.0f} events/s")