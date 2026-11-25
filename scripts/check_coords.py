import sys
import pandas as pd
from baac_io import PREFIXES, find_file, read_table

f = find_file(sys.argv[1], PREFIXES["characteristics"])
if f is None:
    raise SystemExit("characteristics file not found")
df, sep, enc = read_table(f)
print("file:", f.name, "| separator:", repr(sep), "| encoding:", enc)
print("columns:", list(df.columns))

for col in ("lat", "long"):
    if col not in df.columns:
        raise SystemExit(f"column '{col}' not found")
    df[col + "_num"] = pd.to_numeric(df[col].str.replace(",", ".", regex=False), errors="coerce")

print("rows:", len(df))
print("lat not numeric:", df["lat_num"].isna().sum())
print("long not numeric:", df["long_num"].isna().sum())
print("lat or long equal to 0:", ((df["lat_num"] == 0) | (df["long_num"] == 0)).sum())

metro = df["dep"].astype(str).str.len() <= 2
print("metropolitan rows:", metro.sum(), "| overseas rows:", (~metro).sum())
outside = metro & ~(df["lat_num"].between(41, 52) & df["long_num"].between(-5.5, 10))
print("metropolitan rows outside France bounds:", outside.sum())

real = df["lat"].str.replace(",", ".", regex=False).str.split(".").str[1].str.rstrip("0").str.len()
print("\nreal decimals in lat (trailing zeros removed):")
print(real.value_counts(dropna=False).sort_index())