DROP TABLE IF EXISTS road_segments;
CREATE TABLE road_segments AS
SELECT DISTINCT ON (least(u,v), greatest(u,v), osm_id, length_m)
       edge_id AS segment_id, u, v, osm_id, name, highway, length_m, geom
FROM road_edges
ORDER BY least(u,v), greatest(u,v), osm_id, length_m, edge_id;
ALTER TABLE road_segments ADD PRIMARY KEY (segment_id);
CREATE INDEX road_segments_geom_idx ON road_segments USING GIST (geom);
SELECT count(*) AS segments, round(sum(length_m)/1000) AS km FROM road_segments;