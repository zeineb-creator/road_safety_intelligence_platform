import os

import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()
MAX_DIST_M = 30  # my choice: about the 90th percentile of junction-crash distances
FRACTIONS = (0.01, 0.02, 0.05, 0.10)
TEST_YEARS = (2021, 2022, 2023, 2024, 2025)

conn = psycopg.connect(
    host="localhost", port=int(os.environ.get("POSTGRES_PORT", "5432")),
    dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)
with conn.cursor() as cur:
    cur.execute("SELECT node_id FROM road_junctions ORDER BY node_id")
    nodes = pd.Index([r[0] for r in cur.fetchall()])
    cur.execute("""
        SELECT e.accident_id, extract(year FROM e.occurred_at)::int, n.node_id, n.m
        FROM crash_events e
        JOIN crashes c USING (accident_id)
        CROSS JOIN LATERAL (
            SELECT p.node_id, ST_Distance(p.geom::geography, e.geom::geography) AS m
            FROM (SELECT node_id, geom FROM road_junctions ORDER BY geom <-> e.geom LIMIT 5) p
            ORDER BY m LIMIT 1
        ) n
        WHERE c.intersection BETWEEN 2 AND 9""")
    ev = pd.DataFrame(cur.fetchall(), columns=["accident_id", "year", "node_id", "m"])
conn.close()

ev["m"] = ev["m"].astype(float)
assigned = ev[ev["m"] <= MAX_DIST_M]
print(f"junction nodes: {len(nodes)} | junction crashes: {len(ev)} | "
      f"assigned within {MAX_DIST_M} m: {len(assigned)} ({len(assigned) / len(ev):.1%})")
print(f"junction nodes with at least one assigned crash (2019-2025): {assigned['node_id'].nunique()}")


def counts(y0, y1):
    d = assigned[(assigned["year"] >= y0) & (assigned["year"] <= y1)]
    return d.groupby("node_id").size().reindex(nodes, fill_value=0).astype(float)


def top_k(score, k):
    order = (pd.DataFrame({"s": score.values, "id": score.index})
             .sort_values(["s", "id"], ascending=[False, True]))
    return order["id"].values[:k]


rows = []
for ty in TEST_YEARS:
    train, test = counts(2019, ty - 1), counts(ty, ty)
    total = test.sum()
    unseen = test[train == 0].sum() / total
    print(f"test {ty}: {int(total)} junction crashes, {unseen:.1%} at junctions with no crash in the training years")
    for name, score in {"raw count": train, "ORACLE (test year)": test}.items():
        for frac in FRACTIONS:
            sel = top_k(score, int(round(frac * len(nodes))))
            rows.append({"test_year": ty, "method": name, "frac": frac,
                         "capture": test.loc[sel].sum() / total})

res = pd.DataFrame(rows)
for frac in FRACTIONS:
    wide = res[res["frac"] == frac].pivot(index="test_year", columns="method", values="capture") * 100
    print(f"\n=== top {frac:.0%} of junction nodes ({int(round(frac * len(nodes)))}): % of test-year junction crashes captured ===")
    print(wide.round(1).to_string())
    mean = wide.mean()
    print(f"mean: raw count {mean['raw count']:.1f}% (PAI {mean['raw count'] / (frac * 100):.1f}), "
          f"oracle {mean['ORACLE (test year)']:.1f}% | even spread would capture {frac * 100:.0f}%")