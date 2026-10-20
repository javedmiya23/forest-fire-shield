from __future__ import annotations

from datetime import datetime
from pathlib import Path
from textwrap import dedent, wrap
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "Forest_Fire_Shield_Project_Handbook.pdf"


def load_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def wrap_code_block(text: str, width: int = 96) -> str:
    wrapped_lines: list[str] = []
    for line in text.rstrip().splitlines():
        stripped = line.rstrip()
        if not stripped:
            wrapped_lines.append("")
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        prefix = " " * indent
        pieces = wrap(
            stripped.lstrip(" "),
            width=max(width - indent, 24),
            subsequent_indent="  ",
            break_long_words=False,
            break_on_hyphens=False,
        )
        wrapped_lines.extend(f"{prefix}{piece}" for piece in pieces or [""])
    return "\n".join(wrapped_lines)


def snippet_between(relative_path: str, start_marker: str, end_marker: str | None = None, extra_lines: int = 0) -> str:
    lines = load_text(relative_path).splitlines()
    start_index = None
    end_index = None
    for index, line in enumerate(lines):
        if start_marker in line:
            start_index = index
            break
    if start_index is None:
        raise ValueError(f"Start marker {start_marker!r} not found in {relative_path}")

    if end_marker is not None:
        for index in range(start_index + 1, len(lines)):
            if end_marker in lines[index]:
                end_index = index
                break
        if end_index is None:
            end_index = len(lines)
    else:
        end_index = min(len(lines), start_index + 18 + extra_lines)

    selected = lines[start_index : min(len(lines), end_index + extra_lines)]
    return "\n".join(selected).rstrip()


styles = getSampleStyleSheet()
TITLE = ParagraphStyle(
    "HandbookTitle",
    parent=styles["Title"],
    fontName="Helvetica-Bold",
    fontSize=24,
    leading=30,
    textColor=colors.HexColor("#0b3954"),
    alignment=TA_CENTER,
    spaceAfter=18,
)
SUBTITLE = ParagraphStyle(
    "Subtitle",
    parent=styles["Heading2"],
    fontName="Helvetica",
    fontSize=12,
    leading=16,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#304d63"),
    spaceAfter=10,
)
H1 = ParagraphStyle(
    "H1",
    parent=styles["Heading1"],
    fontName="Helvetica-Bold",
    fontSize=18,
    leading=22,
    textColor=colors.HexColor("#102a43"),
    spaceBefore=8,
    spaceAfter=8,
)
H2 = ParagraphStyle(
    "H2",
    parent=styles["Heading2"],
    fontName="Helvetica-Bold",
    fontSize=14,
    leading=18,
    textColor=colors.HexColor("#1f3c56"),
    spaceBefore=8,
    spaceAfter=6,
)
H3 = ParagraphStyle(
    "H3",
    parent=styles["Heading3"],
    fontName="Helvetica-Bold",
    fontSize=11,
    leading=14,
    textColor=colors.HexColor("#284b63"),
    spaceBefore=6,
    spaceAfter=4,
)
BODY = ParagraphStyle(
    "Body",
    parent=styles["BodyText"],
    fontName="Helvetica",
    fontSize=9.4,
    leading=13.8,
    textColor=colors.HexColor("#102a43"),
    spaceAfter=6,
)
BULLET = ParagraphStyle(
    "Bullet",
    parent=BODY,
    leftIndent=14,
    firstLineIndent=-8,
    bulletIndent=0,
    spaceAfter=3,
)
SMALL = ParagraphStyle(
    "Small",
    parent=BODY,
    fontSize=8.2,
    leading=11.2,
    textColor=colors.HexColor("#486581"),
)
CODE_STYLE = ParagraphStyle(
    "CodeLabel",
    parent=BODY,
    fontName="Helvetica-Bold",
    fontSize=9.2,
    leading=12,
    textColor=colors.HexColor("#7c2d12"),
    spaceBefore=4,
    spaceAfter=3,
)
CODE_BLOCK_STYLE = ParagraphStyle(
    "CodeBlock",
    parent=BODY,
    fontName="Courier",
    fontSize=6.8,
    leading=8.2,
    textColor=colors.black,
    leftIndent=8,
    rightIndent=8,
    spaceAfter=6,
)


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#d9e2ec"))
    canvas.line(40, A4[1] - 34, A4[0] - 40, A4[1] - 34)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#486581"))
    canvas.drawString(42, A4[1] - 28, "Forest Fire Shield Project Handbook")
    canvas.drawRightString(A4[0] - 42, 22, f"Page {doc.page}")
    canvas.restoreState()


def heading(text: str, level: int = 1) -> Paragraph:
    style = H1 if level == 1 else H2 if level == 2 else H3
    return Paragraph(escape(text), style)


