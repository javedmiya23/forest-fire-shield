from typing import Any

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point, mapping, shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Device, Forest, ForestUpload
from .schemas import (
    CoordinateResponse,
    ForestCreateRequest,
    ForestDetailResponse,
    ForestGeoJsonSummary,
    ForestGeoJsonValidationResponse,
)


settings = get_settings()

DEFAULT_FOREST_NAME = "Forest Fire Shield Forest"

PROPERTY_ALIASES = {
    "name": ["name", "forest_name", "title"],
    "admin_email": ["admin_email", "email", "contact_email"],
    "vegetation_type": ["vegetation_type", "vegetation", "veg_type"],
    "tree_density": ["tree_density", "treeDensity", "trees"],
    "canopy_density": ["canopy_density", "canopyDensity"],
    "fuel_load": ["fuel_load", "dry_biomass", "fuel"],
    "moisture_class": ["moisture_class", "moisture", "humidity_class"],
}

LAYER_KEYWORDS = {
    "water_bodies": ["water", "lake", "river", "stream", "pond", "reservoir", "wetland"],
    "roads_access": ["road", "trail", "path", "track", "route", "access"],
    "firebreaks": ["firebreak", "break_line", "breakline", "buffer_strip"],
    "wildlife_habitats": ["habitat", "wildlife", "animal", "fauna", "species", "corridor"],
    "vegetation_zones": ["vegetation", "veg", "canopy", "forest_type", "tree", "biomass"],
    "terrain_elevation": ["elevation", "slope", "terrain", "contour", "altitude"],
    "settlements": ["settlement", "village", "hamlet", "building", "community"],
    "water_points": ["hydrant", "water_point", "tank", "source_point"],
}
SENSOR_KEYWORDS = ["sensor", "esp32", "device", "board", "ignition_node", "node"]


def get_current_forest(db: Session) -> Forest | None:
    return db.scalar(select(Forest).order_by(Forest.created_at.desc(), Forest.id.desc()))


def get_latest_forest_upload(db: Session, forest_id: int) -> ForestUpload | None:
    return db.scalar(
        select(ForestUpload)
        .where(ForestUpload.forest_id == forest_id)
        .order_by(ForestUpload.uploaded_at.desc(), ForestUpload.id.desc())
    )


def _pick_property(properties: dict[str, Any], key: str) -> str | None:
    for alias in PROPERTY_ALIASES[key]:
        value = properties.get(alias)
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        return str(value)
    return None


def _iter_features(source_geojson: dict[str, Any]) -> list[dict[str, Any]]:
    geojson_type = source_geojson.get("type")
    if geojson_type == "FeatureCollection":
        return list(source_geojson.get("features", []))
    if geojson_type == "Feature":
        return [source_geojson]
    if "type" in source_geojson:
        return [{"type": "Feature", "geometry": source_geojson, "properties": {}}]
    raise ValueError("Invalid GeoJSON payload.")


