"""
Marine, weather, and vessel data acquisition module.
Provides abstract provider interfaces, Copernicus Marine Service provider,
Open-Meteo atmospheric wind provider, composite data fusion provider,
vessel registry providers, and vector conversion utilities.
"""

from naudisha.data.weather_provider import (
    WeatherProvider,
    MockWeatherProvider,
    ConditionRequest,
    BatchCapableProvider,
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
from naudisha.data.vessel_provider import (
    VesselRecord,
    VesselProvider,
    RegistryVesselProvider,
    CompositeVesselProvider,
    MockVesselProvider,
    GLOBAL_VESSEL_REGISTRY,
)

__all__ = [
    "WeatherProvider",
    "MockWeatherProvider",
    "ConditionRequest",
    "BatchCapableProvider",
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
    "VesselRecord",
    "VesselProvider",
    "RegistryVesselProvider",
    "CompositeVesselProvider",
    "MockVesselProvider",
    "GLOBAL_VESSEL_REGISTRY",
    "CopernicusDatasetSpec",
    "CMEMS_OCEAN_CURRENTS_SPEC",
    "CMEMS_SURFACE_CURRENTS_HOURLY_SPEC",
    "CMEMS_WAVES_SPEC",
    "convert_current_vectors_to_speed_and_direction",
    "convert_speed_and_direction_to_vectors",
    "MS_TO_KNOTS",
    "KMH_TO_KNOTS",
]
