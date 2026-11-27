import os

import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()
conn = psycopg.connect(
    host="localhost", port=int(os.environ.get("POSTGRES_PORT", "5432")),
    dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)
SQL = """
SELECT s.segment_id, coalesce(s.name, '(no name)') AS name, s.highway,
       s.length_m, count(*) AS crashes, sum(e.n_killed) AS killed
FROM crash_events e JOIN road_segments s USING (segment_id)
WHERE e.occurred_at < '2025-01-01'
GROUP BY s.segment_id, s.name, s.highway, s.length_m
"""
with conn.cursor() as cur:
    cur.execute(SQL)
    df = pd.DataFrame(cur.fetchall(),
                      columns=["segment_id", "name", "highway", "length_m", "crashes", "killed"])
conn.close()
df["length_m"] = df["length_m"].astype(float).round(0)
df["per_km"] = (df["crashes"] / (df["length_m"].clip(lower=100) / 1000)).round(0)

print("=== top 15 by crash count (2019-2024) ===")
print(df.sort_values(["crashes", "segment_id"], ascending=[False, True]).head(15).to_string(index=False))
print("\n=== top 15 by crashes per km, 100 m floor (2019-2024) ===")
print(df.sort_values(["per_km", "segment_id"], ascending=[False, True]).head(15).to_string(index=False))