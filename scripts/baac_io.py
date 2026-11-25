from pathlib import Path
import pandas as pd

PREFIXES = {
    "characteristics": "car",
    "places": "lieux",
    "vehicles": "vehicules",
    "users": "usagers",
}


def find_file(year_dir, prefix):
    for f in sorted(Path(year_dir).glob("*.csv")):
        name = f.name.lower()
        if name.startswith(prefix) and "immatricul" not in name:
            return f
    return None


def read_table(path):
    """Read a BAAC csv as text, detecting encoding and separator."""
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(path, encoding=enc, newline="") as fh:
                header = fh.readline()
            sep = max([";", ",", "\t"], key=header.count)
            df = pd.read_csv(path, sep=sep, dtype=str, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    df.columns = [c.strip().lstrip("\ufeff") for c in df.columns]
    return df, sep, enc


def id_column(df):
    for c in df.columns:
        if c.lower() in ("num_acc", "accident_id"):
            return c
    return None