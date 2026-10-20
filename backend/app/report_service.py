from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import re

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .analysis_service import build_fire_analysis_response
from .forest_service import get_latest_forest_upload, summarize_geojson
from .models import FireSimulation, ImpactReport

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    REPORTLAB_IMPORT_ERROR: Exception | None = None
except ImportError as exc:  # pragma: no cover - dependency availability is runtime-specific
    REPORTLAB_IMPORT_ERROR = exc


def _latest_report_record(db: Session) -> ImpactReport | None:
    return db.scalar(
        select(ImpactReport)
        .options(
            joinedload(ImpactReport.forest),
            joinedload(ImpactReport.device),
            joinedload(ImpactReport.fire_event),
        )
        .order_by(ImpactReport.generated_at.desc(), ImpactReport.id.desc())
    )


def _resolve_simulation(db: Session, report: ImpactReport) -> FireSimulation | None:
    simulation_id = report.summary_json.get("simulation_id")
    if simulation_id is not None:
        simulation = db.scalar(
            select(FireSimulation)
            .options(joinedload(FireSimulation.steps))
            .where(FireSimulation.id == simulation_id)
        )
        if simulation is not None:
            return simulation

    if report.fire_event_id is not None:
        simulation = db.scalar(
            select(FireSimulation)
            .options(joinedload(FireSimulation.steps))
            .where(FireSimulation.fire_event_id == report.fire_event_id)
            .order_by(FireSimulation.generated_at.desc(), FireSimulation.id.desc())
        )
        if simulation is not None:
            return simulation

    return db.scalar(
        select(FireSimulation)
        .options(joinedload(FireSimulation.steps))
        .order_by(FireSimulation.generated_at.desc(), FireSimulation.id.desc())
    )


def _format_datetime(value: datetime | str | None) -> str:
    if value is None:
        return "Not available"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if value.tzinfo is None:
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _format_number(value: float | int | None, suffix: str = "", digits: int = 0) -> str:
    if value is None:
        return "Not available"
    if isinstance(value, int) or digits == 0:
        rendered = f"{round(float(value)):,}"
    else:
        rendered = f"{float(value):,.{digits}f}"
    return f"{rendered}{suffix}"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "forest-report"


