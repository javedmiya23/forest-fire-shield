from __future__ import annotations

import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Device, FireEvent, SensorReading


settings = get_settings()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dedupe_emails(addresses: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for address in addresses:
        normalized = address.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(address.strip())
    return unique


def _resolve_recipients(device: Device) -> list[str]:
    recipients: list[str] = []

    forest = device.forest
    if forest is not None and forest.admin_email:
        recipients.append(forest.admin_email)

    recipients.extend(settings.alert_email_recipients)
    return _dedupe_emails(recipients)


def _location_summary(device: Device) -> str:
    if device.location_geom is not None:
        sensor_point = to_shape(device.location_geom)
        return f"{float(sensor_point.y):.6f}, {float(sensor_point.x):.6f} (sensor point)"

    forest = device.forest
    if forest is not None and forest.center_lat is not None and forest.center_lon is not None:
        return f"{float(forest.center_lat):.6f}, {float(forest.center_lon):.6f} (forest centroid)"

    return "Forest location unavailable"


def _build_weather_lines(db: Session) -> list[str]:
    try:
        from .weather_service import get_current_weather

        weather = get_current_weather(db)
    except Exception:
        weather = None

    if weather is None:
        return ["Weather context: unavailable"]

    return [
        f"Weather source: {weather.source_name}",
        f"Temperature: {weather.temperature if weather.temperature is not None else 'n/a'} C",
        f"Humidity: {weather.relative_humidity if weather.relative_humidity is not None else 'n/a'}%",
        f"Wind speed: {weather.wind_speed if weather.wind_speed is not None else 'n/a'} km/h",
        f"Wind direction: {weather.wind_direction if weather.wind_direction is not None else 'n/a'} deg",
        f"Precipitation: {weather.precipitation if weather.precipitation is not None else 'n/a'} mm",
    ]


def _build_email_message(
    db: Session,
    *,
    fire_event: FireEvent,
    device: Device,
    reading: SensorReading,
    recipients: list[str],
) -> EmailMessage:
    forest_name = device.forest.name if device.forest is not None else "Unassigned Forest"
    subject = f"{settings.alert_email_subject_prefix} Fire alert for {forest_name}"

    message = EmailMessage()
    message["From"] = settings.alert_email_from
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject

    body_lines = [
        "Forest Fire Shield detected an alarm event.",
        "",
        f"Forest: {forest_name}",
        f"Device: {device.device_code}",
        f"Fire event ID: {fire_event.id}",
        f"Trigger: {fire_event.trigger_type or reading.trigger}",
        f"Severity score: {reading.severity_score}",
        f"Detected at: {reading.recorded_at.isoformat()}",
        f"Location: {_location_summary(device)}",
        "",
        "Sensor snapshot:",
        f"  MQ2: {reading.mq2_analog} analog / {reading.mq2_digital} digital",
        f"  MQ4: {reading.mq4_analog} analog / {reading.mq4_digital} digital",
        f"  MQ7: {reading.mq7_analog} analog / {reading.mq7_digital} digital",
        f"  MQ135: {reading.mq135_analog} analog / {reading.mq135_digital} digital",
        f"  Flame sensor: {'detected' if reading.flame_detected else 'not detected'}",
        f"  IR sensor: {'detected' if reading.ir_detected else 'not detected'}",
        "",
        "Weather context:",
        *[f"  {line}" for line in _build_weather_lines(db)],
        "",
        "Recommended action: inspect the forest area immediately and verify the live dashboard.",
    ]
    message.set_content("\n".join(body_lines))
    return message


def _send_email(message: EmailMessage) -> None:
    timeout = float(settings.alert_email_timeout_seconds)

    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=timeout) as smtp:
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def _friendly_smtp_error(exc: Exception) -> str:
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "Alert delivery failed: SMTP authentication failed. Check username, password, or app password."
    if isinstance(exc, smtplib.SMTPConnectError):
        return "Alert delivery failed: SMTP connection failed. Check the SMTP host and port."
    if isinstance(exc, smtplib.SMTPServerDisconnected):
        return "Alert delivery failed: SMTP server disconnected unexpectedly."
    return f"Alert delivery failed: {exc}"


def dispatch_fire_alert(
    db: Session,
    *,
    fire_event: FireEvent,
    device: Device,
    reading: SensorReading,
) -> FireEvent:
    if not reading.alarm or fire_event.status != "active" or fire_event.alert_sent:
        return fire_event

    if not settings.alert_email_enabled:
        fire_event.notes = "Alert email is disabled in backend configuration."
        db.add(fire_event)
        db.commit()
        return fire_event

    recipients = _resolve_recipients(device)
    if not recipients:
        fire_event.notes = "Alert email pending: no forest admin or fallback recipient is configured."
        db.add(fire_event)
        db.commit()
        return fire_event

    if not settings.alert_email_from or not settings.smtp_host:
        fire_event.notes = "Alert email pending: SMTP host or sender address is missing."
        db.add(fire_event)
        db.commit()
        return fire_event

    try:
        message = _build_email_message(
            db,
            fire_event=fire_event,
            device=device,
            reading=reading,
            recipients=recipients,
        )
        _send_email(message)
    except Exception as exc:
        fire_event.notes = _friendly_smtp_error(exc)
        db.add(fire_event)
        db.commit()
        return fire_event

    fire_event.alert_sent = True
    fire_event.notes = f"Alert email sent via SMTP to {', '.join(recipients)} at {_utcnow().isoformat()}."
    db.add(fire_event)
    db.commit()
    return fire_event
