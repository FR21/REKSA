import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401
from app.api.v1.health import router as health_router
from app.api.v1.router import router as api_router
from app.core.config import settings
from app.database import Base, engine
from app.database.seed import seed_database
from app.database.session import SessionLocal
from app.services.mqtt_handler import handle_mqtt_message
from app.services.mqtt_service import MQTTService

mqtt_service = MQTTService(settings.mqtt_host, settings.mqtt_port, handler=handle_mqtt_message)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
    mqtt_service.loop = asyncio.get_running_loop()
    mqtt_service.start()
    yield
    mqtt_service.stop()


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
