from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.db.session import db_session


router = APIRouter(prefix="/api")


class MissionConfigPatch(BaseModel):
    selected_cell_count: int = Field(ge=1, le=10000)


def build_power_budget(selected_cell_count: int | None = None) -> dict:
    with db_session() as connection:
        config = dict(connection.execute("SELECT * FROM MISSION_CONFIG WHERE id = 1").fetchone())
        rows = connection.execute(
            """SELECT s.name AS subsystem, c.name, c.power_draw_mW, c.is_payload
               FROM COMPONENT c JOIN SUBSYSTEM s ON s.id = c.subsystem_id
               ORDER BY s.id, c.id"""
        ).fetchall()
    if selected_cell_count is not None:
        config["selected_cell_count"] = selected_cell_count
    components = [dict(row) for row in rows]
    total_mw = sum(component["power_draw_mW"] for component in components)
    total_w = total_mw / 1000
    generated_w = config["selected_cell_count"] * config["solar_cell_power_W"]
    margin_w = generated_w - total_w
    energy_orbit_mwh = total_w * config["orbit_duration_hours"] * 1000
    subsystem_draw = {}
    for component in components:
        subsystem_draw[component["subsystem"]] = subsystem_draw.get(component["subsystem"], 0) + component["power_draw_mW"]
    ranked = sorted(components, key=lambda item: item["power_draw_mW"], reverse=True)
    for component in ranked:
        component["energy_per_orbit_mWh"] = component["power_draw_mW"] / 1000 * config["orbit_duration_hours"] * 1000
    return {
        "config": config,
        "components": components,
        "total_power_mW": round(total_mw, 2),
        "total_power_W": round(total_w, 4),
        "generated_power_W": round(generated_w, 4),
        "power_margin_W": round(margin_w, 4),
        "energy_per_orbit_mWh": round(energy_orbit_mwh, 2),
        "orbits_per_day": config["orbits_per_day"],
        "energy_per_day_mWh": round(energy_orbit_mwh * config["orbits_per_day"], 2),
        "subsystem_draw_mW": {name: round(value, 2) for name, value in subsystem_draw.items()},
        "top_components": ranked[:6],
    }


@router.get("/power-budget")
def get_power_budget():
    return build_power_budget()


@router.patch("/mission-config")
def update_mission_config(patch: MissionConfigPatch):
    with db_session() as connection:
        connection.execute(
            "UPDATE MISSION_CONFIG SET selected_cell_count = ? WHERE id = 1",
            (patch.selected_cell_count,),
        )
    return build_power_budget()


@router.get("/telemetry/latest")
def get_latest_telemetry():
    with db_session() as connection:
        frame = connection.execute("SELECT * FROM FRAME ORDER BY id DESC LIMIT 1").fetchone()
        if frame is None:
            return {"frame": None}
        readings = connection.execute(
            """SELECT c.name, c.unit, r.value FROM READING r
               JOIN CHANNEL c ON c.id = r.channel_id WHERE r.frame_id = ?""",
            (frame["id"],),
        ).fetchall()
    return {"frame": dict(frame), "readings": {row["name"]: {"value": row["value"], "unit": row["unit"]} for row in readings}}


@router.get("/telemetry/history")
def get_telemetry_history(limit: int = Query(default=30, ge=1, le=500)):
    with db_session() as connection:
        frames = connection.execute(
            "SELECT id, received_at, sequence_number, rssi, link_status FROM FRAME ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result = []
        for frame in reversed(frames):
            readings = connection.execute(
                "SELECT c.name, r.value, c.unit FROM READING r JOIN CHANNEL c ON c.id = r.channel_id WHERE r.frame_id = ?",
                (frame["id"],),
            ).fetchall()
            result.append({**dict(frame), "readings": {row["name"]: {"value": row["value"], "unit": row["unit"]} for row in readings}})
    return {"frames": result}
