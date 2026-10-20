# 🌲🔥 Forest Fire Shield

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![Angular](https://img.shields.io/badge/Angular-21.2+-DD0031?logo=angular&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-4169E1?logo=postgresql&logoColor=white)
![PostGIS](https://img.shields.io/badge/PostGIS-3.4+-4169E1?logo=postgresql&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/TailwindCSS-4.2+-38B2AC?logo=tailwindcss&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)

---

> **An advanced wildfire monitoring & simulation system** — built for a single forest with one ESP32 sensor node.  
> Real-time ingestion, live dashboard, weather enrichment, fire event detection, spread simulation, and post-fire impact analysis.

---

## 🎯 Problem Statement

Wildfires cause devastating ecological and economic damage. Early detection and spread prediction can save lives, forests, and infrastructure.

**Forest Fire Shield** demonstrates a complete end-to-end IoT + geospatial pipeline:

1. **ESP32** with MQ2, MQ4, MQ7, MQ135, Flame, and IR sensors → streams live readings
2. **FastAPI** ingestion API → validates, stores, enriches with weather
3. **PostgreSQL + PostGIS** → spatial storage for forests, sensors, fire polygons
4. **Angular + MapLibre GL** → real-time dashboard with interactive map
5. **Rule-based simulation engine** → predicts hourly fire spread using vegetation, fuel, wind, humidity
6. **Analysis engine** → generates impact reports (burnt area, vegetation loss, habitat impact)
7. **Email alerts** → notifies admins on fire detection

---

## ✨ Features

| Category | Features |
|----------|----------|
| 🛰️ **Ingestion** | REST + legacy `/data` endpoint, payload validation, raw storage |
| 📡 **Live Stream** | WebSocket `/ws/live` for real-time sensor updates to dashboard |
| 🗺️ **Forest Management** | GeoJSON upload, wizard-based creation, spatial validation |
| 🌤️ **Weather** | Open-Meteo integration, cached, auto-refreshed |
| 🚨 **Fire Events** | Auto-open/close based on thresholds, cooldown logic |
| 📈 **Simulation** | Hourly spread polygons, wind-driven, fuel-aware, confidence scoring |
| 📊 **Analysis** | Burnt area, vegetation loss, habitat impact, PDF report generation |
| 📧 **Alerts** | SMTP email (Gmail app password), open/update/close notifications |
| 🔭 **Observability** | OpenTelemetry → Grafana/OTel LGTM stack (traces, metrics, logs) |
| 🐳 **DevOps** | Docker Compose for PostGIS + Observability stack |

---

## 🛠 Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| **Backend API** | FastAPI | 0.115+ |
| **Async Server** | Uvicorn | Latest |
| **Database** | PostgreSQL + PostGIS | 16 / 3.4 |
| **ORM** | SQLAlchemy 2.0 + GeoAlchemy2 | Latest |
| **Validation** | Pydantic v2 | Latest |
| **Weather** | Open-Meteo API | Free tier |
| **Email** | SMTP (Gmail) | App password |
| **Telemetry** | OpenTelemetry Python | Latest |
| **Frontend Framework** | Angular | 21.2+ |
| **Map Rendering** | MapLibre GL JS | 5.21+ |
| **Styling** | Tailwind CSS v4 | 4.2+ |
| **Charts/Animations** | GSAP | 3.14+ |
| **Containerization** | Docker Compose | v2 |

---

## 🏗 Architecture

```text
┌─────────────┐     ┌──────────────────┐     ┌────────────────────┐
│   ESP32     │────▶│   FastAPI API    │────▶│  PostgreSQL/PostGIS│
│  (Sensors)  │     │  (Ingestion)     │     │  (Spatial Storage) │
└─────────────┘     └────────┬─────────┘     └────────┬───────────┘
                             │                        │
                    ┌────────▼────────┐      ┌────────▼────────┐
                    │  WebSocket      │      │  Background     │
                    │  Live Stream    │      │  Workers        │
                    └────────┬────────┘      └────────┬────────┘
                             │                        │
                    ┌────────▼────────┐      ┌────────▼────────┐
                    │  Angular        │      │  Weather /      │
                    │  Dashboard      │      │  Simulation /   │
                    │  (MapLibre)     │      │  Alerts /       │
                    └─────────────────┘      │  Analysis       │
                                            └─────────────────┘
```

---

## 📁 Folder Structure

```text
Forest_Fire_Shield_Project/
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app, routes, lifespan
│   │   ├── config.py          # Settings (pydantic-settings style)
│   │   ├── database.py        # SQLAlchemy engine, session, init
│   │   ├── models.py          # SQLAlchemy + GeoAlchemy models
│   │   ├── schemas.py         # Pydantic request/response models
│   │   ├── services.py        # Core business logic
│   │   ├── forest_service.py  # Forest CRUD, GeoJSON handling
│   │   ├── weather_service.py # Open-Meteo integration
│   │   ├── alert_service.py   # SMTP email alerts
│   │   ├── simulation_service.py # Fire spread simulation
│   │   ├── analysis_service.py    # Post-fire impact analysis
│   │   ├── report_service.py  # PDF report generation
│   │   ├── automation_service.py  # Background job runner
│   │   ├── live_stream.py     # WebSocket manager
│   │   └── telemetry.py       # OpenTelemetry setup
│   ├── requirements.txt
│   ├── docker-compose.yml     # PostGIS + Observability stack
│   ├── .env                   # Local config (NOT committed)
│   └── .env.example           # Template
├── frontend/                   # Angular 21 application
│   ├── src/
│   │   ├── app/
│   │   │   ├── core/          # API services, models, live stream
│   │   │   ├── pages/         # Dashboard, Forest Setup, Simulation, Analysis
│   │   │   ├── shared/        # Forest Map, Simulation Reel components
│   │   │   ├── app.routes.ts  # Routing config
│   │   │   └── app.config.ts  # App config
│   │   ├── styles.css         # Global styles (Tailwind)
│   │   └── main.ts            # Bootstrap
│   ├── package.json
│   ├── angular.json
│   └── tsconfig*.json
├── docs/                       # Documentation
│   ├── assets/
│   │   └── system-workflow.svg
│   ├── system-design.md       # Full architecture & design
│   ├── simulation-model.md    # Simulation algorithm details
│   ├── demo-runbook.md        # Step-by-step demo guide
│   └── generate_project_handbook.py
├── sample-data/                # Sample GeoJSON forests (small files only)
│   └── geojson/
│       ├── forest-demo-valid.geojson
│       ├── forest-demo-invalid-missing-boundary.geojson
│       ├── amazon-ducke-required-project-ready.geojson
│       └── bannerghatta-required-project-ready.geojson
├── .gitignore
├── LICENSE
├── CONTRIBUTING.md
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

- **Windows 10/11** (or Linux/macOS)
- **Git** installed
- **Docker Desktop** (recommended) **OR** PostgreSQL 16 + PostGIS 3.4 installed locally
- **Python 3.11+** and **Node.js 20+**

### 1. Clone & Configure

```bash
git clone https://github.com/javedmiya23/forest-fire-shield.git
cd forest-fire-shield

# Backend config
cd backend
cp .env.example .env
# Edit .env with your settings (see below)
```

### 2. Start Infrastructure (Docker)

```bash
# From backend/
docker compose up -d
# Starts: PostGIS on 5432, Grafana/OTel LGTM on 3000, OTLP on 4317/4318
```

> **No Docker?** Install PostgreSQL + PostGIS locally, create DB `forest_fire_shield`, update `DATABASE_URL` in `.env`.

### 3. Backend

```bash
# From backend/
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt

# Run API (auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: **http://localhost:8000/docs** (Swagger) / **http://localhost:8000/redoc** (ReDoc)

### 4. Frontend

```bash
# New terminal, from frontend/
npm ci
npm start
# Or for LAN access: npm run start:lan
```

Dashboard: **http://localhost:4200**

---

## ⚙️ Configuration (`.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostGIS connection string | `postgresql+psycopg://postgres:postgres@localhost:5432/forest_fire_shield` |
| `CORS_ALLOWED_ORIGINS` | Frontend origins | `http://localhost:4200,http://127.0.0.1:4200` |
| `WEATHER_API_URL` | Open-Meteo endpoint | `https://api.open-meteo.com/v1/forecast` |
| `ALERT_EMAIL_ENABLED` | Enable email alerts | `true` |
| `SMTP_HOST` | SMTP server | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USERNAME` | Gmail address | *(required)* |
| `SMTP_PASSWORD` | **Gmail App Password** | *(required)* |
| `ALERT_EMAIL_FROM` | Sender address | *(required)* |
| `ALERT_EMAIL_RECIPIENTS` | Comma-separated list | *(required)* |
| `OTEL_ENABLED` | Enable OpenTelemetry | `false` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector | `http://127.0.0.1:4318` |

> **🔐 Security**: Never commit `.env`. Use Gmail **App Password** (not account password). See [Google App Passwords](https://support.google.com/accounts/answer/185833).

---

## 📡 ESP32 Payload Format

The ingestion endpoint expects JSON:

```json
{
  "device_code": "FFS_ESP32_01",
  "timestamp_ms": 1715000000000,
  "mq2_analog": 1200,
  "mq2_digital": 0,
  "mq4_analog": 800,
  "mq4_digital": 0,
  "mq7_analog": 500,
  "mq7_digital": 0,
  "mq135_analog": 1000,
  "mq135_digital": 0,
  "flame_detected": 0,
  "ir_detected": 0,
  "rssi": -45,
  "firmware_version": "1.0.0"
}
```

**Endpoint**: `POST http://<api-host>:8000/api/v1/ingest` (or legacy `/data`)

---

## 🗺️ Forest GeoJSON Requirements

Upload via **Forest Setup Wizard** or `POST /api/v1/forests/upload-geojson`.

**Required properties** in FeatureCollection:
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Polygon", "coordinates": [[[lon,lat],...]] },
      "properties": {
        "name": "My Forest",
        "vegetation_type": "tropical_dry_deciduous",
        "tree_density": "high",
        "canopy_density": "dense",
        "fuel_load": "high",
        "moisture_class": "dry",
        "admin_email": "admin@example.com"
      }
    }
  ]
}
```

**Optional**: water_bodies, roads, firebreaks, watch_towers, settlements, habitat_zones, slope, soil, elevation.

---

## 🧪 Simulation Algorithm (Summary)

> **Rule-based, physics-inspired** — not ML (explainable for academic defense).

1. **Grid** the forest boundary (configurable cell size, default 45m)
2. **Resistance** per cell from vegetation + fuel + moisture + canopy
3. **Wind vector** increases spread probability downwind
4. **Humidity/precipitation** reduces spread
5. **Barriers** (water, firebreaks) stop/slow spread
6. **Output**: Hourly polygons (1–6h), area, heading, intensity

**Config** (via `.env` or API):
- `SIMULATION_DEFAULT_HOURS=6`
- `SIMULATION_DEFAULT_CELL_SIZE_M=45`
- `SIMULATION_MAX_CELLS=3500`

---

## 📊 Analysis Outputs

- **Estimated burnt area** (m²)
- **Vegetation loss score** (0–100)
- **Habitat impact score** (0–100)
- **Spread timeline** (hourly polygons)
- **Peak sensor readings** during event
- **PDF Report** (auto-generated, downloadable)

---

## 🔭 Observability (Optional)

Enable with `OTEL_ENABLED=true` in `.env`.

Stack (via `docker compose`):
- **Grafana**: http://localhost:3000 (admin/admin)
- **OTLP HTTP**: http://localhost:4318/v1/traces, /v1/metrics
- **OTLP gRPC**: localhost:4317

---

## 🧪 Testing

```bash
# Backend
cd backend
pytest --cov=app --cov-report=term-missing

