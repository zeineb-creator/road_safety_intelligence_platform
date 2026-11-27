import os

import h3
import numpy as np
import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()


def load_cell_month():
    conn = psycopg.connect(
        host="localhost", port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    with conn.cursor() as cur:
        cur.execute("SELECT h3_cell, month, n_crashes, severity, n_killed FROM cell_month")
        df = pd.DataFrame(cur.fetchall(),
                          columns=["h3_cell", "month", "n_crashes", "severity", "n_killed"])
    conn.close()
    df["month"] = pd.to_datetime(df["month"])
    for c in ("n_crashes", "severity", "n_killed"):
        df[c] = df[c].astype(float)
    return df


def window(df, cells, start, end):
    d = df[(df["month"] >= start) & (df["month"] <= end)]
    return (d.groupby("h3_cell")[["n_crashes", "severity", "n_killed"]].sum()
            .reindex(cells, fill_value=0.0))


def top_k(score, k):
    tmp = pd.DataFrame({"s": score.values, "c": score.index}, index=score.index)
    return tmp.sort_values(["s", "c"], ascending=[False, True]).index[:k]


def _ring_sums(series, k):
    pos = {c: i for i, c in enumerate(series.index)}
    rows, cols = [], []
    for c, i in pos.items():
        for nb in h3.grid_disk(c, k):
            j = pos.get(nb)
            if j is not None:
                rows.append(i)
                cols.append(j)
    rows, cols = np.array(rows), np.array(cols)
    x = series.values.astype(float)
    s = np.zeros(len(x))
    np.add.at(s, rows, x[cols])
    w = np.bincount(rows, minlength=len(x)).astype(float)
    return x, s, w


def gi_star(series, k):
    x, s, w = _ring_sums(series, k)
    n = len(x)
    xbar = x.mean()
    sd = np.sqrt((x ** 2).mean() - xbar ** 2)
    z = (s - w * xbar) / (sd * np.sqrt((n * w - w ** 2) / (n - 1)))
    return pd.Series(z, index=series.index)


def smoothed(series, k):
    x, s, w = _ring_sums(series, k)
    return pd.Series(s / w, index=series.index)