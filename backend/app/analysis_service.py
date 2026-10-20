from __future__ import annotations

from math import cos, radians

from geoalchemy2.shape import to_shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .forest_service import get_current_forest, get_latest_forest_upload, summarize_geojson
from .models import Device, FireEvent, FireSimulation, ImpactReport, SensorReading
from .schemas import AnalysisSensorPeak, FireAnalysisResponse
from .services import get_latest_reading
from .simulation_service import get_latest_fire_simulation
from .weather_service import get_current_weather

LAT_METERS = 110_540.0


def _meters_per_degree_lon(latitude: float) -> float:
    return max(111_320.0 * cos(radians(latitude)), 1.0)


def _project_geometry(geometry: BaseGeometry, origin_lat: float, origin_lon: float) -> BaseGeometry:
    lon_scale = _meters_per_degree_lon(origin_lat)

    def forward(x, y, z=None):
        return ((x - origin_lon) * lon_scale, (y - origin_lat) * LAT_METERS)

    return transform(forward, geometry)


def _forest_area_m2(forest) -> float | None:
    if forest is None or forest.boundary_geom is None:
        return None

    boundary = to_shape(forest.boundary_geom)
    centroid = boundary.centroid
    projected = _project_geometry(boundary, centroid.y, centroid.x)
    return round(float(projected.area), 2)


def _impact_level(vegetation_loss_score: int, habitat_impact_score: int) -> str:
    severity = max(vegetation_loss_score, habitat_impact_score)
    if severity >= 80:
        return "critical"
    if severity >= 60:
        return "high"
    if severity >= 35:
        return "moderate"
    return "low"


def _damage_label(score: int) -> str:
    if score >= 80:
        return "Severe canopy and ground-layer loss likely."
    if score >= 60:
        return "High vegetation stress and widespread burn impact likely."
    if score >= 35:
        return "Moderate localized vegetation damage likely."
    return "Low to limited vegetation damage likely."


def _wildlife_label(score: int, habitat_detected: bool) -> str:
    if habitat_detected and score >= 70:
        return "Habitat disruption is likely significant, especially in mapped wildlife zones."
    if score >= 70:
        return "High wildlife disturbance risk across the affected footprint."
    if score >= 40:
        return "Moderate habitat disturbance risk is likely."
    return "Low-to-moderate wildlife disturbance risk."


def _recommended_actions(report_status: str, impact_level: str) -> list[str]:
    actions = [
        "Review the simulated spread corridor against known roads, water bodies, and access routes.",
        "Inspect the highest-severity sensor intervals to verify ignition progression.",
    ]
    if report_status == "preliminary":
        actions.append("Treat this as a live impact estimate until the fire event is resolved.")
    else:
        actions.append("Archive the event report and compare it with any on-site observations after closure.")

    if impact_level in {"high", "critical"}:
        actions.append("Prioritize post-fire ecological assessment for vegetation recovery and habitat restoration.")
    return actions


def _sensor_peak(readings: list[SensorReading], analog_attr: str, digital_attr: str, label: str) -> AnalysisSensorPeak:
    max_analog = max((getattr(reading, analog_attr) for reading in readings), default=0)
    digital_trigger_count = sum(1 for reading in readings if getattr(reading, digital_attr) == 0)
    return AnalysisSensorPeak(
        sensor=label,
        max_analog=max_analog,
        digital_trigger_count=digital_trigger_count,
    )


def _select_analysis_event(db: Session) -> FireEvent | None:
    resolved = db.scalar(
        select(FireEvent)
        .options(joinedload(FireEvent.device), joinedload(FireEvent.forest))
        .where(FireEvent.status == "resolved")
        .order_by(FireEvent.ended_at.desc().nullslast(), FireEvent.updated_at.desc())
    )
    if resolved is not None:
        return resolved

    return db.scalar(
        select(FireEvent)
        .options(joinedload(FireEvent.device), joinedload(FireEvent.forest))
        .order_by(FireEvent.updated_at.desc(), FireEvent.id.desc())
    )


def _simulation_for_event(db: Session, fire_event: FireEvent | None) -> FireSimulation | None:
    if fire_event is not None:
        linked = db.scalar(
            select(FireSimulation)
            .options(joinedload(FireSimulation.device), joinedload(FireSimulation.steps))
            .where(FireSimulation.fire_event_id == fire_event.id)
            .order_by(FireSimulation.generated_at.desc(), FireSimulation.id.desc())
        )
        if linked is not None:
            return linked

    return get_latest_fire_simulation(db)