# Frontend
cd frontend
npm test -- --watch=false --browsers=ChromeHeadless
```

---

## 📦 Production Deployment Notes

- Use **Gunicorn + Uvicorn workers**: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app`
- Reverse proxy: **Nginx** (SSL termination, static files)
- Database: Managed PostgreSQL (RDS, Cloud SQL) with PostGIS
- Secrets: **Never** in `.env` — use Docker secrets, Kubernetes secrets, or cloud secret manager
- Frontend: `ng build --configuration production` → serve via Nginx or CDN
- Monitoring: Enable `OTEL_ENABLED=true`, point to production OTLP collector

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Branching strategy
- Commit conventions (Conventional Commits)
- Code style (ruff, prettier, eslint)
- PR process

---

## 🙏 Credits & Acknowledgments

- **Open-Meteo** — free weather API
- **MapLibre GL** — open-source map rendering
- **PostGIS** — spatial SQL superpowers
- **FastAPI** — modern, fast Python web framework
- **Angular** — robust frontend platform
- **Tailwind CSS** — utility-first styling
- **GSAP** — buttery animations
- **OpenTelemetry** — vendor-neutral observability

---

## 👨‍💻 Author

**Javed Miya**  
🔗 [GitHub](https://github.com/javedmiya23)

---

## ⭐ Star This Repo

If this project helped you, **give it a star** — it motivates more open-source work!

---

> **Academic Integrity Note**: This is a **demo/simulation** for educational purposes.  
> It uses **estimated models**, not real-time satellite data.  
> Always label outputs as **"simulation"** and **"impact estimate"** — never as exact predictions.
