"""
Marine and weather data acquisition module.
Provides abstract provider interfaces, Copernicus Marine Service provider,
Open-Meteo atmospheric wind provider, composite data fusion provider,
dataset specifications, and vector conversion utilities.
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
from naudisha.data.copernicus_provider import (
    CopernicusMarineProvider,
    CopernicusProviderError,
    CopernicusAuthenticationError,
    CopernicusDataUnavailableError,
)
from naudisha.data.wind_provider import (
    OpenMeteoWindProvider,
    WindProviderError,
    WindNetworkError,
    WindDataUnavailableError,
    WindResponseMalformedError,
    KMH_TO_KNOTS,
)
from naudisha.data.composite_provider import (
    CompositeEnvironmentalProvider,
)

__all__ = [
    "WeatherProvider",
    "MockWeatherProvider",
    "CopernicusMarineProvider",
    "CopernicusProviderError",
    "CopernicusAuthenticationError",
    "CopernicusDataUnavailableError",
    "OpenMeteoWindProvider",
    "WindProviderError",
    "WindNetworkError",
    "WindDataUnavailableError",
    "WindResponseMalformedError",
    "CompositeEnvironmentalProvider",
    "CopernicusDatasetSpec",
    "CMEMS_OCEAN_CURRENTS_SPEC",
    "CMEMS_SURFACE_CURRENTS_HOURLY_SPEC",
    "CMEMS_WAVES_SPEC",
    "convert_current_vectors_to_speed_and_direction",
    "convert_speed_and_direction_to_vectors",
    "MS_TO_KNOTS",
    "KMH_TO_KNOTS",
]
