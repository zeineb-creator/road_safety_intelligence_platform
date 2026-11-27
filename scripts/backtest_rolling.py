import pandas as pd

from hotspot_lib import load_cell_month, window, top_k, gi_star, smoothed

df = load_cell_month()
cells = pd.Index(sorted(df["h3_cell"].unique()))
N = len(cells)
FRACTIONS = (0.02, 0.05, 0.10)
TEST_YEARS = (2021, 2022, 2023, 2024, 2025)

rows = []
for ty in TEST_YEARS:
    train = window(df, cells, "2019-01-01", f"{ty - 1}-12-31")  # all earlier years
    test = window(df, cells, f"{ty}-01-01", f"{ty}-12-31")
    total = test["n_crashes"].sum()
    methods = {
        "raw count": train["n_crashes"],
        "severity weight": train["severity"],
        "smoothed 1-ring": smoothed(train["n_crashes"], 1),
        "Gi* 1-ring": gi_star(train["n_crashes"], 1),
        "ORACLE (test year)": test["n_crashes"],
    }
    for name, score in methods.items():
        for frac in FRACTIONS:
            k = int(round(frac * N))
            sel = top_k(score, k)
            rows.append({"test_year": ty, "method": name, "frac": frac,
                         "capture": test.loc[sel, "n_crashes"].sum() / total})

res = pd.DataFrame(rows)
for frac in FRACTIONS:
    wide = res[res["frac"] == frac].pivot(index="test_year", columns="method", values="capture")
    print(f"\n=== top {frac:.0%} of cells: % of test-year crashes captured ===")
    print((wide * 100).round(1).to_string())
    print("mean over splits:", {k: round(v * 100, 1) for k, v in wide.mean().items()})
    for other in ("severity weight", "smoothed 1-ring", "Gi* 1-ring"):
        d = (wide["raw count"] - wide[other]) * 100
        print(f"raw count minus {other}: mean {d.mean():+.1f} pts, "
              f"raw count better in {(d > 0).sum()}/{len(d)} splits")