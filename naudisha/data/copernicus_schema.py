"""
Copernicus Marine Service (CMEMS) dataset schemas, variable definitions, and conversion utilities.
Defines metadata contracts and mathematical conversion helpers for mapping CMEMS physical oceanography
and wave forecast variables into NauDisha's EnvironmentalData model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# Conversion factor: 1 meter per second (m/s) = 1.9438444924 knots
MS_TO_KNOTS: float = 1.9438444924


@dataclass(frozen=True)
class CopernicusDatasetSpec:
    """
    Metadata specification for a Copernicus Marine Service dataset.

    Attributes:
        product_id: CMEMS product family ID.
        dataset_id: Exact dataset identifier in the CMEMS catalogue.
        title: Descriptive product title.
        variables: Dictionary of variable name -> (description, physical_units).
        spatial_resolution: Spatial grid resolution (degrees).
        temporal_resolution: Forecast/analysis time step.
        depth_level: Depth layer to query (meters below surface, e.g. 0.494m).
        coverage: Geographic bounding coverage.
    """
    product_id: str
    dataset_id: str
    title: str
    variables: Dict[str, Tuple[str, str]]
    spatial_resolution: str
    temporal_resolution: str
    depth_level: Optional[float]
    coverage: str = "Global (180W-180E, 80S-90N)"


# 1. Primary Ocean Currents / Hydrodynamics Dataset Specification
CMEMS_OCEAN_CURRENTS_SPEC = CopernicusDatasetSpec(
    product_id="GLOBAL_ANALYSISFORECAST_PHY_001_024",
    dataset_id="cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i",
    title="Global Ocean Physics Analysis and Forecast - Currents (Instantaneous)",
    variables={
        "uo": ("Eastward water velocity", "m/s"),
        "vo": ("Northward water velocity", "m/s"),
    },
    spatial_resolution="0.083° x 0.083° (~9 km / 1/12°)",
    temporal_resolution="6-hourly instantaneous (PT6H-i)",
    depth_level=0.494,  # Surface layer
)

# 2. Alternative Hourly Surface Currents Dataset Specification
CMEMS_SURFACE_CURRENTS_HOURLY_SPEC = CopernicusDatasetSpec(
    product_id="GLOBAL_ANALYSISFORECAST_PHY_001_024",
    dataset_id="cmems_mod_glo_phy_anfc_merged-uv_PT1H-i",
    title="Global Ocean Physics Analysis and Forecast - Merged UV Surface Currents",
    variables={
        "utotal": ("Surface eastward total velocity", "m/s"),
        "vtotal": ("Surface northward total velocity", "m/s"),
    },
    spatial_resolution="0.083° x 0.083° (~9 km)",
    temporal_resolution="1-hourly instantaneous (PT1H-i)",
    depth_level=0.0,
)

# 3. Primary Ocean Waves Dataset Specification
CMEMS_WAVES_SPEC = CopernicusDatasetSpec(
    product_id="GLOBAL_ANALYSISFORECAST_WAV_001_027",
    dataset_id="cmems_mod_glo_wav_anfc_0.083deg_PT3H-i",
    title="Global Ocean Waves Analysis and Forecast - Spectral Wave Parameters",
    variables={
        "VHM0": ("Spectral significant wave height (Hs)", "m"),
        "VMDR": ("Mean wave direction from which waves propagate", "degrees"),
        "VTPK": ("Peak wave period (Tp)", "s"),
    },
    spatial_resolution="0.083° x 0.083° (~9 km / 1/12°)",
    temporal_resolution="3-hourly instantaneous (PT3H-i)",
    depth_level=None,  # Surface wave spectrum
)


def convert_current_vectors_to_speed_and_direction(
    uo_mps: float,
    vo_mps: float,
) -> Tuple[float, float]:
    """
    Converts eastward (uo) and northward (vo) velocity components in meters per second (m/s)
    into scalar current speed (knots) and oceanographic current flow direction (degrees [0, 360)).

    Convention:
        - uo: Eastward velocity component (positive = flowing East).
        - vo: Northward velocity component (positive = flowing North).
        - Current direction: Direction towards which current flows in degrees [0, 360) (0° = North, 90° = East).

    Args:
        uo_mps: Eastward current velocity in m/s.
        vo_mps: Northward current velocity in m/s.

    Returns:
        (current_speed_knots, current_direction_degrees)
    """
    speed_mps = math.sqrt(uo_mps**2 + vo_mps**2)
    speed_knots = speed_mps * MS_TO_KNOTS

    # atan2(uo, vo) gives angle clockwise from North (0° = North, 90° = East, 180° = South, 270° = West)
    direction_deg = (math.degrees(math.atan2(uo_mps, vo_mps)) + 360.0) % 360.0

    return (speed_knots, direction_deg)


def convert_speed_and_direction_to_vectors(
    speed_knots: float,
    direction_deg: float,
) -> Tuple[float, float]:
    """
    Converts current speed (knots) and flow direction (degrees [0, 360)) back into
    eastward (uo) and northward (vo) velocity components in m/s.

    Returns:
        (uo_mps, vo_mps)
    """
    speed_mps = speed_knots / MS_TO_KNOTS
    rad = math.radians(direction_deg)
    uo_mps = speed_mps * math.sin(rad)
    vo_mps = speed_mps * math.cos(rad)
    return (uo_mps, vo_mps)
