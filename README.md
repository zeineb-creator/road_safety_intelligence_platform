# Road Safety Intelligence Platform

A learning project on open data: it replays French injury-crash records (BAAC) as a live Kafka stream, enriches them with PostGIS and OpenStreetMap roads, and (in progress) detects high-risk locations and answers questions about them with a local LLM agent.

The stack is free and open source, apart from Docker Desktop (used for local development on Windows, free for personal use).

## What it does today

- Loads 7 years (2019-2025) of French crash data into PostGIS and reconciles the row counts with the source files.
- Replays the crashes of Paris and the inner suburbs (départements 75, 92, 93, 94) into Kafka in timestamp order.
- A consumer validates each event, snaps it to the nearest road, assigns an H3 cell and a severity weight, and saves it. Invalid messages go to a dead-letter topic.
- The pipeline is safe to stop, restart and replay: restarting after a crash and processing duplicate messages both give exactly the source counts.

## Architecture (implemented)

```
BAAC CSV files (data.gouv.fr)
      |  scripts/load_baac.py
      v
PostGIS table `crashes`  (one row per accident, exclusions flagged, never deleted)
      |  scripts/replay_producer.py
      v
Kafka topic `crashes.raw`
      |  scripts/consumer.py   <-- PostGIS table `road_segments` (OpenStreetMap, via OSMnx)
      v                |
PostGIS table          +--> Kafka topic `crashes.dead-letter` (invalid messages)
`crash_events`
(road segment, H3 cell, severity weight, snap status)
```

Planned: spatial hotspot statistics, document retrieval (RAG), an agent with typed tools, a live map and observability.

## Results so far

Measured on one laptop, Windows 11 + Docker Desktop.

**Data reconciliation** (rows in the `crashes` table equal the source files):

| Year | Accidents | Usable (mainland, valid coordinates) |
|---|---|---|
| 2019 | 58,840 | 56,015 |
| 2020 | 47,744 | 45,121 |
| 2021 | 56,518 | 53,540 |
| 2022 | 55,302 | 52,380 |
| 2023 | 54,822 | 51,641 |
| 2024 | 54,402 | 51,055 |
| 2025 | 55,093 | 51,836 |

Study region: **84,516** usable accidents in départements 75, 92, 93 and 94 (2019-2025).

**Pipeline results:**

| Check | Result |
|---|---|
| Crashes snapped to a road within 50 m | 83,810 (99.2%) |
| Crashes more than 50 m from a drivable road (kept, no road assigned) | 706 (0.8%) |
| Consumer killed after saving 20,000 events, then restarted | Ends with 84,516 rows, no duplicates |
| Every event sent twice (169,032 messages) | Ends with 84,516 rows |
| Invalid messages | Land in the dead-letter topic, consumer keeps running |
| Consumer throughput | about 1,000 events/s (batch replay, one consumer, local machine) |

`scripts/check_pipeline.py` runs 11 automatic checks (counts, duplicates, severity totals, row-by-row comparison with the source, snap status, H3 cells).

**Hotspot backtest** (rolling origin: train on all years before the test year,
test years 2021-2025, mean share of test-year crashes captured):

| Unit and budget | Past raw count | Best variant tested | Even spread |
|---|---|---|---|
| H3 cells (res. 9), top 5% of cells | 22.9% | Gi* 18.5% (worse) | 5% |
| Road segments, top 5% of road length | 26.4% | density, 100 m floor: 30.6% | 5% |
| Road segments, mid-block crashes, top 5% of length | 39.6% | density, 250 m floor: 40.8% | 5% |
| Junction nodes, top 5% of nodes | 41.6% | not tested | 5% |

- Gi*, neighbor smoothing and severity weights did not beat plain past counts.
- 22-45% of crashes happen at places with no crash in the training years.
- Rows are not comparable (different units and universes); no exposure data, so
  this measures where crashes happen, not risk per vehicle-km.

  
## Quick start (Windows PowerShell)

Requirements: Docker Desktop, Git, Python 3.11+.

```powershell
git clone https://github.com/zeineb-creator/road_safety_intelligence_platform.git
cd road_safety_intelligence_platform
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env        # then edit .env and set a password
docker compose up -d
docker compose ps                  # wait until postgres is healthy
```

Create the two Kafka topics:

