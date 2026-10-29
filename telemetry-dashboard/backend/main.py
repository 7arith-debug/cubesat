import asyncio
import json
import math
import struct
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.rest import router
from backend.api.ws import hub
from backend.config import FRONTEND_DIR, MOCK_FRAME_INTERVAL_SECONDS
from backend.db.session import db_session, initialize_database
from backend.ingestion.listener import generate_mock_frame, monotonic_seconds


def create_placeholder_glb(path: Path) -> None:
    generator = "Horizon-1 CubeSat dashboard placeholder"
    if path.exists():
        try:
            with path.open("rb") as asset_file:
                header = asset_file.read(20)
                if header[:4] != b"glTF":
                    return
                json_length = struct.unpack_from("<I", header, 12)[0]
                metadata = json.loads(asset_file.read(json_length).decode("utf-8"))
            if metadata.get("asset", {}).get("generator") != generator:
                return
        except (OSError, ValueError, struct.error):
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    material_specs = {
        "frame": ([0.025, 0.027, 0.032, 1], 0.04, 0.78),
        "panel": ([0.32, 0.33, 0.35, 1], 0.08, 0.72),
        "steel": ([0.34, 0.36, 0.4, 1], 0.72, 0.3),
        "black": ([0.018, 0.022, 0.03, 1], 0.28, 0.32),
        "port": ([0.035, 0.11, 0.13, 1], 0.55, 0.34),
        "gold": ([0.56, 0.38, 0.13, 1], 0.72, 0.29),
    }
    geometry = {name: {"positions": [], "normals": []} for name in material_specs}

    def add_triangle(material: str, points: tuple, normal: tuple) -> None:
        first, second, third = points
        edge_a = tuple(second[index] - first[index] for index in range(3))
        edge_b = tuple(third[index] - first[index] for index in range(3))
        cross = (
            edge_a[1] * edge_b[2] - edge_a[2] * edge_b[1],
            edge_a[2] * edge_b[0] - edge_a[0] * edge_b[2],
            edge_a[0] * edge_b[1] - edge_a[1] * edge_b[0],
        )
        if sum(cross[index] * normal[index] for index in range(3)) < 0:
            second, third = third, second
        entry = geometry[material]
        for point in (first, second, third):
            entry["positions"].extend(point)
            entry["normals"].extend(normal)

    def add_box(material: str, low: tuple, high: tuple) -> None:
        x0, y0, z0 = low
        x1, y1, z1 = high
        faces = (
            ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0, 0, 1)),
            ((x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (0, 0, -1)),
            ((x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (1, 0, 0)),
            ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (-1, 0, 0)),
            ((x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0), (0, 1, 0)),
            ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0)),
        )
        for first, second, third, fourth, normal in faces:
            add_triangle(material, (first, second, third), normal)
            add_triangle(material, (first, third, fourth), normal)

    def add_cylinder(material: str, center: tuple, radius: float, depth: float, axis: str, segments: int = 20) -> None:
        axis_index = {"x": 0, "y": 1, "z": 2}[axis]
        start = list(center)
        end = list(center)
        start[axis_index] -= depth / 2
        end[axis_index] += depth / 2
        ring_indices = [index for index in range(3) if index != axis_index]
        for index in range(segments):
            angle_a = index * 6.283185307179586 / segments
            angle_b = (index + 1) * 6.283185307179586 / segments
            radial_a = [0.0, 0.0, 0.0]
            radial_b = [0.0, 0.0, 0.0]
            radial_a[ring_indices[0]] = radius * math.cos(angle_a)
            radial_a[ring_indices[1]] = radius * math.sin(angle_a)
            radial_b[ring_indices[0]] = radius * math.cos(angle_b)
            radial_b[ring_indices[1]] = radius * math.sin(angle_b)
            start_a = tuple(start[axis] + radial_a[axis] for axis in range(3))
            start_b = tuple(start[axis] + radial_b[axis] for axis in range(3))
            end_a = tuple(end[axis] + radial_a[axis] for axis in range(3))
            end_b = tuple(end[axis] + radial_b[axis] for axis in range(3))
            mid_angle = (angle_a + angle_b) / 2
            outward = [0.0, 0.0, 0.0]
            outward[ring_indices[0]] = math.cos(mid_angle)
            outward[ring_indices[1]] = math.sin(mid_angle)
            outward = tuple(outward)
            add_triangle(material, (start_a, end_a, end_b), outward)
            add_triangle(material, (start_a, end_b, start_b), outward)
            axis_normal = [0.0, 0.0, 0.0]
            axis_normal[axis_index] = 1.0
            add_triangle(material, (tuple(end), end_a, end_b), tuple(axis_normal))
            axis_normal[axis_index] = -1.0
            add_triangle(material, (tuple(start), start_b, start_a), tuple(axis_normal))

    # 1U enclosure: side panels sit between four full-height corner rails.
    add_box("frame", (-1, 1.075, -1), (1, 1.135, 1))
    add_box("frame", (-1, -1.135, -1), (1, -1.075, 1))
    for x_sign in (-1, 1):
        for z_sign in (-1, 1):
            add_box(
                "frame",
                (x_sign * 1.0 - (0.16 if x_sign > 0 else 0), -1.075, z_sign * 1.0 - (0.16 if z_sign > 0 else 0)),
                (x_sign * 1.0 if x_sign > 0 else -0.84, 1.075, z_sign * 1.0 if z_sign > 0 else -0.84),
            )
    add_box("panel", (-0.84, -1.075, 0.962), (0.84, 1.075, 0.984))
    add_box("panel", (-0.84, -1.075, -0.984), (0.84, 1.075, -0.962))
    add_box("panel", (0.962, -1.075, -0.84), (0.984, 1.075, 0.84))
    add_box("panel", (-0.984, -1.075, -0.84), (-0.962, 1.075, 0.84))

    def add_front_port(center_x: float, center_y: float, width: float, height: float) -> None:
        x0, x1 = center_x - width / 2, center_x + width / 2
        y0, y1 = center_y - height / 2, center_y + height / 2
        add_box("black", (x0, y0, 0.984), (x1, y1, 0.993))
        border = 0.018
        add_box("steel", (x0 - border, y0 - border, 0.991), (x1 + border, y0, 1.002))
        add_box("steel", (x0 - border, y1, 0.991), (x1 + border, y1 + border, 1.002))
        add_box("steel", (x0 - border, y0, 0.991), (x0, y1, 1.002))
        add_box("steel", (x1, y0, 0.991), (x1 + border, y1, 1.002))
        add_box("port", (center_x - width * 0.28, center_y - height * 0.18, 0.994), (center_x + width * 0.28, center_y + height * 0.12, 0.998))

    def add_side_port(center_z: float, center_y: float, width: float, height: float, x_sign: int) -> None:
        z0, z1 = center_z - width / 2, center_z + width / 2
        y0, y1 = center_y - height / 2, center_y + height / 2
        border = 0.018
        if x_sign > 0:
            black_x = (0.984, 0.993)
            rim_x = (0.991, 1.002)
            inset_x = (0.994, 0.998)
        else:
            black_x = (-0.993, -0.984)
            rim_x = (-1.002, -0.991)
            inset_x = (-0.998, -0.994)
        add_box("black", (black_x[0], y0, z0), (black_x[1], y1, z1))
        add_box("steel", (rim_x[0], y0 - border, z0 - border), (rim_x[1], y0, z1 + border))
        add_box("steel", (rim_x[0], y1, z0 - border), (rim_x[1], y1 + border, z1 + border))
        add_box("steel", (rim_x[0], y0, z0 - border), (rim_x[1], y1, z0))
        add_box("steel", (rim_x[0], y0, z1), (rim_x[1], y1, z1 + border))
        add_box("port", (inset_x[0], center_y - height * 0.18, center_z - width * 0.28), (inset_x[1], center_y + height * 0.12, center_z + width * 0.28))

    add_front_port(-0.4, 0.42, 0.24, 0.14)
    add_front_port(-0.4, -0.5, 0.24, 0.14)
    add_box("black", (-0.52, 0.35, -0.993), (-0.28, 0.49, -0.984))
    add_box("steel", (-0.538, 0.332, -1.002), (-0.262, 0.35, -0.991))
    add_box("steel", (-0.538, 0.49, -1.002), (-0.262, 0.508, -0.991))
    add_box("steel", (-0.538, 0.35, -1.002), (-0.52, 0.49, -0.991))
    add_box("steel", (-0.28, 0.35, -1.002), (-0.262, 0.49, -0.991))
    add_box("port", (-0.4672, 0.3748, -0.998), (-0.3328, 0.4668, -0.994))
    add_box("black", (-0.52, -0.57, -0.993), (-0.28, -0.43, -0.984))
    add_box("steel", (-0.538, -0.588, -1.002), (-0.262, -0.57, -0.991))
    add_box("steel", (-0.538, -0.43, -1.002), (-0.262, -0.412, -0.991))
    add_box("steel", (-0.538, -0.57, -1.002), (-0.52, -0.43, -0.991))
    add_box("steel", (-0.28, -0.57, -1.002), (-0.262, -0.43, -0.991))
    add_box("port", (-0.4672, -0.5452, -0.998), (-0.3328, -0.4532, -0.994))
    add_side_port(-0.22, 0.12, 0.26, 0.18, 1)
    add_side_port(0.34, -0.02, 0.26, 0.18, 1)

    # Four fasteners per side panel plus the top-plate corner screws.
    for x in (-0.72, 0.72):
        for y in (-0.91, 0.91):
            add_cylinder("steel", (x, y, 0.994), 0.032, 0.025, "z")
            add_box("black", (x - 0.014, y - 0.003, 1.007), (x + 0.014, y + 0.003, 1.009))
            add_cylinder("steel", (x, y, -0.994), 0.032, 0.025, "z")
    for z in (-0.72, 0.72):
        for y in (-0.91, 0.91):
            add_cylinder("steel", (0.994, y, z), 0.032, 0.025, "x")
            add_cylinder("steel", (-0.994, y, z), 0.032, 0.025, "x")
    for x in (-0.83, 0.83):
        for z in (-0.83, 0.83):
            add_cylinder("steel", (x, 1.139, z), 0.035, 0.022, "y")

    # Antenna base, short brass collar, and dark whip on the top plate.
    antenna_x, antenna_z = 0.28, -0.23
    add_cylinder("gold", (antenna_x, 1.164, antenna_z), 0.095, 0.045, "y", 28)
    add_cylinder("black", (antenna_x, 1.2, antenna_z), 0.061, 0.035, "y", 24)
    add_cylinder("black", (antenna_x, 1.49, antenna_z), 0.038, 0.56, "y", 24)

    # A small protruding service switch on the lower-right of the front face.
    add_cylinder("black", (0.42, -0.72, 1.01), 0.082, 0.055, "z")
    add_cylinder("steel", (0.42, -0.72, 1.055), 0.045, 0.06, "z")
    add_cylinder("black", (0.42, -0.72, 1.102), 0.066, 0.035, "z")
    add_cylinder("black", (0.42, -0.72, -1.01), 0.082, 0.055, "z")
    add_cylinder("steel", (0.42, -0.72, -1.055), 0.045, 0.06, "z")
    add_cylinder("black", (0.42, -0.72, -1.102), 0.066, 0.035, "z")

    binary = bytearray()
    buffer_views = []
    accessors = []
    primitives = []
    materials = []
    for material_index, (name, spec) in enumerate(material_specs.items()):
        positions = geometry[name]["positions"]
        normals = geometry[name]["normals"]
        if not positions:
            continue
        position_bytes = struct.pack(f"<{len(positions)}f", *positions)
        position_offset = len(binary)
        binary.extend(position_bytes)
        buffer_views.append({"buffer": 0, "byteOffset": position_offset, "byteLength": len(position_bytes), "target": 34962})
        position_view = len(buffer_views) - 1
        normal_bytes = struct.pack(f"<{len(normals)}f", *normals)
        normal_offset = len(binary)
        binary.extend(normal_bytes)
        buffer_views.append({"buffer": 0, "byteOffset": normal_offset, "byteLength": len(normal_bytes), "target": 34962})
        normal_view = len(buffer_views) - 1
        vertex_count = len(positions) // 3
        xs, ys, zs = positions[0::3], positions[1::3], positions[2::3]
        accessors.append({"bufferView": position_view, "componentType": 5126, "count": vertex_count, "type": "VEC3", "min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]})
        position_accessor = len(accessors) - 1
        accessors.append({"bufferView": normal_view, "componentType": 5126, "count": vertex_count, "type": "VEC3"})
        normal_accessor = len(accessors) - 1
        base_color, metallic, roughness = spec
        materials.append({"pbrMetallicRoughness": {"baseColorFactor": base_color, "metallicFactor": metallic, "roughnessFactor": roughness}})
        primitives.append({"attributes": {"POSITION": position_accessor, "NORMAL": normal_accessor}, "material": len(materials) - 1, "mode": 4})

    binary_length = len(binary)
    binary.extend(b"\x00" * ((4 - len(binary) % 4) % 4))
    gltf = {
        "asset": {"version": "2.0", "generator": generator},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": primitives}],
        "materials": materials,
        "buffers": [{"byteLength": binary_length}],
        "bufferViews": buffer_views,
        "accessors": accessors,
    }
    json_chunk = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_chunk += b" " * ((4 - len(json_chunk) % 4) % 4)
    total_length = 12 + 8 + len(json_chunk) + 8 + len(binary)
    path.write_bytes(
        struct.pack("<4sII", b"glTF", 2, total_length)
        + struct.pack("<I4s", len(json_chunk), b"JSON")
        + json_chunk
        + struct.pack("<I4s", len(binary), b"BIN\x00")
        + bytes(binary)
    )


async def mock_telemetry_loop(first_sequence_number: int) -> None:
    started = monotonic_seconds()
    sequence_number = first_sequence_number
    while True:
        frame = generate_mock_frame(sequence_number, monotonic_seconds() - started)
        await hub.broadcast(frame)
        sequence_number += 1
        await asyncio.sleep(MOCK_FRAME_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    create_placeholder_glb(FRONTEND_DIR / "assets" / "cubesat.glb")
    with db_session() as connection:
        next_sequence = connection.execute("SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM FRAME").fetchone()[0]
    task = asyncio.create_task(mock_telemetry_loop(next_sequence))
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Horizon-1 EPS Dashboard", version="1.0.0", lifespan=lifespan)
app.include_router(router)
app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets", check_dir=False), name="assets")


@app.get("/", include_in_schema=False)
def homepage():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/dashboard", include_in_schema=False)
def dashboard_page():
    return FileResponse(FRONTEND_DIR / "dashboard.html")


@app.websocket("/ws/telemetry")
async def telemetry_socket(websocket: WebSocket):
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(websocket)
