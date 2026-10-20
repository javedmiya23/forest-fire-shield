from datetime import datetime
from typing import Any

from pydantic import BaseModel


class GasChannel(BaseModel):
    analog: int
    digital: int


class GasSensors(BaseModel):
    mq2: GasChannel
    mq4: GasChannel
    mq7: GasChannel
    mq135: GasChannel


class BooleanSensor(BaseModel):
    detected: bool


class FireLogic(BaseModel):
    mq_fire: bool
    flame_fire: bool
    alarm: bool
    trigger: str


class SensorPayload(BaseModel):
    device_id: str
    timestamp_ms: int
    gas_sensors: GasSensors
    flame_sensor: BooleanSensor
    ir_sensor: BooleanSensor
    fire_logic: FireLogic


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime


class DeviceStatus(BaseModel):
    device_id: str
    status: str
    last_seen_at: datetime | None
    seconds_since_last_seen: int | None


class FireEventSummary(BaseModel):
    id: int
    status: str
    trigger_type: str | None
    started_at: datetime
    last_alarm_at: datetime | None
    ended_at: datetime | None
    max_severity: int | None
    alert_sent: bool = False
    notes: str | None = None


class SensorReadingSummary(BaseModel):
    id: int
    device_id: str
    recorded_at: datetime
    severity_score: int
    gas_sensors: GasSensors
    flame_sensor: BooleanSensor
    ir_sensor: BooleanSensor
    fire_logic: FireLogic
    fire_event_id: int | None


class IngestResponse(BaseModel):
    status: str
    device_id: str
    received_at: datetime
    reading_id: int
    event_action: str
    device_status: DeviceStatus
    fire_event: FireEventSummary | None


class ReadingHistoryResponse(BaseModel):
    items: list[SensorReadingSummary]
    total: int
    limit: int
    alarm_only: bool


class DashboardMetrics(BaseModel):
    total_readings: int
    readings_last_24h: int
    alarm_readings_last_24h: int
    average_severity_last_24h: float | None
    max_severity_last_24h: int | None
    latest_alarm_at: datetime | None


class CoordinateInput(BaseModel):
    latitude: float
    longitude: float


class CoordinateResponse(BaseModel):
    latitude: float
    longitude: float
    source: str | None = None


class WeatherCurrentResponse(BaseModel):
    captured_at: datetime
    source_name: str
    latitude: float
    longitude: float
    location_source: str
    temperature: float | None
    relative_humidity: float | None
    wind_speed: float | None
    wind_direction: float | None
    precipitation: float | None


class AutomationJobStatus(BaseModel):
    name: str
    status: str
    last_run_at: datetime | None
    last_success_at: datetime | None
    detail: str | None
    affected_count: int | None = None


class AutomationStatusResponse(BaseModel):
    enabled: bool
    poll_interval_seconds: int
    weather_refresh_interval_seconds: int
    fire_event_cleanup_interval_seconds: int
    device_status_sync_interval_seconds: int
    stale_fire_event_seconds: int
    worker_started_at: datetime | None = None
    weather_refresh: AutomationJobStatus
    fire_event_cleanup: AutomationJobStatus
    device_status_sync: AutomationJobStatus


class ObservabilityStatusResponse(BaseModel):
    enabled: bool
    status: str
    detail: str | None
    service_name: str
    service_namespace: str
    environment: str
    exporter_endpoint: str
    grafana_dashboard_url: str


class DashboardSummary(BaseModel):
    generated_at: datetime
    device_status: DeviceStatus
    latest_reading: SensorReadingSummary | None
    active_fire_event: FireEventSummary | None
    latest_fire_event: FireEventSummary | None
    metrics: DashboardMetrics
    weather: WeatherCurrentResponse | None = None


class FireSimulationAssumptions(BaseModel):
    model_type: str
    model_version: str
    simulation_mode: str
    horizon_hours: int
    cell_size_m: float
    active_burn_hours: int
    fuel_factor: float
    weather_factor: float
    severity_factor: float
    wind_push_direction: float | None
    notes: list[str]


class FireSimulationStepResponse(BaseModel):
    hour_offset: int
    estimated_area_m2: float
    spread_heading: float | None
    intensity_score: int
    active_cells: int
    burnt_cells: int
    affected_geojson: dict[str, Any]


class FireSimulationResponse(BaseModel):
    id: int
    generated_at: datetime
    model_version: str
    forest_id: int | None
    device_id: str | None
    fire_event_id: int | None
    ignition_point: CoordinateResponse
    weather: WeatherCurrentResponse | None
    assumptions: FireSimulationAssumptions
    steps: list[FireSimulationStepResponse]


class AnalysisSensorPeak(BaseModel):
    sensor: str
    max_analog: int
    digital_trigger_count: int


class FireAnalysisResponse(BaseModel):
    id: int
    generated_at: datetime
    report_status: str
    impact_level: str
    forest_name: str | None
    device_id: str | None
    fire_event_id: int | None
    simulation_id: int | None
    event_started_at: datetime | None
    event_ended_at: datetime | None
    event_duration_minutes: float | None
    peak_severity: int | None
    average_severity: float | None
    alarm_packet_count: int
    estimated_burnt_area_m2: float | None
    estimated_burnt_area_hectares: float | None
    forest_area_m2: float | None
    estimated_burn_ratio: float | None
    vegetation_loss_score: int
    habitat_impact_score: int
    likely_vegetation_damage: str
    likely_wildlife_impact: str
    spread_heading: float | None
    summary_text: str
    sensor_peaks: list[AnalysisSensorPeak]
    recommended_actions: list[str]


class ForestCreateRequest(BaseModel):
    name: str
    admin_email: str | None = None
    vegetation_type: str | None = None
    tree_density: str | None = None
    canopy_density: str | None = None
    fuel_load: str | None = None
    moisture_class: str | None = None
    boundary_geojson: dict[str, Any]
    sensor_location: CoordinateInput | None = None
    source_geojson: dict[str, Any] | None = None


class ForestGeoJsonSummary(BaseModel):
    feature_count: int
    point_features: int
    line_features: int
    polygon_features: int
    boundary_detected: bool
    sensor_detected: bool
    detected_layers: list[str]
    property_keys: list[str]
    missing_recommended_layers: list[str]


class ForestGeoJsonValidationResponse(BaseModel):
    is_compatible: bool
    message: str
    summary: ForestGeoJsonSummary
    boundary_geojson: dict[str, Any] | None
    sensor_location: CoordinateResponse | None


class ForestDetailResponse(BaseModel):
    id: int
    name: str
    center: CoordinateResponse
    vegetation_type: str | None
    tree_density: str | None
    canopy_density: str | None
    fuel_load: str | None
    moisture_class: str | None
    admin_email: str | None
    boundary_geojson: dict[str, Any] | None
    source_geojson: dict[str, Any] | None
    sensor_location: CoordinateResponse | None
    device_id: str | None
    geojson_summary: ForestGeoJsonSummary | None = None
