from __future__ import annotations

from math import atan2, ceil, cos, floor, radians, sqrt
from typing import Any

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .config import get_settings
from .forest_service import LAYER_KEYWORDS, get_current_forest, get_latest_forest_upload
from .models import Device, FireEvent, FireSimulation, SensorReading, SimulationStep
from .schemas import (
    CoordinateResponse,
    FireSimulationAssumptions,
    FireSimulationResponse,
    FireSimulationStepResponse,
    WeatherCurrentResponse,
)
from .services import get_active_fire_event, get_latest_reading
from .weather_service import get_current_weather


settings = get_settings()

MODEL_VERSION = "grid_v2_barrier_aware"
LAT_METERS = 110_540.0
WATER_LAYER_KEYWORDS = tuple(LAYER_KEYWORDS["water_bodies"])
ROAD_LAYER_KEYWORDS = tuple(LAYER_KEYWORDS["roads_access"])
FIREBREAK_LAYER_KEYWORDS = tuple(LAYER_KEYWORDS["firebreaks"])

VEGETATION_FACTORS = {
    "scrub": 0.94,
    "grassland": 0.88,
    "mixed_forest": 1.08,
    "deciduous": 1.12,
    "dry_deciduous": 1.2,
    "coniferous": 1.28,
    "pine": 1.32,
    "eucalyptus": 1.18,
}
TREE_DENSITY_FACTORS = {
    "low": 0.84,
    "medium": 1.0,
    "high": 1.14,
    "very_high": 1.24,
}
CANOPY_DENSITY_FACTORS = {
    "sparse": 0.88,
    "medium": 1.0,
    "dense": 1.12,
    "closed": 1.18,
}
FUEL_LOAD_FACTORS = {
    "low": 0.8,
    "moderate": 1.0,
    "high": 1.22,
    "extreme": 1.38,
}
MOISTURE_FACTORS = {
    "wet": 0.68,
    "normal": 0.92,
    "dry": 1.14,
    "very_dry": 1.32,
}

NEIGHBOR_DIRECTIONS = [
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
]