def _stringify_properties(properties: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in properties.items():
        parts.append(str(key).lower())
        if isinstance(value, (str, int, float, bool)):
            parts.append(str(value).lower())
    return " ".join(parts)


def _looks_like_sensor(properties: dict[str, Any]) -> bool:
    property_blob = _stringify_properties(properties)
    return any(keyword in property_blob for keyword in SENSOR_KEYWORDS)


def summarize_geojson(source_geojson: dict[str, Any]) -> ForestGeoJsonSummary:
    feature_count = 0
    point_features = 0
    line_features = 0
    polygon_features = 0
    boundary_detected = False
    sensor_detected = False
    property_keys: set[str] = set()
    layer_hits: dict[str, int] = {name: 0 for name in LAYER_KEYWORDS}

    for feature in _iter_features(source_geojson):
        geometry = feature.get("geometry")
        if not geometry:
            continue

        feature_count += 1
        current_shape = shape(geometry)
        geometry_type = current_shape.geom_type
        properties = feature.get("properties") or {}
        property_keys.update(sorted(str(key) for key in properties.keys()))
        property_blob = _stringify_properties(properties)

        if geometry_type == "Point":
            point_features += 1
            if _looks_like_sensor(properties) or point_features == 1:
                sensor_detected = True
        elif geometry_type in {"LineString", "MultiLineString"}:
            line_features += 1
        elif geometry_type in {"Polygon", "MultiPolygon"}:
            polygon_features += 1
            boundary_detected = True

        for layer_name, keywords in LAYER_KEYWORDS.items():
            if any(keyword in property_blob for keyword in keywords):
                layer_hits[layer_name] += 1

    detected_layers = [layer_name for layer_name, count in layer_hits.items() if count > 0]
    missing_recommended_layers = [
        layer_name
        for layer_name in ["water_bodies", "roads_access", "vegetation_zones"]
        if layer_name not in detected_layers
    ]

    return ForestGeoJsonSummary(
        feature_count=feature_count,
        point_features=point_features,
        line_features=line_features,
        polygon_features=polygon_features,
        boundary_detected=boundary_detected,
        sensor_detected=sensor_detected,
        detected_layers=detected_layers,
        property_keys=sorted(property_keys),
        missing_recommended_layers=missing_recommended_layers,
    )


def _extract_boundary_and_sensor(
    source_geojson: dict[str, Any],
) -> tuple[BaseGeometry, Point | None, dict[str, Any]]:
    boundary: BaseGeometry | None = None
    sensor_point: Point | None = None
    fallback_point: Point | None = None
    boundary_properties: dict[str, Any] = {}

    for feature in _iter_features(source_geojson):
        geometry = feature.get("geometry")
        if not geometry:
            continue

        current_shape = shape(geometry)
        geometry_type = current_shape.geom_type
        properties = feature.get("properties") or {}

        if geometry_type in {"Polygon", "MultiPolygon"} and boundary is None:
            boundary = current_shape
            boundary_properties = properties
            continue

        if geometry_type == "Point":
            if fallback_point is None:
                fallback_point = current_shape
            if sensor_point is None and _looks_like_sensor(properties):
                sensor_point = current_shape

    if boundary is None:
        raise ValueError("GeoJSON must include at least one Polygon or MultiPolygon for the forest boundary.")

    if sensor_point is None:
        sensor_point = fallback_point

    return boundary, sensor_point, boundary_properties


def _build_generated_source_geojson(request: ForestCreateRequest) -> dict[str, Any]:
    features: list[dict[str, Any]] = [
        {
            "type": "Feature",
            "properties": {
                "name": request.name,
                "admin_email": request.admin_email,
                "vegetation_type": request.vegetation_type,
                "tree_density": request.tree_density,
                "canopy_density": request.canopy_density,
                "fuel_load": request.fuel_load,
                "moisture_class": request.moisture_class,
            },
            "geometry": request.boundary_geojson,
        }
    ]

    if request.sensor_location is not None:
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "name": "esp32_sensor_point",
                    "device_id": settings.default_device_code,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        request.sensor_location.longitude,
                        request.sensor_location.latitude,
                    ],
                },
            }
        )

    return request.source_geojson or {
        "type": "FeatureCollection",
        "features": features,
    }


def _get_or_create_default_device(db: Session) -> Device:
    device = db.scalar(select(Device).where(Device.device_code == settings.default_device_code))
    if device is None:
        device = Device(device_code=settings.default_device_code, status="unknown")
        db.add(device)
        db.flush()
    return device


def _apply_device_forest_link(db: Session, forest: Forest, sensor_point: Point | None) -> Device:
    device = _get_or_create_default_device(db)
    device.forest_id = forest.id

    if sensor_point is not None:
        device.location_geom = from_shape(sensor_point, srid=4326)

    db.add(device)
    db.flush()
    return device


def _build_center_response(forest: Forest) -> CoordinateResponse:
    return CoordinateResponse(
        latitude=float(forest.center_lat),
        longitude=float(forest.center_lon),
        source="forest_centroid",
    )


def _build_sensor_response(device: Device | None) -> CoordinateResponse | None:
    if device is None or device.location_geom is None:
        return None

    sensor_point = to_shape(device.location_geom)
    return CoordinateResponse(
        latitude=float(sensor_point.y),
        longitude=float(sensor_point.x),
        source="sensor_point",
    )


def build_forest_detail_response(db: Session, forest: Forest) -> ForestDetailResponse:
    device = db.scalar(
        select(Device)
        .where(Device.forest_id == forest.id)
        .order_by(Device.updated_at.desc(), Device.id.desc())
    )
    latest_upload = get_latest_forest_upload(db, forest.id)

    boundary_geojson = None
    geojson_summary = None
    if forest.boundary_geom is not None:
        boundary_geojson = mapping(to_shape(forest.boundary_geom))
    if latest_upload is not None:
        geojson_summary = summarize_geojson(latest_upload.source_geojson)

    return ForestDetailResponse(
        id=forest.id,
        name=forest.name,
        center=_build_center_response(forest),
        vegetation_type=forest.vegetation_type,
        tree_density=forest.tree_density,
        canopy_density=forest.canopy_density,
        fuel_load=forest.fuel_load,
        moisture_class=forest.moisture_class,
        admin_email=forest.admin_email,
        boundary_geojson=boundary_geojson,
        source_geojson=latest_upload.source_geojson if latest_upload is not None else None,
        sensor_location=_build_sensor_response(device),
        device_id=device.device_code if device is not None else None,
        geojson_summary=geojson_summary,
    )


