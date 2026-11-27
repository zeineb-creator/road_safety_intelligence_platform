import numpy as np
import pandas as pd

from hotspot_lib import load_cell_month, window, top_k, _ring_sums

df = load_cell_month()
cells = pd.Index(sorted(df["h3_cell"].unique()))
N = len(cells)
FRACTIONS = (0.02, 0.05, 0.10)
TEST_YEARS = (2021, 2022, 2023, 2024, 2025)


def train_counts(test_year, half_life=None, drop_2020=False):
    d = df[(df["month"] >= "2019-01-01") & (df["month"] <= f"{test_year - 1}-12-31")].copy()
    if drop_2020:
        d = d[d["month"].dt.year != 2020]
    if half_life:
        age_years = (pd.Timestamp(f"{test_year}-01-01") - d["month"]).dt.days / 365.25
        d["w"] = 0.5 ** (age_years / half_life)
    else:
        d["w"] = 1.0
    d["x"] = d["n_crashes"] * d["w"]
    return d.groupby("h3_cell")["x"].sum().reindex(cells, fill_value=0.0)


def neighbor_blend(series, alpha):
    x, s, w = _ring_sums(series, 1)
    nb_mean = np.where(w > 1, (s - x) / np.maximum(w - 1, 1), 0.0)  # mean of neighbors, self excluded
    return pd.Series(x + alpha * nb_mean, index=series.index)


rows = []
for ty in TEST_YEARS:
    test = window(df, cells, f"{ty}-01-01", f"{ty}-12-31")
    total = test["n_crashes"].sum()
    base = train_counts(ty)
    methods = {
        "raw count": base,
        "raw, 2020 dropped": train_counts(ty, drop_2020=True),
        "recency, half-life 2y": train_counts(ty, half_life=2),
        "recency, half-life 1y": train_counts(ty, half_life=1),
        "raw + 0.1 x neighbors": neighbor_blend(base, 0.1),
        "raw + 0.25 x neighbors": neighbor_blend(base, 0.25),
        "raw + 0.5 x neighbors": neighbor_blend(base, 0.5),
    }
    for name, score in methods.items():
        for frac in FRACTIONS:
            k = int(round(frac * N))
            sel = top_k(score, k)
            rows.append({"test_year": ty, "method": name, "frac": frac,
                         "capture": test.loc[sel, "n_crashes"].sum() / total})

res = pd.DataFrame(rows)
for frac in FRACTIONS:
    wide = res[res["frac"] == frac].pivot(index="test_year", columns="method", values="capture") * 100
    diff = wide.sub(wide["raw count"], axis=0).drop(columns="raw count")
    out = pd.DataFrame({
        "diff 2021-23 (selection)": diff.loc[2021:2023].mean(),
        "diff 2024-25 (confirmation)": diff.loc[2024:2025].mean(),
        "better than raw, of 5": (diff > 0).sum(),
    }).round(2)
    print(f"\n=== top {frac:.0%}: capture minus raw count, in percentage points ===")
    print(out.to_string())