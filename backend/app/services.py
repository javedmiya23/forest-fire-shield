from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from .alert_service import dispatch_fire_alert
from .config import get_settings
from .live_stream import get_live_stream_manager
from .models import Device, FireEvent, SensorReading
from .schemas import (
    BooleanSensor,
    DashboardMetrics,
    DashboardSummary,
    DeviceStatus,
    FireEventSummary,
    FireLogic,
    GasChannel,
    GasSensors,
    IngestResponse,
    ReadingHistoryResponse,
    SensorPayload,
    SensorReadingSummary,
)
from .telemetry import record_ingest


settings = get_settings()
live_stream_manager = get_live_stream_manager()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def calculate_device_status(last_seen_at: datetime | None) -> tuple[str, int | None]:
    if last_seen_at is None:
        return "unknown", None

    seconds_since_last_seen = max(int((utcnow() - last_seen_at).total_seconds()), 0)
    if seconds_since_last_seen <= settings.device_connected_seconds:
        return "connected", seconds_since_last_seen
    if seconds_since_last_seen <= settings.device_warning_seconds:
        return "warning", seconds_since_last_seen
    return "disconnected", seconds_since_last_seen


def build_device_status(device: Device | None) -> DeviceStatus:
    device_id = device.device_code if device else settings.default_device_code
    last_seen_at = device.last_seen_at if device else None
    status, seconds_since_last_seen = calculate_device_status(last_seen_at)

    return DeviceStatus(
        device_id=device_id,
        status=status,
        last_seen_at=last_seen_at,
        seconds_since_last_seen=seconds_since_last_seen,
    )


def calculate_severity(payload: SensorPayload) -> int:
    score = 0.0

    for sensor_name, threshold in settings.sensor_thresholds.items():
        sensor = getattr(payload.gas_sensors, sensor_name)
        ratio = sensor.analog / threshold if threshold else 0
        score += min(ratio, 2.0) * 10
        if sensor.digital == 0:
            score += 5

    if payload.fire_logic.mq_fire:
        score += 15
    if payload.fire_logic.alarm:
        score += 10
    if payload.flame_sensor.detected:
        score += 35
    if payload.ir_sensor.detected:
        score += 10
    if payload.fire_logic.flame_fire:
        score += 10

    return min(int(round(score)), 100)


def build_fire_event_summary(fire_event: FireEvent | None) -> FireEventSummary | None:
    if fire_event is None:
        return None

    return FireEventSummary(
        id=fire_event.id,
        status=fire_event.status,
        trigger_type=fire_event.trigger_type,
        started_at=fire_event.started_at,
        last_alarm_at=fire_event.last_alarm_at,
        ended_at=fire_event.ended_at,
        max_severity=fire_event.max_severity,
        alert_sent=fire_event.alert_sent,
        notes=fire_event.notes,
    )


def build_sensor_reading_summary(reading: SensorReading, device_code: str) -> SensorReadingSummary:
    return SensorReadingSummary(
        id=reading.id,
        device_id=device_code,
        recorded_at=reading.recorded_at,
        severity_score=reading.severity_score,
        gas_sensors=GasSensors(
            mq2=GasChannel(analog=reading.mq2_analog, digital=reading.mq2_digital),
            mq4=GasChannel(analog=reading.mq4_analog, digital=reading.mq4_digital),
            mq7=GasChannel(analog=reading.mq7_analog, digital=reading.mq7_digital),
            mq135=GasChannel(analog=reading.mq135_analog, digital=reading.mq135_digital),
        ),
        flame_sensor=BooleanSensor(detected=reading.flame_detected),
        ir_sensor=BooleanSensor(detected=reading.ir_detected),
        fire_logic=FireLogic(
            mq_fire=reading.mq_fire,
            flame_fire=reading.flame_fire,
            alarm=reading.alarm,
            trigger=reading.trigger,
        ),
        fire_event_id=reading.fire_event_id,
    )


def build_live_sensor_event(
    *,
    reading: SensorReading,
    device: Device,
    device_status: DeviceStatus,
    fire_event: FireEvent | None,
    event_action: str,
) -> dict:
    reading_summary = build_sensor_reading_summary(reading, device.device_code)
    fire_event_summary = build_fire_event_summary(fire_event)
    return {
        "type": "sensor_update",
        "timestamp": reading.recorded_at.isoformat(),
        "event_action": event_action,
        "reading": reading_summary.model_dump(mode="json"),
        "device_status": device_status.model_dump(mode="json"),
        "fire_event": fire_event_summary.model_dump(mode="json") if fire_event_summary else None,
        "transport": "websocket",
    }


