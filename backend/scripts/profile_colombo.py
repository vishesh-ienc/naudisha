"""
Benchmark script for Colombo and regional routes.
"""

import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from naudisha.api.services import RoutePlanningService
from scripts.profile_pipeline import benchmark_corridor

if __name__ == "__main__":
    service = RoutePlanningService()
    # Benchmark Mumbai to Colombo (Cold)
    r1 = benchmark_corridor("Mumbai to Colombo [Cold]", 18.85, 72.45, 6.94, 79.84, "balanced", service)
    # Benchmark Colombo (Objective Switch: Safety)
    r2 = benchmark_corridor("Mumbai to Colombo [Objective: Safety]", 18.85, 72.45, 6.94, 79.84, "safety", service)
