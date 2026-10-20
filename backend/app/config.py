from dataclasses import dataclass, field
from functools import lru_cache
from os import getenv
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_list(value: str | None, default: list[str]) -> list[str]:
    if value is None:
        return default
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]


@dataclass(frozen=True)
class Settings:
    app_name: str = getenv("APP_NAME", "Forest Fire Shield API")
    api_host: str = getenv("API_HOST", "0.0.0.0")
    api_port: int = int(getenv("API_PORT", "8000"))
    api_reload: bool = _as_bool(getenv("API_RELOAD"), True)
    cors_allowed_origins: list[str] = field(
        default_factory=lambda: _as_list(
            getenv("CORS_ALLOWED_ORIGINS"),
            [
                "http://localhost:4200",
                "http://127.0.0.1:4200",
            ],
        )
    )
    weather_api_url: str = getenv("WEATHER_API_URL", "https://api.open-meteo.com/v1/forecast")
    weather_cache_minutes: int = int(getenv("WEATHER_CACHE_MINUTES", "15"))
    database_url: str = getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/forest_fire_shield",
    )
    auto_create_schema: bool = _as_bool(getenv("AUTO_CREATE_SCHEMA"), True)
    postgis_required: bool = _as_bool(getenv("POSTGIS_REQUIRED"), True)
    device_connected_seconds: int = int(getenv("DEVICE_CONNECTED_SECONDS", "60"))
    device_warning_seconds: int = int(getenv("DEVICE_WARNING_SECONDS", "180"))
    fire_cooldown_seconds: int = int(getenv("FIRE_COOLDOWN_SECONDS", "30"))
    websocket_ping_interval_seconds: int = int(getenv("WEBSOCKET_PING_INTERVAL_SECONDS", "20"))
    background_jobs_enabled: bool = _as_bool(getenv("BACKGROUND_JOBS_ENABLED"), True)
    background_job_poll_seconds: int = int(getenv("BACKGROUND_JOB_POLL_SECONDS", "20"))
    weather_refresh_interval_seconds: int = int(
        getenv(
            "WEATHER_REFRESH_INTERVAL_SECONDS",
            str(max(int(getenv("WEATHER_CACHE_MINUTES", "15")) * 60, 300)),
        )
    )
    fire_event_cleanup_interval_seconds: int = int(
        getenv("FIRE_EVENT_CLEANUP_INTERVAL_SECONDS", "30")
    )
    device_status_sync_interval_seconds: int = int(
        getenv("DEVICE_STATUS_SYNC_INTERVAL_SECONDS", "20")
    )
    stale_fire_event_seconds: int = int(
        getenv(
            "STALE_FIRE_EVENT_SECONDS",
            str(max(int(getenv("FIRE_COOLDOWN_SECONDS", "30")) * 4, int(getenv("DEVICE_WARNING_SECONDS", "180")))),
        )
    )
    alert_email_enabled: bool = _as_bool(getenv("ALERT_EMAIL_ENABLED"), True)
    alert_email_subject_prefix: str = getenv("ALERT_EMAIL_SUBJECT_PREFIX", "[Forest Fire Shield]")
    alert_email_from: str = getenv("ALERT_EMAIL_FROM", "")
    alert_email_recipients: list[str] = field(
        default_factory=lambda: _as_list(getenv("ALERT_EMAIL_RECIPIENTS"), [])
    )
    alert_email_timeout_seconds: int = int(getenv("ALERT_EMAIL_TIMEOUT_SECONDS", "15"))
    smtp_host: str = getenv("SMTP_HOST", "")
    smtp_port: int = int(getenv("SMTP_PORT", "587"))
    smtp_username: str = getenv("SMTP_USERNAME", "")
    smtp_password: str = getenv("SMTP_PASSWORD", "")
    smtp_use_tls: bool = _as_bool(getenv("SMTP_USE_TLS"), True)
    smtp_use_ssl: bool = _as_bool(getenv("SMTP_USE_SSL"), False)
    otel_enabled: bool = _as_bool(getenv("OTEL_ENABLED"), False)
    otel_service_name: str = getenv("OTEL_SERVICE_NAME", "forest-fire-shield-api")
    otel_service_namespace: str = getenv("OTEL_SERVICE_NAMESPACE", "forest-fire-shield")
    otel_environment: str = getenv("OTEL_ENVIRONMENT", "development")
    otel_exporter_otlp_endpoint: str = getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    otel_exporter_otlp_traces_endpoint: str = getenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        f"{getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://127.0.0.1:4318').rstrip('/')}/v1/traces",
    )
    otel_exporter_otlp_metrics_endpoint: str = getenv(
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
        f"{getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://127.0.0.1:4318').rstrip('/')}/v1/metrics",
    )
    otel_metric_export_interval_ms: int = int(getenv("OTEL_METRIC_EXPORT_INTERVAL_MS", "10000"))
    grafana_dashboard_url: str = getenv("GRAFANA_DASHBOARD_URL", "http://localhost:3000")
    simulation_default_hours: int = int(getenv("SIMULATION_DEFAULT_HOURS", "6"))
    simulation_default_cell_size_m: int = int(getenv("SIMULATION_DEFAULT_CELL_SIZE_M", "45"))
    simulation_active_burn_hours: int = int(getenv("SIMULATION_ACTIVE_BURN_HOURS", "2"))
    simulation_max_cells: int = int(getenv("SIMULATION_MAX_CELLS", "3500"))
    default_device_code: str = getenv("DEFAULT_DEVICE_CODE", "FFS_ESP32_01")
    sensor_thresholds: dict[str, int] = field(
        default_factory=lambda: {
            "mq2": int(getenv("MQ2_ANALOG_THRESHOLD", "1100")),
            "mq4": int(getenv("MQ4_ANALOG_THRESHOLD", "2000")),
            "mq7": int(getenv("MQ7_ANALOG_THRESHOLD", "4000")),
            "mq135": int(getenv("MQ135_ANALOG_THRESHOLD", "2850")),
        }
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
