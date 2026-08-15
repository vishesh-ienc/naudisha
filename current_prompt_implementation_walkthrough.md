# Current Prompt Implementation Walkthrough: Copernicus Marine Service Configuration & Dataset Identification

## 🎯 Scope of Current Prompt
- Pivot environmental data strategy from Open-Meteo to the official **Copernicus Marine Service (CMEMS)** as the primary oceanographic source.
- Configure and verify Copernicus Marine access using the official `copernicusmarine` toolbox (v2.4.1).
- Explore catalogue metadata and identify exact dataset IDs and variables for ocean currents (`uo`, `vo`) and waves (`VHM0`, `VMDR`, `VTPK`).
- Design mathematical conversion formulas mapping CMEMS variables to NauDisha's `EnvironmentalData` model.
- Add offline unit tests for schemas and conversions without network/credential dependencies.
- Create a verification script demonstrating access, metadata discovery, and vector conversions.
- Ensure strict credential privacy (never hardcoding or logging credentials; `.gitignore` exclusions).
- Preserve 100% decoupling: zero modifications to D* Lite, `GeographicGridGraph`, `CostModel`, or scoring formulas.

---

## 🛠 Changes Implemented

### 1. Architecture Transition & Strategy
- **Primary Source**: Copernicus Marine Service is established as the primary oceanographic provider for research-grade current and wave data.
- **Wind Strategy**: Copernicus focuses on marine hydrodynamics; wind parameters (`wind_speed`, `wind_direction`) will be supplied by a complementary atmospheric provider (e.g., NOAA GFS or Open-Meteo) in a subsequent step.
- **Provider Decoupling**: Kept `WeatherProvider` abstract interface in [`naudisha/data/weather_provider.py`](file:///c:/Users/VISHESH/Desktop/naudisha/naudisha/data/weather_provider.py) completely decoupled.

### 2. Dependency & Security Configuration
- **Package**: Added `copernicusmarine>=2.0.0` under optional dependencies in [`pyproject.toml`](file:///c:/Users/VISHESH/Desktop/naudisha/pyproject.toml).
- **Toolbox Installation**: Installed `copernicusmarine==2.4.1` into the Python environment.
- **Security & Privacy**: Updated [`.gitignore`](file:///c:/Users/VISHESH/Desktop/naudisha/.gitignore) to exclude `.copernicusmarine/`, `*.nc`, `*.grib`, and any local credential or raster data files. Local session authentication is managed exclusively through standard user profile credential storage.

### 3. Discovered Datasets & Schema Specification ([`naudisha/data/copernicus_schema.py`](file:///c:/Users/VISHESH/Desktop/naudisha/naudisha/data/copernicus_schema.py))
Defined dataset specifications and conversion helpers:

#### A. Ocean Currents (Physics)
- **Product ID**: `GLOBAL_ANALYSISFORECAST_PHY_001_024`
- **Primary Dataset ID**: `cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i`
- **Variables**: `uo` (Eastward velocity, $m/s$), `vo` (Northward velocity, $m/s$)
- **Depth Layer**: $0.494\text{ m}$ (Surface layer)
- **Spatial Resolution**: $0.083^\circ \times 0.083^\circ$ (~9 km / $1/12^\circ$), Global coverage including Indian Ocean
- **Temporal Resolution**: 6-hourly instantaneous
- **Alternative Hourly Dataset**: `cmems_mod_glo_phy_anfc_merged-uv_PT1H-i` (`utotal`, `vtotal`, 1-hourly surface)

#### B. Ocean Waves
- **Product ID**: `GLOBAL_ANALYSISFORECAST_WAV_001_027`
- **Dataset ID**: `cmems_mod_glo_wav_anfc_0.083deg_PT3H-i`
- **Variables**: `VHM0` (Significant wave height, $m$), `VMDR` (Mean wave direction, $^\circ$), `VTPK` (Peak wave period, $s$)
- **Spatial Resolution**: $0.083^\circ \times 0.083^\circ$ (~9 km)
- **Temporal Resolution**: 3-hourly instantaneous

### 4. Mathematical Vector & Variable Conversion Formulas
- **Current Speed ($v_{\text{knots}}$)**:
  $$v_{\text{magnitude}} = \sqrt{u_o^2 + v_o^2}\text{ m/s}$$
  $$v_{\text{knots}} = v_{\text{magnitude}} \times 1.9438444924$$
- **Current Flow Direction ($\theta_{\text{flow}}$)**:
  $$\theta_{\text{flow}} = \left(90^\circ - \text{atan2}(v_o, u_o) \cdot \frac{180^\circ}{\pi} + 360^\circ\right) \pmod{360^\circ}$$
  *(Oceanographic heading towards which current is flowing, $0^\circ = \text{North}, 90^\circ = \text{East}$)*
- **Wave Parameters**:
  - `wave_height` = `VHM0` ($m$)
  - `wave_direction` = `VMDR` ($^\circ$)
  - `wave_period` = `VTPK` ($s$)

### 5. Verification Script ([`examples/verify_copernicus_access.py`](file:///c:/Users/VISHESH/Desktop/naudisha/examples/verify_copernicus_access.py))
- Demonstrates active Copernicus Marine Toolbox version, session verification, metadata retrieval, and live vector conversions without exposing credentials.

---

## 🧪 Verification & Test Results

### 1. Offline Unit Test Suite (57/57 Tests Passed)
```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```
```
test_ocean_currents_spec_integrity (test_copernicus_metadata.TestCopernicusSchemas.test_ocean_currents_spec_integrity) ... ok
test_surface_currents_hourly_spec_integrity (test_copernicus_metadata.TestCopernicusSchemas.test_surface_currents_hourly_spec_integrity) ... ok
test_waves_spec_integrity (test_copernicus_metadata.TestCopernicusSchemas.test_waves_spec_integrity) ... ok
test_cardinal_directions (test_copernicus_metadata.TestVectorConversions.test_cardinal_directions) ... ok
test_mapping_to_environmental_data_model (test_copernicus_metadata.TestVectorConversions.test_mapping_to_environmental_data_model) ... ok
test_roundtrip_conversions (test_copernicus_metadata.TestVectorConversions.test_roundtrip_conversions) ... ok
... (All 51 previous tests including D* Lite, Graph, CostModel, Scorers, and Dijkstra Oracle) ...

----------------------------------------------------------------------
Ran 57 tests in 0.021s

OK
```

### 2. Copernicus Access & Discovery Script Output
```
======================================================================
   NauDisha - Copernicus Marine Service Configuration & Discovery
======================================================================

[1] COPERNICUS MARINE TOOLBOX:
    Toolbox Version: 2.4.1
    Authentication:  Local Credential Session Active

----------------------------------------------------------------------
   [2] IDENTIFIED OCEAN CURRENTS (PHYSICS) DATASETS
----------------------------------------------------------------------
   A. Primary 6-Hourly Instantaneous Current Vectors (3D Surface Layer):

   [Dataset ID]:         cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i
   [Product ID]:         GLOBAL_ANALYSISFORECAST_PHY_001_024
   [Title]:              Global Ocean Physics Analysis and Forecast - Currents (Instantaneous)
   [Spatial Resolution]: 0.083 deg x 0.083 deg (~9 km / 1/12 deg)
   [Temporal Interval]:  6-hourly instantaneous (PT6H-i)
   [Depth Level]:        0.494 m
   [Coverage]:           Global (180W-180E, 80S-90N)
   [Variables]:
       * uo       -> Eastward water velocity (m/s)
       * vo       -> Northward water velocity (m/s)

   B. Alternative 1-Hourly Instantaneous Merged Surface UV Currents:

   [Dataset ID]:         cmems_mod_glo_phy_anfc_merged-uv_PT1H-i
   [Product ID]:         GLOBAL_ANALYSISFORECAST_PHY_001_024
   [Title]:              Global Ocean Physics Analysis and Forecast - Merged UV Surface Currents
   [Spatial Resolution]: 0.083 deg x 0.083 deg (~9 km)
   [Temporal Interval]:  1-hourly instantaneous (PT1H-i)
   [Depth Level]:        0.0 m
   [Coverage]:           Global (180W-180E, 80S-90N)
   [Variables]:
       * utotal   -> Surface eastward total velocity (m/s)
       * vtotal   -> Surface northward total velocity (m/s)

----------------------------------------------------------------------
   [3] IDENTIFIED OCEAN WAVES FORECAST DATASET
----------------------------------------------------------------------

   [Dataset ID]:         cmems_mod_glo_wav_anfc_0.083deg_PT3H-i
   [Product ID]:         GLOBAL_ANALYSISFORECAST_WAV_001_027
   [Title]:              Global Ocean Waves Analysis and Forecast - Spectral Wave Parameters
   [Spatial Resolution]: 0.083 deg x 0.083 deg (~9 km / 1/12 deg)
   [Temporal Interval]:  3-hourly instantaneous (PT3H-i)
   [Depth Level]:        Surface Spectrum
   [Coverage]:           Global (180W-180E, 80S-90N)
   [Variables]:
       * VHM0     -> Spectral significant wave height (Hs) (m)
       * VMDR     -> Mean wave direction from which waves propagate (degrees)
       * VTPK     -> Peak wave period (Tp) (s)

======================================================================
   [4] MATHEMATICAL VECTOR CONVERSION DEMONSTRATION
======================================================================
    Sample Copernicus Vectors:  uo = +0.52 m/s, vo = +0.88 m/s
    Converted Speed (knots):    1.99 knots (1 m/s = 1.943844 kn)
    Converted Direction (deg):  30.6 deg (Oceanographic flow heading)

======================================================================
   [5] ENVIRONMENTALDATA INTEGRATION ROADMAP
======================================================================
    * wave_height        <-- CMEMS VHM0 (Spectral significant wave height, m)
    * wave_direction     <-- CMEMS VMDR (Mean wave direction, deg)
    * wave_period        <-- CMEMS VTPK (Peak wave period, s)
    * current_speed      <-- CMEMS sqrt(uo^2 + vo^2) * 1.943844 (knots)
    * current_direction  <-- CMEMS (90 - atan2(vo, uo)) mod 360 (deg)
    * wind_speed         <-- Atmospheric Provider (e.g. NOAA GFS / Open-Meteo)
    * wind_direction     <-- Atmospheric Provider
======================================================================
   COPERNICUS MARINE ACCESS & METADATA DISCOVERY VERIFIED
======================================================================
```
