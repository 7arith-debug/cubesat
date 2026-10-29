import math
import time

from backend.db.session import insert_frame
from backend.ingestion.parser import parse_eps_payload


def generate_mock_frame(sequence_number: int, elapsed_seconds: float) -> dict:
    cycle = (elapsed_seconds % 120) / 120
    sunlight = max(0.0, math.sin(cycle * math.tau))
    battery_soc = 58 + 28 * (0.5 - 0.5 * math.cos(cycle * math.tau))
    solar_voltage = 7.4 + sunlight * 1.2
    solar_current = sunlight * 0.34
    solar_power = solar_voltage * solar_current
    charging = sunlight > 0.08 and battery_soc < 84
    payload = parse_eps_payload(
        {
            "battery_voltage": 7.05 + battery_soc * 0.012,
            "battery_current": (0.12 + sunlight * 0.17) if charging else -(0.18 + (1 - sunlight) * 0.08),
            "battery_soc": battery_soc,
            "battery_temp": 24 + 3 * math.sin(elapsed_seconds / 17),
            "solar_voltage": solar_voltage,
            "solar_current": solar_current,
            "solar_power": solar_power,
            "charge_status": 1.0 if charging else 0.0,
        }
    )
    rssi = -72 + 8 * math.sin(elapsed_seconds / 9)
    return insert_frame(sequence_number, rssi, "LOCKED", payload)


def monotonic_seconds() -> float:
    return time.monotonic()