def para(text: str, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(escape(" ".join(text.strip().split())), style)


def bullet(text: str) -> Paragraph:
    return Paragraph(escape(" ".join(text.strip().split())), BULLET, bulletText="•")


def code_block(label: str, code_text: str) -> list:
    return [
        Paragraph(escape(label), CODE_STYLE),
        Preformatted(wrap_code_block(code_text), CODE_BLOCK_STYLE),
    ]


backend_file_descriptions = [
    ("backend/app/config.py", "Loads .env settings, applies defaults, and centralizes runtime configuration."),
    ("backend/app/database.py", "Creates the SQLAlchemy engine/session and auto-initializes PostgreSQL/PostGIS tables."),
    ("backend/app/models.py", "Defines forests, uploads, devices, readings, fire events, weather, simulations, and analysis tables."),
    ("backend/app/schemas.py", "Defines the request and response contracts that FastAPI exposes."),
    ("backend/app/main.py", "Registers all HTTP and WebSocket endpoints and lifecycle hooks."),
    ("backend/app/services.py", "Handles ingestion, severity scoring, device connectivity, fire-event lifecycle, and dashboard metrics."),
    ("backend/app/forest_service.py", "Validates GeoJSON, extracts forest geometry, and stores forest metadata."),
    ("backend/app/weather_service.py", "Resolves the weather location, caches snapshots, and fetches current weather."),
    ("backend/app/simulation_service.py", "Runs the grid-based fire spread model."),
    ("backend/app/analysis_service.py", "Builds post-fire ecological and operational impact estimates."),
    ("backend/app/alert_service.py", "Sends SMTP alerts when a fire event opens."),
    ("backend/app/automation_service.py", "Runs periodic weather refresh, stale fire cleanup, and device sync."),
    ("backend/app/live_stream.py", "Maintains WebSocket connections and pushes live sensor updates."),
    ("backend/app/report_service.py", "Converts the latest analysis result into a downloadable PDF."),
    ("backend/app/telemetry.py", "Enables optional OpenTelemetry instrumentation."),
]

frontend_file_descriptions = [
    ("frontend/src/app/app.ts", "Bootstraps the Angular shell."),
    ("frontend/src/app/app.routes.ts", "Defines routes for overview, forest setup, dashboard, simulation, and analysis."),
    ("frontend/src/app/core/api.models.ts", "Contains TypeScript interfaces mirroring backend schemas."),
    ("frontend/src/app/core/api.service.ts", "Encapsulates REST API calls from Angular to FastAPI."),
    ("frontend/src/app/core/live-stream.service.ts", "Handles WebSocket lifecycle and reconnect logic."),
    ("frontend/src/app/core/map-style.config.ts", "Configures MapLibre basemap selection."),
    ("frontend/src/app/pages/home-page.component.ts", "Implements the landing page."),
    ("frontend/src/app/pages/forest-setup-page.component.ts", "Implements GeoJSON validation/upload and the forest creation flow."),
    ("frontend/src/app/pages/dashboard-page.component.ts", "Coordinates dashboard summary, readings history, and WebSocket events."),
    ("frontend/src/app/pages/simulation-page.component.ts", "Runs simulations and manages hour-by-hour playback."),
    ("frontend/src/app/pages/analysis-page.component.ts", "Generates analysis reports and exposes PDF export."),
    ("frontend/src/app/shared/components/forest-map/forest-map.component.ts", "Renders the command-style interactive map."),
    ("frontend/src/app/shared/components/simulation-reel/simulation-reel.component.ts", "Creates the cinematic simulation preview/export canvas."),
]

glossary = [
    ("Analog value", "The continuous numeric reading from an MQ gas sensor, used for threshold-based fire evidence."),
    ("Analysis report", "The post-fire summary generated after a fire event and simulation run, including impact estimates and recommended actions."),
    ("Admin email", "The recipient address used by the backend alert service when a fire event opens."),
    ("Alarm", "A boolean state representing whether the backend considers the current packet dangerous enough to flag as fire-related."),
    ("Alarm packets", "Sensor packets whose computed fire logic contains alarm=true."),
    ("Area", "Usually refers to estimated affected area in square meters in the simulation and analysis modules."),
    ("Automation Watch", "Dashboard panel showing background worker status for weather refresh, fire-event cleanup, and device sync."),
    ("Basemap", "The visual map tiles rendered below forest and fire overlays, such as street or hybrid satellite view."),
    ("Boundary", "The main forest polygon that defines the area of interest."),
    ("Burn ratio", "Estimated burnt area divided by total mapped forest area."),
    ("Burnt cells", "Grid cells that have already burned in the simulation model."),
    ("Canopy density", "A forest metadata field indicating how dense the upper tree cover is."),
    ("Cell size", "The side length, in meters, of each simulation grid cell. Smaller values give more detail but increase computation."),
    ("Center point", "The centroid of the uploaded forest boundary stored in the backend."),
    ("Command layer", "The 3D visual overlay on the map showing wind corridor, scanline effects, and command context."),
    ("Connected", "Device status when packets arrive within the configured heartbeat window."),
    ("Dashboard summary", "Aggregated backend response containing latest reading, metrics, device status, weather, and fire-event context."),
    ("Detected layers", "GeoJSON layer categories inferred from uploaded properties, such as water bodies, roads, or wildlife habitats."),
    ("Device heartbeat", "The repeated packet flow used to determine whether the ESP32 is still online."),
    ("Device status", "One of connected, warning, disconnected, or unknown based on packet recency."),
    ("Digital value", "The binary 0/1 trigger output from an MQ sensor module."),
    ("ESP32", "The microcontroller board used to read sensors and post data to the FastAPI backend."),
    ("FeatureCollection", "A GeoJSON container holding multiple features such as polygons, lines, and points."),
    ("Fire event", "A backend entity that represents a continuous period of alarm activity."),
    ("Fire logic", "The decision block containing mq_fire, flame_fire, alarm, and trigger."),
    ("Firebreak", "A mapped barrier layer used to reduce or block spread in the simulation."),
    ("Flame fire", "A boolean indicating that flame-driven evidence, rather than only gas evidence, contributed to fire logic."),
    ("Flame sensor", "The hardware sensor that detects direct flame signatures."),
    ("Forest detail", "The backend response that returns saved forest metadata, boundary, sensor point, and GeoJSON summary."),
    ("Fuel factor", "A simulation coefficient derived from vegetation type, tree density, canopy density, fuel load, and moisture class."),
    ("Fuel load", "The estimated amount of dry biomass available to burn."),
    ("GeoJSON", "The spatial data format used to upload or create forest boundaries and related map layers."),
    ("Grafana", "The optional visualization layer used when telemetry is enabled."),
    ("Habitat impact", "An analysis score estimating how much the simulated fire could disturb wildlife zones."),
    ("Hour offset", "The simulated hour number for each simulation step, such as 1, 2, 3, and so on."),
    ("Humidity", "Relative humidity fetched from the weather API and used in simulation and monitoring."),
    ("Ignition point", "The initial location from which the simulation begins spreading."),
    ("Impact level", "Categorical analysis classification such as low, moderate, high, or critical."),
    ("Intensity score", "Per-step simulation metric indicating current spread strength."),
    ("IR sensor", "Infrared-based sensor used as an additional fire-related signal."),
    ("Location source", "Indicates whether weather coordinates came from the sensor point or forest centroid."),
    ("MapLibre", "The frontend mapping library used to render the interactive map."),
    ("Model assumptions", "The explainable parameters and notes attached to each simulation run."),
    ("Moisture class", "A forest metadata field describing how dry or wet the forest fuel conditions are."),
    ("MQ fire", "A boolean indicating that gas sensor evidence crossed the fire threshold logic."),
    ("OpenTelemetry", "Optional backend telemetry instrumentation for traces and metrics."),
    ("Polygon", "The GeoJSON geometry type used to represent a forest boundary or affected simulation area."),
    ("PostGIS", "PostgreSQL spatial extension used to store and process geospatial geometries."),
    ("Precipitation", "Rainfall-related weather field used to damp spread in the simulation."),
    ("Raw payload", "The original JSON packet stored with a sensor reading for traceability."),
    ("Reading history", "A backend response returning a time window of stored sensor packets."),
    ("Realtime stream", "The live WebSocket pipeline that pushes sensor updates to the dashboard."),
    ("Relative humidity", "The percentage humidity value returned by the weather API."),
    ("Severity score", "A derived 0-100 value computed from analog ratios, digital trips, flame, IR, and alarm evidence."),
    ("Sensor linked", "Map badge indicating that a sensor point exists and is being used on the map."),
    ("Simulation mode", "Descriptive label representing how the current simulation was configured."),
    ("Simulation reel", "The cinematic frontend export surface that renders a premium fire spread animation."),
    ("Source geojson", "The stored original GeoJSON that contains the uploaded forest and optional thematic layers."),
    ("Spread heading", "The dominant estimated direction in which the simulated fire is moving."),
    ("Stale fire event", "An active fire event that should be resolved automatically because no alarm heartbeat has been received for too long."),
    ("Temperature", "The current air temperature fetched from Open-Meteo for the forest location."),
    ("Telemetry", "Machine-readable runtime metrics and traces emitted by the backend when enabled."),
    ("Tree density", "A forest metadata field representing how closely packed the trees are."),
    ("Trigger", "A text label such as flame or gas that explains why a packet was classified as fire-related."),
    ("Vegetation type", "The main ecological category of the forest, used in simulation and display."),
    ("Weather factor", "A simulation coefficient derived from temperature, humidity, wind, and precipitation."),
    ("Weather snapshot", "A cached backend record of the latest fetched weather state."),
    ("WebSocket", "A persistent browser-backend connection used for live sensor push."),
    ("Wind direction", "Direction from which the weather API reports wind, converted internally to downwind push for simulation."),
    ("Wind push direction", "Simulation-friendly wind heading after converting the reported wind direction to the downwind direction."),
    ("Wind speed", "Weather API field used to bias the spread model."),
]

viva_questions = [
    ("What problem does Forest Fire Shield solve?", "It provides early wildfire detection plus geospatial decision support by combining ESP32 sensor ingestion, forest mapping, weather enrichment, simulation, and analysis in one system."),
    ("Why did you use ESP32?", "ESP32 is affordable, has enough GPIO and ADC capability for multiple sensors, supports Wi-Fi directly, and is well suited for a final-year IoT prototype."),
    ("Why Angular instead of React?", "Angular gives stronger structure for forms, routing, services, and dashboards, which fits a multi-workspace project like this."),
    ("Why FastAPI instead of Django?", "FastAPI is lighter for API-first systems, integrates cleanly with JSON ingestion from ESP32, and fits Python-based GIS and simulation work."),
    ("Why PostgreSQL with PostGIS?", "Because the project stores points, polygons, centroids, and affected footprints. PostGIS is purpose-built for those tasks."),
    ("Why not use a pure machine learning model for fire spread?", "A pure ML model would need a strong labeled wildfire dataset. This project uses an explainable deterministic model that is easier to defend academically."),
    ("How is fire detected?", "The backend combines MQ analog ratios, MQ digital triggers, flame detection, IR status, and fire-logic flags to compute severity and decide fire-event state."),
    ("What is severity score?", "It is a 0-100 derived score summarizing the seriousness of the latest packet from multiple sensor channels."),
    ("How do you get temperature and humidity without dedicated weather sensors?", "The backend uses the saved forest location and calls Open-Meteo to fetch current weather."),
    ("What is cell size in the simulation?", "It is the size of each grid cell in meters. Smaller values give more detail but increase computation."),
    ("How are email alerts sent?", "When a fire event opens, the backend alert service sends an SMTP email to the configured admin recipient."),
    ("What is stored in the database?", "Forests, uploaded GeoJSON, devices, sensor readings, weather snapshots, fire events, simulations, simulation steps, and impact reports."),
    ("How do roads and water bodies affect simulation?", "They are extracted from GeoJSON and used as barrier layers. Water strongly suppresses spread; roads and firebreaks reduce crossing probability."),
    ("What does the analysis module produce?", "It estimates burnt area, burn ratio, vegetation loss score, habitat impact score, likely damage narratives, and recommended actions."),
    ("Why is this project advanced compared to a simple alarm?", "Because it adds geospatial modeling, weather-aware simulation, dashboard analytics, PDF reporting, and optional realtime and observability features."),
    ("How does the live dashboard update?", "It uses REST APIs for baseline state and WebSocket push for live sensor events."),
    ("What are the main limitations?", "It is still a simulation rather than an exact real-world prediction, and it does not yet use high-resolution terrain or multi-device deployment."),
    ("How do you validate GeoJSON uploads?", "The backend checks for a valid polygon boundary, tries to find a sensor point, and summarizes optional layers."),
    ("How do you know the ESP32 is connected?", "Device connectivity is computed from the time difference between now and the last received packet."),
    ("How would you extend the project in the future?", "I would add multiple devices, terrain-aware spread, satellite hotspot validation, responder routing, and stronger historical analytics."),
]


def build_story() -> list:
    story: list = []
    today = datetime.now().strftime("%d %B %Y")

    story.extend(
        [
            Spacer(1, 0.35 * inch),
            Paragraph("Forest Fire Shield", TITLE),
            Paragraph("Comprehensive Project Handbook and Viva Guide", SUBTITLE),
            Paragraph(
                "A detailed implementation guide covering architecture, stack decisions, code walkthroughs, deployment, debugging, database access, glossary, and viva preparation.",
                SUBTITLE,
            ),
            Spacer(1, 0.2 * inch),
            Paragraph(f"Generated on {today}", SUBTITLE),
            Spacer(1, 0.35 * inch),
            para(
                """
                This handbook is written specifically for the current Forest Fire Shield repository. It is meant to support your final-year project explanation, practical demonstration, report writing, poster preparation, and viva answers.
                """
            ),
            para(
                """
                The document goes beyond a README and tries to explain the system as a complete engineering artifact. It describes what the project does, why the stack was chosen, what each major file contributes, how the database should be inspected, how the project should be deployed, how to debug common failures, and how to defend design decisions academically.
                """
            ),
            PageBreak(),
            heading("Table of Contents", 1),
        ]
    )

    toc_items = [
        "1. Project Overview",
        "2. Why This Tech Stack Was Chosen",
        "3. Alternatives Considered and Why They Were Not Chosen",
        "4. End-to-End System Workflow",
        "5. Repository Structure",
        "6. Backend Deep Dive",
        "7. Frontend Deep Dive",
        "8. Main Code Snippets and Explanation",
        "9. API Catalog",
        "10. Database Design and DBeaver Usage",
        "11. SQL Queries for Every Table",
        "12. Deployment Guide",
        "13. Debugging and Troubleshooting Guide",
        "14. Project Glossary",
        "15. Demo Checklist and Best Practices",
        "16. Future Improvements",
        "17. Viva Questions and Answers",
    ]
    story.extend(bullet(item) for item in toc_items)
    story.append(PageBreak())

    story.append(heading("1. Project Overview", 1))
    story.append(
        para(
            """
            Forest Fire Shield is a single-forest, single-ESP32 wildfire detection and decision-support platform. It starts with live sensing from ESP32 hardware, stores evidence in PostgreSQL/PostGIS, visualizes the forest through a GeoJSON-driven map workflow, enriches the dashboard with weather data, raises email alerts when fire conditions occur, simulates future spread hour by hour, and generates post-fire impact analysis with PDF reporting.
            """
        )
    )
    story.append(
        para(
            """
            The system is deliberately designed as an end-to-end pipeline rather than a loose set of features. Hardware packets move through validation, persistence, event lifecycle logic, weather context, simulation, analysis, and user-facing visualization. That full-stack continuity is what makes the project stronger than a basic IoT alarm.
            """
        )
    )
    story.append(heading("Primary goals", 2))
    story.extend(
        bullet(item)
        for item in [
            "Detect gas-, smoke-, and flame-related evidence from ESP32 sensors in real time.",
            "Store incoming packets for later analysis, reporting, and demonstration.",
            "Allow a user to upload or create a forest map in GeoJSON form.",
            "Use the mapped forest location to fetch weather data such as temperature, humidity, wind speed, and wind direction.",
            "Open, update, and resolve fire events automatically based on sensor evidence.",
            "Simulate likely fire spread using an explainable deterministic model.",
            "Estimate ecological impact after the event and export a PDF report.",
        ]
    )
    story.append(heading("Hardware in the project", 2))
    story.extend(
        bullet(item)
        for item in [
            "ESP32: central microcontroller and Wi-Fi communication unit.",
            "MQ2: combustible gas and smoke evidence channel.",
            "MQ4: methane-related gas evidence channel.",
            "MQ7: carbon monoxide evidence channel.",
            "MQ135: air-quality and smoke-related gas evidence channel.",
            "Flame sensor: direct optical flame evidence.",
            "IR sensor: extra infrared evidence that supports event interpretation.",
            "Buzzer: local alarm output when fire logic is triggered.",
        ]
    )

    story.append(PageBreak())
    story.append(heading("2. Why This Tech Stack Was Chosen", 1))
    story.append(
        para(
            """
            The stack was chosen to maximize practical implementation quality, geospatial suitability, academic explainability, and final-demo stability. The goal was not simply to use fashionable tools. The goal was to choose tools that fit a geospatial IoT simulation project with the least unnecessary complexity and the strongest defendability in front of a guide or panel.
            """
        )
    )

    stack_sections = [
        (
            "Angular for the frontend",
            [
                "Angular gives a structured project layout for forms, services, routing, and dashboards.",
                "It works very well for admin-style UIs where there are multiple modules such as setup, dashboard, simulation, and analysis.",
                "TypeScript interfaces align cleanly with FastAPI response models, which reduces integration mistakes.",
            ],
            ["Strong structure and routing.", "Excellent for typed service layers and long-lived dashboards.", "Good fit for enterprise-style presentation quality."],
            ["Slightly more verbose than React for very small experiments.", "Initial learning curve is higher if the developer is new to Angular."],
        ),
        (
            "FastAPI for the backend",
            [
                "FastAPI is lightweight and API-first, which matches ESP32 JSON ingestion very well.",
                "It supports async HTTP calls, easy schema definition, and automatic Swagger docs.",
                "Python is also a strong ecosystem for geospatial, simulation, PDF generation, and ML-adjacent work.",
            ],
            ["Fast JSON API development.", "Automatic request and response validation.", "Excellent fit for weather fetching, simulation, and reporting."],
            ["Not as batteries-included as Django for auth/admin panels.", "Long-term large-system architecture may require stronger service decomposition."],
        ),
        (
            "PostgreSQL + PostGIS for the database",
            [
                "The project stores points, polygons, centroids, and affected areas. A plain relational store is not enough.",
                "PostGIS allows the backend to store and reason about geometry objects directly.",
                "Spatial indexing and geometry conversion are extremely valuable for GeoJSON-based workflows.",
            ],
            ["Best fit for geospatial storage and queries.", "Reliable open-source relational database.", "Supports both structured rows and spatial reasoning."],
            ["Requires PostGIS extension availability.", "Slightly more setup effort than SQLite."],
        ),
        (
            "MapLibre + MapTiler for map rendering",
            [
                "The project needs an interactive, stylish, and scriptable map layer in the frontend.",
                "MapLibre gives good control over basemap styles, custom layers, markers, and overlays.",
                "MapTiler provides the higher-quality street and hybrid basemap styles used in the polished UI.",
            ],
            ["Strong visual control.", "No lock-in to Google Maps.", "Good support for 3D-style command-center presentation."],
            ["Needs API key management for premium basemaps.", "Large GeoJSON files can affect browser rendering performance."],
        ),
        (
            "WebSockets for live sensor push",
            [
                "Polling alone is enough to build a dashboard, but WebSockets make the control-room feel live and responsive.",
                "Sensor updates can be pushed immediately after ingestion instead of waiting for the next poll cycle.",
            ],
            ["Improves demo quality and responsiveness.", "Useful for future scaling to multiple devices or live operator stations."],
            ["Adds some runtime complexity compared to plain REST polling.", "Requires WebSocket library support in the backend server."],
        ),
        (
            "OpenTelemetry + Grafana as optional observability",
            [
                "These are not required for core wildfire functionality.",
                "They were added as an advanced layer so the project can also demonstrate enterprise-style observability.",
                "They allow runtime monitoring of traces, metrics, and backend health when enabled.",
            ],
            ["Makes the architecture look more production-grade.", "Useful when explaining non-functional system qualities."],
            ["Adds extra infrastructure and can generate noise if enabled without the collector running.", "Should be disabled when not explicitly being demonstrated."],
        ),
    ]
    for section_title, rationale, pros, cons in stack_sections:
        story.append(heading(section_title, 2))
        story.extend(para(item) for item in rationale)
        story.append(heading("Pros", 3))
        story.extend(bullet(item) for item in pros)
        story.append(heading("Cons", 3))
        story.extend(bullet(item) for item in cons)

    story.append(PageBreak())
    story.append(heading("3. Alternatives Considered and Why They Were Not Chosen", 1))
    for title, text in [
        ("React instead of Angular", "React is excellent, but Angular gave more built-in structure for a multi-module final-year project with forms, routing, services, and dashboard workflows."),
        ("Django instead of FastAPI", "Django is powerful, but the project is fundamentally API-driven. FastAPI is simpler for JSON ingestion, simulation services, and Swagger-based testing."),
        (".NET backend instead of Python", "A .NET backend would be strong for enterprise APIs, but Python fits geospatial processing, geometry handling, simulation logic, weather integration, and PDF generation more naturally in this project."),
        ("MongoDB instead of PostgreSQL/PostGIS", "MongoDB can store JSON-like data, but PostGIS is the better choice for polygons, points, centroids, and spatial workflows."),
        ("Pure machine learning fire spread model", "Without a large labeled wildfire dataset, a pure ML model would be hard to justify and explain. The deterministic model gives more academic clarity."),
    ]:
        story.append(heading(title, 2))
        story.append(para(text))

    story.append(PageBreak())
    story.append(heading("4. End-to-End System Workflow", 1))
    story.extend(
        bullet(item)
        for item in [
            "Step 1: The ESP32 reads gas, flame, and IR sensors and packages the values into a JSON payload.",
            "Step 2: The ESP32 sends the payload to the FastAPI backend over Wi-Fi using the /data endpoint.",
            "Step 3: The backend validates the payload using Pydantic schemas.",
            "Step 4: The backend stores the reading in PostgreSQL and updates device last_seen_at.",
            "Step 5: The backend computes severity and synchronizes the fire event lifecycle.",
            "Step 6: If a fire event opens, the backend sends an SMTP email alert.",
            "Step 7: The backend broadcasts the reading over WebSocket so the Angular dashboard updates instantly.",
            "Step 8: The forest module stores the GeoJSON boundary and sensor location in PostGIS-backed tables.",
            "Step 9: The weather service fetches current weather for the forest location and caches it in the database.",
            "Step 10: The simulation engine uses forest metadata, weather, severity, and barrier layers to generate hourly spread polygons.",
            "Step 11: The analysis engine combines event evidence and simulation output into a post-fire impact estimate.",
            "Step 12: The report service generates a PDF from the latest analysis report.",
        ]
    )

    story.append(PageBreak())
    story.append(heading("5. Repository Structure", 1))
    story.append(heading("Backend files", 2))
    story.extend(bullet(f"{path}: {desc}") for path, desc in backend_file_descriptions)
    story.append(heading("Frontend files", 2))
    story.extend(bullet(f"{path}: {desc}") for path, desc in frontend_file_descriptions)

    story.append(PageBreak())
    story.append(heading("6. Backend Deep Dive", 1))
    story.append(
        para(
            """
            The backend is the operational core of the system. It exposes the REST API, WebSocket endpoint, database persistence, forest processing, weather retrieval, simulation engine, analysis engine, alerting, automation, and optional telemetry.
            """
        )
    )
    for title, text in [
        ("Configuration and environment loading", "config.py loads the .env file and exposes a cached Settings object containing API, database, weather, simulation, alert, WebSocket, automation, and telemetry settings."),
        ("Database initialization", "database.py creates the SQLAlchemy engine and session factory. At startup, initialize_database() optionally creates the PostGIS extension and all ORM tables."),
        ("Data modeling", "models.py defines the persistent entities: forests, forest uploads, devices, readings, fire events, weather snapshots, fire simulations, simulation steps, and impact reports."),
        ("API contract layer", "schemas.py separates transport models from database models and is the basis for validation and Swagger documentation."),
        ("Main FastAPI application", "main.py wires all routes together, starts the automation worker in lifespan, initializes telemetry, and exposes both REST and WebSocket interfaces."),
        ("Ingestion and fire-event logic", "services.py converts every sensor packet into stored state by calculating severity, updating device heartbeat, synchronizing the fire event, triggering alerting, and broadcasting a live update."),
        ("GeoJSON handling", "forest_service.py validates uploaded GeoJSON, extracts the boundary and sensor point, summarizes optional layers, and stores the normalized forest context."),
        ("Weather subsystem", "weather_service.py decides whether weather should be fetched from the sensor point or forest centroid, caches snapshots, and returns normalized weather data."),
        ("Simulation subsystem", "simulation_service.py implements the grid-based spread model using weather, severity, ecological metadata, and barrier layers such as water, roads, and firebreaks."),
        ("Analysis subsystem", "analysis_service.py combines event evidence and simulation output into a defendable impact estimate with vegetation and habitat scoring."),
        ("Report subsystem", "report_service.py renders the latest analysis report into a PDF using ReportLab."),
        ("Alerting subsystem", "alert_service.py sends SMTP alerts while ensuring that an email failure does not break the ingestion pipeline."),
        ("Automation subsystem", "automation_service.py keeps weather, device statuses, and stale fire-event cleanup moving in the background."),
        ("Realtime subsystem", "live_stream.py maintains WebSocket connections and pushes live sensor frames and heartbeat frames to the frontend."),
        ("Telemetry subsystem", "telemetry.py keeps observability optional so the project can run cleanly even without an OTLP collector."),
    ]:
        story.append(heading(title, 2))
        story.append(para(text))

    story.append(PageBreak())
    story.append(heading("7. Frontend Deep Dive", 1))
    story.append(
        para(
            """
            The frontend is a multi-workspace control interface rather than just a single dashboard. It covers the overview page, forest setup, live dashboard, simulation studio, analysis studio, and shared geospatial rendering components.
            """
        )
    )
    for title, text in [
        ("App shell and routing", "The Angular shell routes the user between overview, forest setup, dashboard, simulation, and analysis. This keeps the project narrative modular and easy to present."),
        ("API models and services", "TypeScript models mirror backend schemas so the frontend remains strongly typed. api.service.ts contains the REST calls and live-stream.service.ts manages WebSocket state and reconnect logic."),
        ("Forest setup page", "The forest setup module supports both GeoJSON upload and manual forest creation. It validates files, previews geometry, captures ecological metadata, and stores the resulting forest in the backend."),
        ("Dashboard page", "The dashboard combines live device status, latest reading, severity trend, latest packets, weather cards, fire-event state, email dispatch status, automation watch, and observability indicators."),
        ("Simulation page", "The simulation page exposes scenario controls, hour-by-hour playback, explainable assumptions, weather context, ignition context, fullscreen map mode, and the cinematic simulation reel."),
        ("Analysis page", "The analysis page generates the post-fire report, shows impact footprint on the map, lists sensor peak evidence, and allows PDF export."),
        ("Forest map component", "This shared map component renders the boundary, source GeoJSON layers, simulation overlay, command-center decorations, 3D pitch, basemap switching, sensor marker, and fullscreen mode."),
        ("Simulation reel component", "This component converts simulation output into a canvas-based cinematic reel with trees, wildlife zones, roads, smoke, embers, weather panel, timeline, and export support."),
    ]:
        story.append(heading(title, 2))
        story.append(para(text))

    story.append(PageBreak())
    story.append(heading("8. Main Code Snippets and Explanation", 1))
    story.append(para("This section focuses on the code that best explains how the project actually works. The snippets are selected from the current repository so the explanations stay tied to your implementation."))

    snippets = [
        ("A. Environment-driven settings in backend/app/config.py", "This snippet shows why the project is configurable without code edits. Core runtime behavior such as API port, database URL, simulation defaults, thresholds, background jobs, and alert settings are defined through environment variables.", snippet_between("backend/app/config.py", "class Settings:", "@lru_cache(maxsize=1)", extra_lines=0)),
        ("B. Database bootstrap in backend/app/database.py", "The backend creates the SQLAlchemy engine once and prepares the PostGIS extension and tables automatically. This makes first-time setup easier during local deployment.", snippet_between("backend/app/database.py", "engine = create_engine(", "def get_db()", extra_lines=4)),
        ("C. Severity calculation in backend/app/services.py", "This logic converts raw sensor channels into a single severity score using analog ratios, digital triggers, flame, IR, and alarm evidence.", snippet_between("backend/app/services.py", "def calculate_severity", "def build_fire_event_summary", extra_lines=0)),
        ("D. ESP32 ingestion pipeline in backend/app/services.py", "This is one of the most important snippets in the project. It creates the device if needed, stores the reading, synchronizes the fire event, sends alerts if appropriate, records telemetry, and broadcasts live updates to the frontend.", snippet_between("backend/app/services.py", "def ingest_sensor_payload", "def get_latest_device", extra_lines=0)),
        ("E. Route registration in backend/app/main.py", "main.py is where the services become an API. These routes expose ingestion, dashboard summary, forest upload, simulation, analysis, PDF export, and the WebSocket live stream.", "\n\n".join([snippet_between("backend/app/main.py", '@app.post("/data"', '@app.get("/api/v1/device-status")'), snippet_between("backend/app/main.py", '@app.get("/api/v1/dashboard/summary"', '@app.get("/api/v1/system/automation")'), snippet_between("backend/app/main.py", '@app.post("/api/v1/forests/upload-geojson"', '@app.post("/api/v1/forests/validate-geojson")'), snippet_between("backend/app/main.py", '@app.post("/api/v1/simulations/run"', '@app.get("/api/v1/simulations/latest")'), snippet_between("backend/app/main.py", '@app.websocket("/ws/live")', 'if __name__ == "__main__":')])),
        ("F. REST API base and calls in frontend/src/app/core/api.service.ts", "api.service.ts keeps HTTP calls out of the UI components. This improves reuse and keeps the pages focused on presentation logic instead of raw endpoint details.", load_text("frontend/src/app/core/api.service.ts")),
        ("G. Forest upload workflow in frontend/src/app/pages/forest-setup-page.component.ts", "The forest setup page handles file selection, GeoJSON parsing, validation, and upload. This is the bridge between user map input and the backend forest model.", snippet_between("frontend/src/app/pages/forest-setup-page.component.ts", "protected async onGeoJsonSelected", "protected uploadGeoJson", extra_lines=0) + "\n\n" + snippet_between("frontend/src/app/pages/forest-setup-page.component.ts", "protected uploadGeoJson()", "protected submitForestBuilder", extra_lines=0)),
        ("H. Simulation controls in frontend/src/app/pages/simulation-page.component.ts", "The frontend keeps simulation state typed and controlled. This shows the run form defaults, compatibility guard for changing forests, and the action that calls the backend.", snippet_between("frontend/src/app/pages/simulation-page.component.ts", "protected readonly runForm", "private playbackTimer", extra_lines=0) + "\n\n" + snippet_between("frontend/src/app/pages/simulation-page.component.ts", "protected runSimulation()", "protected selectHour", extra_lines=0)),
        ("I. WebSocket live push in backend/app/live_stream.py", "The live stream manager is the reason the dashboard can react instantly to new packets. It accepts clients, sends a connection frame, broadcasts updates, and runs heartbeat messages.", load_text("backend/app/live_stream.py")),
        ("J. Fullscreen command map in frontend/src/app/shared/components/forest-map/forest-map.component.ts", "The shared map component supports sensor markers, 3D command styling, boundary rendering, simulation overlay, basemap switching, and fullscreen mode.", snippet_between("frontend/src/app/shared/components/forest-map/forest-map.component.ts", "template: `", "ngAfterViewInit(): void {", extra_lines=0) + "\n\n" + snippet_between("frontend/src/app/shared/components/forest-map/forest-map.component.ts", "protected async toggleFullscreen()", "private renderMapData", extra_lines=0)),
        ("K. Simulation reel export in frontend/src/app/shared/components/simulation-reel/simulation-reel.component.ts", "This code creates the cinematic reel experience by rendering simulation output into a canvas and exporting it as WebM when the browser supports MediaRecorder.", snippet_between("frontend/src/app/shared/components/simulation-reel/simulation-reel.component.ts", "protected async exportVideo()", "private animatePreview", extra_lines=0)),
    ]
    for label, explanation, code in snippets:
        story.append(heading(label, 2))
        story.append(para(explanation))
        story.extend(code_block("Code snippet", code))

    story.append(PageBreak())
    story.append(heading("9. API Catalog", 1))
    for route, desc in [
        ("GET /health", "Basic health endpoint that confirms the backend is up."),
        ("POST /data", "Legacy ESP32-compatible ingestion endpoint that stores a sensor packet and updates system state."),
        ("POST /api/v1/ingest", "Versioned ingestion endpoint that performs the same work as /data."),
        ("GET /api/v1/device-status", "Returns connectivity state based on last packet time."),
        ("GET /api/v1/readings/latest", "Returns the latest stored sensor packet summary."),
        ("GET /api/v1/readings/history", "Returns recent sensor packets with optional alarm-only filtering."),
        ("GET /api/v1/dashboard/summary", "Returns the main dashboard payload containing metrics, reading, events, and weather."),
        ("GET /api/v1/system/automation", "Returns background-worker state and recent automation job results."),
        ("GET /api/v1/system/observability", "Returns telemetry and observability status information."),
        ("POST /api/v1/forests/create", "Creates or updates the forest from manually entered metadata and geometry."),
        ("POST /api/v1/forests/upload-geojson", "Uploads a GeoJSON file and persists it as the current forest."),
        ("POST /api/v1/forests/validate-geojson", "Checks whether a GeoJSON file is compatible before saving."),
        ("GET /api/v1/forests/current", "Returns the currently saved forest and its summary."),
        ("GET /api/v1/weather/current", "Returns cached or freshly fetched weather for the forest location."),
        ("POST /api/v1/simulations/run", "Runs the fire spread engine and stores a new simulation record."),
        ("GET /api/v1/simulations/latest", "Returns the most recent simulation."),
        ("POST /api/v1/analysis/generate", "Generates the latest impact analysis report."),
        ("GET /api/v1/analysis/latest", "Returns the latest impact analysis summary."),
        ("GET /api/v1/analysis/latest/report.pdf", "Downloads the latest impact report as PDF."),
        ("WS /ws/live", "Pushes live sensor updates and heartbeats to the dashboard."),
    ]:
        story.append(heading(route, 2))
        story.append(para(desc))

    story.append(PageBreak())
    story.append(heading("10. Database Design and DBeaver Usage", 1))
    story.append(para("The database is one of the strengths of this project because it stores both normal relational data and geospatial geometry. DBeaver is useful because it allows table browsing, filtering, SQL execution, and side-by-side inspection of related records."))
    story.append(heading("How to connect DBeaver", 2))
    story.extend(
        bullet(item)
        for item in [
            "Open DBeaver and create a new PostgreSQL connection.",
            "Host: localhost",
            "Port: 5432",
            "Database: forest_fire_shield",
            "Username: postgres",
            "Password: the value from backend/.env",
            "Test the connection, then browse Schemas -> public -> Tables.",
        ]
    )
    story.append(heading("Tables in this project", 2))
    story.extend(bullet(table_name) for table_name in ["forests", "forest_uploads", "devices", "sensor_readings", "weather_snapshots", "fire_events", "fire_simulations", "simulation_steps", "impact_reports"])

    story.append(PageBreak())
    story.append(heading("11. SQL Queries for Every Table", 1))
    story.append(para("The following query bank is designed for DBeaver or psql. These are read-only queries that help verify ingestion, forest upload, device linking, fire events, weather, simulation output, and final analysis reports."))
    sql_sections = [
        ("General database inspection", [("List all tables", r"\dt"), ("Show database size", "SELECT pg_size_pretty(pg_database_size('forest_fire_shield'));"), ("Count rows in all main tables", dedent("""SELECT 'forests' AS table_name, COUNT(*) FROM forests\nUNION ALL SELECT 'forest_uploads', COUNT(*) FROM forest_uploads\nUNION ALL SELECT 'devices', COUNT(*) FROM devices\nUNION ALL SELECT 'sensor_readings', COUNT(*) FROM sensor_readings\nUNION ALL SELECT 'weather_snapshots', COUNT(*) FROM weather_snapshots\nUNION ALL SELECT 'fire_events', COUNT(*) FROM fire_events\nUNION ALL SELECT 'fire_simulations', COUNT(*) FROM fire_simulations\nUNION ALL SELECT 'simulation_steps', COUNT(*) FROM simulation_steps\nUNION ALL SELECT 'impact_reports', COUNT(*) FROM impact_reports;"""))]),
        ("forests table", [("Show all forests", "SELECT id, name, center_lat, center_lon, vegetation_type, tree_density, canopy_density, fuel_load, moisture_class, admin_email, created_at FROM forests ORDER BY id DESC;"), ("Show forest geometry type", "SELECT id, name, GeometryType(boundary_geom) AS geometry_type FROM forests;"), ("Show forest boundary as WKT", "SELECT id, name, ST_AsText(boundary_geom) FROM forests;"), ("Show forest area in square meters", "SELECT id, name, ST_Area(ST_Transform(boundary_geom, 3857)) AS area_m2 FROM forests;")]),
        ("forest_uploads table", [("Show uploaded files", "SELECT id, forest_id, file_name, uploaded_at FROM forest_uploads ORDER BY uploaded_at DESC;"), ("Pretty-print uploaded GeoJSON", "SELECT id, file_name, jsonb_pretty(source_geojson::jsonb) FROM forest_uploads ORDER BY uploaded_at DESC LIMIT 1;")]),
        ("devices table", [("Show all devices", "SELECT id, device_code, forest_id, status, last_seen_at, created_at, updated_at FROM devices ORDER BY id DESC;"), ("Show device point geometry", "SELECT id, device_code, ST_AsText(location_geom) AS sensor_point FROM devices;"), ("Show linked forest names", dedent("""SELECT d.id, d.device_code, d.status, d.last_seen_at, f.name AS forest_name\nFROM devices d\nLEFT JOIN forests f ON f.id = d.forest_id\nORDER BY d.id DESC;"""))]),
        ("sensor_readings table", [("Latest 20 readings", "SELECT id, device_id, recorded_at, timestamp_ms, alarm, trigger, severity_score FROM sensor_readings ORDER BY recorded_at DESC LIMIT 20;"), ("Full latest reading", "SELECT * FROM sensor_readings ORDER BY recorded_at DESC LIMIT 1;"), ("Latest alarm readings", "SELECT id, recorded_at, trigger, severity_score FROM sensor_readings WHERE alarm = true ORDER BY recorded_at DESC LIMIT 20;"), ("Average and max severity", "SELECT AVG(severity_score) AS avg_severity, MAX(severity_score) AS max_severity FROM sensor_readings;"), ("MQ peak summary", "SELECT MAX(mq2_analog) AS mq2_max, MAX(mq4_analog) AS mq4_max, MAX(mq7_analog) AS mq7_max, MAX(mq135_analog) AS mq135_max FROM sensor_readings;"), ("Readings count per hour", "SELECT date_trunc('hour', recorded_at) AS hour_slot, COUNT(*) FROM sensor_readings GROUP BY hour_slot ORDER BY hour_slot DESC;")]),
        ("weather_snapshots table", [("Latest weather snapshots", "SELECT id, forest_id, captured_at, source_name, latitude, longitude, temperature, relative_humidity, wind_speed, wind_direction, precipitation FROM weather_snapshots ORDER BY captured_at DESC LIMIT 20;"), ("Latest weather only", "SELECT * FROM weather_snapshots ORDER BY captured_at DESC LIMIT 1;")]),
        ("fire_events table", [("Show all fire events", "SELECT id, forest_id, device_id, status, trigger_type, started_at, last_alarm_at, ended_at, max_severity, alert_sent FROM fire_events ORDER BY id DESC;"), ("Active fire events", "SELECT * FROM fire_events WHERE status = 'active' ORDER BY started_at DESC;"), ("Resolved fire events", "SELECT * FROM fire_events WHERE status = 'resolved' ORDER BY ended_at DESC;"), ("Event duration", "SELECT id, started_at, ended_at, EXTRACT(EPOCH FROM (ended_at - started_at))/60 AS duration_minutes FROM fire_events WHERE ended_at IS NOT NULL ORDER BY id DESC;")]),
        ("fire_simulations table", [("Show all simulations", "SELECT id, forest_id, device_id, fire_event_id, generated_at, model_version, ignition_lat, ignition_lon FROM fire_simulations ORDER BY generated_at DESC;"), ("Show assumptions JSON", "SELECT id, jsonb_pretty(assumptions_json::jsonb) FROM fire_simulations ORDER BY generated_at DESC LIMIT 1;")]),
        ("simulation_steps table", [("Show simulation steps", "SELECT id, simulation_id, hour_offset, estimated_area_m2, spread_heading, intensity_score, active_cells, burnt_cells FROM simulation_steps ORDER BY simulation_id DESC, hour_offset ASC;"), ("Latest simulation timeline", dedent("""SELECT s.hour_offset, s.estimated_area_m2, s.spread_heading, s.intensity_score, s.active_cells, s.burnt_cells\nFROM simulation_steps s\nWHERE s.simulation_id = (SELECT id FROM fire_simulations ORDER BY generated_at DESC LIMIT 1)\nORDER BY s.hour_offset;""")), ("Latest simulation geometry as GeoJSON", dedent("""SELECT id, simulation_id, hour_offset, ST_AsGeoJSON(affected_geom)::json AS affected_geojson\nFROM simulation_steps\nWHERE simulation_id = (SELECT id FROM fire_simulations ORDER BY generated_at DESC LIMIT 1)\nORDER BY hour_offset;"""))]),
        ("impact_reports table", [("Show all reports", "SELECT id, forest_id, device_id, fire_event_id, generated_at, estimated_burnt_area_m2, vegetation_loss_score, habitat_impact_score, impact_level FROM impact_reports ORDER BY generated_at DESC;"), ("Latest report summary JSON", "SELECT id, jsonb_pretty(summary_json::jsonb) FROM impact_reports ORDER BY generated_at DESC LIMIT 1;")]),
        ("Useful join queries", [("Latest reading with device and event", dedent("""SELECT r.id, r.recorded_at, r.severity_score, r.alarm, r.trigger,\n       d.device_code,\n       e.status AS fire_event_status\nFROM sensor_readings r\nJOIN devices d ON d.id = r.device_id\nLEFT JOIN fire_events e ON e.id = r.fire_event_id\nORDER BY r.recorded_at DESC\nLIMIT 20;""")), ("Latest simulation with forest name", dedent("""SELECT sim.id, sim.generated_at, sim.model_version, f.name AS forest_name\nFROM fire_simulations sim\nLEFT JOIN forests f ON f.id = sim.forest_id\nORDER BY sim.generated_at DESC\nLIMIT 10;""")), ("Latest impact report with event context", dedent("""SELECT ir.id, ir.generated_at, ir.impact_level, ir.estimated_burnt_area_m2,\n       fe.started_at, fe.ended_at, fe.max_severity\nFROM impact_reports ir\nLEFT JOIN fire_events fe ON fe.id = ir.fire_event_id\nORDER BY ir.generated_at DESC\nLIMIT 10;"""))]),
    ]
    for section_title, queries in sql_sections:
        story.append(heading(section_title, 2))
        for label, sql in queries:
            story.extend(code_block(label, sql))

    story.append(PageBreak())
    story.append(heading("12. Deployment Guide", 1))
    story.append(para("The project is optimized for local demonstration on Windows using Docker for PostgreSQL/PostGIS, a Python virtual environment for the backend, and Node.js for the Angular frontend."))
    story.append(heading("Prerequisites", 2))
    story.extend(bullet(item) for item in ["Python 3.12+", "Node.js LTS", "Docker Desktop", "PostgreSQL/PostGIS container via docker compose", "DBeaver for database inspection", "Arduino IDE for ESP32 firmware upload"])
    story.extend(code_block("Backend setup", dedent(r"""cd d:\vs_forest_fire\n.\.venv\Scripts\python -m pip install -r backend\requirements.txt\ncd backend\ndocker compose up -d\n.\.venv\Scripts\python -m app.main""")))
    story.extend(code_block("Frontend setup", dedent(r"""cd d:\vs_forest_fire\frontend\nnpm install\nnpm start""")))
    story.append(heading("Frontend and backend URLs", 2))
    story.extend(bullet(item) for item in ["Swagger docs: http://127.0.0.1:8000/docs", "Angular app: http://localhost:4200", "ESP32 ingest endpoint: http://<your-laptop-ip>:8000/data"])
    story.append(heading("ESP32 deployment notes", 2))
    story.extend(bullet(item) for item in ["Make sure the ESP32 and laptop are on the same Wi-Fi or hotspot.", "Use the laptop's active LAN IP in SERVER_URL, not 127.0.0.1.", "Keep a delay of around 3000-5000 ms in loop() to avoid excessive packet spam.", "Confirm that the backend binds to 0.0.0.0:8000 for LAN access."])

    story.append(PageBreak())
    story.append(heading("13. Debugging and Troubleshooting Guide", 1))
    debugging_items = [
        ("ESP32 shows HTTP Response: -1", ["Check that SERVER_URL uses the laptop's current LAN IP, not an old IP and not 127.0.0.1.", "Confirm the backend is bound to 0.0.0.0:8000.", "Verify Windows firewall is not blocking port 8000.", "Make sure ESP32 and laptop are on the same network."]),
        ("Swagger works on localhost but ESP32 cannot connect", ["The backend is probably only reachable locally if started incorrectly.", "Start the backend with python -m app.main so it uses API_HOST from .env."]),
        ("Weather shows null on the dashboard", ["No forest is currently saved, or the forest has no sensor point/centroid.", "Upload or create a forest first, then call weather again."]),
        ("Simulation world map zooms out across two continents", ["This usually happens when a new forest was uploaded but the previous simulation still belongs to the old forest.", "Run a new simulation after uploading a different forest."]),
        ("Map looks too heavy or slow after GeoJSON upload", ["The uploaded GeoJSON may be too large or have too many coordinates/features.", "Clip the area of interest, simplify geometry, or use the project-ready sample files."]),
        ("WebSocket 404 or unsupported upgrade request", ["Make sure the websockets package is installed in the backend environment.", "Restart the backend after installing dependencies."]),
        ("OpenTelemetry export errors appear in the backend terminal", ["Either run the observability container stack or set OTEL_ENABLED=false in .env.", "Telemetry is optional and should usually be off for a normal demo."]),
        ("Email alerts are not sent", ["Check SMTP host, port, username, password, sender email, and recipient list in .env.", "Verify network access and whether the email provider requires an app password."]),
        ("Simulation run appears to do nothing", ["Check whether the form contains an invalid cell size or missing forest context.", "The backend requires cell_size_m between 15 and 250."]),
        ("Frontend shows blank page", ["Restart npm start, check Angular build errors, and hard-refresh the browser with Ctrl+Shift+R.", "Also check the browser console for runtime errors."]),
        ("PDF report export fails", ["Generate analysis first. The report endpoint depends on an existing impact report.", "If analysis exists but PDF still fails, check report_service.py and the backend terminal trace."]),
    ]
    for title, items in debugging_items:
        story.append(heading(title, 2))
        story.extend(bullet(item) for item in items)
    story.append(heading("Recommended stable demo configuration", 2))
    story.extend(bullet(item) for item in ["Set API_RELOAD=false so the backend does not hot-reload during the final demo.", "Set OTEL_ENABLED=false unless you are specifically demonstrating observability.", "Use a prepared GeoJSON instead of a very large raw GIS export.", "Keep cell size near 45 m for a good speed/detail balance.", "Open the simulation reel in Chrome or Edge for best WebM export support."])

    story.append(PageBreak())
    story.append(heading("14. Project Glossary", 1))
    story.append(para("The glossary below explains the most important user-facing and technical terms that appear across the frontend, backend, simulation engine, and database."))
    for term, meaning in glossary:
        story.append(heading(term, 2))
        story.append(para(meaning))

    story.append(PageBreak())
    story.append(heading("15. Demo Checklist and Best Practices", 1))
    story.extend(bullet(item) for item in ["Start Docker before starting the backend.", "Confirm PostgreSQL/PostGIS container is healthy.", "Start the backend and open Swagger once.", "Start the frontend and confirm all main routes load.", "Check that the saved forest is the correct one before showing simulation or analysis.", "Confirm ESP32 packets appear in the backend terminal.", "Keep one DBeaver SQL tab ready with the latest readings query as backup evidence.", "Trigger one sample alarm event before demo so email, event lifecycle, and analysis have content to show.", "Run at least one simulation in advance so the reel and PDF report have material.", "Keep prepared sample GeoJSON files in case live upload or hardware behaves unexpectedly."])

    story.append(PageBreak())
    story.append(heading("16. Future Improvements", 1))
    story.extend(bullet(item) for item in ["Support multiple forests and multiple ESP32 devices.", "Integrate terrain slope and higher-resolution fuel maps into the simulation engine.", "Add a responder mobile interface and route suggestions.", "Add satellite hotspot cross-checking for additional validation.", "Improve upload preprocessing for very large GeoJSON files.", "Move the MapTiler API key to runtime configuration rather than source code.", "Add historical trend analytics and event comparison features.", "Extend export options beyond WebM to MP4 or GIF if needed."])

    story.append(PageBreak())
    story.append(heading("17. Viva Questions and Answers", 1))
    story.append(para("The questions below are intentionally written in a way that a guide, examiner, or reviewer may realistically ask them. The answers are concise enough to memorize but still technical enough to sound strong and honest."))
    for index, (question, answer) in enumerate(viva_questions, start=1):
        story.append(heading(f"Q{index}. {question}", 2))
        story.append(para(answer))

    story.append(PageBreak())
    story.append(heading("Closing Note", 1))
    story.append(para("Forest Fire Shield is strongest when it is presented honestly: sensor packets are observed facts; weather, simulation, and analysis are well-explained derived layers built on top of those facts."))
    story.append(para("This handbook was generated to help you explain not only what the project does, but also why it was designed this way and how to operate it confidently during final demonstration and viva."))
    return story


def build_pdf() -> Path:
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=52,
        bottomMargin=34,
        title="Forest Fire Shield Project Handbook",
        author="Codex",
        subject="Comprehensive handbook for the Forest Fire Shield project",
    )
    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return OUTPUT


if __name__ == "__main__":
    output = build_pdf()
    print(f"Generated: {output}")
