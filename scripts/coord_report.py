from pathlib import Path
import pandas as pd
from baac_io import PREFIXES, find_file, read_table, id_column

root = Path("data/raw")
years = sorted(int(p.name) for p in root.iterdir() if p.is_dir() and p.name.isdigit())

summary = []
for y in years:
    df, _, _ = read_table(find_file(root / str(y), PREFIXES["characteristics"]))
    key = id_column(df)
    for c in ("lat", "long"):
        df[c + "_num"] = pd.to_numeric(df[c].str.replace(",", ".", regex=False), errors="coerce")
    metro = df["dep"].astype(str).str.len() <= 2
    outside = metro & ~(df["lat_num"].between(41, 52) & df["long_num"].between(-5.5, 10))

    decimals = (df["lat"].str.replace(",", ".", regex=False)
                .str.split(".").str[1].str.rstrip("0").str.len().fillna(0))
    low4 = (decimals <= 4).mean() * 100
    low3 = (decimals <= 3).mean() * 100

    print(f"\n===== {y} =====")
    if outside.any():
        print("Outside France bounds:")
        print(df.loc[outside, [key, "dep", "com", "adr", "lat", "long"]].to_string())

    top = (df.groupby(["lat", "long"]).size().sort_values(ascending=False).head(3))
    print("Most repeated coordinate pairs:")
    print(top.to_string())

    summary.append({"year": y, "accidents": len(df), "outside_bounds": int(outside.sum()),
                    "pct_<=4_decimals": round(low4, 1), "pct_<=3_decimals": round(low3, 1)})

print("\n===== SUMMARY =====")
print(pd.DataFrame(summary).to_string(index=False))