import os

import numpy as np
import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()
conn = psycopg.connect(
    host="localhost", port=int(os.environ.get("POSTGRES_PORT", "5432")),
    dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)
with conn.cursor() as cur:
    cur.execute("SELECT segment_id, length_m FROM road_segments ORDER BY segment_id")
    seg = pd.DataFrame(cur.fetchall(), columns=["segment_id", "length_m"]).set_index("segment_id")
    cur.execute("""SELECT segment_id, extract(year FROM occurred_at)::int, count(*), sum(severity_weight)
                   FROM crash_events WHERE segment_id IS NOT NULL GROUP BY 1, 2""")
    ev = pd.DataFrame(cur.fetchall(), columns=["segment_id", "year", "n", "sev"])
    cur.execute("SELECT count(*) FROM crash_events WHERE segment_id IS NULL")
    far = cur.fetchone()[0]
conn.close()

seg["length_m"] = seg["length_m"].astype(float)
ev["n"], ev["sev"] = ev["n"].astype(float), ev["sev"].astype(float)
total_len = seg["length_m"].sum()
FRACTIONS = (0.01, 0.02, 0.05, 0.10)
TEST_YEARS = (2021, 2022, 2023, 2024, 2025)

print(f"segments: {len(seg)} | road length: {total_len / 1000:.0f} km | crashes without segment (excluded): {far}")
print(f"segments with at least one snapped crash (2019-2025): {ev['segment_id'].nunique()}")


def counts(y0, y1, col):
    d = ev[(ev["year"] >= y0) & (ev["year"] <= y1)]
    return d.groupby("segment_id")[col].sum().reindex(seg.index, fill_value=0.0)


def select_by_length(score, frac):
    """Highest-scoring segments until the cumulative length reaches frac of the network."""
    order = (pd.DataFrame({"s": score.values, "id": score.index})
             .sort_values(["s", "id"], ascending=[False, True]))
    cum = np.cumsum(seg.loc[order["id"], "length_m"].values)
    k = np.searchsorted(cum, frac * total_len, side="right")
    return order["id"].values[:k]


rows = []
for ty in TEST_YEARS:
    train_n = counts(2019, ty - 1, "n")
    train_s = counts(2019, ty - 1, "sev")
    test_n = counts(ty, ty, "n")
    total = test_n.sum()
    unseen = test_n[train_n == 0].sum() / total
    print(f"test {ty}: {int(total)} snapped crashes, {unseen:.1%} on segments with no crash in the training years")
    for name, score in {"raw count": train_n, "severity weight": train_s,
                        "ORACLE (test year)": test_n}.items():
        for frac in FRACTIONS:
            sel = select_by_length(score, frac)
            rows.append({"test_year": ty, "method": name, "frac": frac,
                         "n_segments": len(sel), "capture": test_n.loc[sel].sum() / total})

res = pd.DataFrame(rows)
for frac in FRACTIONS:
    sub = res[res["frac"] == frac]
    wide = sub.pivot(index="test_year", columns="method", values="capture") * 100
    nseg = int(sub[sub["method"] == "raw count"]["n_segments"].mean())
    print(f"\n=== top {frac:.0%} of road length (about {nseg} segments): % of test-year crashes captured ===")
    print(wide.round(1).to_string())
    print("mean over splits:", {k: round(v, 1) for k, v in wide.mean().items()},
          "| uniform per km would capture:", f"{frac * 100:.0f}")
    d = wide["raw count"] - wide["severity weight"]
    print(f"raw count minus severity weight: mean {d.mean():+.1f} pts, raw better in {(d > 0).sum()}/{len(d)} splits")