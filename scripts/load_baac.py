import io
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

from baac_io import PREFIXES, find_file, read_table, id_column

load_dotenv()
ROOT = Path("data/raw")
YEARS = range(2019, 2026)

# Reconciliation targets from the exploration steps: (rows, overseas, bad coordinates)
EXPECTED = {
    2019: (58840, 2824, 1), 2020: (47744, 2623, 0), 2021: (56518, 2978, 0),
    2022: (55302, 2922, 0), 2023: (54822, 3181, 0), 2024: (54402, 3344, 3),
    2025: (55093, 3256, 1),
}

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS crashes (
    accident_id      bigint PRIMARY KEY,
    year             smallint NOT NULL,
    occurred_at      timestamp,
    dep              text,
    com              text,
    adr              text,
    lum              smallint,
    atm              smallint,
    col              smallint,
    agg              smallint,
    intersection     smallint,
    lat              double precision,
    lon              double precision,
    geom             geometry(Point, 4326),
    n_vehicles       integer,
    n_users          integer,
    n_killed         integer,
    n_hospitalized   integer,
    n_slight         integer,
    n_unhurt         integer,
    exclusion_reason text
);
CREATE INDEX IF NOT EXISTS crashes_geom_idx ON crashes USING GIST (geom);
CREATE INDEX IF NOT EXISTS crashes_year_idx ON crashes (year);
"""


def load_table(year, label):
    f = find_file(ROOT / str(year), PREFIXES[label])
    df, _, _ = read_table(f)
    return df.rename(columns={id_column(df): "Num_Acc"})


def build_year(y):
    car = load_table(y, "characteristics")
    users = load_table(y, "users")
    veh = load_table(y, "vehicles")

    out = pd.DataFrame()
    out["accident_id"] = car["Num_Acc"].astype("int64")
    out["year"] = y

    date = pd.to_datetime(
        {"year": pd.to_numeric(car["an"], errors="coerce"),
         "month": pd.to_numeric(car["mois"], errors="coerce"),
         "day": pd.to_numeric(car["jour"], errors="coerce")},
        errors="coerce",
    )
    out["occurred_at"] = date + pd.to_timedelta(car["hrmn"] + ":00", errors="coerce")

    out["dep"], out["com"], out["adr"] = car["dep"], car["com"], car["adr"]
    for src, dst in [("lum", "lum"), ("atm", "atm"), ("col", "col"),
                     ("agg", "agg"), ("int", "intersection")]:
        out[dst] = pd.to_numeric(car[src], errors="coerce").astype("Int64")
    out["lat"] = pd.to_numeric(car["lat"].str.replace(",", ".", regex=False), errors="coerce")
    out["lon"] = pd.to_numeric(car["long"].str.replace(",", ".", regex=False), errors="coerce")

    # Severity counts per accident (grav: 1 unharmed, 2 killed, 3 hospitalized, 4 slight)
    u = users.copy()
    grav = pd.to_numeric(u["grav"], errors="coerce")
    u["unhurt"], u["killed"] = grav == 1, grav == 2
    u["hospitalized"], u["slight"] = grav == 3, grav == 4
    g = u.groupby("Num_Acc")[["unhurt", "killed", "hospitalized", "slight"]].sum()
    g["n_users"] = u.groupby("Num_Acc").size()
    key = car["Num_Acc"]
    out["n_vehicles"] = key.map(veh.groupby("Num_Acc").size()).fillna(0).astype(int)
    out["n_users"] = key.map(g["n_users"]).fillna(0).astype(int)
    out["n_killed"] = key.map(g["killed"]).fillna(0).astype(int)
    out["n_hospitalized"] = key.map(g["hospitalized"]).fillna(0).astype(int)
    out["n_slight"] = key.map(g["slight"]).fillna(0).astype(int)
    out["n_unhurt"] = key.map(g["unhurt"]).fillna(0).astype(int)

    # Exclusions: flagged, never deleted, so row counts reconcile with the source
    overseas = out["dep"].astype(str).str.len() > 2
    in_box = out["lat"].between(41, 52) & out["lon"].between(-5.5, 10)
    zero = (out["lat"] == 0) | (out["lon"] == 0)
    bad_coords = ~overseas & (~in_box | zero)
    reason = pd.Series(pd.NA, index=out.index, dtype="object")
    reason = reason.mask(out["occurred_at"].isna(), "bad_datetime")
    reason = reason.mask(bad_coords, "bad_coordinates")
    reason = reason.mask(overseas, "overseas")
    out["exclusion_reason"] = reason
    return out


def main():
    conn = psycopg.connect(
        host="localhost",
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    with conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
            cur.execute("TRUNCATE crashes")
            for y in YEARS:
                df = build_year(y)
                buf = io.StringIO()
                df.to_csv(buf, index=False, header=False, na_rep="")
                cols = ", ".join(df.columns)
                with cur.copy(f"COPY crashes ({cols}) FROM STDIN WITH (FORMAT csv)") as cp:
                    cp.write(buf.getvalue())
                print(f"{y}: sent {len(df)} rows")

            cur.execute("""
                UPDATE crashes SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
                WHERE lat IS NOT NULL AND lon IS NOT NULL
                  AND exclusion_reason IS DISTINCT FROM 'bad_coordinates'
            """)

            cur.execute("""
                SELECT year, count(*),
                       count(*) FILTER (WHERE exclusion_reason = 'overseas'),
                       count(*) FILTER (WHERE exclusion_reason = 'bad_coordinates'),
                       count(*) FILTER (WHERE exclusion_reason = 'bad_datetime'),
                       count(*) FILTER (WHERE exclusion_reason IS NULL)
                FROM crashes GROUP BY year ORDER BY year
            """)
            print("\nyear  rows  overseas  bad_coords  bad_datetime  usable  check")
            ok = True
            for year, n, ov, bc, bd, usable in cur.fetchall():
                match = (n, ov, bc) == EXPECTED[year]
                ok &= match
                print(f"{year}  {n}  {ov}  {bc}  {bd}  {usable}  {'OK' if match else 'MISMATCH'}")
            if not ok:
                print("\nReconciliation failed, nothing was saved.")
                sys.exit(1)
    print("\nAll counts reconcile. Data saved.")


if __name__ == "__main__":
    main()