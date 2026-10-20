from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Forest(Base):
    __tablename__ = "forests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    boundary_geom = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True),
        nullable=True,
    )
    center_lat: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    center_lon: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    vegetation_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tree_density: Mapped[str | None] = mapped_column(String(50), nullable=True)
    canopy_density: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fuel_load: Mapped[str | None] = mapped_column(String(50), nullable=True)
    moisture_class: Mapped[str | None] = mapped_column(String(50), nullable=True)
    admin_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    devices: Mapped[list["Device"]] = relationship(back_populates="forest")
    fire_events: Mapped[list["FireEvent"]] = relationship(back_populates="forest")
    uploads: Mapped[list["ForestUpload"]] = relationship(back_populates="forest")
    weather_snapshots: Mapped[list["WeatherSnapshot"]] = relationship(back_populates="forest")
    fire_simulations: Mapped[list["FireSimulation"]] = relationship(back_populates="forest")
    impact_reports: Mapped[list["ImpactReport"]] = relationship(back_populates="forest")


class ForestUpload(Base):
    __tablename__ = "forest_uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forest_id: Mapped[int] = mapped_column(ForeignKey("forests.id"), index=True, nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_geojson: Mapped[dict] = mapped_column(JSON, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    forest: Mapped[Forest] = relationship(back_populates="uploads")


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_code: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    forest_id: Mapped[int | None] = mapped_column(ForeignKey("forests.id"), nullable=True)
    location_geom = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    forest: Mapped[Forest | None] = relationship(back_populates="devices")
    sensor_readings: Mapped[list["SensorReading"]] = relationship(back_populates="device")
    fire_events: Mapped[list["FireEvent"]] = relationship(back_populates="device")
    fire_simulations: Mapped[list["FireSimulation"]] = relationship(back_populates="device")
    impact_reports: Mapped[list["ImpactReport"]] = relationship(back_populates="device")


class FireEvent(Base):
    __tablename__ = "fire_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forest_id: Mapped[int | None] = mapped_column(ForeignKey("forests.id"), nullable=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_alarm_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    trigger_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    max_severity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    forest: Mapped[Forest | None] = relationship(back_populates="fire_events")
    device: Mapped[Device] = relationship(back_populates="fire_events")
    sensor_readings: Mapped[list["SensorReading"]] = relationship(back_populates="fire_event")
    simulations: Mapped[list["FireSimulation"]] = relationship(back_populates="fire_event")
    impact_reports: Mapped[list["ImpactReport"]] = relationship(back_populates="fire_event")


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True, nullable=False)
    fire_event_id: Mapped[int | None] = mapped_column(ForeignKey("fire_events.id"), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    timestamp_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mq2_analog: Mapped[int] = mapped_column(Integer, nullable=False)
    mq2_digital: Mapped[int] = mapped_column(Integer, nullable=False)
    mq4_analog: Mapped[int] = mapped_column(Integer, nullable=False)
    mq4_digital: Mapped[int] = mapped_column(Integer, nullable=False)
    mq7_analog: Mapped[int] = mapped_column(Integer, nullable=False)
    mq7_digital: Mapped[int] = mapped_column(Integer, nullable=False)
    mq135_analog: Mapped[int] = mapped_column(Integer, nullable=False)
    mq135_digital: Mapped[int] = mapped_column(Integer, nullable=False)
    flame_detected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ir_detected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    mq_fire: Mapped[bool] = mapped_column(Boolean, nullable=False)
    flame_fire: Mapped[bool] = mapped_column(Boolean, nullable=False)
    alarm: Mapped[bool] = mapped_column(Boolean, index=True, nullable=False)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)
    severity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    device: Mapped[Device] = relationship(back_populates="sensor_readings")
    fire_event: Mapped[FireEvent | None] = relationship(back_populates="sensor_readings")


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forest_id: Mapped[int | None] = mapped_column(ForeignKey("forests.id"), index=True, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    temperature: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    relative_humidity: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    wind_speed: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    wind_direction: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    precipitation: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    forest: Mapped[Forest | None] = relationship(back_populates="weather_snapshots")


class FireSimulation(Base):
    __tablename__ = "fire_simulations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forest_id: Mapped[int | None] = mapped_column(ForeignKey("forests.id"), index=True, nullable=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), index=True, nullable=True)
    fire_event_id: Mapped[int | None] = mapped_column(ForeignKey("fire_events.id"), index=True, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    ignition_lat: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    ignition_lon: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    assumptions_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    forest: Mapped[Forest | None] = relationship(back_populates="fire_simulations")
    device: Mapped[Device | None] = relationship(back_populates="fire_simulations")
    fire_event: Mapped[FireEvent | None] = relationship(back_populates="simulations")
    steps: Mapped[list["SimulationStep"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
        order_by="SimulationStep.hour_offset",
    )


class SimulationStep(Base):
    __tablename__ = "simulation_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[int] = mapped_column(ForeignKey("fire_simulations.id"), index=True, nullable=False)
    hour_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    affected_geom = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True),
        nullable=False,
    )
    estimated_area_m2: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    spread_heading: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    intensity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    active_cells: Mapped[int] = mapped_column(Integer, nullable=False)
    burnt_cells: Mapped[int] = mapped_column(Integer, nullable=False)

    simulation: Mapped[FireSimulation] = relationship(back_populates="steps")


class ImpactReport(Base):
    __tablename__ = "impact_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forest_id: Mapped[int | None] = mapped_column(ForeignKey("forests.id"), index=True, nullable=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), index=True, nullable=True)
    fire_event_id: Mapped[int | None] = mapped_column(ForeignKey("fire_events.id"), index=True, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    estimated_burnt_area_m2: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    vegetation_loss_score: Mapped[int] = mapped_column(Integer, nullable=False)
    habitat_impact_score: Mapped[int] = mapped_column(Integer, nullable=False)
    impact_level: Mapped[str] = mapped_column(String(30), nullable=False)
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    forest: Mapped[Forest | None] = relationship(back_populates="impact_reports")
    device: Mapped[Device | None] = relationship(back_populates="impact_reports")
    fire_event: Mapped[FireEvent | None] = relationship(back_populates="impact_reports")
