# NauDisha — Dynamic & Optimal Ship Routing System

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**NauDisha** is an intelligent, dynamic maritime routing platform designed to calculate optimal sea routes for commercial and naval vessels. By integrating dynamic weather and oceanographic data with ship hydrodynamic profiles, NauDisha optimizes routes for transit time, fuel consumption, and navigational safety while avoiding marine hazards and non-navigable zones.

---

## 🧭 Project Purpose & Overview

Maritime voyages operate across dynamic, hostile, and constantly shifting ocean environments. Traditional static rhumb-line or great-circle routes do not account for real-time changes in ocean currents, headwinds, swell heights, or adverse weather systems.

**NauDisha** addresses this challenge by providing:
1. **Multi-Objective Cost Model**: Balances travel time, fuel burn proxy, aerodynamic wind drag, sea-state wave impact, ocean current assistance, and safety envelopes.
2. **Dynamic Replanning Foundation**: Architected to support incremental graph pathfinding algorithms (**D* Lite**) that adapt routes in real-time as forecasts evolve without recalculating from scratch.
3. **Modular Extensibility**: Decoupled score calculators and data contracts allowing seamless drop-in replacement with validated naval architecture formulas and open marine data APIs.

---

## 🏗 Architecture

NauDisha is structured into clean, modular layers:

```
naudisha/
├── core/                  # Core domain models, normalization, and mathematical derived calculations
│   ├── models.py          # Data models: ShipProfile, EnvironmentalData, SegmentData, CostWeights, etc.
│   ├── calculations.py    # Haversine distance, bearing, relative angles, effective speed, travel time
│   └── normalization.py   # Configurable min-max normalization clamped to [0.0, 1.0]
├── cost/                  # Multi-factor cost model engine
│   ├── scorers.py         # Modular scoring functions (0 = Best, 1 = Worst)
│   └── model.py           # CostModel class, weighted sum, and non-navigability handling
├── routing/               # Future D* Lite graph search engine & dynamic replanning interfaces
│   └── dstar_lite.py      # Abstract routing engine and D* Lite interfaces
├── data/                  # Future marine and weather forecast providers
│   └── weather_provider.py# WeatherProvider interface & mock simulation provider
└── api/                   # Future API / Dashboard adapters
```

---

## 📊 Data Categories

| Category | Description | Fields / Models |
| :--- | :--- | :--- |
| **Static Data** | Invariant vessel characteristics and dimensions | `ShipProfile`: `ship_type`, `length`, `beam`, `draft`, `cruising_speed`, `maximum_speed` |
| **Dynamic Data** | Real-time / forecast meteorological & ocean state | `EnvironmentalData`: `timestamp`, `wind_speed`, `wind_direction`, `wave_height`, `wave_direction`, `wave_period`, `current_speed`, `current_direction` |
| **Navigational Data** | Geographic segment definitions and safety constraints | `SegmentData`: `start_lat`, `start_lon`, `end_lat`, `end_lon`, `is_navigable` |
| **Derived Metrics** | Mathematically computed nautical & hydrodynamic values | `DerivedSegmentMetrics`: `distance_nm`, `bearing`, `relative_wind_dir`, `relative_current_dir`, `along_track_current`, `effective_speed`, `travel_time_hours` |

---

## ⚙️ Cost Model Foundation

The total cost of traversing any navigational segment is computed as a weighted linear combination of normalized component scores:

$$\text{Total Cost} = \sum_{i} w_i \cdot s_i$$

$$\text{Total Cost} = w_{\text{time}} s_{\text{time}} + w_{\text{fuel}} s_{\text{fuel}} + w_{\text{wind}} s_{\text{wind}} + w_{\text{wave}} s_{\text{wave}} + w_{\text{current}} s_{\text{current}} + w_{\text{safety}} s_{\text{safety}}$$

### Scoring Scale:
- **`0.0` = Best / Optimal** (e.g. strong assisting current, calm sea, minimum travel time)
- **`1.0` = Worst / High Penalty** (e.g. severe headwind, high opposing current, extreme delay)
- **`math.inf` = Non-Navigable** (landmass, draft violation, or conditions exceeding vessel survival thresholds)

All scores use configurable min/max reference bounds (`ScoringConfig`) and are strictly clamped to $[0.0, 1.0]$.

