from pathlib import Path
from baac_io import PREFIXES, find_file, read_table, id_column

root = Path("data/raw")
years = sorted(int(p.name) for p in root.iterdir() if p.is_dir() and p.name.isdigit())
REF = 2023

cols, ids = {}, {}
for y in years:
    for label, prefix in PREFIXES.items():
        f = find_file(root / str(y), prefix)
        if f is None:
            print(y, label, "MISSING FILE")
            continue
        df, sep, enc = read_table(f)
        key = id_column(df)
        cols[(y, label)] = list(df.columns)
        ids[(y, label)] = set(df[key]) if key else set()
        if label == "characteristics":
            print(f"{y} characteristics: id column '{key}', sample '{df[key].iloc[0]}', "
                  f"lengths {sorted(df[key].str.len().unique())}")

print(f"\n--- Column differences vs {REF} ---")
for label in PREFIXES:
    ref = cols.get((REF, label), [])
    for y in years:
        c = cols.get((y, label))
        if c is None or y == REF:
            continue
        added = [x for x in c if x not in ref]
        removed = [x for x in ref if x not in c]
        if added or removed:
            print(f"{label} {y}: added {added} | removed {removed}")
        elif c != ref:
            print(f"{label} {y}: same columns, different order")

print("\n--- Same accident IDs in all four tables? ---")
for y in years:
    base = ids.get((y, "characteristics"), set())
    for label in ("places", "vehicles", "users"):
        other = ids.get((y, label), set())
        if other != base:
            print(f"{y} {label}: {len(base - other)} IDs only in characteristics, "
                  f"{len(other - base)} only in {label}")
print("done")