"""
NauDisha — Dynamic & Optimal Ship Routing System
=================================================
A modular maritime routing platform powered by dynamic graph search algorithms (D* Lite)
and multi-factor environmental cost models.
"""

__version__ = "0.1.0"
__author__ = "NauDisha Team"

from naudisha.core.models import (
    ShipProfile,
    EnvironmentalData,
    SegmentData,
    CostWeights,
    ScoringConfig,
    DerivedSegmentMetrics,
    SegmentScores,
    SegmentEvaluation,
)
from naudisha.cost.model import CostModel
from naudisha.routing.graph import (
    GridConfig,
    GridNode,
    GridEdge,
    GeographicGridGraph,
)
from naudisha.routing.dstar_lite import DStarLite
from naudisha.data import (
    WeatherProvider,
    MockWeatherProvider,
    CopernicusMarineProvider,
    CopernicusProviderError,
    CopernicusAuthenticationError,
    CopernicusDataUnavailableError,
    OpenMeteoWindProvider,
    WindProviderError,
    WindNetworkError,
    WindDataUnavailableError,
    WindResponseMalformedError,
    CompositeEnvironmentalProvider,
)

__all__ = [
    "ShipProfile",
    "EnvironmentalData",
    "SegmentData",
    "CostWeights",
    "ScoringConfig",
    "DerivedSegmentMetrics",
    "SegmentScores",
    "SegmentEvaluation",
    "CostModel",
    "GridConfig",
    "GridNode",
    "GridEdge",
    "GeographicGridGraph",
    "DStarLite",
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
]
