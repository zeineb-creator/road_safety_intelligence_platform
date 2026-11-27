# Learning log

Personal log of what happened, what went wrong and what I learned. Started
2026-11-25. Measured results come with their numbers; guesses are marked as
hypotheses.

## Week 0: setup

- **Docker Desktop must be running.** `docker run hello-world` failed with
  `failed to connect to the docker API` until Docker Desktop had finished
  starting ("Engine running").
- **Windows hides file extensions.** `.env.example` was saved as
  `.env.example.txt`. Fixed with `git mv`. Turn on "File name extensions" in
  File Explorer.
- **Files edited on github.com are not on the local disk.** Run `git pull`
  before editing locally.
- **Commands go one per line.** Two commands pasted on one line ran as a single
  wrong command (`check_pipeline.pypython ...`).
- **A Kafka consumer group remembers its offset.** A new group id re-reads the
  topic from the start; the same group id continues where it stopped.

## Week 1: data foundation

- **Port conflict.** Windows had its own PostgreSQL 17 service on port 5432.
  My script connected to it instead of the Docker database and got an
  authentication error. The Docker Postgres now uses port 5433
  (`POSTGRES_PORT` in `.env`).
- **BAAC structure.** Four tables per year, joined by `Num_Acc`. Only
  Characteristics has one row per accident. Places has one row per accident in
  2019-2022 and one row per road involved from 2023. In 2022 the accident id
  column of the characteristics file is called `Accident_Id`. `id_usager` is
  missing from the users files of 2019 and 2020.
- **Accidents per year** (the numbers the loader must reproduce): 2019 58,840,
  2020 47,744, 2021 56,518, 2022 55,302, 2023 54,822, 2024 54,402,
  2025 55,093. 2020 is 19% below 2019 (COVID restrictions).
- **A check that measured the wrong thing.** My first precision check counted
  decimals as written, and every 2023 row had 8. The file pads values with
  zeros, and the padding differs by year (7, 10 or 8 decimals written). The
  real precision is the number of decimals after removing trailing zeros.
  Lesson: a check can pass while measuring the wrong thing.
- **Coordinates are clean apart from 5 rows** (1 placeholder in 2019, 4 swapped
  latitude/longitude in Corsica in 2024-2025). They are excluded and listed
  in the data dictionary. About 6% of accidents have 4 or fewer real
  decimals (about 10 m or worse); 2019-2020 are slightly coarser (9.4% and
  8.7%).
- **Loader design.** Bad rows are flagged (`exclusion_reason`), never deleted,
  so counts reconcile with the source. The load is one transaction, and it
  compares rows, overseas rows and bad-coordinate rows per year with numbers
  measured independently before loading.
- **Times are rounded.** 87.3% of accidents are recorded on a multiple of
  5 minutes and 14.1% exactly on the hour, against 20% and 1.7% if minutes were
  uniform. The hourly curve is plausible (peaks at 8h and 17-18h, minimum at
  3h) with no midnight placeholder spike. 456 accidents are at 00:00 and
  294 at 00:01; I have no explanation for the 00:01 excess.
- **Region size.** Paris and the inner suburbs (75, 92, 93, 94) hold 84,516
  usable accidents over 7 years, about 12,000 a year. My first guess of
  5,000-8,000 a year was too low.

## Week 2: streaming pipeline

- **The replay is a simulation.** The producer reads the `crashes` table, ordered
  by timestamp then accident id. Order within a 5-minute block is arbitrary.
- **OSMnx returns a directed graph.** Two-way streets were stored twice.
  152,661 edges became 106,882 distinct segments (-30%), and the length went
  from 15,480 km to 10,955 km. Snapping uses `road_segments`.
- **Snapping results.** 83,810 crashes (99.2%) are within 50 m of a drivable
  road and 706 (0.8%) are farther. A first quick query gave 722 because
  the spatial index orders by distance in degrees; the consumer takes the
  5 nearest candidates by index and measures them in meters.
- **Snap distance is not a proof of the right street.** Median 0.9 m, but at
  intersections and between parallel streets the nearest road can be wrong.
- **The 50 m threshold is a judgment call.** Crashes farther than 10 / 25 / 50 /
  75 / 100 / 200 / 300 m: 3,402 / 1,432 / 706 / 390 / 274 / 113 / 59. The
  counts fall smoothly, with no natural cut-off.
