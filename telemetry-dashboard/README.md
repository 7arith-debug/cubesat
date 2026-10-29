# Horizon-1 CubeSat Dashboard

A local, no-build dashboard for the Horizon-1 CubeSat prototype. The FastAPI app serves a model-viewer homepage and an EPS power-budget dashboard backed by SQLite and simulated live telemetry.

## Run locally

From this directory, create and activate a virtual environment, then install the backend requirements:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
uvicorn backend.main:app
```

Open `http://127.0.0.1:8000/` for the 3D homepage or `http://127.0.0.1:8000/dashboard` for the EPS dashboard. On first startup, the app creates and seeds `backend/telemetry.db`, creates a placeholder cube at `frontend/assets/cubesat.glb` if no model is present, and begins broadcasting simulated EPS frames. Replace the placeholder GLB with the CAD export at the same path to display the real assembly.

## API

- `GET /api/power-budget` returns mission configuration, component draws, subsystem totals, and derived orbit/day energy values.
- `PATCH /api/mission-config` accepts `{"selected_cell_count": 12}` and persists the solar-cell count.
- `GET /api/telemetry/latest` returns the latest stored frame and its readings.
- `GET /api/telemetry/history?limit=30` returns recent frames and readings.
- `WS /ws/telemetry` broadcasts every newly inserted frame.

The mock EPS values cycle through illumination and eclipse conditions. Replace `backend/ingestion/listener.py` with the radio/decoder adapter when hardware ingestion is ready.
