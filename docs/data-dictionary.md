# Data dictionary

Source: data.gouv.fr, "Bases de données annuelles des accidents corporels de la
circulation routière", Ministère de l'intérieur / ONISR (BAAC files).
License: Licence Ouverte. Downloaded: 2026-11-25.
Years loaded: 2019-2025.

Files named `vehicules-immatricule*` belong to a separate registration dataset
and are not used.

## 1. Source tables and grain

| Table | File pattern | Grain |
|---|---|---|
| Characteristics | caract / carcteristiques / Caract | 1 row per accident |
| Places | lieux / Lieux | 2019-2022: 1 row per accident; from 2023: 1 row per road involved |
| Vehicles | vehicules / Vehicules | 1 row per vehicle |
| Users | usagers / Usagers | 1 row per person |

Rows per table and year (the four tables contain exactly the same set of
accident ids in every year):

| Year | Accidents (Characteristics) | Places rows | Vehicles rows | Users rows |
|---|---|---|---|---|
| 2019 | 58,840 | 58,840 | 100,710 | 132,977 |
| 2020 | 47,744 | 47,744 | 81,066 | 105,295 |
| 2021 | 56,518 | 56,518 | 97,315 | 129,248 |
| 2022 | 55,302 | 55,302 | 94,493 | 126,662 |
| 2023 | 54,822 | 70,860 | 93,585 | 125,789 |
| 2024 | 54,402 | 70,248 | 92,678 | 125,187 |
| 2025 | 55,093 | 71,116 | 93,865 | 126,376 |

- Join key: `Num_Acc` (12 characters, `YYYY` + 8 digits, clean text).
- Only Characteristics has one row per accident. Joining the other tables
  directly duplicates accidents, so they are aggregated to accident level first.
- File names are inconsistent across years (typo `carcteristiques` in 2022,
  mixed case and separators), so files are matched by prefix.

## 2. Format observations

- **Reading:** all files are read as text (`;` separator, `utf-8-sig`), then
  converted deliberately.
- **Decimal commas:** `lat` and `long` are text like `48,86638600`.
- **IDs with spaces:** `id_vehicule` and `id_usager` contain spaces
  (`155 680 557`). `Num_Acc` has none (the data.gouv.fr preview only displays
  spaces).
- **Date and time are split** across `jour`, `mois`, `an` and `hrmn` (`06:00`).
  There are no seconds.
- **Time is rounded.** Among usable accidents, 87.3% are recorded on a multiple
  of 5 minutes, 43.2% on a multiple of 15 and 14.1% at minute :00 (uniform
  minutes would give 20%, 6.7% and 1.7%). Order of events within a few
  minutes carries no information. Replay order: timestamp, then accident id.
- **Special values:** `-1` means "not specified" (to be confirmed against the
  official description file) and empty cells appear as NaN. Neither is a real
  measurement.
- **Missing values (2023):** `adr` 1,389 (Characteristics); `voie` 12,747,
  `v2` 64,976, `lartpc` 70,829 (Places); `occutc` 92,747 (Vehicles);
  `an_nais` 2,598 (Users).
- **Severity** is in `grav` (Users): 1 unharmed, 2 killed, 3 hospitalized,
  4 slight injury. The codes are not ordered by severity, so `grav` is never used
  as a number. Mapping taken from ONISR documentation and not yet re-checked
  against each year's description file; the exact definition of "killed"
  (for example the 30-day rule) is to be confirmed there.
- **`dep`:** metropolitan codes have at most 2 characters (including Corsica
  `2A`, `2B`); overseas codes have 3 digits (for example `971`).

## 3. Coordinate quality

