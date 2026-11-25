# Data dictionary: BAAC (road crashes, France)

Source: data.gouv.fr, "Bases de données annuelles des accidents corporels de la
circulation routière", Ministère de l'intérieur / ONISR.
License: Licence Ouverte. Downloaded: 2026-11-25.
Years analyzed so far: 2023 (other years pending).

Files named `vehicules-immatricule*` belong to a separate registration dataset
and are not used.

## 1. Tables and grain

| Table | File pattern | Grain | 2023 rows | Distinct Num_Acc |
|---|---|---|---|---|
| Characteristics | caract / carcteristiques / Caract | 1 row per accident | 54,822 | 54,822 |
| Places | lieux / Lieux | 1 row per road involved | 70,860 | 54,822 |
| Vehicles | vehicules / Vehicules | 1 row per vehicle | 93,585 | 54,822 |
| Users | usagers / Usagers | 1 row per person | 125,789 | 54,822 |

- Join key: `Num_Acc` (12-digit accident ID, clean text).
- Reference count for 2023: **54,822 accidents**.
- Only Characteristics has one row per accident. Joining the other tables
  directly duplicates accidents, so they are aggregated to accident level first.
- File names are inconsistent across years (typo `carcteristiques` in 2022,
  mixed case and separators), so files are matched by prefix, not by exact name.

## 2. Format observations

- **Reading:** all files are read as text (`;` separator, `utf-8-sig`), then
  converted deliberately.
- **Decimal commas:** `lat` and `long` are text like `48,86638600`.
  Conversion requires replacing the comma with a point.
- **IDs with spaces:** `id_vehicule` and `id_usager` contain spaces
  (`155 680 557`). `Num_Acc` has none (the website only displays spaces).
- **Date and time are split** across `jour`, `mois`, `an`, `hrmn` (`06:00`).
  There are no seconds, so many accidents share the same timestamp.
  Replay order: timestamp, then `Num_Acc`.
- **Special values:** `-1` means "not specified" (per BAAC documentation, to be
  verified against the official description file) and empty cells appear as
  NaN. Neither is a real measurement.
- **Missing values (2023):** `adr` 1,389 (Characteristics); `voie` 12,747,
  `v2` 64,976, `lartpc` 70,829 (Places); `occutc` 92,747 (Vehicles);
  `an_nais` 2,598 (Users).
- **Severity** is in `grav` (Users): 1 unharmed, 2 killed, 3 hospitalized,
  4 slight injury. The codes are NOT ordered by severity, so `grav` is never
  used as a number. An explicit weight mapping will be defined.
- **`dep`:** metropolitan codes have at most 2 characters (including Corsica
  `2A`, `2B`); overseas codes have 3 digits (for example `971`).

## 3. Coordinate quality (2023)

| Check | Result |
|---|---|
| `lat` / `long` not numeric | 0 |
| `lat` or `long` equal to 0 | 0 |
| Metropolitan rows outside France bounds | 0 (of 51,641) |
| Overseas rows | 3,181 (5.8%), excluded from road-network snapping |

Real precision of `lat` (number of decimals after removing trailing zeros;
the file pads every value to 8 decimals):

| Real decimals | Rows | Share | Approx. resolution |
|---|---|---|---|
| 0-3 | 754 | 1.4% | 100 m or worse |
| 4 | 2,741 | 5.0% | about 10 m |
| 5-8 | 51,327 | 93.6% | about 1 m or better |

- Number of decimals measures how finely a value is written, not whether the
  location is correct.
- Rows with 4 decimals or fewer (3,495, 6.4%) will be flagged as low
  precision at the snapping step.
- One row has 0 decimals (probable placeholder), to be inspected manually.
- Rows with 7 decimals (1,147) vs 8 (9,267) suggest mixed recording methods.
  This is an observation, not a confirmed explanation.

## 4. Changes between years

| Places | lieux / Lieux | 2019-2022: 1 row per accident; from 2023: 1 row per road involved | 70,860 (2023) | 54,822 |

## 4. Changes between years (2019-2025)

- All files: `;` separator, `utf-8-sig` encoding, every year.
- `Num_Acc`: 12 characters in every year. In the 2022 characteristics file the
  column is named `Accident_Id` (normalized to `Num_Acc` on load).
- `id_usager` is absent from the users files of 2019 and 2020 (present from 2021).
- Places grain: 1 row per accident in 2019-2022; several per accident from 2023.
- The four tables contain exactly the same set of accident IDs in every year.
- Not yet verified: whether code meanings changed between years (to be compared
  with each year's official description file before using a code column).

Accidents per year (reconciliation targets): 2019 58,840 | 2020 47,744 |
2021 56,518 | 2022 55,302 | 2023 54,822 | 2024 54,402 | 2025 55,093.

## 5. Exclusions (to be finalized)

### Coordinate exclusions (2019-2025)

| Year | Num_Acc | dep | Problem | Decision |
|---|---|---|---|---|
| 2019 | 201900033874 | 93 | lat = long = 11 (placeholder) | Excluded |
| 2024 | 202400008235 | 2B | lat/long swapped | Excluded |
| 2024 | 202400011273 | 2B | lat/long swapped | Excluded |
| 2024 | 202400013466 | 2B | lat/long swapped | Excluded |
| 2025 | 202500038525 | 2B | lat/long swapped | Excluded |

- Rule: exclude rather than repair, and list every exclusion here.
- Number of padded zeros in `lat`/`long` varies by year (7 digits in 2019-2020,
  10 in 2021-2022, 8 in 2023-2025), so real precision is measured after
  removing trailing zeros.
- Share of rows with 4 or fewer real decimals (about 10 m or worse):
  2019 9.4%, 2020 8.7%, 2021 6.7%, 2022-2025 6.3-6.4%.
  2019-2020 are slightly coarser, noted for the backtest.
- Most repeated coordinate pair per year: at most 18 rows, so no large default
  location was found among the top 3 pairs. Overseas pairs (for example
  Tahiti, lat about -17.5) are valid and excluded by the dep rule.