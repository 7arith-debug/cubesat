import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from backend.config import DATABASE_PATH


SUBSYSTEMS = ("ADCS", "COMMS", "EPS", "Payload")

COMPONENTS = (
    ("ADCS", "Reaction wheels", 420, 0),
    ("ADCS", "Magnetorquers", 180, 0),
    ("ADCS", "Sun sensors", 95, 0),
    ("COMMS", "UHF transceiver", 680, 0),
    ("COMMS", "LoRa backup radio", 310, 0),
    ("COMMS", "Antenna deployment", 120, 0),
    ("EPS", "On-board computer", 380, 0),
    ("EPS", "Power regulation", 160, 0),
    ("EPS", "Battery monitor", 85, 0),
    ("Payload", "Imaging sensor", 520, 1),
    ("Payload", "Payload processor", 290, 1),
    ("Payload", "Thermal sensor array", 75, 1),
)

CHANNELS = (
    ("EPS", "battery_voltage", "V", "float"),
    ("EPS", "battery_current", "A", "float"),
    ("EPS", "battery_soc", "%", "float"),
    ("EPS", "battery_temp", "degC", "float"),
    ("EPS", "solar_voltage", "V", "float"),
    ("EPS", "solar_current", "A", "float"),
    ("EPS", "solar_power", "W", "float"),
    ("EPS", "charge_status", "state", "enum"),
)

CHANNEL_IDS = {name: index + 1 for index, (_, name, _, _) in enumerate(CHANNELS)}


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def db_session() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(path: Path = DATABASE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    connection.executescript(schema)

    connection.executemany("INSERT OR IGNORE INTO SUBSYSTEM(name) VALUES (?)", [(name,) for name in SUBSYSTEMS])
    subsystem_ids = {row["name"]: row["id"] for row in connection.execute("SELECT id, name FROM SUBSYSTEM")}
    for subsystem, name, _, _ in COMPONENTS:
        connection.execute(
            """DELETE FROM COMPONENT WHERE subsystem_id = ? AND name = ?
               AND id NOT IN (SELECT MIN(id) FROM COMPONENT WHERE subsystem_id = ? AND name = ?)""",
            (subsystem_ids[subsystem], name, subsystem_ids[subsystem], name),
        )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_component_subsystem_name ON COMPONENT(subsystem_id, name)"
    )
    connection.executemany(
        "INSERT OR IGNORE INTO COMPONENT(subsystem_id, name, power_draw_mW, is_payload) VALUES (?, ?, ?, ?)",
        [(subsystem_ids[subsystem], name, draw, payload) for subsystem, name, draw, payload in COMPONENTS],
    )
    connection.execute(
        """INSERT OR IGNORE INTO MISSION_CONFIG
           (id, solar_cell_power_W, orbit_duration_hours, orbits_per_day, selected_cell_count)
           VALUES (1, 0.55, 1.55, 15.5, 8)"""
    )
    connection.executemany(
        "INSERT OR IGNORE INTO CHANNEL(subsystem_id, name, unit, data_type) VALUES (?, ?, ?, ?)",
        [(subsystem_ids[subsystem], name, unit, data_type) for subsystem, name, unit, data_type in CHANNELS],
    )
    connection.commit()
    connection.close()


def insert_frame(sequence_number: int, rssi: float, link_status: str, values: dict[str, float]) -> dict[str, Any]:
    received_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db_session() as connection:
        cursor = connection.execute(
            "INSERT INTO FRAME(received_at, sequence_number, rssi, link_status) VALUES (?, ?, ?, ?)",
            (received_at, sequence_number, rssi, link_status),
        )
        frame_id = cursor.lastrowid
        connection.executemany(
            "INSERT INTO READING(frame_id, channel_id, value) VALUES (?, ?, ?)",
            [(frame_id, CHANNEL_IDS[name], value) for name, value in values.items()],
        )
    return {
        "sequence_number": sequence_number,
        "received_at": received_at,
        "rssi": rssi,
        "link_status": link_status,
        "readings": values,
    }