| Year | Rows | Mainland | Overseas | Mainland outside France bounds | Rows with 4 or fewer real decimals | 3 or fewer |
|---|---|---|---|---|---|---|
| 2019 | 58,840 | 56,016 | 2,824 | 1 | 9.4% | 1.9% |
| 2020 | 47,744 | 45,121 | 2,623 | 0 | 8.7% | 1.4% |
| 2021 | 56,518 | 53,540 | 2,978 | 0 | 6.7% | 1.3% |
| 2022 | 55,302 | 52,380 | 2,922 | 0 | 6.3% | 1.3% |
| 2023 | 54,822 | 51,641 | 3,181 | 0 | 6.4% | 1.4% |
| 2024 | 54,402 | 51,058 | 3,344 | 3 | 6.3% | 1.3% |
| 2025 | 55,093 | 51,837 | 3,256 | 1 | 6.3% | 1.4% |

- In every year, `lat` and `long` are numeric after replacing the comma, and none
  equals 0. France bounds used: latitude 41-52, longitude -5.5-10.
- Mainland plus overseas equals the accident count each year, so the `dep` code
  format is consistent from 2019 to 2025.
- **Real precision** is the number of decimals after removing trailing zeros.
  The number of decimals written varies by year (7 in 2019-2020, 10 in
  2021-2022, 8 in 2023-2025), so written length says nothing about precision.
- The number of decimals measures how finely a value is written, not whether
  the location is correct.

Real precision of `lat` in 2023:

| Real decimals | Rows | Share | Approx. resolution |
|---|---|---|---|
| 0-3 | 754 | 1.4% | 100 m or worse |
| 4 | 2,741 | 5.0% | about 10 m |
| 5-8 | 51,327 | 93.6% | about 1 m or better |

- One 2023 row has 0 real decimals (probable placeholder); not inspected yet.
- Rows with 7 real decimals (1,147) versus 8 (9,267) suggest mixed recording
  methods. This is an observation, not a confirmed explanation.
- The most repeated coordinate pair in a year appears at most 18 times, so no
  large default location was found among the top 3 pairs of each year.
  Overseas pairs (for example Tahiti, latitude about -17.5) are valid.

## 4. Changes between years (2019-2025)

- All files use the `;` separator and `utf-8-sig` encoding in every year.
- `Num_Acc` has 12 characters in every year. In the 2022 characteristics file
  the column is named `Accident_Id` (normalized to `Num_Acc` on load).
- `id_usager` is absent from the users files of 2019 and 2020 (present from
  2021).
- Places grain: 1 row per accident in 2019-2022; several per accident from 2023.
- Padding of coordinate values with zeros differs by year (see section 3).
- Not yet verified: whether code meanings changed between years.

## 5. Exclusions

Excluded rows stay in the table with an `exclusion_reason`.

| Reason | Rule | Rows 2019-2025 |
|---|---|---|
| `overseas` | `dep` has 3 characters | 21,128 |
| `bad_coordinates` | Mainland row outside France bounds, or latitude or longitude equal to 0 | 5 |
| `bad_datetime` | Date or time not parseable | 0 |

Rows excluded for bad coordinates:

| Year | Accident | dep | Problem |
|---|---|---|---|
| 2019 | 201900033874 | 93 | lat = long = 11 (placeholder) |
| 2024 | 202400008235 | 2B | latitude and longitude swapped |
| 2024 | 202400011273 | 2B | latitude and longitude swapped |
| 2024 | 202400013466 | 2B | latitude and longitude swapped |
| 2025 | 202500038525 | 2B | latitude and longitude swapped |

Rule: exclude rather than repair, and list every exclusion here.

## 6. Table `crashes` (PostGIS, one row per accident, 2019-2025)

Built by `scripts/load_baac.py` from Characteristics, plus counts aggregated
from Users and Vehicles. Row counts per year reconcile with section 1.

- `accident_id` (primary key), `year`, `occurred_at` (date and time, no seconds)
- `dep`, `com`, `adr`, `lum`, `atm`, `col`, `agg`, `intersection`
- `lat`, `lon` (decimal degrees) and `geom` (Point, SRID 4326)
- `n_vehicles`, `n_users`, `n_killed`, `n_hospitalized`, `n_slight`, `n_unhurt`
  (counted from `grav` in Users)
