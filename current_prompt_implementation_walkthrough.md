# Current Prompt Implementation Walkthrough: Copernicus Marine Data Provider Implementation

## 🎯 Scope of Current Prompt
- Implement the first real Copernicus Marine data provider for NauDisha: `CopernicusMarineProvider`.
- Architecture data flow:
  $$\text{Copernicus Marine} \longrightarrow \text{EnvironmentalData} \longrightarrow \text{CostModel} \longrightarrow \text{GeographicGridGraph} \longrightarrow D^* \text{ Lite}$$
- Reuse existing Copernicus dataset schemas and mathematical vector conversion formulas (`cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i` and `cmems_mod_glo_wav_anfc_0.083deg_PT3H-i`).
- Support targeted spatial/temporal point queries using `copernicusmarine.read_dataframe` to avoid downloading full datasets.
- Handle ocean current vectors $(u_o, v_o)$ and spectral wave variables $(VHM0, VMDR, VTPK)$.
- Explicitly set `wind_speed=None` and `wind_direction=None` (no mock wind invention) with backwards-compatible `Optional[float]` validation in `EnvironmentalData`.
- Implement robust exception hierarchy (`CopernicusProviderError`, `CopernicusAuthenticationError`, `CopernicusDataUnavailableError`).
- Add dependency injection to support fast offline unit testing without network/credential requirements.
- Add live integration script [`examples/fetch_copernicus_sample.py`](file:///c:/Users/VISHESH/Desktop/naudisha/examples/fetch_copernicus_sample.py).
- Preserve 100% decoupling: zero modifications to D* Lite, `GeographicGridGraph`, or `CostModel` formulas.

---

## 🛠 Changes Implemented

### 1. `EnvironmentalData` Model Compatibility ([`naudisha/core/models.py`](file:///c:/Users/VISHESH/Desktop/naudisha/naudisha/core/models.py))
- Updated field annotations to `Optional[float] = None` with None-safe `__post_init__` validation.
- Allows cleanly creating `EnvironmentalData` objects where wind data is pending from a secondary atmospheric provider without inventing dummy numbers.

### 2. `CopernicusMarineProvider` Implementation ([`naudisha/data/copernicus_provider.py`](file:///c:/Users/VISHESH/Desktop/naudisha/naudisha/data/copernicus_provider.py))
- Implements `WeatherProvider.fetch_conditions(lat, lon, timestamp)`.
- **Targeted Subsetting**: Queries minimal spatial window ($[\text{lat} \pm 0.1^\circ]$, $[\text{lon} \pm 0.1^\circ]$) and time window ($[t \pm 3\text{h}]$) via `copernicusmarine.read_dataframe` with `coordinates_selection_method="nearest"`.
- **Ocean Currents Conversion**:
  - Speed: $v_{\text{knots}} = \sqrt{u_o^2 + v_o^2} \times 1.9438444924$
  - Direction: $\theta_{\text{flow}} = (90^\circ - \text{atan2}(v_o, u_o) \cdot \frac{180^\circ}{\pi} + 360^\circ) \pmod{360^\circ}$
- **Ocean Waves Extraction**: Maps `VHM0` ($m$) to `wave_height`, `VMDR` ($^\circ$) to `wave_direction`, and `VTPK` ($s$) to `wave_period`.
- **In-Memory Cache**: Automatically caches responses using `(round(lat, 2), round(lon, 2), timestamp_hour)` keys.
- **Pre-Flight Credential Safety**: Checks for credential presence before network execution to avoid blocking automated tasks on interactive stdin.

### 3. Module & Package Exports ([`naudisha/data/__init__.py`](file:///c:/Users/VISHESH/Desktop/naudisha/naudisha/data/__init__.py), [`naudisha/__init__.py`](file:///c:/Users/VISHESH/Desktop/naudisha/naudisha/__init__.py))
- Exported `CopernicusMarineProvider`, `CopernicusProviderError`, `CopernicusAuthenticationError`, and `CopernicusDataUnavailableError`.

### 4. Offline Unit Test Suite ([`tests/test_copernicus_provider.py`](file:///c:/Users/VISHESH/Desktop/naudisha/tests/test_copernicus_provider.py))
- Added 7 offline unit tests using dependency-injected mock data readers:
  - `test_successful_fetch_and_mapping`
  - `test_in_memory_cache_hit`
  - `test_missing_current_values_raises_error`
  - `test_nan_current_values_raises_error`
  - `test_missing_wave_values_raises_error`
  - `test_authentication_error_handling`
  - `test_coordinate_bounds_validation`

### 5. Live Data Integration Sample ([`examples/fetch_copernicus_sample.py`](file:///c:/Users/VISHESH/Desktop/naudisha/examples/fetch_copernicus_sample.py))
- Script requesting a live sample for Arabian Sea / Indian Ocean coordinates ($18.50^\circ\text{N}, 72.00^\circ\text{E}$).
- Cleanly outputs returned `EnvironmentalData` and provides actionable guidance if local credentials are required.

---

## 🧪 Verification & Test Results

### 1. Unit Test Suite (64/64 Tests Passed)
```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```
```
test_authentication_error_handling (test_copernicus_provider.TestCopernicusMarineProvider.test_authentication_error_handling) ... ok
test_coordinate_bounds_validation (test_copernicus_provider.TestCopernicusMarineProvider.test_coordinate_bounds_validation) ... ok
test_in_memory_cache_hit (test_copernicus_provider.TestCopernicusMarineProvider.test_in_memory_cache_hit) ... ok
test_missing_current_values_raises_error (test_copernicus_provider.TestCopernicusMarineProvider.test_missing_current_values_raises_error) ... ok
test_missing_wave_values_raises_error (test_copernicus_provider.TestCopernicusMarineProvider.test_missing_wave_values_raises_error) ... ok
test_nan_current_values_raises_error (test_copernicus_provider.TestCopernicusMarineProvider.test_nan_current_values_raises_error) ... ok
test_successful_fetch_and_mapping (test_copernicus_provider.TestCopernicusMarineProvider.test_successful_fetch_and_mapping) ... ok
... (All 57 previous unit tests: Copernicus schemas, D* Lite, Dijkstra oracle, Graph, CostModel) ...

----------------------------------------------------------------------
Ran 64 tests in 0.054s

OK
```

### 2. Live Sample Output
```
======================================================================
   NauDisha - Copernicus Marine Service Live Sample Data Fetch
======================================================================

[1] TARGET QUERY PARAMETERS:
    Location:   (18.50N, 72.00E) - Arabian Sea / Indian Ocean
    Timestamp:  2026-08-15T12:00:00Z

[2] INITIALIZING COPERNICUS MARINE PROVIDER...

[3] FETCHING LIVE OCEANOGRAPHIC CONDITIONS...
    - Querying Ocean Currents (uo, vo from Global Physics Forecast)...
    - Querying Wave Parameters (Hs, direction, period from Wave Forecast)...

[!] AUTHENTICATION ERROR:
    No local Copernicus Marine credentials found in ~/.copernicusmarine/ or environment variables. Please run 'copernicusmarine login' in your terminal to authenticate with your Copernicus account.
    Please run 'copernicusmarine login' in your terminal to set up local credentials.
```
