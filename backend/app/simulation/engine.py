from __future__ import annotations

from typing import Any

from app.services.websocket_service import websocket_manager
from app.simulation.state import build_state


class SimulationEngine:
    def __init__(self) -> None:
        self.state = build_state(42)
        self._near_miss_created = False

    async def reset(self) -> None:
        self._near_miss_created = False
        self.state = build_state(42)
        await websocket_manager.broadcast("simulation.status_changed", self.get_status())
        await websocket_manager.broadcast("worker.updated", {"workers": self.state["workers"]})

    def get_status(self) -> dict[str, Any]:
        return {
            "status": "READY",
            "workers": len(self.state["workers"]),
            "devices": len(self.state["devices"]),
            "hazards": len(self.state["hazards"]),
            "simulation_data": True,
        }


simulation_engine = SimulationEngine()