def _readings_for_event(db: Session, fire_event: FireEvent | None) -> list[SensorReading]:
    if fire_event is not None:
        return list(
            db.scalars(
                select(SensorReading)
                .where(SensorReading.fire_event_id == fire_event.id)
                .order_by(SensorReading.recorded_at.asc(), SensorReading.id.asc())
            )
        )

    latest = get_latest_reading(db)
    return [latest] if latest is not None else []


def build_fire_analysis_response(report: ImpactReport) -> FireAnalysisResponse:
    summary = report.summary_json
    return FireAnalysisResponse(
        id=report.id,
        generated_at=report.generated_at,
        report_status=summary["report_status"],
        impact_level=report.impact_level,
        forest_name=summary.get("forest_name"),
        device_id=summary.get("device_id"),
        fire_event_id=report.fire_event_id,
        simulation_id=summary.get("simulation_id"),
        event_started_at=summary.get("event_started_at"),
        event_ended_at=summary.get("event_ended_at"),
        event_duration_minutes=summary.get("event_duration_minutes"),
        peak_severity=summary.get("peak_severity"),
        average_severity=summary.get("average_severity"),
        alarm_packet_count=summary.get("alarm_packet_count", 0),
        estimated_burnt_area_m2=float(report.estimated_burnt_area_m2) if report.estimated_burnt_area_m2 is not None else None,
        estimated_burnt_area_hectares=summary.get("estimated_burnt_area_hectares"),
        forest_area_m2=summary.get("forest_area_m2"),
        estimated_burn_ratio=summary.get("estimated_burn_ratio"),
        vegetation_loss_score=report.vegetation_loss_score,
        habitat_impact_score=report.habitat_impact_score,
        likely_vegetation_damage=summary["likely_vegetation_damage"],
        likely_wildlife_impact=summary["likely_wildlife_impact"],
        spread_heading=summary.get("spread_heading"),
        summary_text=summary["summary_text"],
        sensor_peaks=[AnalysisSensorPeak.model_validate(item) for item in summary.get("sensor_peaks", [])],
        recommended_actions=list(summary.get("recommended_actions", [])),
    )


def get_latest_impact_report(db: Session) -> ImpactReport | None:
    return db.scalar(
        select(ImpactReport)
        .order_by(ImpactReport.generated_at.desc(), ImpactReport.id.desc())
    )


