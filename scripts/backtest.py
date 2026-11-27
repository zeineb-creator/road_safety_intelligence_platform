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
with conn.cursor() as cur:
    cur.execute("SELECT h3_cell, month, n_crashes, severity, n_killed FROM cell_month")
    df = pd.DataFrame(cur.fetchall(),
                      columns=["h3_cell", "month", "n_crashes", "severity", "n_killed"])
df["month"] = pd.to_datetime(df["month"])
for c in ("n_crashes", "severity", "n_killed"):
    df[c] = df[c].astype(float)

TRAIN = ("2019-01-01", "2021-12-31")
TEST = ("2022-01-01", "2025-12-31")
FRACTIONS = (0.01, 0.02, 0.05, 0.10)

cells = pd.Index(sorted(df["h3_cell"].unique()))
N = len(cells)


def window(start, end):
    d = df[(df["month"] >= start) & (df["month"] <= end)]
    return (d.groupby("h3_cell")[["n_crashes", "severity", "n_killed"]].sum()
            .reindex(cells, fill_value=0.0))


train, test = window(*TRAIN), window(*TEST)
tot_crashes, tot_sev = test["n_crashes"].sum(), test["severity"].sum()


def top_k(score, k):
    # ties are broken by cell id, so results are reproducible
    tmp = pd.DataFrame({"s": score.values, "c": score.index}, index=score.index)
    return tmp.sort_values(["s", "c"], ascending=[False, True]).index[:k]


METHODS = {
    "raw count (train)": train["n_crashes"],
    "severity weight (train)": train["severity"],
    "ORACLE by crash count (test)": test["n_crashes"],
    "ORACLE by severity (test)": test["severity"],
}

rows = []
for name, score in METHODS.items():
    for frac in FRACTIONS:
        k = int(round(frac * N))
        sel = top_k(score, k)
        cap_n = test.loc[sel, "n_crashes"].sum() / tot_crashes
        cap_s = test.loc[sel, "severity"].sum() / tot_sev
        rows.append({"method": name, "top cells": f"{frac:.0%} ({k})",
                     "test crashes captured": f"{cap_n:.1%}",
                     "test severity captured": f"{cap_s:.1%}",
                     "PAI": round(cap_n / (k / N), 1)})
for frac in FRACTIONS:
    k = int(round(frac * N))
    rows.append({"method": "random (expected)", "top cells": f"{frac:.0%} ({k})",
                 "test crashes captured": f"{k / N:.1%}",
                 "test severity captured": f"{k / N:.1%}", "PAI": 1.0})

print(f"study cells: {N} | train {TRAIN[0]}..{TRAIN[1]} | test {TEST[0]}..{TEST[1]}")
print(f"train crashes: {int(train['n_crashes'].sum())} | test crashes: {int(tot_crashes)}")
print(pd.DataFrame(rows).to_string(index=False))