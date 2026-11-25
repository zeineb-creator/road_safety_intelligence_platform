import csv
import io
import os

import osmnx as ox
import psycopg
import shapely
from dotenv import load_dotenv

load_dotenv()
conn = psycopg.connect(
    host="localhost", port=int(os.environ.get("POSTGRES_PORT", "5432")),
    dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)

# Area = convex hull of the region's usable crashes, plus a small margin (about 500 m)
with conn.cursor() as cur:
    cur.execute("""
        SELECT ST_AsText(ST_Buffer(ST_ConvexHull(ST_Collect(geom)), 0.005))
        FROM crashes
        WHERE exclusion_reason IS NULL AND dep IN ('75','92','93','94')
    """)
    polygon = shapely.from_wkt(cur.fetchone()[0])

print("Downloading the road network, this can take several minutes...")
G = ox.graph_from_polygon(polygon, network_type="drive", simplify=True)
edges = ox.graph_to_gdfs(G, nodes=False).reset_index()
print("edges downloaded:", len(edges))


def txt(v):
    if isinstance(v, (list, tuple)):
        return ";".join(map(str, v))
    if v is None or v != v:  # None or NaN
        return ""
    return str(v)


buf = io.StringIO()
w = csv.writer(buf)
for _, r in edges.iterrows():
    geom = shapely.set_srid(r["geometry"], 4326)
    w.writerow([int(r["u"]), int(r["v"]), int(r["key"]), txt(r.get("osmid")),
                txt(r.get("name")), txt(r.get("highway")), float(r["length"]),
                shapely.to_wkb(geom, hex=True, include_srid=True)])

with conn:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS road_edges (
                edge_id  serial PRIMARY KEY,
                u bigint, v bigint, k integer,
                osm_id text, name text, highway text,
                length_m real,
                geom geometry(LineString, 4326)
            );
            CREATE INDEX IF NOT EXISTS road_edges_geom_idx ON road_edges USING GIST (geom);
            TRUNCATE road_edges RESTART IDENTITY;
        """)
        with cur.copy("COPY road_edges (u, v, k, osm_id, name, highway, length_m, geom) "
                      "FROM STDIN WITH (FORMAT csv)") as cp:
            cp.write(buf.getvalue())
        cur.execute("SELECT count(*), round(sum(length_m)/1000) FROM road_edges")
        n, km = cur.fetchone()
        print(f"saved {n} road segments, about {km} km of road")