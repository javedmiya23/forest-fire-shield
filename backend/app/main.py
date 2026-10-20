import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .automation_service import get_automation_status, start_automation_worker, stop_automation_worker
from .config import get_settings
from .database import get_db, initialize_database
from .analysis_service import build_fire_analysis_response, generate_fire_analysis, get_latest_impact_report
from .forest_service import (
    build_forest_detail_response,
    create_or_update_forest,
    create_or_update_forest_from_geojson,
    get_current_forest,
    validate_geojson_payload,
)
from .live_stream import get_live_stream_manager
from .schemas import (
    AutomationStatusResponse,
    DashboardSummary,
    DeviceStatus,
    FireAnalysisResponse,
    FireEventSummary,
    ForestCreateRequest,
    ForestDetailResponse,
    ForestGeoJsonValidationResponse,
    FireSimulationResponse,
    HealthResponse,
    IngestResponse,
    ObservabilityStatusResponse,
    ReadingHistoryResponse,
    SensorPayload,
    SensorReadingSummary,
    WeatherCurrentResponse,
)
from .report_service import build_latest_analysis_pdf
from .simulation_service import get_latest_fire_simulation, run_fire_simulation, build_fire_simulation_response
from .telemetry import initialize_telemetry, shutdown_telemetry, telemetry_state
from .services import (
    build_dashboard_summary,
    build_device_status,
    build_fire_event_summary,
    build_reading_history_response,
    build_sensor_reading_summary,
    get_active_fire_event,
    get_latest_device,
    get_latest_reading,
    ingest_sensor_payload,
)
from .weather_service import get_current_weather


settings = get_settings()
live_stream_manager = get_live_stream_manager()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    initialize_telemetry(app)
    live_stream_manager.attach_loop(asyncio.get_running_loop())
    worker = start_automation_worker()
    try:
        yield
    finally:
        await stop_automation_worker(worker)
        await live_stream_manager.shutdown()
        shutdown_telemetry()


app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", timestamp=datetime.now(timezone.utc))


@app.post("/api/v1/ingest", response_model=IngestResponse)
def ingest_api(payload: SensorPayload, db: Session = Depends(get_db)) -> IngestResponse:
    return ingest_sensor_payload(db, payload)


@app.post("/data", response_model=IngestResponse)
def ingest_legacy(payload: SensorPayload, db: Session = Depends(get_db)) -> IngestResponse:
    return ingest_sensor_payload(db, payload)


@app.get("/api/v1/device-status", response_model=DeviceStatus)
def device_status(db: Session = Depends(get_db)) -> DeviceStatus:
    return build_device_status(get_latest_device(db))


@app.get("/api/v1/fire-events/active", response_model=FireEventSummary | None)
def active_fire_event(db: Session = Depends(get_db)) -> FireEventSummary | None:
    return build_fire_event_summary(get_active_fire_event(db))


@app.get("/api/v1/readings/latest", response_model=SensorReadingSummary | None)
def latest_reading(db: Session = Depends(get_db)) -> SensorReadingSummary | None:
    reading = get_latest_reading(db)
    if reading is None:
        return None
    return build_sensor_reading_summary(reading, reading.device.device_code)


@app.get("/api/v1/readings/history", response_model=ReadingHistoryResponse)
def readings_history(
    limit: int = Query(50, ge=1, le=500),
    alarm_only: bool = Query(False),
    db: Session = Depends(get_db),
) -> ReadingHistoryResponse:
    return build_reading_history_response(db, limit=limit, alarm_only=alarm_only)