def get_or_create_device(db: Session, device_code: str, recorded_at: datetime) -> Device:
    device = db.scalar(select(Device).where(Device.device_code == device_code))
    if device is None:
        device = Device(
            device_code=device_code,
            status="connected",
            last_seen_at=recorded_at,
        )
        db.add(device)
        db.flush()
        return device

    device.last_seen_at = recorded_at
    device.status = "connected"
    db.add(device)
    db.flush()
    return device


def sync_fire_event(
    db: Session,
    device: Device,
    reading: SensorReading,
    payload: SensorPayload,
) -> tuple[str, FireEvent | None]:
    active_event = db.scalar(
        select(FireEvent)
        .where(FireEvent.device_id == device.id, FireEvent.status == "active")
        .order_by(FireEvent.started_at.desc())
    )

    if payload.fire_logic.alarm:
        if active_event is None:
            active_event = FireEvent(
                forest_id=device.forest_id,
                device_id=device.id,
                started_at=reading.recorded_at,
                last_alarm_at=reading.recorded_at,
                status="active",
                trigger_type=payload.fire_logic.trigger,
                max_severity=reading.severity_score,
            )
            db.add(active_event)
            db.flush()
            return "opened", active_event

        active_event.last_alarm_at = reading.recorded_at
        active_event.trigger_type = payload.fire_logic.trigger
        active_event.max_severity = max(active_event.max_severity or 0, reading.severity_score)
        db.add(active_event)
        db.flush()
        return "updated", active_event

    if active_event is None or active_event.last_alarm_at is None:
        return "none", None

    cooldown_seconds = int((reading.recorded_at - active_event.last_alarm_at).total_seconds())
    if cooldown_seconds >= settings.fire_cooldown_seconds:
        active_event.status = "resolved"
        active_event.ended_at = reading.recorded_at
        db.add(active_event)
        db.flush()
        return "resolved", active_event

    return "monitoring", active_event


def ingest_sensor_payload(db: Session, payload: SensorPayload) -> IngestResponse:
    recorded_at = utcnow()
    device = get_or_create_device(db, payload.device_id, recorded_at)
    severity_score = calculate_severity(payload)

    reading = SensorReading(
        device_id=device.id,
        recorded_at=recorded_at,
        timestamp_ms=payload.timestamp_ms,
        mq2_analog=payload.gas_sensors.mq2.analog,
        mq2_digital=payload.gas_sensors.mq2.digital,
        mq4_analog=payload.gas_sensors.mq4.analog,
        mq4_digital=payload.gas_sensors.mq4.digital,
        mq7_analog=payload.gas_sensors.mq7.analog,
        mq7_digital=payload.gas_sensors.mq7.digital,
        mq135_analog=payload.gas_sensors.mq135.analog,
        mq135_digital=payload.gas_sensors.mq135.digital,
        flame_detected=payload.flame_sensor.detected,
        ir_detected=payload.ir_sensor.detected,
        mq_fire=payload.fire_logic.mq_fire,
        flame_fire=payload.fire_logic.flame_fire,
        alarm=payload.fire_logic.alarm,
        trigger=payload.fire_logic.trigger,
        severity_score=severity_score,
        raw_payload=payload.model_dump(),
    )
    db.add(reading)
    db.flush()

    event_action, fire_event = sync_fire_event(db, device, reading, payload)
    if fire_event is not None:
        reading.fire_event_id = fire_event.id
        db.add(reading)

    device_status = build_device_status(device)
    db.commit()
    record_ingest(payload.fire_logic.alarm)

    if fire_event is not None:
        fire_event = dispatch_fire_alert(
            db,
            fire_event=fire_event,
            device=device,
            reading=reading,
        )

    live_stream_manager.broadcast_nowait(
        build_live_sensor_event(
            reading=reading,
            device=device,
            device_status=device_status,
            fire_event=fire_event,
            event_action=event_action,
        )
    )

    return IngestResponse(
        status="accepted",
        device_id=device.device_code,
        received_at=recorded_at,
        reading_id=reading.id,
        event_action=event_action,
        device_status=device_status,
        fire_event=build_fire_event_summary(fire_event),
    )