def _upsert_forest(
    db: Session,
    *,
    name: str | None,
    admin_email: str | None,
    vegetation_type: str | None,
    tree_density: str | None,
    canopy_density: str | None,
    fuel_load: str | None,
    moisture_class: str | None,
    boundary_shape: BaseGeometry,
    sensor_point: Point | None,
    source_geojson: dict[str, Any],
    file_name: str | None,
) -> ForestDetailResponse:
    forest = get_current_forest(db)
    if forest is None:
        forest = Forest(name=name or DEFAULT_FOREST_NAME)
        db.add(forest)
        db.flush()

    centroid = boundary_shape.centroid

    forest.name = name or forest.name or DEFAULT_FOREST_NAME
    forest.boundary_geom = from_shape(boundary_shape, srid=4326)
    forest.center_lat = float(centroid.y)
    forest.center_lon = float(centroid.x)
    forest.admin_email = admin_email
    forest.vegetation_type = vegetation_type
    forest.tree_density = tree_density
    forest.canopy_density = canopy_density
    forest.fuel_load = fuel_load
    forest.moisture_class = moisture_class
    db.add(forest)
    db.flush()

    upload = ForestUpload(
        forest_id=forest.id,
        file_name=file_name,
        source_geojson=source_geojson,
    )
    db.add(upload)

    _apply_device_forest_link(db, forest, sensor_point)
    db.commit()

    return build_forest_detail_response(db, forest)


def create_or_update_forest(db: Session, request: ForestCreateRequest) -> ForestDetailResponse:
    source_geojson = _build_generated_source_geojson(request)
    boundary_shape = shape(request.boundary_geojson)
    if boundary_shape.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError("boundary_geojson must be a Polygon or MultiPolygon.")

    sensor_point = None
    if request.sensor_location is not None:
        sensor_point = Point(request.sensor_location.longitude, request.sensor_location.latitude)

    return _upsert_forest(
        db,
        name=request.name,
        admin_email=request.admin_email,
        vegetation_type=request.vegetation_type,
        tree_density=request.tree_density,
        canopy_density=request.canopy_density,
        fuel_load=request.fuel_load,
        moisture_class=request.moisture_class,
        boundary_shape=boundary_shape,
        sensor_point=sensor_point,
        source_geojson=source_geojson,
        file_name=None,
    )


def create_or_update_forest_from_geojson(
    db: Session,
    source_geojson: dict[str, Any],
    *,
    file_name: str | None = None,
    name: str | None = None,
    admin_email: str | None = None,
    vegetation_type: str | None = None,
    tree_density: str | None = None,
    canopy_density: str | None = None,
    fuel_load: str | None = None,
    moisture_class: str | None = None,
) -> ForestDetailResponse:
    boundary_shape, sensor_point, properties = _extract_boundary_and_sensor(source_geojson)

    return _upsert_forest(
        db,
        name=name or _pick_property(properties, "name") or DEFAULT_FOREST_NAME,
        admin_email=admin_email or _pick_property(properties, "admin_email"),
        vegetation_type=vegetation_type or _pick_property(properties, "vegetation_type"),
        tree_density=tree_density or _pick_property(properties, "tree_density"),
        canopy_density=canopy_density or _pick_property(properties, "canopy_density"),
        fuel_load=fuel_load or _pick_property(properties, "fuel_load"),
        moisture_class=moisture_class or _pick_property(properties, "moisture_class"),
        boundary_shape=boundary_shape,
        sensor_point=sensor_point,
        source_geojson=source_geojson,
        file_name=file_name,
    )


def validate_geojson_payload(source_geojson: dict[str, Any]) -> ForestGeoJsonValidationResponse:
    summary = summarize_geojson(source_geojson)
    boundary_geojson = None
    sensor_location = None
    message = "GeoJSON is compatible with Forest Fire Shield."

    try:
        boundary_shape, sensor_point, _ = _extract_boundary_and_sensor(source_geojson)
        boundary_geojson = mapping(boundary_shape)
        if sensor_point is not None:
            sensor_location = CoordinateResponse(
                latitude=float(sensor_point.y),
                longitude=float(sensor_point.x),
                source="sensor_point",
            )
    except ValueError as exc:
        return ForestGeoJsonValidationResponse(
            is_compatible=False,
            message=str(exc),
            summary=summary,
            boundary_geojson=None,
            sensor_location=None,
        )

    if not summary.sensor_detected:
        message = "GeoJSON is compatible. No explicit sensor point was found, so the forest centroid can be used until you add one."

    return ForestGeoJsonValidationResponse(
        is_compatible=True,
        message=message,
        summary=summary,
        boundary_geojson=boundary_geojson,
        sensor_location=sensor_location,
    )