- `exclusion_reason`: NULL means usable (361,588 usable accidents in the
  whole of mainland France); analytics filter on `exclusion_reason IS NULL`.

The load is one transaction (all or nothing).

## 7. Kafka topics

| Topic | Content |
|---|---|
| `crashes.raw` | One JSON message per accident of the study region (départements 75, 92, 93, 94), key = accident id |
| `crashes.dead-letter` | Messages the consumer rejected |

`crashes.raw` message (`schema_version` 1): `accident_id`, `occurred_at`
(ISO timestamp), `dep`, `com`, `adr`, `lat`, `lon`, `lum`, `atm`, `col`, `agg`,
`intersection`, `n_vehicles`, `n_users`, `n_killed`, `n_hospitalized`,
`n_slight`, `n_unhurt`.

The consumer validates (Pydantic) `schema_version` = 1, `accident_id` > 0,
latitude 41-52, longitude -5.5-10, counts >= 0, and requires `occurred_at`
and `dep`. Other fields are ignored.

`crashes.dead-letter` message: `error` (truncated to 500 characters), `topic`,
`partition`, `offset`, `value` (the original message).

## 8. Road network tables (OpenStreetMap, ODbL)

Built by `scripts/load_roads.py`. Network type `drive`; area = convex hull of
the study region's usable crashes plus a margin of 0.005 degrees.

- `road_edges`: 152,661 directed edges as returned by OSMnx. Columns `edge_id`,
  `u`, `v`, `k`, `osm_id`, `name`, `highway`, `length_m`, `geom`. A two-way
  street appears twice.
- `road_segments`: 106,882 distinct segments, about 10,955 km, built by
  `scripts/sql/road_segments.sql`. Two edges count as the same segment when
  they share both endpoints, the OSM id and the length. Snapping uses this
  table.

- `road_nodes`: 72,009 nodes rebuilt from the ends of `road_segments`
  (`scripts/sql/road_nodes.sql`).
- `road_junctions`: 62,817 nodes with 3 or more segments, with `degree`
  (`scripts/sql/road_junctions.sql`).

  
## 9. Table `crash_events` (output of the consumer)

One row per accident of the study region, upserted by `accident_id`.

- `accident_id` (primary key), `occurred_at`, `dep`, `lat`, `lon`, `geom`
- `segment_id`, `snap_distance_m`, `snap_status`
- `h3_cell` (H3 resolution 9, cells of about 0.1 km2)
- `severity_weight` = 10 x `n_killed` + 3 x `n_hospitalized` + 1 x `n_slight`
  (unharmed people weigh 0; the weights are design choices, not facts)
- `n_killed`, `n_hospitalized`, `n_slight`, `n_unhurt`, `processed_at`

Snapping rule: take the 5 nearest segments by spatial index, measure the true
distance in meters and keep the closest.

| `snap_status` | Meaning | Rows (2026-11-27) |
|---|---|---|
| `snapped` | Nearest segment within 50 m, `segment_id` set | 83,810 |
| `far` | Nearest segment farther than 50 m, `segment_id` empty | 706 |
| `no_road` | No segment found | 0 |

The 50 m threshold is a design choice. A short distance does not prove the
crash belongs to that road.

## 10. View `cell_month`

Defined in `scripts/sql/cell_month.sql`. One row per H3 cell and month, from
`crash_events`: `h3_cell`, `month`, `n_crashes`, `severity` (sum of
`severity_weight`), `n_killed`. Used by the hotspot backtests. 70,170 rows,
6,370 cells with at least one crash.

## 11. Checks and not yet verified

- `scripts/check_pipeline.py` runs 11 checks of `crash_events` against
  `crashes` (counts, duplicates, severity totals, row by row comparison,
  snap statuses, H3 cells, severity formula).
- `docs/quality-report.md` is generated from the database by
  `scripts/make_quality_report.py`. Do not edit it by hand.
- Not yet verified: meaning of codes (`grav`, `lum`, `atm`, `col`) in each
  year's description file, the meaning of `-1`, and the definition of a death.