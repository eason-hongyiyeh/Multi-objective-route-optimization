PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS stops (
    stop_id TEXT PRIMARY KEY,
    stop_name TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS pois (
    poi_id TEXT PRIMARY KEY,
    poi_name TEXT NOT NULL,
    poi_type TEXT NOT NULL,
    rating REAL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    osm_type TEXT,
    osm_id TEXT,
    address TEXT,
    source TEXT
);

CREATE TABLE IF NOT EXISTS poi_items (
    item_id TEXT PRIMARY KEY,
    item_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS route_edges (
    edge_id TEXT PRIMARY KEY,
    route_name TEXT NOT NULL,
    from_stop_id TEXT NOT NULL,
    to_stop_id TEXT NOT NULL,
    travel_time_min INTEGER NOT NULL CHECK (travel_time_min >= 0),
    FOREIGN KEY (from_stop_id) REFERENCES stops(stop_id),
    FOREIGN KEY (to_stop_id) REFERENCES stops(stop_id)
);

CREATE TABLE IF NOT EXISTS stop_poi_mapping (
    stop_id TEXT NOT NULL,
    poi_id TEXT NOT NULL,
    walking_time_min INTEGER NOT NULL CHECK (walking_time_min >= 0),
    PRIMARY KEY (stop_id, poi_id),
    FOREIGN KEY (stop_id) REFERENCES stops(stop_id) ON DELETE CASCADE,
    FOREIGN KEY (poi_id) REFERENCES pois(poi_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS poi_item_mapping (
    poi_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    price INTEGER NOT NULL CHECK (price >= 0),
    service_time_min INTEGER NOT NULL CHECK (service_time_min >= 0),
    PRIMARY KEY (poi_id, item_id),
    FOREIGN KEY (poi_id) REFERENCES pois(poi_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES poi_items(item_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_stops_name ON stops(stop_name);
CREATE INDEX IF NOT EXISTS idx_pois_name ON pois(poi_name);
CREATE INDEX IF NOT EXISTS idx_pois_type ON pois(poi_type);
CREATE INDEX IF NOT EXISTS idx_route_edges_route ON route_edges(route_name);
CREATE INDEX IF NOT EXISTS idx_route_edges_from_stop ON route_edges(from_stop_id);
CREATE INDEX IF NOT EXISTS idx_route_edges_to_stop ON route_edges(to_stop_id);
CREATE INDEX IF NOT EXISTS idx_stop_poi_poi ON stop_poi_mapping(poi_id);
CREATE INDEX IF NOT EXISTS idx_poi_item_item ON poi_item_mapping(item_id);
