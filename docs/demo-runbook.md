# Forest Fire Shield Demo Runbook

## 1. Demo Goal

Show the project as a complete wildfire intelligence workflow:

1. forest context setup
2. ESP32 live data ingestion
3. weather enrichment
4. fire event detection and email alerting
5. fire spread simulation
6. post-fire analysis and PDF report export

## 2. Before The Demo

Make sure these are ready:

- Docker Desktop is running
- PostgreSQL/PostGIS container is running
- backend starts without errors
- frontend starts without errors
- ESP32 and laptop are on the same Wi-Fi
- SMTP email is working
- MapTiler key is present if you want satellite/hybrid basemap

## 3. Start Commands

### Database

From `backend`:

```powershell
docker compose up -d
```

### Backend

From `backend`:

```powershell
d:\vs_forest_fire\.venv\Scripts\python -m app.main
```

### Frontend

From `frontend`:

```powershell
npm start
```

Open:

```text
http://localhost:4200
```

## 4. Recommended Demo Flow

### Step 1. Overview

Open the landing page and explain:

- this is a single-forest, single-ESP32 wildfire detection and decision-support platform
- data flows from ESP32 to FastAPI to PostgreSQL/PostGIS to Angular dashboards

### Step 2. Forest Setup

Open `/forest/setup` and show:

- GeoJSON upload
- Create Your Forest Map
- validation summary
- rendered forest map

Say:

"The system supports uploaded GeoJSON and also helps a non-technical user build the forest map manually."

### Step 3. Live Dashboard

Open `/dashboard` and show:

- device connectivity
- latest sensor readings
- weather cards
- automation watch
- email dispatch state
- live severity trend
- recent packet timeline

Say:

"This dashboard shows observed facts from the ESP32 and backend automation, not only predictions."

### Step 4. Trigger Fire

Use your hardware smoke/flame condition and show:

- alarm state becomes active
- fire event opens
- email dispatch updates
- database stores the packet automatically

### Step 5. Simulation

Open `/simulation` and run a simulation.

Show:

- hour-by-hour spread
- assumptions
- weather context
- map overlay
- cinematic reel export

Say:

"This is not a black-box ML model. It is a deterministic, physics-inspired, grid-based simulation."

Important explanation:

- wind biases spread direction
- humidity and precipitation reduce spread
- uploaded roads, water bodies, and firebreaks now reduce spread in the backend model

### Step 6. Analysis

Open `/analysis` and generate analysis.

Show:

- burnt area
- vegetation loss estimate
- habitat impact estimate
- sensor evidence
- recommended actions
- PDF report export

Say:

"The analysis produces an impact estimate, not a claim of exact real-world loss."

## 5. Best Viva Answers

### Why not ML first?

Use this answer:

"Because this project has one ESP32 node and no large labeled wildfire dataset, a pure ML model would be hard to train and hard to justify academically. So we used an explainable deterministic simulation first, and ML can be added later for calibration."

### How is weather used?

Use this answer:

"Weather is fetched from the forest GeoJSON location, preferably the ESP32 sensor point, otherwise the forest centroid. Temperature, humidity, wind speed, wind direction, and precipitation influence simulation and dashboard context."

### How do roads and water affect simulation?

Use this answer:

"Uploaded GeoJSON layers are not only rendered visually. Water bodies strongly suppress spread, and roads/firebreaks reduce spread when the fire path crosses them."

### Are animal deaths exact?

Use this answer:

"No. We show impact estimates such as habitat disturbance and vegetation loss, which is academically more honest than claiming exact wildlife mortality without field evidence."

## 6. Backup Plan If Hardware Fails

If the ESP32 is not available during demo:

- use the existing stored readings in the database
- show dashboard history
- run simulation from the latest saved context
- generate analysis from the saved event
- export the PDF report

## 7. Final Things To Keep Open During Demo

- frontend dashboard
- simulation page
- analysis page
- backend terminal
- Arduino serial monitor
- DBeaver or Swagger only if needed

## 8. Final Safety Notes

- call analysis an estimate
- call simulation a prediction, not certainty
- clearly separate live sensor observation from derived outputs
- if asked about future work, mention terrain slope, satellite hotspot validation, and ML-based calibration