def build_latest_analysis_pdf(db: Session) -> tuple[bytes, str]:
    if REPORTLAB_IMPORT_ERROR is not None:
        raise RuntimeError("PDF export requires the 'reportlab' package. Install backend dependencies again.")

    report = _latest_report_record(db)
    if report is None:
        raise ValueError("Generate an analysis report before exporting PDF.")

    analysis = build_fire_analysis_response(report)
    forest = report.forest
    simulation = _resolve_simulation(db, report)
    latest_upload = get_latest_forest_upload(db, forest.id) if forest is not None else None
    geojson_summary = summarize_geojson(latest_upload.source_geojson) if latest_upload is not None else None
    weather_context = report.summary_json.get("weather_context") or {}

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title="Forest Fire Shield Impact Report",
        author="Forest Fire Shield",
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportEyebrow",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#C08457"),
            spaceAfter=5,
            uppercase=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportLead",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=16,
            textColor=colors.HexColor("#334155"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=8,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MutedSmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.6,
            leading=12,
            textColor=colors.HexColor("#64748B"),
        )
    )

    story = [
        Paragraph("Forest Fire Shield", styles["ReportEyebrow"]),
        Paragraph("Wildfire Impact and Simulation Report", styles["ReportTitle"]),
        Paragraph(
            f"Generated { _format_datetime(analysis.generated_at) } from the latest stored fire analysis, "
            "simulation output, forest metadata, and sensor evidence.",
            styles["ReportLead"],
        ),
    ]

    meta_table = Table(
        [
            ["Forest", forest.name if forest is not None else analysis.forest_name or "Unknown"],
            ["Impact Level", analysis.impact_level.title()],
            ["Report Status", analysis.report_status.title()],
            ["Device", analysis.device_id or "Not linked"],
            ["Fire Event", str(analysis.fire_event_id) if analysis.fire_event_id is not None else "Not linked"],
            ["Simulation", str(analysis.simulation_id) if analysis.simulation_id is not None else "Not linked"],
        ],
        colWidths=[34 * mm, 54 * mm, 34 * mm, 54 * mm],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([meta_table, Spacer(1, 10)])

    story.append(Paragraph("Executive Summary", styles["SectionTitle"]))
    story.append(Paragraph(analysis.summary_text, styles["ReportLead"]))

    key_metrics = Table(
        [
            ["Burnt Area", _format_number(analysis.estimated_burnt_area_m2, " m2"), "Burn Ratio", _format_number((analysis.estimated_burn_ratio or 0) * 100, "%", 1)],
            ["Vegetation Loss", str(analysis.vegetation_loss_score), "Habitat Impact", str(analysis.habitat_impact_score)],
            ["Peak Severity", _format_number(analysis.peak_severity), "Average Severity", _format_number(analysis.average_severity, digits=2)],
            ["Alarm Packets", _format_number(analysis.alarm_packet_count), "Duration", _format_number(analysis.event_duration_minutes, " min", 2)],
        ],
        colWidths=[34 * mm, 54 * mm, 34 * mm, 54 * mm],
    )
    key_metrics.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#08151D")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#1E293B")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#334155")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([Paragraph("Key Metrics", styles["SectionTitle"]), key_metrics, Spacer(1, 10)])

    forest_rows = [
        ["Forest Name", forest.name if forest is not None else analysis.forest_name or "Unknown"],
        ["Vegetation Type", forest.vegetation_type if forest is not None and forest.vegetation_type else "Not set"],
        ["Tree Density", forest.tree_density if forest is not None and forest.tree_density else "Not set"],
        ["Canopy Density", forest.canopy_density if forest is not None and forest.canopy_density else "Not set"],
        ["Fuel Load", forest.fuel_load if forest is not None and forest.fuel_load else "Not set"],
        ["Moisture Class", forest.moisture_class if forest is not None and forest.moisture_class else "Not set"],
        ["Mapped Forest Area", _format_number(analysis.forest_area_m2, " m2", 2)],
    ]
    if geojson_summary is not None:
        forest_rows.extend(
            [
                ["Detected Layers", ", ".join(geojson_summary.detected_layers) or "Boundary only"],
                ["Missing Recommended Layers", ", ".join(geojson_summary.missing_recommended_layers) or "None"],
            ]
        )

    forest_table = Table(forest_rows, colWidths=[48 * mm, 128 * mm])
    forest_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend([Paragraph("Forest Context", styles["SectionTitle"]), forest_table, Spacer(1, 10)])

    weather_rows = [
        ["Temperature", _format_number(weather_context.get("temperature"), " C", 1)],
        ["Humidity", _format_number(weather_context.get("relative_humidity"), "%", 1)],
        ["Wind Speed", _format_number(weather_context.get("wind_speed"), " km/h", 1)],
        ["Wind Direction", _format_number(weather_context.get("wind_direction"), " deg", 0)],
        ["Precipitation", _format_number(weather_context.get("precipitation"), " mm", 1)],
        ["Weather Snapshot", _format_datetime(weather_context.get("captured_at"))],
    ]
    if simulation is not None:
        weather_rows.extend(
            [
                ["Simulation Model", simulation.model_version],
                ["Simulation Steps", str(len(simulation.steps))],
            ]
        )

    weather_table = Table(weather_rows, colWidths=[48 * mm, 128 * mm])
    weather_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([Paragraph("Weather and Simulation Context", styles["SectionTitle"]), weather_table, Spacer(1, 10)])

    story.append(Paragraph("Impact Interpretation", styles["SectionTitle"]))
    story.append(Paragraph(f"Vegetation impact: {analysis.likely_vegetation_damage}", styles["ReportLead"]))
    story.append(Paragraph(f"Wildlife impact: {analysis.likely_wildlife_impact}", styles["ReportLead"]))

    sensor_peak_rows = [["Sensor", "Max Analog", "Digital Trips"]]
    sensor_peak_rows.extend(
        [[peak.sensor, str(peak.max_analog), str(peak.digital_trigger_count)] for peak in analysis.sensor_peaks]
    )
    sensor_table = Table(sensor_peak_rows, colWidths=[50 * mm, 50 * mm, 50 * mm])
    sensor_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#0F172A")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([Paragraph("Sensor Evidence", styles["SectionTitle"]), sensor_table, Spacer(1, 10)])

    bullet_style = ParagraphStyle(
        name="BulletText",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#0F172A"),
        leftIndent=0,
    )
    action_items = [
        ListItem(Paragraph(action, bullet_style), leftIndent=10) for action in analysis.recommended_actions
    ]
    story.append(Paragraph("Recommended Actions", styles["SectionTitle"]))
    story.append(ListFlowable(action_items, bulletType="bullet", start="circle"))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Method Note", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "This PDF is an explainable impact estimate generated from live ESP32 sensor evidence, uploaded forest metadata, "
            "cached weather context, and the latest deterministic wildfire spread simulation. It is intended for demo, guide review, "
            "and post-event comparison rather than official field certification.",
            styles["MutedSmall"],
        )
    )

    def draw_footer(canvas, document) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(document.leftMargin, 10 * mm, "Forest Fire Shield // Wildfire Intelligence Suite")
        canvas.drawRightString(A4[0] - document.rightMargin, 10 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)

    filename = f"{_slugify(forest.name if forest is not None else analysis.forest_name or 'forest')}-impact-report-{analysis.id}.pdf"
    return buffer.getvalue(), filename
