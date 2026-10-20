# Fire Simulation Model

## What We Are Using

Forest Fire Shield uses a deterministic, physics-inspired spread model.

It is not a pure machine learning model.

The current model is a grid-based cellular spread simulation:

- the uploaded forest boundary is converted into a grid
- the ESP32 sensor location acts as the ignition point
- weather and forest attributes control how quickly neighboring cells ignite
- uploaded water bodies, roads, and firebreaks can damp or block spread
- the predicted spread is generated hour by hour

## Why We Chose This Instead Of ML First

This project has only one ESP32 device and does not have a large labeled wildfire dataset.

Because of that:

- a pure ML model would be hard to train properly
- it would be difficult to justify academically
- it would behave like a black box in viva or project review

This rule-based model is better for a final-year project because it is:

- explainable
- reproducible
- realistic enough for a demo
- easy to improve later with ML calibration

## Inputs Used By The Model

### Forest inputs

- forest boundary polygon from GeoJSON
- vegetation type
- tree density
- canopy density
- fuel load
- moisture class
- optional barrier layers such as water bodies, roads/access routes, and firebreaks

### Sensor inputs

- ESP32 device location
- latest sensor severity score
- active fire event if one exists

### Weather inputs

- temperature
- relative humidity
- wind speed
- wind direction
- precipitation

## How The Model Works

1. Convert the forest polygon into a local meter-based grid.
2. Mark the ESP32 point as the ignition origin.
3. Compute a fuel factor from vegetation, tree density, canopy density, fuel load, and moisture class.
4. Compute a weather factor from temperature, humidity, and precipitation.
5. Compute a severity factor from the latest fire reading or active fire event.
6. Detect barrier layers from GeoJSON and convert them into local spread-resistance zones.
7. Spread the fire from each active grid cell to neighboring cells using wind-biased directional scoring plus barrier penalties.
8. Repeat the spread process for each hour and merge burnt cells into predicted fire polygons.

## Spread Logic

Each neighboring cell gets a spread score based on:

```text
spread_score = base_potential * distance_factor * wind_alignment * crossing_factor * target_cell_factor
```

Where:

- `base_potential` depends on fuel factor, weather factor, and severity factor
- `distance_factor` slightly penalizes diagonal spread
- `wind_alignment` boosts spread in the downwind direction and suppresses spread against wind
- `crossing_factor` reduces spread when the path between two cells crosses mapped water, roads, or firebreaks
- `target_cell_factor` reduces ignition potential for cells already intersecting barrier zones

If the spread score crosses the ignition threshold, that neighboring cell becomes active in the next time step.

## Barrier Handling

The upgraded model is barrier-aware.

- water bodies act as the strongest spread suppressor
- cells dominated by mapped water are treated as near-non-burnable
- roads/access lines reduce spread when fire has to cross them
- firebreak lines or polygons reduce spread more strongly than roads

This means uploaded GeoJSON layers are not only visualized in the frontend. They now directly influence the backend spread calculation.

## Wind Handling

Weather APIs usually give wind direction as the direction the wind comes from.

For fire spread, we need the direction the wind pushes the fire toward.

So the model uses:

```text
downwind_direction = wind_direction + 180 degrees
```

Then neighboring cells that lie closer to that heading receive a higher spread score.

## Hourly Output

For each hour, the model stores:

- affected fire polygon
- estimated burnt area in square meters
- spread heading
- intensity score
- active cell count
- burnt cell count

## What To Say To Your Guide

You can explain it like this:

"We are using a deterministic grid-based wildfire spread simulation, not a black-box ML model. The forest is divided into cells. Each cell receives a spread score based on forest fuel properties, humidity, precipitation, wind speed, wind direction, and current fire severity from the ESP32 readings. Cells in the downwind direction ignite faster, while wetter conditions slow the spread. If uploaded GeoJSON contains roads, water bodies, or firebreaks, the model uses them as spread-resistance layers. The output is generated hour by hour as predicted fire polygons clipped to the actual forest boundary."

## Honest Limitation Statement

For academic correctness, say this clearly:

- this is a simulation and impact estimate, not an exact real-world prediction
- terrain slope and high-resolution fuel maps are not yet included
- the model is designed for explainability and demo realism
- ML can be added later for calibration or risk scoring
