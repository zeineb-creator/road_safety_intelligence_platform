CREATE OR REPLACE VIEW cell_month AS
SELECT h3_cell,
       date_trunc('month', occurred_at)::date AS month,
       count(*)            AS n_crashes,
       sum(severity_weight) AS severity,
       sum(n_killed)        AS n_killed
FROM crash_events
GROUP BY 1, 2;