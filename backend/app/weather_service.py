from datetime import timedelta
from decimal import Decimal

import httpx
from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .forest_service import get_current_forest
from .models import Device, WeatherSnapshot
from .schemas import WeatherCurrentResponse
from .services import utcnow


settings = get_settings()


def _as_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _get_weather_location(db: Session) -> tuple[int | None, float, float, str] | None:
    forest = get_current_forest(db)
    if forest is None:
        return None

    device = db.scalar(
        select(Device)
        .where(Device.forest_id == forest.id, Device.location_geom.is_not(None))
        .order_by(Device.updated_at.desc(), Device.id.desc())
    )
    if device is not None and device.location_geom is not None:
        sensor_point = to_shape(device.location_geom)
        return forest.id, float(sensor_point.y), float(sensor_point.x), "sensor_point"

    if forest.center_lat is None or forest.center_lon is None:
        return None

    return forest.id, float(forest.center_lat), float(forest.center_lon), "forest_centroid"


def _get_cached_snapshot(
    db: Session,
    *,
    forest_id: int | None,
    latitude: float,
    longitude: float,
) -> WeatherSnapshot | None:
    cache_cutoff = utcnow() - timedelta(minutes=settings.weather_cache_minutes)
    snapshot = db.scalar(
        select(WeatherSnapshot)
        .where(
            WeatherSnapshot.forest_id == forest_id,
            WeatherSnapshot.captured_at >= cache_cutoff,
        )
        .order_by(WeatherSnapshot.captured_at.desc(), WeatherSnapshot.id.desc())
    )
    if snapshot is None:
        return None

    if round(float(snapshot.latitude), 6) != round(latitude, 6):
        return None
    if round(float(snapshot.longitude), 6) != round(longitude, 6):
        return None

    return snapshot


def _build_weather_response(snapshot: WeatherSnapshot, location_source: str) -> WeatherCurrentResponse:
    return WeatherCurrentResponse(
        captured_at=snapshot.captured_at,
        source_name=snapshot.source_name,
        latitude=float(snapshot.latitude),
        longitude=float(snapshot.longitude),
        location_source=location_source,
        temperature=_as_float(snapshot.temperature),
        relative_humidity=_as_float(snapshot.relative_humidity),
        wind_speed=_as_float(snapshot.wind_speed),
        wind_direction=_as_float(snapshot.wind_direction),
        precipitation=_as_float(snapshot.precipitation),
    )


def get_current_weather(db: Session, *, force_refresh: bool = False) -> WeatherCurrentResponse | None:
    location = _get_weather_location(db)
    if location is None:
        return None

    forest_id, latitude, longitude, location_source = location

    if not force_refresh:
        cached = _get_cached_snapshot(
            db,
            forest_id=forest_id,
            latitude=latitude,
            longitude=longitude,
        )
        if cached is not None:
            return _build_weather_response(cached, location_source)

    response = httpx.get(
        settings.weather_api_url,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation",
            "timezone": "auto",
        },
        timeout=15.0,
    )
    response.raise_for_status()
    payload = response.json()

    current = payload.get("current") or {}
    snapshot = WeatherSnapshot(
        forest_id=forest_id,
        source_name="open-meteo",
        latitude=latitude,
        longitude=longitude,
        temperature=current.get("temperature_2m"),
        relative_humidity=current.get("relative_humidity_2m"),
        wind_speed=current.get("wind_speed_10m"),
        wind_direction=current.get("wind_direction_10m"),
        precipitation=current.get("precipitation"),
        raw_payload=payload,
    )
    db.add(snapshot)
    db.commit()

    return _build_weather_response(snapshot, location_source)
