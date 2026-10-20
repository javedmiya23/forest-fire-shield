from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI

from .config import get_settings
from .database import engine


settings = get_settings()


@dataclass
class TelemetryState:
    enabled: bool = False
    status: str = "disabled"
    detail: str | None = None
    instrumented: bool = False
    tracer_provider: object | None = None
    meter_provider: object | None = None
    ws_connections: object | None = None
    ws_messages_sent: object | None = None
    sensor_packets_ingested: object | None = None
    alarm_packets_ingested: object | None = None


telemetry_state = TelemetryState()


def initialize_telemetry(app: FastAPI) -> TelemetryState:
    if telemetry_state.instrumented:
        return telemetry_state

    if not settings.otel_enabled:
        telemetry_state.enabled = False
        telemetry_state.status = "disabled"
        telemetry_state.detail = "Set OTEL_ENABLED=true to export traces and metrics to Grafana."
        return telemetry_state

    try:
        from opentelemetry import metrics, trace
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        telemetry_state.enabled = False
        telemetry_state.status = "unavailable"
        telemetry_state.detail = f"OpenTelemetry packages are missing: {exc}"
        return telemetry_state

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.namespace": settings.otel_service_namespace,
            "deployment.environment": settings.otel_environment,
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_traces_endpoint)
        )
    )
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=settings.otel_exporter_otlp_metrics_endpoint),
        export_interval_millis=settings.otel_metric_export_interval_ms,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    FastAPIInstrumentor.instrument_app(app, excluded_urls="/health")
    SQLAlchemyInstrumentor().instrument(engine=engine)
    HTTPXClientInstrumentor().instrument()

    meter = metrics.get_meter(settings.otel_service_name)
    telemetry_state.ws_connections = meter.create_up_down_counter(
        "forest_fire_ws_connections",
        description="Current active live WebSocket connections.",
    )
    telemetry_state.ws_messages_sent = meter.create_counter(
        "forest_fire_ws_messages_sent_total",
        description="Total live stream messages pushed to dashboard clients.",
    )
    telemetry_state.sensor_packets_ingested = meter.create_counter(
        "forest_fire_sensor_packets_total",
        description="Total ESP32 payloads accepted by the backend.",
    )
    telemetry_state.alarm_packets_ingested = meter.create_counter(
        "forest_fire_alarm_packets_total",
        description="Total ESP32 payloads flagged as alarm packets.",
    )

    telemetry_state.enabled = True
    telemetry_state.status = "enabled"
    telemetry_state.detail = (
        f"Exporting telemetry to {settings.otel_exporter_otlp_endpoint} "
        f"for Grafana at {settings.grafana_dashboard_url}."
    )
    telemetry_state.instrumented = True
    telemetry_state.tracer_provider = tracer_provider
    telemetry_state.meter_provider = meter_provider
    return telemetry_state


def record_ws_connection(delta: int) -> None:
    counter = telemetry_state.ws_connections
    if telemetry_state.enabled and counter is not None:
        counter.add(delta)


def record_ws_message(count: int = 1) -> None:
    counter = telemetry_state.ws_messages_sent
    if telemetry_state.enabled and counter is not None:
        counter.add(count)


def record_ingest(alarm: bool) -> None:
    packets = telemetry_state.sensor_packets_ingested
    alarms = telemetry_state.alarm_packets_ingested
    if telemetry_state.enabled and packets is not None:
        packets.add(1)
    if telemetry_state.enabled and alarm and alarms is not None:
        alarms.add(1)


def shutdown_telemetry() -> None:
    tracer_provider = telemetry_state.tracer_provider
    meter_provider = telemetry_state.meter_provider
    try:
        if meter_provider is not None:
            meter_provider.shutdown()
    except Exception:
        pass

    try:
        if tracer_provider is not None:
            tracer_provider.shutdown()
    except Exception:
        pass