def _normalize_label(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _lookup_factor(table: dict[str, float], value: str | None, default: float = 1.0) -> float:
    normalized = _normalize_label(value)
    if normalized is None:
        return default
    return table.get(normalized, default)


def _ensure_multipolygon(geometry: BaseGeometry) -> MultiPolygon:
    if isinstance(geometry, MultiPolygon):
        return geometry
    if isinstance(geometry, Polygon):
        return MultiPolygon([geometry])
    if geometry.geom_type == "GeometryCollection":
        polygons = []
        for item in geometry.geoms:
            if isinstance(item, Polygon):
                polygons.append(item)
            elif isinstance(item, MultiPolygon):
                polygons.extend(list(item.geoms))
        if polygons:
            return MultiPolygon(polygons)
    raise ValueError("Simulation geometry did not resolve to a polygonal area.")


def _meters_per_degree_lon(latitude: float) -> float:
    return max(111_320.0 * cos(radians(latitude)), 1.0)


def _make_projection(origin_lat: float, origin_lon: float):
    lon_scale = _meters_per_degree_lon(origin_lat)

    def forward(x: Any, y: Any, z: Any = None):
        if isinstance(x, (list, tuple)):
            return (
                [(value - origin_lon) * lon_scale for value in x],
                [(value - origin_lat) * LAT_METERS for value in y],
            )
        return (
            (x - origin_lon) * lon_scale,
            (y - origin_lat) * LAT_METERS,
        )

    def inverse(x: Any, y: Any, z: Any = None):
        if isinstance(x, (list, tuple)):
            return (
                [(value / lon_scale) + origin_lon for value in x],
                [(value / LAT_METERS) + origin_lat for value in y],
            )
        return (
            (x / lon_scale) + origin_lon,
            (y / LAT_METERS) + origin_lat,
        )

    return forward, inverse


def _project_geometry(geometry: BaseGeometry, origin_lat: float, origin_lon: float) -> BaseGeometry:
    forward, _ = _make_projection(origin_lat, origin_lon)
    return transform(forward, geometry)


def _unproject_geometry(geometry: BaseGeometry, origin_lat: float, origin_lon: float) -> BaseGeometry:
    _, inverse = _make_projection(origin_lat, origin_lon)
    return transform(inverse, geometry)


def _build_candidate_cells(boundary_local: BaseGeometry, cell_size_m: float) -> tuple[dict[tuple[int, int], BaseGeometry], dict[tuple[int, int], tuple[float, float]]]:
    cells: dict[tuple[int, int], BaseGeometry] = {}
    centers: dict[tuple[int, int], tuple[float, float]] = {}
    min_x, min_y, max_x, max_y = boundary_local.bounds

    for ix in range(floor(min_x / cell_size_m), ceil(max_x / cell_size_m)):
        for iy in range(floor(min_y / cell_size_m), ceil(max_y / cell_size_m)):
            cell = box(
                ix * cell_size_m,
                iy * cell_size_m,
                (ix + 1) * cell_size_m,
                (iy + 1) * cell_size_m,
            )
            clipped = cell.intersection(boundary_local)
            if clipped.is_empty:
                continue
            if clipped.area < cell.area * 0.18:
                continue
            cells[(ix, iy)] = clipped
            centers[(ix, iy)] = ((ix + 0.5) * cell_size_m, (iy + 0.5) * cell_size_m)

    return cells, centers


def _find_ignition_cell(
    centers: dict[tuple[int, int], tuple[float, float]],
    ignition_local: Point,
) -> tuple[int, int]:
    ignition_xy = (ignition_local.x, ignition_local.y)
    return min(
        centers,
        key=lambda key: (centers[key][0] - ignition_xy[0]) ** 2 + (centers[key][1] - ignition_xy[1]) ** 2,
    )


def _iter_source_features(source_geojson: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not source_geojson:
        return []

    geojson_type = source_geojson.get("type")
    if geojson_type == "FeatureCollection":
        return list(source_geojson.get("features", []))
    if geojson_type == "Feature":
        return [source_geojson]
    if "type" in source_geojson:
        return [{"type": "Feature", "geometry": source_geojson, "properties": {}}]
    return []


def _stringify_properties(properties: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in properties.items():
        parts.append(str(key).lower())
        if isinstance(value, (str, int, float, bool)):
            parts.append(str(value).lower())
    return " ".join(parts)


def _has_keywords(blob: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in blob for keyword in keywords)


def _extract_barrier_geometries(source_geojson: dict[str, Any] | None) -> dict[str, list[BaseGeometry]]:
    barriers: dict[str, list[BaseGeometry]] = {
        "water_bodies": [],
        "roads_access": [],
        "firebreaks": [],
    }

    for feature in _iter_source_features(source_geojson):
        geometry = feature.get("geometry")
        if not geometry:
            continue

        current_geometry = shape(geometry)
        if current_geometry.is_empty:
            continue

        property_blob = _stringify_properties(feature.get("properties") or {})
        if _has_keywords(property_blob, WATER_LAYER_KEYWORDS):
            barriers["water_bodies"].append(current_geometry)
        if _has_keywords(property_blob, ROAD_LAYER_KEYWORDS):
            barriers["roads_access"].append(current_geometry)
        if _has_keywords(property_blob, FIREBREAK_LAYER_KEYWORDS):
            barriers["firebreaks"].append(current_geometry)

    return barriers


def _buffer_barrier_geometry(geometry: BaseGeometry, width_m: float) -> BaseGeometry:
    if geometry.geom_type in {"LineString", "MultiLineString", "Point", "MultiPoint"}:
        return geometry.buffer(width_m, cap_style=2, join_style=2)
    return geometry.buffer(0)


def _build_barrier_zones(
    source_geojson: dict[str, Any] | None,
    *,
    origin_lat: float,
    origin_lon: float,
    cell_size_m: float,
    boundary_local: BaseGeometry,
) -> tuple[dict[str, BaseGeometry | None], list[str]]:
    extracted = _extract_barrier_geometries(source_geojson)
    zone_definitions = {
        "water_bodies": max(cell_size_m * 0.24, 7.0),
        "roads_access": max(cell_size_m * 0.14, 5.0),
        "firebreaks": max(cell_size_m * 0.26, 10.0),
    }
    zones: dict[str, BaseGeometry | None] = {}
    used_layers: list[str] = []

    for layer_name, geometries in extracted.items():
        if not geometries:
            zones[layer_name] = None
            continue

        projected_items: list[BaseGeometry] = []
        for geometry in geometries:
            local_geometry = _project_geometry(geometry, origin_lat, origin_lon)
            clipped = local_geometry.intersection(boundary_local.buffer(cell_size_m * 0.6))
            if clipped.is_empty:
                continue
            projected_items.append(_buffer_barrier_geometry(clipped, zone_definitions[layer_name]))

        if not projected_items:
            zones[layer_name] = None
            continue

        zones[layer_name] = unary_union(projected_items)
        used_layers.append(layer_name)

    return zones, used_layers


def _build_cell_spread_modifiers(
    cells: dict[tuple[int, int], BaseGeometry],
    barrier_zones: dict[str, BaseGeometry | None],
) -> tuple[dict[tuple[int, int], float], set[tuple[int, int]]]:
    modifiers: dict[tuple[int, int], float] = {}
    blocked_cells: set[tuple[int, int]] = set()
    water_zone = barrier_zones.get("water_bodies")
    road_zone = barrier_zones.get("roads_access")
    firebreak_zone = barrier_zones.get("firebreaks")

    for cell_key, cell in cells.items():
        area = max(cell.area, 1.0)
        water_ratio = cell.intersection(water_zone).area / area if water_zone is not None and not water_zone.is_empty else 0.0
        road_ratio = cell.intersection(road_zone).area / area if road_zone is not None and not road_zone.is_empty else 0.0
        firebreak_ratio = (
            cell.intersection(firebreak_zone).area / area
            if firebreak_zone is not None and not firebreak_zone.is_empty
            else 0.0
        )

        if water_ratio >= 0.34:
            blocked_cells.add(cell_key)
            modifiers[cell_key] = 0.04
            continue

        factor = 1.0
        factor *= max(0.18, 1.0 - min(water_ratio * 1.25, 0.76))
        factor *= max(0.34, 1.0 - min(firebreak_ratio * 1.08, 0.62))
        factor *= max(0.76, 1.0 - min(road_ratio * 0.42, 0.2))
        modifiers[cell_key] = round(factor, 3)

    return modifiers, blocked_cells


def _barrier_crossing_factor(
    start: tuple[float, float],
    end: tuple[float, float],
    barrier_zones: dict[str, BaseGeometry | None],
) -> float:
    segment = LineString([start, end])
    factor = 1.0

    water_zone = barrier_zones.get("water_bodies")
    if water_zone is not None and not water_zone.is_empty and segment.intersects(water_zone):
        factor *= 0.18

    firebreak_zone = barrier_zones.get("firebreaks")
    if firebreak_zone is not None and not firebreak_zone.is_empty and segment.intersects(firebreak_zone):
        factor *= 0.32

    road_zone = barrier_zones.get("roads_access")
    if road_zone is not None and not road_zone.is_empty and segment.intersects(road_zone):
        factor *= 0.74

    return factor


def _fuel_factor(forest) -> float:
    factor = 1.0
    factor *= _lookup_factor(VEGETATION_FACTORS, forest.vegetation_type, 1.04)
    factor *= _lookup_factor(TREE_DENSITY_FACTORS, forest.tree_density, 1.0)
    factor *= _lookup_factor(CANOPY_DENSITY_FACTORS, forest.canopy_density, 1.0)
    factor *= _lookup_factor(FUEL_LOAD_FACTORS, forest.fuel_load, 1.0)
    factor *= _lookup_factor(MOISTURE_FACTORS, forest.moisture_class, 1.0)
    return round(factor, 3)


def _weather_factor(weather: WeatherCurrentResponse | None) -> float:
    if weather is None:
        return 1.0

    temperature = weather.temperature if weather.temperature is not None else 26.0
    humidity = weather.relative_humidity if weather.relative_humidity is not None else 45.0
    precipitation = weather.precipitation if weather.precipitation is not None else 0.0

    temperature_factor = min(max(0.86 + ((temperature - 18.0) / 30.0), 0.78), 1.32)
    humidity_factor = min(max(1.18 - (humidity / 140.0), 0.56), 1.12)
    precipitation_factor = min(max(1.0 - (precipitation * 0.38), 0.42), 1.0)
    return round(temperature_factor * humidity_factor * precipitation_factor, 3)


def _severity_factor(reading: SensorReading | None, fire_event: FireEvent | None) -> float:
    base_severity = 45
    if fire_event is not None and fire_event.max_severity is not None:
        base_severity = fire_event.max_severity
    if reading is not None:
        base_severity = max(base_severity, reading.severity_score)
    return round(min(1.45, max(0.9, 0.82 + (base_severity / 160.0))), 3)


def _wind_push_direction(weather: WeatherCurrentResponse | None) -> float | None:
    if weather is None or weather.wind_direction is None:
        return None
    return round((weather.wind_direction + 180.0) % 360.0, 2)


def _wind_alignment(
    dx: float,
    dy: float,
    wind_push_direction: float | None,
    wind_speed: float | None,
) -> float:
    if wind_push_direction is None or wind_speed is None or wind_speed <= 0.1:
        return 1.0

    heading = (atan2(dx, dy) * 180.0 / 3.141592653589793) % 360.0
    difference = abs(heading - wind_push_direction)
    if difference > 180.0:
        difference = 360.0 - difference

    alignment = cos(radians(difference))
    influence = min(wind_speed / 25.0, 1.25)
    factor = 1.0 + (alignment * 0.72 * influence)
    return min(max(factor, 0.42), 1.82)


def _intensity_score(active_cells: int, base_potential: float, wind_speed: float | None) -> int:
    wind_component = (wind_speed or 0.0) * 0.7
    intensity = 12.0 + (active_cells * 6.0) + (base_potential * 22.0) + wind_component
    return int(min(max(round(intensity), 10), 100))


def _heading_from_vectors(vectors: list[tuple[float, float, float]], default_heading: float | None) -> float | None:
    if not vectors:
        return default_heading

    sum_x = 0.0
    sum_y = 0.0
    for dx, dy, weight in vectors:
        sum_x += dx * weight
        sum_y += dy * weight

    if abs(sum_x) < 1e-6 and abs(sum_y) < 1e-6:
        return default_heading

    return round((atan2(sum_x, sum_y) * 180.0 / 3.141592653589793) % 360.0, 2)


def _build_assumptions(
    *,
    simulation_mode: str,
    hours: int,
    cell_size_m: float,
    fuel_factor: float,
    weather_factor: float,
    severity_factor: float,
    wind_push_direction: float | None,
    barrier_layers_used: list[str],
    blocked_cell_count: int,
) -> dict[str, Any]:
    notes = [
        "Grid-based deterministic spread clipped to the uploaded forest boundary.",
        "Wind direction is converted to downwind spread direction by adding 180 degrees.",
        "Fuel multiplier comes from vegetation type, tree density, canopy density, fuel load, and moisture class.",
        "Weather multiplier reduces or increases spread using temperature, humidity, and precipitation.",
        "This is a physics-inspired simulation model, not a machine-learning predictor.",
    ]
    if barrier_layers_used:
        notes.append(
            "Barrier-aware spread damping is active using uploaded "
            + ", ".join(layer.replace("_", " ") for layer in barrier_layers_used)
            + "."
        )
        if "water_bodies" in barrier_layers_used:
            notes.append("Cells dominated by mapped water are treated as near-non-burnable, and crossing water sharply suppresses spread.")
        if "roads_access" in barrier_layers_used or "firebreaks" in barrier_layers_used:
            notes.append("Roads and firebreak corridors reduce the ignition chance of neighboring cells when the spread path crosses them.")
        if blocked_cell_count:
            notes.append(f"{blocked_cell_count} simulation cells were heavily constrained by mapped barrier layers.")
    else:
        notes.append("No water, road, or firebreak layers were detected, so spread uses boundary, fuel, weather, and severity only.")

    return FireSimulationAssumptions(
        model_type="grid_cellular_spread",
        model_version=MODEL_VERSION,
        simulation_mode=simulation_mode,
        horizon_hours=hours,
        cell_size_m=round(cell_size_m, 2),
        active_burn_hours=settings.simulation_active_burn_hours,
        fuel_factor=fuel_factor,
        weather_factor=weather_factor,
        severity_factor=severity_factor,
        wind_push_direction=wind_push_direction,
        notes=notes,
    ).model_dump(mode="json")


def build_fire_simulation_response(simulation: FireSimulation) -> FireSimulationResponse:
    assumptions = FireSimulationAssumptions.model_validate(simulation.assumptions_json)
    weather_payload = simulation.assumptions_json.get("weather")
    weather = None
    if weather_payload is not None:
        weather = WeatherCurrentResponse.model_validate(weather_payload)

    step_responses = []
    for step in simulation.steps:
        step_responses.append(
            FireSimulationStepResponse(
                hour_offset=step.hour_offset,
                estimated_area_m2=float(step.estimated_area_m2),
                spread_heading=float(step.spread_heading) if step.spread_heading is not None else None,
                intensity_score=step.intensity_score,
                active_cells=step.active_cells,
                burnt_cells=step.burnt_cells,
                affected_geojson=mapping(to_shape(step.affected_geom)),
            )
        )

    device_code = simulation.device.device_code if simulation.device is not None else None

    return FireSimulationResponse(
        id=simulation.id,
        generated_at=simulation.generated_at,
        model_version=simulation.model_version,
        forest_id=simulation.forest_id,
        device_id=device_code,
        fire_event_id=simulation.fire_event_id,
        ignition_point=CoordinateResponse(
            latitude=float(simulation.ignition_lat),
            longitude=float(simulation.ignition_lon),
            source="sensor_point",
        ),
        weather=weather,
        assumptions=assumptions,
        steps=step_responses,
    )


def get_latest_fire_simulation(db: Session) -> FireSimulation | None:
    return db.scalar(
        select(FireSimulation)
        .options(
            joinedload(FireSimulation.device),
            joinedload(FireSimulation.steps),
        )
        .order_by(FireSimulation.generated_at.desc(), FireSimulation.id.desc())
    )


def run_fire_simulation(
    db: Session,
    *,
    hours: int | None = None,
    cell_size_m: float | None = None,
    force_weather_refresh: bool = False,
) -> FireSimulationResponse:
    forest = get_current_forest(db)
    if forest is None or forest.boundary_geom is None:
        raise ValueError("Create or upload a forest boundary before running the simulation.")

    boundary_geo = to_shape(forest.boundary_geom)
    fire_event = get_active_fire_event(db)
    latest_reading = get_latest_reading(db)
    latest_upload = get_latest_forest_upload(db, forest.id)

    device = db.scalar(
        select(Device)
        .where(Device.forest_id == forest.id)
        .order_by(Device.updated_at.desc(), Device.id.desc())
    )
    if fire_event is not None and fire_event.device is not None:
        device = fire_event.device

    ignition_geo = boundary_geo.centroid
    if device is not None and device.location_geom is not None:
        ignition_geo = to_shape(device.location_geom)

    weather = get_current_weather(db, force_refresh=force_weather_refresh)
    horizon_hours = hours or settings.simulation_default_hours
    requested_cell_size = float(cell_size_m or settings.simulation_default_cell_size_m)

    boundary_local = _project_geometry(boundary_geo, ignition_geo.y, ignition_geo.x)
    ignition_local = Point(0.0, 0.0)

    adaptive_cell_size = max(
        requested_cell_size,
        sqrt(max(boundary_local.area, 1.0) / max(settings.simulation_max_cells, 1)),
    )
    cells, centers = _build_candidate_cells(boundary_local, adaptive_cell_size)
    if not cells:
        raise ValueError("Forest boundary is too small or invalid for simulation grid generation.")

    barrier_zones, barrier_layers_used = _build_barrier_zones(
        latest_upload.source_geojson if latest_upload is not None else None,
        origin_lat=ignition_geo.y,
        origin_lon=ignition_geo.x,
        cell_size_m=adaptive_cell_size,
        boundary_local=boundary_local,
    )
    cell_spread_modifiers, blocked_cells = _build_cell_spread_modifiers(cells, barrier_zones)
    available_centers = {key: center for key, center in centers.items() if key not in blocked_cells}
    if not available_centers:
        raise ValueError("Mapped barrier layers leave no burnable forest cells for simulation.")

    ignition_cell = _find_ignition_cell(available_centers, ignition_local)
    fuel_factor = _fuel_factor(forest)
    weather_factor = _weather_factor(weather)
    severity_factor = _severity_factor(latest_reading, fire_event)
    wind_push_direction = _wind_push_direction(weather)
    base_potential = fuel_factor * weather_factor * severity_factor
    wind_speed = weather.wind_speed if weather is not None else None

    active_cells: dict[tuple[int, int], int] = {ignition_cell: 0}
    burnt_cells: set[tuple[int, int]] = set()
    step_payloads: list[dict[str, Any]] = []

    for hour in range(1, horizon_hours + 1):
        new_cells: set[tuple[int, int]] = set()
        heading_vectors: list[tuple[float, float, float]] = []

        for cell_key, age in list(active_cells.items()):
            center_x, center_y = centers[cell_key]

            for dx_step, dy_step in NEIGHBOR_DIRECTIONS:
                neighbor_key = (cell_key[0] + dx_step, cell_key[1] + dy_step)
                if neighbor_key not in centers:
                    continue
                if neighbor_key in blocked_cells:
                    continue
                if neighbor_key in active_cells or neighbor_key in burnt_cells or neighbor_key in new_cells:
                    continue

                neighbor_x, neighbor_y = centers[neighbor_key]
                dx = neighbor_x - center_x
                dy = neighbor_y - center_y
                distance_factor = 1.0 if dx_step == 0 or dy_step == 0 else 0.86
                wind_alignment = _wind_alignment(dx, dy, wind_push_direction, wind_speed)
                crossing_factor = _barrier_crossing_factor(
                    (center_x, center_y),
                    (neighbor_x, neighbor_y),
                    barrier_zones,
                )
                target_cell_factor = cell_spread_modifiers.get(neighbor_key, 1.0)
                spread_score = base_potential * distance_factor * wind_alignment * crossing_factor * target_cell_factor

                if spread_score >= 1.18:
                    new_cells.add(neighbor_key)
                    heading_vectors.append((dx, dy, spread_score))

        next_active_cells: dict[tuple[int, int], int] = {}
        for cell_key, age in active_cells.items():
            next_age = age + 1
            if next_age >= settings.simulation_active_burn_hours:
                burnt_cells.add(cell_key)
            else:
                next_active_cells[cell_key] = next_age
        for cell_key in new_cells:
            next_active_cells[cell_key] = 0

        active_cells = next_active_cells
        affected_cells = set(burnt_cells) | set(active_cells.keys())
        if not affected_cells:
            affected_cells = {ignition_cell}

        affected_local = unary_union([cells[cell_key] for cell_key in affected_cells]).intersection(boundary_local)
        if affected_local.is_empty:
            affected_local = cells[ignition_cell]

        affected_geo = _ensure_multipolygon(
            _unproject_geometry(affected_local, ignition_geo.y, ignition_geo.x)
        )
        step_payloads.append(
            {
                "hour_offset": hour,
                "geometry": affected_geo,
                "estimated_area_m2": round(float(affected_local.area), 2),
                "spread_heading": _heading_from_vectors(heading_vectors, wind_push_direction),
                "intensity_score": _intensity_score(len(active_cells), base_potential, wind_speed),
                "active_cells": len(active_cells),
                "burnt_cells": len(burnt_cells),
            }
        )

    simulation_mode = "event_driven" if fire_event is not None else "scenario_preview"
    assumptions_json = _build_assumptions(
        simulation_mode=simulation_mode,
        hours=horizon_hours,
        cell_size_m=adaptive_cell_size,
        fuel_factor=fuel_factor,
        weather_factor=weather_factor,
        severity_factor=severity_factor,
        wind_push_direction=wind_push_direction,
        barrier_layers_used=barrier_layers_used,
        blocked_cell_count=len(blocked_cells),
    )
    assumptions_json["weather"] = weather.model_dump(mode="json") if weather is not None else None
    assumptions_json["barrier_layers_used"] = barrier_layers_used
    assumptions_json["blocked_cell_count"] = len(blocked_cells)

    simulation = FireSimulation(
        forest_id=forest.id,
        device_id=device.id if device is not None else None,
        fire_event_id=fire_event.id if fire_event is not None else None,
        model_version=MODEL_VERSION,
        ignition_lat=float(ignition_geo.y),
        ignition_lon=float(ignition_geo.x),
        assumptions_json=assumptions_json,
    )
    db.add(simulation)
    db.flush()

    for step_payload in step_payloads:
        db.add(
            SimulationStep(
                simulation_id=simulation.id,
                hour_offset=step_payload["hour_offset"],
                affected_geom=from_shape(step_payload["geometry"], srid=4326),
                estimated_area_m2=step_payload["estimated_area_m2"],
                spread_heading=step_payload["spread_heading"],
                intensity_score=step_payload["intensity_score"],
                active_cells=step_payload["active_cells"],
                burnt_cells=step_payload["burnt_cells"],
            )
        )

    db.commit()
    db.refresh(simulation)

    persisted_simulation = db.scalar(
        select(FireSimulation)
        .options(
            joinedload(FireSimulation.device),
            joinedload(FireSimulation.steps),
        )
        .where(FireSimulation.id == simulation.id)
    )
    if persisted_simulation is None:
        raise ValueError("Simulation was generated but could not be reloaded.")

    return build_fire_simulation_response(persisted_simulation)