- **Far crashes are a long tail.** 706 crashes over 501 distinct addresses,
  median distance 80 m. The top addresses include park roads, the
  Charles de Gaulle airport, large squares and bridges (Concorde, Pont d'Iéna,
  Porte Maillot) and the A4 motorway. At Place de la Concorde the 14 far
  crashes sit at 12 different points 57-130 m from a road, so they are not a
  single recorded "centre of the place". The cause is not established.
  Hypotheses, not tested: roads missing from the `drive` network, or
  coordinate errors of 50-130 m.
- **Consumer design.** Save to the database, then commit the Kafka offset,
  never the reverse. Writes are upserts keyed by accident id, so a replayed
  batch changes nothing. Invalid messages go to `crashes.dead-letter` with
  the error, topic, partition, offset and original value.
- **Tests.**
  - *Crash and restart:* the first attempt finished before I could close the
    window, so it tested nothing. I added a `--crash-after` option that exits
    right after the database commit and before the offset commit. The
    restart then re-read the last 500 events (saved 65,016 = 84,516 - 19,500)
    and ended with 84,516 rows, 84,516 distinct ids and equal killed totals.
    The first restart attempt saved 0 because the killed consumer was still
    registered in the group; I added `session.timeout.ms` 10000.
  - *Every event sent twice:* 169,032 messages processed, 84,516 rows.
  - *Bad messages:* both landed in the dead-letter topic and the consumer
    kept running.
  - `scripts/check_pipeline.py` runs 11 checks and all pass.
- **Throughput:** 1,005 events/s for 169,032 messages (half were duplicates
  that update an existing row). One consumer, local machine, replay at full
  speed, so it is not a live rate.
- **Mistakes worth remembering.** A missing variable definition
  (`t_first`) crashed the consumer on its first batch. `git add .` committed
  OSMnx's `cache/` folder (80.6 MB); fixed with a `.gitignore` entry, and by
  amending the last commit and force-pushing it.

## Week 3: hotspots

- **Cell sizes.** 6,370 H3 cells (resolution 9) contain at least one crash.
  The 748 cells with 31 or more crashes hold 43.8% of crashes, and the
  1,926 cells with 1-3 crashes hold only 4.1%.
- **Persistence baseline.** The top 100 cells by severity in 2019-2021 and in
  2022-2025 share 50 cells (random would share about 1.6).
- **Backtest design.** Select cells from the training years only, then
  measure the share of test-year crashes that fall in them. Metrics:
  capture rate, PAI (capture divided by the share of cells selected), an
  oracle (selection with hindsight, a ceiling no method can reach) and a
  random baseline.
- **Rolling backtest** (test years 2021-2025, training on all earlier years
  from 2019). Mean share of crashes captured by the top 5% of cells:
  oracle 27.6%, raw count 22.9%, severity weight 22.1%, Gi* 1-ring 18.5%,
  neighbor-smoothed count 18.5%; random 5%.
  - Raw count beat Gi* and smoothing in 5/5 splits at 2%, 5% and 10% of
    cells (by 2.5, 4.5 and 6.0 points).
  - Gi* and smoothing give almost identical rankings: with binary weights
    the Gi* z-score is a linear function of the neighborhood sum for cells
    with the same number of neighbors.
  - Severity weights (10/3/1) did not help (0.6-0.9 points worse).
  - More history did not clearly help: raw count captured 23.3% in 2021
    (2 training years) and 21.9% in 2025 (6 years).
- **Variants** (selected on 2021-2023, confirmed on 2024-2025; differences with
  raw count in percentage points of captured crashes). No variant was
  consistently better than raw count:
  - neighbor blend +0.1: +0.08 / +0.19 at 5%, but mixed at 2% and 10%;
    blend +0.5 worse (-0.15 / -0.01 at 5%, -0.14 / -0.30 at 10%)
  - recency weighting, half-life 2 years: between -0.06 and +0.19;
    half-life 1 year worse at 5% and 10% (-0.23 / -0.17 and -0.31 / -0.20)
  - dropping 2020 from training: worse in the selection years (-0.70 at 5%,
    -1.04 at 10%), which includes the 2021 split trained on 2019 alone
  With 18 variant and fraction combinations and differences this small, one
  small win could be chance. Conclusion: raw count with all history is hard to
  beat here.
