from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from reksa_ai import __version__
from reksa_ai.contracts import (
    CombinedAnalysisRequest,
    CombinedAnalysisResponse,
    ForecastRequest,
    ForecastResponse,
    PriorityEvent,
    PriorityResponse,
)
from reksa_ai.inference import NearMissRiskForecaster, PriorityEngine


def _optional_path(environment_name: str) -> Path | None:
    value = os.getenv(environment_name)
    return Path(value) if value else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.forecaster = NearMissRiskForecaster(_optional_path("REKSA_FORECAST_MODEL"))
    app.state.priority_engine = PriorityEngine(_optional_path("REKSA_PRIORITY_MODEL"))
    yield


app = FastAPI(
    title="REKSA AI Advisory Service",
    version=__version__,
    description=(
        "Advisory inference for temporal risk forecasting and post-event supervisor prioritization. "
        "This service does not control local safety alarms or verify near-miss events."
    ),
    lifespan=lifespan,
)


@app.get("/health", tags=["System"])
async def health() -> dict[str, Any]:
    forecaster = app.state.forecaster
    priority_engine = app.state.priority_engine
    return {
        "status": "ok",
        "version": __version__,
        "safety_role": "ADVISORY_ONLY",
        "forecaster": {
            "mode": "TRAINED_MODEL" if forecaster.bundle else "RULE_BASED_BASELINE",
            "load_error": forecaster.load_error,
        },
        "priority_engine": {
            "mode": "TRAINED_MODEL" if priority_engine.bundle else "RULE_BASED_BASELINE",
            "load_error": priority_engine.load_error,
        },
    }


@app.post("/v1/forecast", response_model=ForecastResponse, tags=["Forecaster"])
async def forecast(payload: ForecastRequest) -> ForecastResponse:
    return app.state.forecaster.predict(payload)


@app.post("/v1/prioritize", response_model=PriorityResponse, tags=["Priority Engine"])
async def prioritize(payload: PriorityEvent) -> PriorityResponse:
    return app.state.priority_engine.predict(payload)


@app.post("/v1/analyze", response_model=CombinedAnalysisResponse, tags=["Supervisor"])
async def analyze(payload: CombinedAnalysisRequest) -> CombinedAnalysisResponse:
    forecast_result = (
        app.state.forecaster.predict(payload.current_window) if payload.current_window else None
    )
    priority_result = (
        app.state.priority_engine.predict(payload.completed_event)
        if payload.completed_event
        else None
    )
    return CombinedAnalysisResponse(
        forecast=forecast_result,
        priority_assessment=priority_result,
    )
