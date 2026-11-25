import asyncio
import csv
import io
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from backend.database import initialize_database, list_experiments
from backend.models import Settings, Tower
from backend.simulation import Simulation
from backend.websocket_manager import WebSocketManager


ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

app = FastAPI(title="NetMotion", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

initialize_database()
simulation = Simulation()
websockets = WebSocketManager()


@app.on_event("startup")
async def startup():
    asyncio.create_task(simulation_loop())


async def simulation_loop():
    while True:
        if simulation.running:
            simulation.step()
            await websockets.broadcast({"type": "state", "state": simulation.state()})
        await asyncio.sleep(0.5)


@app.get("/api/state")
async def get_state():
    return simulation.state()


@app.post("/api/simulations/start")
async def start_simulation():
    simulation.start()
    return {"running": True}


@app.post("/api/simulations/pause")
async def pause_simulation():
    simulation.pause()
    return {"running": False}


@app.post("/api/simulations/resume")
async def resume_simulation():
    simulation.resume()
    return {"running": True}


@app.post("/api/simulations/reset")
async def reset_simulation():
    simulation.reset()
    return simulation.state()


@app.post("/api/settings")
async def update_settings(settings: Settings):
    simulation.update_settings(settings.model_dump())
    return simulation.state()


@app.post("/api/scenarios/{name}")
async def apply_scenario(name: str):
    valid = {"Normal Mobility", "High Congestion", "High-Speed Mobility", "Tower Failure", "Combined Scenario"}
    if name not in valid:
        raise HTTPException(status_code=400, detail="Unknown scenario")
    simulation.set_scenario(name)
    return simulation.state()


@app.post("/api/towers")
async def add_tower(tower: Tower):
    if any(item["id"] == tower.id for item in simulation.towers):
        raise HTTPException(status_code=409, detail="Tower ID already exists")
    simulation.towers.append(tower.model_dump())
    return simulation.state()


@app.delete("/api/towers/{tower_id}")
async def remove_tower(tower_id: str):
    tower = next((item for item in simulation.towers if item["id"] == tower_id), None)
    if tower is None:
        raise HTTPException(status_code=404, detail="Tower not found")
    simulation.towers.remove(tower)
    return simulation.state()


@app.patch("/api/towers/{tower_id}")
async def update_tower(tower_id: str, payload: dict):
    tower = next((item for item in simulation.towers if item["id"] == tower_id), None)
    if tower is None:
        raise HTTPException(status_code=404, detail="Tower not found")
    for key in ("x", "y", "capacity", "enabled", "name"):
        if key in payload:
            tower[key] = payload[key]
    return simulation.state()


@app.post("/api/users")
async def add_user():
    simulation.settings["user_count"] = min(200, int(simulation.settings["user_count"]) + 1)
    simulation._ensure_users()
    return simulation.state()


@app.delete("/api/users/{user_id}")
async def remove_user(user_id: str):
    user = next((item for item in simulation.users if item["id"] == user_id), None)
    if user is None:
        raise HTTPException(status_code=404, detail="Mobile user not found")
    simulation.users.remove(user)
    simulation.settings["user_count"] = len(simulation.users)
    return simulation.state()


@app.get("/api/analytics")
async def get_analytics():
    return simulation.state()


@app.post("/api/experiments")
async def save_experiment(payload: dict):
    name = payload.get("name") or f"Experiment {len(list_experiments()) + 1}"
    experiment_id, record = simulation.save_experiment(name)
    record["id"] = experiment_id
    return record


@app.get("/api/experiments")
async def get_experiments():
    return list_experiments()


@app.get("/api/experiments/export/csv")
async def export_csv():
    records = list_experiments()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Date", "Duration (s)", "Users", "Towers", "Scenario",
                     "Conventional Success %", "Mobility Success %"])
    for record in records:
        writer.writerow([
            record["id"], record["name"], record["created_at"], record["duration_seconds"],
            record["user_count"], record["tower_count"], record["scenario"],
            record["conventional_results"]["handover_success_rate"],
            record["mobility_results"]["handover_success_rate"],
        ])
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=netmotion-experiment-history.csv"},
    )


@app.get("/api/experiments/export/pdf")
async def export_pdf():
    records = list_experiments()
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    width, height = A4
    pdf.setTitle("NetMotion Experiment Report")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, height - 50, "NetMotion - Experiment Report")
    pdf.setFont("Helvetica", 10)
    y = height - 80
    if not records:
        pdf.drawString(50, y, "No simulation experiments saved.")
    for record in records[:20]:
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(50, y, f"{record['id']}. {record['name']} - {record['scenario']}")
        y -= 16
        pdf.setFont("Helvetica", 9)
        pdf.drawString(50, y, f"Date: {record['created_at']} | Duration: {record['duration_seconds']} s")
        y -= 14
        pdf.drawString(50, y,
                       f"Conventional success: {record['conventional_results']['handover_success_rate']}% "
                       f"| Mobility-aware success: {record['mobility_results']['handover_success_rate']}%")
        y -= 24
        if y < 60:
            pdf.showPage()
            y = height - 60
    pdf.save()
    output.seek(0)
    return StreamingResponse(output, media_type="application/pdf",
                             headers={"Content-Disposition": "attachment; filename=netmotion-report.pdf"})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websockets.connect(websocket)
    try:
        await websocket.send_json({"type": "state", "state": simulation.state()})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websockets.disconnect(websocket)


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return (FRONTEND / "index.html").read_text(encoding="utf-8")