- **Empirical Bayes would not change the ranking** with identical exposure for
  every cell, because the shrunk estimate rises with the raw count. It only
  matters with a prior that varies by cell (road length, road class).
- **Limits of these results.** 5 splits that share training data, one cell
  size, only crash capture, and study cells restricted to cells with at least
  one crash in 2019-2025.

### Segment-level backtest (budget = share of road length, 106,882 segments, 10,955 km)

Same rolling design as the cell backtest. Far crashes (706) have no segment and
are excluded. Mean over 5 splits (2021-2025), share of test-year crashes captured:

| Top share of road length | Raw count | Severity weight | Oracle by count |
|---|---|---|---|
| 1% | 6.1% | 6.2% | 8.0% |
| 2% | 11.9% | 11.3% | 15.1% |
| 5% | 26.4% | 24.3% | 40.7% |
| 10% | 41.3% | 39.7% | 74.3% |

- Only 29,969 segments (28%) have a snapped crash in 2019-2025. 22-41% of
  test-year crashes are on segments with no crash in the training years.
- Raw count reaches 56-79% of the oracle (91% at cell level): segment-level
  ranking is much noisier.
- Severity weighting was worse than raw count at 2%, 5% and 10% (5/5 splits).
- Ranking by count under a length budget picks long segments (top 1% of length =
  77 segments, about 1.4 km each, against 0.1 km on average), and the oracle by
  count is therefore not a true ceiling. Density rankings are the next test.
- Hypothesis, not tested: simplification splits a junction's crashes between the
  segments that meet there.
  
  ### Density variants (crashes per km, with a minimum length)

Score = training crashes / max(segment length, floor). Floors of 100 m (about
the average segment length) and 250 m were chosen by me, not tuned.
Mean share of test-year crashes captured, top share of road length:

| Share | Raw count | Density 100 m | Density 250 m | Count oracle | Density oracle |
|---|---|---|---|---|---|
| 1% | 6.1% | 10.1% | 9.6% | 8.0% | 21.3% |
| 2% | 11.9% | 16.9% | 16.1% | 15.1% | 34.9% |
| 5% | 26.4% | 30.6% | 29.6% | 40.7% | 67.6% |
| 10% | 41.3% | 45.2% | 43.9% | 74.3% | 91.8% |

- Both density rankings beat raw count in 5/5 splits at every fraction
  (+2.7 to +5.0 points). The 100 m floor did better than 250 m.
- A density ranking trained on past years beats the count oracle at 1% and 2%,
  so the count oracle was not a ceiling. The density oracle is a hindsight
  upper bound that fits one year's noise.
- Hypothesis, not tested: part of the gain comes from short segments (junction
  pieces) that are cheap in a length budget.

  - What the rankings select (training 2019-2024). Top 15 by raw count: 14
  motorway/tunnel segments (0.9-4.4 km) plus the Périphérique. Top 15 by density:
  urban blocks and squares (Boulevard Saint-Denis, Concorde, République, Rue
  Ordener...), 11-166 m long. Some are pieces of a junction (11-13 m segments
  with 19-27 crashes), some are real short blocks.
- At the top 1% of road length (about 110 km), raw count selects 78 segments
  (about 1.4 km each), density with a 100 m floor 872 (about 130 m each).
- Without traffic volumes, neither ranking measures risk: motorways carry more
  vehicles per km. Deaths are rare at segment level (most top segments have 0).
- Hypothesis, not tested: junction crashes are split between the pieces of a
  junction by nearest-segment snapping, so the density winners partly reflect
  how OSM cuts junctions.

  
## Open questions

- Why are 706 crashes more than 50 m from a drivable road? (Compare with the
  road network that includes service roads.)
- One 2023 row has 0 real decimals in `lat`; not inspected yet.
- Have code meanings (`grav`, `lum`, `atm`, `col`) changed between years?
- Do hotspots work better at other cell sizes, on road segments, or scored as
  zones instead of single cells?
- Does a prior based on road length or class beat raw counts?
- Throughput under a live replay speed and with a failing broker.