```powershell
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --create --topic crashes.raw --bootstrap-server localhost:9092
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --create --topic crashes.dead-letter --bootstrap-server localhost:9092
```

Download the BAAC files for 2019-2025 from the link [https://www.data.gouv.fr/datasets/bases-de-donnees-annuelles-des-accidents-corporels-de-la-circulation-routiere-annees-de-2005-a-2025?resource_id=2ad65965-36a1-4452-9c08-61a6c874e3e6](https://www.data.gouv.fr/datasets/bases-de-donnees-annuelles-des-accidents-corporels-de-la-circulation-routiere-annees-de-2005-a-2025?resource_id=2ad65965-36a1-4452-9c08-61a6c874e3e6) ("Bases de données annuelles des accidents corporels de la circulation routière") and put the four files of each year in `data/raw/<year>/`. The `data/` folder is not tracked by Git.

Run the pipeline in order:

```powershell
python scripts\load_baac.py                       # load and reconcile the crashes table
python scripts\load_roads.py                      # download the OSM road network
Get-Content scripts\sql\road_segments.sql | docker compose exec -T postgres psql -U crash -d crashes
python scripts\replay_producer.py                 # send events to Kafka (--speed, --limit, --deps)
python scripts\consumer.py --exit-when-idle 15    # enrich and save events
python scripts\check_pipeline.py                  # 11 automatic checks
```

The `-U crash -d crashes` values must match `POSTGRES_USER` and `POSTGRES_DB` in your `.env`.

To start a replay from a clean topic, delete and recreate it first:

```powershell
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --delete --topic crashes.raw --bootstrap-server localhost:9092
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --create --topic crashes.raw --bootstrap-server localhost:9092
```

## Repository layout

| Path | Purpose |
|---|---|
| `docker-compose.yml` | PostgreSQL/PostGIS and Kafka (KRaft) |
| `scripts/load_baac.py` | Normalizes and loads the BAAC files, with reconciliation |
| `scripts/load_roads.py` | Downloads the OSM road network (OSMnx) |
| `scripts/replay_producer.py` | Replays crashes into Kafka in timestamp order |
| `scripts/consumer.py` | Validates, snaps, assigns H3 cell and severity, upserts |
| `scripts/check_pipeline.py` | End-to-end consistency checks |
| `scripts/make_quality_report.py` | Generates `docs/quality-report.md` from the database |
| `scripts/explore_baac.py`, `check_coords.py`, `coord_report.py`, `compare_years.py` | Data exploration and checks |
| `docs/data-dictionary.md` | Tables, columns, quirks and changes between years |
| `docs/quality-report.md` | Generated data quality report |
| `docs/LICENSES.md` | Licenses and attribution |

## Limitations

- **Replay, not live data.** BAAC is published once a year, so the stream is a simulation. The producer reads the `crashes` table, not the CSV files directly.
- **Times are rounded.** About 87% of accidents are recorded on a multiple of 5 minutes, so the order of events within a few minutes is not meaningful.
- **Snapping can choose the wrong road.** A small distance does not prove the right street, especially at intersections. 0.8% of crashes are more than 50 m from any drivable road (parks, an airport, large squares and a long tail of other addresses); the cause is not established, and the 50 m threshold is a judgment call.
- **Coordinate precision varies.** About 6% of accidents have coordinates written with 4 or fewer decimals (about 10 m or worse).
- **Overseas territories are excluded** from road snapping (about 6% of rows), as are a handful of rows with invalid coordinates (listed in `docs/quality-report.md`).
- **No exposure data.** Without traffic volumes, counts show where crashes happen, not risk per vehicle-kilometre.
- **Severity weights and the H3 resolution are design choices**, not facts from the data, and will be compared in the hotspot analysis.
- Code meanings (`grav`, `lum`, `atm`, ...) have not yet been verified against each year's official description file.

## Data sources and licenses

- **Crashes:** BAAC files, Ministère de l'Intérieur / ONISR, via data.gouv.fr, under the Licence Ouverte.
- **Roads:** © OpenStreetMap contributors, under the ODbL (attribution required; derived databases must stay under the ODbL). Downloaded with OSMnx (MIT).
- **Code:** MIT license (see `LICENSE`).

See `docs/LICENSES.md` for the full table.