def get_latest_device(db: Session) -> Device | None:
    return db.scalar(select(Device).order_by(Device.last_seen_at.desc().nullslast()))


def get_active_fire_event(db: Session) -> FireEvent | None:
    return db.scalar(
        select(FireEvent)
        .where(FireEvent.status == "active")
        .order_by(FireEvent.started_at.desc())
    )


def get_latest_fire_event(db: Session) -> FireEvent | None:
    return db.scalar(
        select(FireEvent)
        .order_by(FireEvent.updated_at.desc(), FireEvent.id.desc())
    )


def get_latest_reading(db: Session) -> SensorReading | None:
    return db.scalar(
        select(SensorReading)
        .options(joinedload(SensorReading.device))
        .order_by(SensorReading.recorded_at.desc())
    )


def get_readings_history(db: Session, limit: int = 50, alarm_only: bool = False) -> list[SensorReading]:
    statement = (
        select(SensorReading)
        .options(joinedload(SensorReading.device))
        .order_by(SensorReading.recorded_at.desc())
        .limit(limit)
    )
    if alarm_only:
        statement = statement.where(SensorReading.alarm.is_(True))
    return list(db.scalars(statement))


def get_readings_count(
    db: Session,
    *,
    since: datetime | None = None,
    alarm_only: bool = False,
) -> int:
    statement = select(func.count(SensorReading.id))
    if since is not None:
        statement = statement.where(SensorReading.recorded_at >= since)
    if alarm_only:
        statement = statement.where(SensorReading.alarm.is_(True))
    return int(db.scalar(statement) or 0)


def get_average_severity(db: Session, *, since: datetime | None = None) -> float | None:
    statement = select(func.avg(SensorReading.severity_score))
    if since is not None:
        statement = statement.where(SensorReading.recorded_at >= since)

    value = db.scalar(statement)
    if value is None:
        return None
    return round(float(value), 2)


def get_max_severity(db: Session, *, since: datetime | None = None) -> int | None:
    statement = select(func.max(SensorReading.severity_score))
    if since is not None:
        statement = statement.where(SensorReading.recorded_at >= since)

    value = db.scalar(statement)
    if value is None:
        return None
    return int(value)


def get_latest_alarm_at(db: Session) -> datetime | None:
    return db.scalar(
        select(SensorReading.recorded_at)
        .where(SensorReading.alarm.is_(True))
        .order_by(SensorReading.recorded_at.desc())
        .limit(1)
    )


def build_reading_history_response(
    db: Session,
    *,
    limit: int = 50,
    alarm_only: bool = False,
) -> ReadingHistoryResponse:
    readings = get_readings_history(db, limit=limit, alarm_only=alarm_only)
    items = [
        build_sensor_reading_summary(reading, reading.device.device_code)
        for reading in readings
    ]
    total = get_readings_count(db, alarm_only=alarm_only)

    return ReadingHistoryResponse(
        items=items,
        total=total,
        limit=limit,
        alarm_only=alarm_only,
    )


def build_dashboard_summary(db: Session) -> DashboardSummary:
    generated_at = utcnow()
    last_24_hours = generated_at - timedelta(hours=24)

    latest_device = get_latest_device(db)
    latest_reading = get_latest_reading(db)
    active_fire_event = get_active_fire_event(db)
    latest_fire_event = get_latest_fire_event(db)

    latest_reading_summary = None
    if latest_reading is not None:
        latest_reading_summary = build_sensor_reading_summary(
            latest_reading,
            latest_reading.device.device_code,
        )

    metrics = DashboardMetrics(
        total_readings=get_readings_count(db),
        readings_last_24h=get_readings_count(db, since=last_24_hours),
        alarm_readings_last_24h=get_readings_count(db, since=last_24_hours, alarm_only=True),
        average_severity_last_24h=get_average_severity(db, since=last_24_hours),
        max_severity_last_24h=get_max_severity(db, since=last_24_hours),
        latest_alarm_at=get_latest_alarm_at(db),
    )

    return DashboardSummary(
        generated_at=generated_at,
        device_status=build_device_status(latest_device),
        latest_reading=latest_reading_summary,
        active_fire_event=build_fire_event_summary(active_fire_event),
        latest_fire_event=build_fire_event_summary(latest_fire_event),
        metrics=metrics,
    )