### Component Breakdown:
1. **Time Score ($s_{\text{time}}$)**: Normalized travel time relative to design cruising speed baseline.
2. **Fuel Score ($s_{\text{fuel}}$)**: Engine load proxy reflecting speed ratio deficits due to resistance.
3. **Wind Score ($s_{\text{wind}}$)**: Aerodynamic drag penalty scaled by wind speed and relative heading (headwind vs. tailwind).
4. **Wave Score ($s_{\text{wave}}$)**: Sea-state added resistance based on significant wave height ($H_s$) and encounter angle.
5. **Current Score ($s_{\text{current}}$)**: Hydrodynamic drift penalty / reward based on along-track velocity component.
6. **Safety Score ($s_{\text{safety}}$)**: Proximity to vessel design operating limits for waves and winds.

---

## 🚀 D* Lite: Future Dynamic Routing Engine

Traditional $A^*$ or Dijkstra pathfinding requires complete graph recalculation whenever weather conditions change along a multi-day voyage. 

**D* Lite** solves this by:
- Operating incrementally from the goal back to the vessel's current position.
- Updating only the nodes and edges affected by changing weather/current forecasts.
- Reusing prior search trees to deliver real-time replanning with low computational overhead.

The abstract interfaces for dynamic routing graphs and incremental replanning are prepared in `naudisha/routing/dstar_lite.py`.

---

## 🧪 Running Unit Tests

NauDisha uses standard Python library tests (no external dependencies required):

```bash
# Run all unit tests using python unittest
python -m unittest discover -s tests -p "test_*.py" -v
```

Or using `pytest` (if installed):

```bash
pytest -v
```

### Test Coverage Includes:
- **Distance**: Haversine great-circle calculation vs. known meridian benchmarks.
- **Bearing**: Initial azimuth across cardinal directions.
- **Relative Direction**: Angle deviation wrapping across $0^\circ / 360^\circ$.
- **Favorable / Opposing Current**: Along-track current vector decomposition.
- **Effective Speed & Travel Time**: Speed over ground calculation and speed clamping limits.
- **Normalization**: Clamping and standard / inverted linear scaling.
- **Weighted Cost**: Multi-objective cost summation.
- **Non-Navigable Segments**: Infinite cost enforcement for land and hazardous conditions.

---

## 💻 Running the Example

Run the included segment cost demonstration script:

```bash
python examples/run_segment_cost.py
```

### Sample Output:
```
======================================================================
   NauDisha — Dynamic & Optimal Ship Routing System
   Cost Model Demonstration
======================================================================

[1] SHIP PROFILE:
    Type:            Container Ship (Post-Panamax)
    Dimensions:      334.0m (L) x 42.8m (B) x 14.5m (D)
    Cruising Speed:  18.0 knots
    Max Speed:       23.0 knots

[2] ENVIRONMENTAL CONDITIONS:
    Timestamp:       2026-08-16T12:00:00Z
    Wind:            22.0 knots from 240.0°
    Waves:           2.8m (Period: 8.5s, Dir: 235.0°)
    Ocean Current:   1.8 knots towards 60.0°

[3] NAVIGATIONAL SEGMENT:
    Start Waypoint:  (18.9220° N, 72.8347° E)
    End Waypoint:    (20.0000° N, 71.5000° E)
    Navigable:       True

----------------------------------------------------------------------
   DERIVED HYDRODYNAMIC & NAUTICAL METRICS
----------------------------------------------------------------------
    Great-Circle Distance:    99.76 NM (184.75 km)
    True Bearing:             309.82°
    Relative Wind Angle:      69.82° (0°=headwind, 180°=tailwind)
    Relative Current Angle:   110.18° (0°=following, 180°=opposing)
    Along-Track Current:      -0.62 knots (Opposing)
    Effective Speed (SOG):    17.38 knots
    Estimated Travel Time:    5.74 hours

----------------------------------------------------------------------
   MODULAR COMPONENT SCORES (0.0 = Best, 1.0 = Worst)
----------------------------------------------------------------------
    Time Score:       0.2575
    Fuel Score:       0.7958
    Wind Score:       0.2959
    Wave Score:       0.3015
    Current Score:    0.5622
    Safety Score:     0.3667

======================================================================
   FINAL WEIGHTED SEGMENT COST: 3.0906
   SEGMENT STATUS:              NAVIGABLE (SAFE)
======================================================================
```

---

## 📦 Minimal Dependencies

NauDisha core has **zero required third-party dependencies** and runs out-of-the-box on standard Python 3.10+.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
