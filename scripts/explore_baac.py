import sys
from baac_io import PREFIXES, find_file, read_table, id_column

year_dir = sys.argv[1]

for label, prefix in PREFIXES.items():
    f = find_file(year_dir, prefix)
    print(f"\n=== {label} ===")
    if f is None:
        print(f"NO FILE starting with '{prefix}' in {year_dir}")
        continue
    df, sep, enc = read_table(f)
    print("file:", f.name, "| separator:", repr(sep), "| encoding:", enc)
    print("rows, columns:", df.shape)
    print("columns:", list(df.columns))
    key = id_column(df)
    if key is None:
        print("WARNING: no Num_Acc-like column found")
        continue
    print(f"id column: {key} | distinct: {df[key].nunique()} of {len(df)} rows")
    print("sample id:", df[key].iloc[0])
    missing = df.isna().sum()
    print("columns with missing values:")
    print(missing[missing > 0])