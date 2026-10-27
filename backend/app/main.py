import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401
from app.api.v1.cloud_ingest import router as cloud_ingest_router
from app.api.v1.health import router as health_router
from app.api.v1.router import router as api_router
from app.core.config import settings
from app.database import Base, engine
from app.database.seed import seed_database
from app.database.session import SessionLocal
from app.services.mqtt_handler import handle_mqtt_message
from app.services.mqtt_service import MQTTService
from app.services.runtime import ai_advisory_service
from app.services.websocket_service import websocket_manager
from app.simulation.engine import simulation_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def check_inactivity_once() -> None:
    from app.api.v1.router import SYSTEM_SETTINGS, sync_today_history
    now = datetime.now(UTC)
    timeout_seconds = SYSTEM_SETTINGS.get("device_offline_timeout", 30)
    threshold = timedelta(seconds=timeout_seconds)
    
    try:
        sync_today_history()
    except Exception:
        pass
    
    for device in simulation_engine.state.get("devices", []):
        is_hw = device.get("hardware_source") or "DEV-HLM-W01" in device.get("id", "")
        if is_hw and device.get("online") and device.get("last_seen"):
            try:
                last_seen = datetime.fromisoformat(device["last_seen"])
                if now - last_seen > threshold:
                    device["online"] = False
                    device["signal"] = 0
                    await websocket_manager.broadcast("device.paired", device)
            except Exception:
                pass
    
    for worker in simulation_engine.state.get("workers", []):
        is_hw = worker.get("hardware_source") or worker.get("calculation_source") == "HARDWARE_MQTT"
        if is_hw and worker.get("online") and worker.get("last_update"):
            try:
                last_update = datetime.fromisoformat(worker["last_update"])
                if now - last_update > threshold:
                    worker["online"] = False
                    worker["risk_level"] = "SAFE"
                    worker["risk_score"] = 0
                    worker["proximity"] = "SAFE"
                    worker["closest_hazard"] = None
                    worker["hazard_name"] = "-"
                    worker["hazard_status"] = "INACTIVE"
                    worker["dominant_factor"] = "Perangkat Offline"
                    worker["recommended_action"] = "Helm keselamatan offline. Pastikan daya perangkat aktif."
                    await websocket_manager.broadcast("worker.updated", worker)
            except Exception:
                pass

    for hazard in simulation_engine.state.get("hazards", []):
        if hazard.get("hardware_source") and hazard.get("online") and hazard.get("last_update"):
            try:
                last_update = datetime.fromisoformat(hazard["last_update"])
                if now - last_update > threshold:
                    hazard["online"] = False
                    hazard["status"] = "INACTIVE"
                    await websocket_manager.broadcast("hazard.updated", hazard)
            except Exception:
                pass


async def monitor_inactivity() -> None:
    while True:
        await check_inactivity_once()
        await asyncio.sleep(5)

mqtt_service = MQTTService(
    settings.mqtt_host,
    settings.mqtt_port,
    handler=handle_mqtt_message,
    username=settings.mqtt_username,
    password=settings.mqtt_password,
    use_tls=settings.mqtt_tls,
    ca_cert=settings.mqtt_ca_cert,
    client_id=settings.mqtt_client_id,
    ack_enabled=settings.mqtt_ack_enabled,
    dedup_max_messages=settings.mqtt_dedup_max_messages,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_database(db)
    except Exception as exc:
        logging.getLogger(__name__).error("Failed during initial DB setup/seed: %s", exc)

    try:
        from app.api.v1.router import CURRENT_USER_PROFILE, SYSTEM_SETTINGS
        from app.services.db_service import db_service
        from app.simulation.engine import simulation_engine

        db_near_misses = db_service.load_near_misses_from_db()
        if db_near_misses:
            simulation_engine.state["near_misses"] = db_near_misses
        db_settings = db_service.load_settings_from_db()
        if db_settings:
            SYSTEM_SETTINGS.update(db_settings)
        db_profile = db_service.get_profile_sync()
        if db_profile:
            CURRENT_USER_PROFILE.update(db_profile)
    except Exception as exc:
        logging.getLogger(__name__).warning("Failed to warm state from DB: %s", exc)

    if settings.mqtt_enabled:
        mqtt_service.loop = asyncio.get_running_loop()
        mqtt_service.start()
    inactivity_task = asyncio.create_task(monitor_inactivity())
    yield
    inactivity_task.cancel()
    if settings.mqtt_enabled:
        mqtt_service.stop()
    await ai_advisory_service.close()


app = FastAPI(
    title="REKSA API",
    description="Radar Evaluasi K3 dan Sensor Ancaman Kerja",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(cloud_ingest_router, prefix=settings.api_prefix)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "REKSA API", "docs": "/docs", "health": "/api/v1/health"}


@app.websocket("/ws/live")
async def live_websocket(websocket: WebSocket) -> None:
    from app.services.websocket_service import websocket_manager

    await websocket_manager.connect(websocket)
    try:
        await websocket.send_json({"event": "system.connection_changed", "data": {"status": "CONNECTED", "mode": "SIMULATION"}})
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({"event": "heartbeat", "data": {"status": "ok"}})
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket)
