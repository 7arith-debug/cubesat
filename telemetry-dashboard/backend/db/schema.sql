PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS SUBSYSTEM (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS COMPONENT (
    id INTEGER PRIMARY KEY,
    subsystem_id INTEGER NOT NULL REFERENCES SUBSYSTEM(id),
    name TEXT NOT NULL,
    power_draw_mW REAL NOT NULL CHECK (power_draw_mW >= 0),
    is_payload INTEGER NOT NULL DEFAULT 0 CHECK (is_payload IN (0, 1))
);

CREATE TABLE IF NOT EXISTS MISSION_CONFIG (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    solar_cell_power_W REAL NOT NULL CHECK (solar_cell_power_W > 0),
    orbit_duration_hours REAL NOT NULL CHECK (orbit_duration_hours > 0),
    orbits_per_day REAL NOT NULL CHECK (orbits_per_day > 0),
    selected_cell_count INTEGER NOT NULL CHECK (selected_cell_count > 0)
);

CREATE TABLE IF NOT EXISTS CHANNEL (
    id INTEGER PRIMARY KEY,
    subsystem_id INTEGER NOT NULL REFERENCES SUBSYSTEM(id),
    name TEXT NOT NULL UNIQUE,
    unit TEXT NOT NULL,
    data_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS FRAME (
    id INTEGER PRIMARY KEY,
    received_at TEXT NOT NULL,
    sequence_number INTEGER NOT NULL UNIQUE,
    rssi REAL NOT NULL,
    link_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS READING (
    id INTEGER PRIMARY KEY,
    frame_id INTEGER NOT NULL REFERENCES FRAME(id) ON DELETE CASCADE,
    channel_id INTEGER NOT NULL REFERENCES CHANNEL(id),
    value REAL NOT NULL,
    UNIQUE (frame_id, channel_id)
);

CREATE TABLE IF NOT EXISTS LINK_EVENT (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    rssi REAL
);

CREATE INDEX IF NOT EXISTS idx_frame_received_at ON FRAME(received_at);
CREATE INDEX IF NOT EXISTS idx_reading_frame_id ON READING(frame_id);
