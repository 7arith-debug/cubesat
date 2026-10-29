from typing import Any


def parse_eps_payload(payload: dict[str, Any]) -> dict[str, float]:
    """Normalize decoded EPS fields to the channel names stored in SQLite."""
    expected = (
        "battery_voltage",
        "battery_current",
        "battery_soc",
        "battery_temp",
        "solar_voltage",
        "solar_current",
        "solar_power",
        "charge_status",
    )
    missing = [name for name in expected if name not in payload]
    if missing:
        raise ValueError(f"EPS payload is missing fields: {', '.join(missing)}")
    return {name: float(payload[name]) for name in expected}