@app.get("/api/v1/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    summary = build_dashboard_summary(db)
    summary.weather = get_current_weather(db)
    return summary


@app.get("/api/v1/system/automation", response_model=AutomationStatusResponse)
def automation_status() -> AutomationStatusResponse:
    return get_automation_status()


@app.get("/api/v1/system/observability", response_model=ObservabilityStatusResponse)
def observability_status() -> ObservabilityStatusResponse:
    return ObservabilityStatusResponse(
        enabled=telemetry_state.enabled,
        status=telemetry_state.status,
        detail=telemetry_state.detail,
        service_name=settings.otel_service_name,
        service_namespace=settings.otel_service_namespace,
        environment=settings.otel_environment,
        exporter_endpoint=settings.otel_exporter_otlp_endpoint,
        grafana_dashboard_url=settings.grafana_dashboard_url,
    )


@app.post("/api/v1/forests/create", response_model=ForestDetailResponse)
def create_forest(request: ForestCreateRequest, db: Session = Depends(get_db)) -> ForestDetailResponse:
    try:
        return create_or_update_forest(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/forests/upload-geojson", response_model=ForestDetailResponse)
async def upload_forest_geojson(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    admin_email: str | None = Form(None),
    vegetation_type: str | None = Form(None),
    tree_density: str | None = Form(None),
    canopy_density: str | None = Form(None),
    fuel_load: str | None = Form(None),
    moisture_class: str | None = Form(None),
    db: Session = Depends(get_db),
) -> ForestDetailResponse:
    try:
        source_geojson = json.loads((await file.read()).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Uploaded file is not valid GeoJSON JSON.") from exc

    try:
        return create_or_update_forest_from_geojson(
            db,
            source_geojson,
            file_name=file.filename,
            name=name,
            admin_email=admin_email,
            vegetation_type=vegetation_type,
            tree_density=tree_density,
            canopy_density=canopy_density,
            fuel_load=fuel_load,
            moisture_class=moisture_class,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/forests/validate-geojson", response_model=ForestGeoJsonValidationResponse)
async def validate_forest_geojson(file: UploadFile = File(...)) -> ForestGeoJsonValidationResponse:
    try:
        source_geojson = json.loads((await file.read()).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Uploaded file is not valid GeoJSON JSON.") from exc

    try:
        return validate_geojson_payload(source_geojson)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/forests/current", response_model=ForestDetailResponse | None)
def current_forest(db: Session = Depends(get_db)) -> ForestDetailResponse | None:
    forest = get_current_forest(db)
    if forest is None:
        return None
    return build_forest_detail_response(db, forest)


@app.get("/api/v1/weather/current", response_model=WeatherCurrentResponse | None)
def current_weather(
    force_refresh: bool = Query(False),
    db: Session = Depends(get_db),
) -> WeatherCurrentResponse | None:
    try:
        return get_current_weather(db, force_refresh=force_refresh)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Weather fetch failed: {exc}") from exc


@app.post("/api/v1/simulations/run", response_model=FireSimulationResponse)
def run_simulation(
    hours: int = Query(settings.simulation_default_hours, ge=1, le=24),
    cell_size_m: float = Query(settings.simulation_default_cell_size_m, ge=15, le=250),
    force_weather_refresh: bool = Query(False),
    db: Session = Depends(get_db),
) -> FireSimulationResponse:
    try:
        return run_fire_simulation(
            db,
            hours=hours,
            cell_size_m=cell_size_m,
            force_weather_refresh=force_weather_refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/simulations/latest", response_model=FireSimulationResponse | None)
def latest_simulation(db: Session = Depends(get_db)) -> FireSimulationResponse | None:
    simulation = get_latest_fire_simulation(db)
    if simulation is None:
        return None
    return build_fire_simulation_response(simulation)


@app.post("/api/v1/analysis/generate", response_model=FireAnalysisResponse)
def generate_analysis(db: Session = Depends(get_db)) -> FireAnalysisResponse:
    try:
        return generate_fire_analysis(db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/analysis/latest", response_model=FireAnalysisResponse | None)
def latest_analysis(db: Session = Depends(get_db)) -> FireAnalysisResponse | None:
    report = get_latest_impact_report(db)
    if report is None:
        return None
    return build_fire_analysis_response(report)


@app.get("/api/v1/analysis/latest/report.pdf")
def latest_analysis_pdf(db: Session = Depends(get_db)) -> Response:
    try:
        pdf_bytes, filename = build_latest_analysis_pdf(db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@app.websocket("/ws/live")
async def live_sensor_stream(websocket: WebSocket) -> None:
    await live_stream_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        live_stream_manager.disconnect(websocket)
    except Exception:
        live_stream_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )
