DROP TABLE IF EXISTS road_junctions;
CREATE TABLE road_junctions AS
SELECT n.node_id, n.geom, d.degree
FROM road_nodes n
JOIN (
    SELECT node_id, count(*) AS degree FROM (
        SELECT u AS node_id FROM road_segments
        UNION ALL
        SELECT v AS node_id FROM road_segments
    ) t GROUP BY node_id
) d USING (node_id)
WHERE d.degree >= 3;
ALTER TABLE road_junctions ADD PRIMARY KEY (node_id);
CREATE INDEX road_junctions_geom_idx ON road_junctions USING GIST (geom);
SELECT count(*) AS junctions, round(avg(degree), 2) AS mean_degree FROM road_junctions;