import type { Feature, FeatureCollection, GeoJsonProperties, Geometry } from 'geojson';

export interface GasChannel {
  analog: number;
  digital: number;
}

export interface GasSensors {
  mq2: GasChannel;
  mq4: GasChannel;
  mq7: GasChannel;
  mq135: GasChannel;
}

export interface BooleanSensor {
  detected: boolean;
}

export interface FireLogic {
  mq_fire: boolean;
  flame_fire: boolean;
  alarm: boolean;
  trigger: string;
}

export interface SensorReadingSummary {
  id: number;
  device_id: string;
  recorded_at: string;
  severity_score: number;
  gas_sensors: GasSensors;
  flame_sensor: BooleanSensor;
  ir_sensor: BooleanSensor;
  fire_logic: FireLogic;
  fire_event_id: number | null;
}

export interface DeviceStatus {
  device_id: string;
  status: string;
  last_seen_at: string | null;
  seconds_since_last_seen: number | null;
}

export interface FireEventSummary {
  id: number;
  status: string;
  trigger_type: string | null;
  started_at: string;
  last_alarm_at: string | null;
  ended_at: string | null;
  max_severity: number | null;
  alert_sent: boolean;
  notes: string | null;
}

export interface ReadingHistoryResponse {
  items: SensorReadingSummary[];
  total: number;
  limit: number;
  alarm_only: boolean;
}

export interface DashboardMetrics {
  total_readings: number;
  readings_last_24h: number;
  alarm_readings_last_24h: number;
  average_severity_last_24h: number | null;
  max_severity_last_24h: number | null;
  latest_alarm_at: string | null;
}

export interface CoordinateInput {
  latitude: number;
  longitude: number;
}

export interface CoordinateResponse extends CoordinateInput {
  source?: string | null;
}

export interface WeatherCurrentResponse {
  captured_at: string;
  source_name: string;
  latitude: number;
  longitude: number;
  location_source: string;
  temperature: number | null;
  relative_humidity: number | null;
  wind_speed: number | null;
  wind_direction: number | null;
  precipitation: number | null;
}

export interface AutomationJobStatus {
  name: string;
  status: string;
  last_run_at: string | null;
  last_success_at: string | null;
  detail: string | null;
  affected_count: number | null;
}

export interface AutomationStatus {
  enabled: boolean;
  poll_interval_seconds: number;
  weather_refresh_interval_seconds: number;
  fire_event_cleanup_interval_seconds: number;
  device_status_sync_interval_seconds: number;
  stale_fire_event_seconds: number;
  worker_started_at: string | null;
  weather_refresh: AutomationJobStatus;
  fire_event_cleanup: AutomationJobStatus;
  device_status_sync: AutomationJobStatus;
}

export interface ObservabilityStatus {
  enabled: boolean;
  status: string;
  detail: string | null;
  service_name: string;
  service_namespace: string;
  environment: string;
  exporter_endpoint: string;
  grafana_dashboard_url: string;
}

export interface DashboardSummary {
  generated_at: string;
  device_status: DeviceStatus;
  latest_reading: SensorReadingSummary | null;
  active_fire_event: FireEventSummary | null;
  latest_fire_event: FireEventSummary | null;
  metrics: DashboardMetrics;
  weather: WeatherCurrentResponse | null;
}

export interface LiveStreamEvent {
  type: string;
  status?: string;
  timestamp: string;
  transport?: string;
  connections?: number;
  event_action?: string;
  reading?: SensorReadingSummary | null;
  device_status?: DeviceStatus | null;
  fire_event?: FireEventSummary | null;
}

export interface FireSimulationAssumptions {
  model_type: string;
  model_version: string;
  simulation_mode: string;
  horizon_hours: number;
  cell_size_m: number;
  active_burn_hours: number;
  fuel_factor: number;
  weather_factor: number;
  severity_factor: number;
  wind_push_direction: number | null;
  notes: string[];
}

export interface FireSimulationStepResponse {
  hour_offset: number;
  estimated_area_m2: number;
  spread_heading: number | null;
  intensity_score: number;
  active_cells: number;
  burnt_cells: number;
  affected_geojson: GeometryPayload;
}

export interface FireSimulationResponse {
  id: number;
  generated_at: string;
  model_version: string;
  forest_id: number | null;
  device_id: string | null;
  fire_event_id: number | null;
  ignition_point: CoordinateResponse;
  weather: WeatherCurrentResponse | null;
  assumptions: FireSimulationAssumptions;
  steps: FireSimulationStepResponse[];
}

export interface AnalysisSensorPeak {
  sensor: string;
  max_analog: number;
  digital_trigger_count: number;
}

export interface FireAnalysisResponse {
  id: number;
  generated_at: string;
  report_status: string;
  impact_level: string;
  forest_name: string | null;
  device_id: string | null;
  fire_event_id: number | null;
  simulation_id: number | null;
  event_started_at: string | null;
  event_ended_at: string | null;
  event_duration_minutes: number | null;
  peak_severity: number | null;
  average_severity: number | null;
  alarm_packet_count: number;
  estimated_burnt_area_m2: number | null;
  estimated_burnt_area_hectares: number | null;
  forest_area_m2: number | null;
  estimated_burn_ratio: number | null;
  vegetation_loss_score: number;
  habitat_impact_score: number;
  likely_vegetation_damage: string;
  likely_wildlife_impact: string;
  spread_heading: number | null;
  summary_text: string;
  sensor_peaks: AnalysisSensorPeak[];
  recommended_actions: string[];
}

export type GeometryPayload = Geometry;
export type GeoJsonDocument = Geometry | Feature<Geometry, GeoJsonProperties> | FeatureCollection<Geometry, GeoJsonProperties>;

export interface ForestCreateRequest {
  name: string;
  admin_email?: string | null;
  vegetation_type?: string | null;
  tree_density?: string | null;
  canopy_density?: string | null;
  fuel_load?: string | null;
  moisture_class?: string | null;
  boundary_geojson: GeometryPayload;
  sensor_location?: CoordinateInput | null;
  source_geojson?: GeoJsonDocument | null;
}

export interface ForestGeoJsonSummary {
  feature_count: number;
  point_features: number;
  line_features: number;
  polygon_features: number;
  boundary_detected: boolean;
  sensor_detected: boolean;
  detected_layers: string[];
  property_keys: string[];
  missing_recommended_layers: string[];
}

export interface ForestGeoJsonValidationResponse {
  is_compatible: boolean;
  message: string;
  summary: ForestGeoJsonSummary;
  boundary_geojson: GeometryPayload | null;
  sensor_location: CoordinateResponse | null;
}

export interface ForestDetailResponse {
  id: number;
  name: string;
  center: CoordinateResponse;
  vegetation_type: string | null;
  tree_density: string | null;
  canopy_density: string | null;
  fuel_load: string | null;
  moisture_class: string | null;
  admin_email: string | null;
  boundary_geojson: GeometryPayload | null;
  source_geojson: GeoJsonDocument | null;
  sensor_location: CoordinateResponse | null;
  device_id: string | null;
  geojson_summary?: ForestGeoJsonSummary | null;
}
