from dataclasses import dataclass


@dataclass(frozen=True)
class TelemetryValue:
    name: str
    unit: str
    value: float


@dataclass(frozen=True)
class TelemetryFrame:
    sequence_number: int
    received_at: str
    rssi: float
    link_status: str
    readings: list[TelemetryValue]