def generate_fire_analysis(db: Session) -> FireAnalysisResponse:
    fire_event = _select_analysis_event(db)
    simulation = _simulation_for_event(db, fire_event)
    readings = _readings_for_event(db, fire_event)
    forest = fire_event.forest if fire_event is not None and fire_event.forest is not None else get_current_forest(db)

    if forest is None:
        raise ValueError("Create or upload a forest before generating fire analysis.")
    if not readings and simulation is None:
        raise ValueError("No fire readings or simulation results are available for analysis.")

    forest_area = _forest_area_m2(forest)
    estimated_burnt_area_m2 = None
    spread_heading = None
    if simulation is not None and simulation.steps:
        last_step = simulation.steps[-1]
        estimated_burnt_area_m2 = round(float(last_step.estimated_area_m2), 2)
        spread_heading = float(last_step.spread_heading) if last_step.spread_heading is not None else None

    estimated_burn_ratio = None
    if estimated_burnt_area_m2 is not None and forest_area:
        estimated_burn_ratio = round(min(estimated_burnt_area_m2 / forest_area, 1.0), 4)

    peak_severity = max((reading.severity_score for reading in readings), default=fire_event.max_severity if fire_event else None)
    avg_severity = round(sum(reading.severity_score for reading in readings) / len(readings), 2) if readings else None
    alarm_packet_count = sum(1 for reading in readings if reading.alarm)

    fuel_weight = 1.0
    for value in [forest.tree_density, forest.canopy_density, forest.fuel_load]:
        if value:
            normalized = value.lower()
            if normalized in {"high", "dense", "heavy"}:
                fuel_weight += 0.18
            elif normalized in {"medium", "moderate"}:
                fuel_weight += 0.1

    vegetation_loss_score = min(
        100,
        round(
            (
                (estimated_burn_ratio or 0.12) * 62
                + ((peak_severity or 35) * 0.28)
                + ((avg_severity or 30) * 0.16)
            )
            * fuel_weight
        ),
    )

    latest_upload = get_latest_forest_upload(db, forest.id)
    geojson_summary = summarize_geojson(latest_upload.source_geojson) if latest_upload is not None else None
    habitat_detected = geojson_summary is not None and "wildlife_habitats" in geojson_summary.detected_layers
    habitat_bonus = 12 if habitat_detected else 0
    habitat_impact_score = min(
        100,
        round(
            (estimated_burn_ratio or 0.1) * 58
            + ((peak_severity or 35) * 0.22)
            + habitat_bonus
        ),
    )
    impact_level = _impact_level(vegetation_loss_score, habitat_impact_score)
    report_status = "final" if fire_event is not None and fire_event.status == "resolved" else "preliminary"

    event_duration_minutes = None
    if fire_event is not None and fire_event.started_at is not None:
        event_end = fire_event.ended_at or fire_event.last_alarm_at
        if event_end is not None:
            event_duration_minutes = round(max((event_end - fire_event.started_at).total_seconds() / 60.0, 0.0), 2)

    likely_vegetation_damage = _damage_label(vegetation_loss_score)
    likely_wildlife_impact = _wildlife_label(habitat_impact_score, habitat_detected)
    forest_name = forest.name
    weather_context = get_current_weather(db)
    device_code = fire_event.device.device_code if fire_event is not None else None
    if device_code is None:
        device = db.scalar(select(Device).where(Device.forest_id == forest.id).order_by(Device.updated_at.desc(), Device.id.desc()))
        device_code = device.device_code if device is not None else None

    summary_text = (
        f"{report_status.capitalize()} impact estimate for {forest_name}: approximately "
        f"{estimated_burnt_area_m2 or 0:.0f} m2 affected with {impact_level} ecological impact, "
        f"driven by peak severity {peak_severity or 0} and spread heading "
        f"{round(spread_heading) if spread_heading is not None else 'n/a'}."
    )

    sensor_peaks = [
        _sensor_peak(readings, "mq2_analog", "mq2_digital", "MQ2"),
        _sensor_peak(readings, "mq4_analog", "mq4_digital", "MQ4"),
        _sensor_peak(readings, "mq7_analog", "mq7_digital", "MQ7"),
        _sensor_peak(readings, "mq135_analog", "mq135_digital", "MQ135"),
    ]

    summary_json = {
        "report_status": report_status,
        "forest_name": forest_name,
        "device_id": device_code,
        "simulation_id": simulation.id if simulation is not None else None,
        "event_started_at": fire_event.started_at.isoformat() if fire_event is not None and fire_event.started_at is not None else None,
        "event_ended_at": fire_event.ended_at.isoformat() if fire_event is not None and fire_event.ended_at is not None else None,
        "event_duration_minutes": event_duration_minutes,
        "peak_severity": peak_severity,
        "average_severity": avg_severity,
        "alarm_packet_count": alarm_packet_count,
        "estimated_burnt_area_hectares": round((estimated_burnt_area_m2 or 0.0) / 10_000.0, 4) if estimated_burnt_area_m2 is not None else None,
        "forest_area_m2": forest_area,
        "estimated_burn_ratio": estimated_burn_ratio,
        "likely_vegetation_damage": likely_vegetation_damage,
        "likely_wildlife_impact": likely_wildlife_impact,
        "spread_heading": spread_heading,
        "summary_text": summary_text,
        "sensor_peaks": [item.model_dump(mode="json") for item in sensor_peaks],
        "recommended_actions": _recommended_actions(report_status, impact_level),
        "weather_context": weather_context.model_dump(mode="json") if weather_context is not None else None,
    }

    report = ImpactReport(
        forest_id=forest.id,
        device_id=fire_event.device_id if fire_event is not None else None,
        fire_event_id=fire_event.id if fire_event is not None else None,
        estimated_burnt_area_m2=estimated_burnt_area_m2,
        vegetation_loss_score=vegetation_loss_score,
        habitat_impact_score=habitat_impact_score,
        impact_level=impact_level,
        summary_json=summary_json,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return build_fire_analysis_response(report)
