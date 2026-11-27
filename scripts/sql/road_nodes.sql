DROP TABLE IF EXISTS road_nodes;
CREATE TABLE road_nodes AS
SELECT DISTINCT ON (node_id) node_id, pt AS geom FROM (
    SELECT u AS node_id, ST_StartPoint(geom) AS pt FROM road_segments
    UNION ALL
    SELECT v AS node_id, ST_EndPoint(geom) AS pt FROM road_segments
) t
ORDER BY node_id;
ALTER TABLE road_nodes ADD PRIMARY KEY (node_id);
CREATE INDEX road_nodes_geom_idx ON road_nodes USING GIST (geom);
SELECT count(*) AS nodes FROM road_nodes;