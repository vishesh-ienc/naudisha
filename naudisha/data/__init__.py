"""
Marine and weather data acquisition module.
Provides abstract provider interfaces and Copernicus Marine Service metadata schemas.
"""

from naudisha.data.weather_provider import (
    WeatherProvider,
    MockWeatherProvider,
)
from naudisha.data.copernicus_schema import (
    CopernicusDatasetSpec,
    CMEMS_OCEAN_CURRENTS_SPEC,
    CMEMS_SURFACE_CURRENTS_HOURLY_SPEC,
    CMEMS_WAVES_SPEC,
    convert_current_vectors_to_speed_and_direction,
    convert_speed_and_direction_to_vectors,
    MS_TO_KNOTS,
)

__all__ = [
    "WeatherProvider",
    "MockWeatherProvider",
    "CopernicusDatasetSpec",
    "CMEMS_OCEAN_CURRENTS_SPEC",
    "CMEMS_SURFACE_CURRENTS_HOURLY_SPEC",
    "CMEMS_WAVES_SPEC",
    "convert_current_vectors_to_speed_and_direction",
    "convert_speed_and_direction_to_vectors",
    "MS_TO_KNOTS",
]
