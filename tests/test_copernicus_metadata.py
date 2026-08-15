"""
Offline unit tests for Copernicus Marine Service (CMEMS) dataset schemas and conversion utilities.
Runs completely offline without network or authentication dependency.
"""

import math
import unittest
from unittest.mock import MagicMock

from naudisha.core.models import EnvironmentalData
from naudisha.data.copernicus_schema import (
    CMEMS_OCEAN_CURRENTS_SPEC,
    CMEMS_SURFACE_CURRENTS_HOURLY_SPEC,
    CMEMS_WAVES_SPEC,
    convert_current_vectors_to_speed_and_direction,
    convert_speed_and_direction_to_vectors,
    MS_TO_KNOTS,
)


class TestCopernicusSchemas(unittest.TestCase):
    """Test suite for Copernicus Marine dataset specifications and schemas."""

    def test_ocean_currents_spec_integrity(self):
        """Verifies ocean currents dataset specification parameters."""
        spec = CMEMS_OCEAN_CURRENTS_SPEC
        self.assertEqual(spec.product_id, "GLOBAL_ANALYSISFORECAST_PHY_001_024")
        self.assertEqual(spec.dataset_id, "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i")
        self.assertIn("uo", spec.variables)
        self.assertIn("vo", spec.variables)
        self.assertEqual(spec.variables["uo"][1], "m/s")
        self.assertEqual(spec.variables["vo"][1], "m/s")
        self.assertEqual(spec.depth_level, 0.494)

    def test_surface_currents_hourly_spec_integrity(self):
        """Verifies hourly surface currents dataset specification."""
        spec = CMEMS_SURFACE_CURRENTS_HOURLY_SPEC
        self.assertEqual(spec.product_id, "GLOBAL_ANALYSISFORECAST_PHY_001_024")
        self.assertEqual(spec.dataset_id, "cmems_mod_glo_phy_anfc_merged-uv_PT1H-i")
        self.assertIn("utotal", spec.variables)
        self.assertIn("vtotal", spec.variables)
        self.assertEqual(spec.depth_level, 0.0)

    def test_waves_spec_integrity(self):
        """Verifies wave parameters dataset specification."""
        spec = CMEMS_WAVES_SPEC
        self.assertEqual(spec.product_id, "GLOBAL_ANALYSISFORECAST_WAV_001_027")
        self.assertEqual(spec.dataset_id, "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i")
        self.assertIn("VHM0", spec.variables)  # Significant wave height
        self.assertIn("VMDR", spec.variables)  # Mean wave direction
        self.assertIn("VTPK", spec.variables)  # Peak wave period
        self.assertEqual(spec.variables["VHM0"][1], "m")
        self.assertEqual(spec.variables["VMDR"][1], "degrees")
        self.assertEqual(spec.variables["VTPK"][1], "s")


class TestVectorConversions(unittest.TestCase):
    """Test suite for mathematical vector conversions between (uo, vo) and (speed, direction)."""

    def test_cardinal_directions(self):
        """Validates velocity conversions for standard cardinal and intercardinal compass headings."""
        # Due North: uo = 0.0, vo = 1.0 m/s -> Direction = 0°, Speed = 1.9438 knots
        spd_n, dir_n = convert_current_vectors_to_speed_and_direction(0.0, 1.0)
        self.assertAlmostEqual(spd_n, MS_TO_KNOTS, places=4)
        self.assertAlmostEqual(dir_n, 0.0, places=4)

        # Due East: uo = 1.0, vo = 0.0 m/s -> Direction = 90°, Speed = 1.9438 knots
        spd_e, dir_e = convert_current_vectors_to_speed_and_direction(1.0, 0.0)
        self.assertAlmostEqual(spd_e, MS_TO_KNOTS, places=4)
        self.assertAlmostEqual(dir_e, 90.0, places=4)

        # Due South: uo = 0.0, vo = -1.0 m/s -> Direction = 180°, Speed = 1.9438 knots
        spd_s, dir_s = convert_current_vectors_to_speed_and_direction(0.0, -1.0)
        self.assertAlmostEqual(spd_s, MS_TO_KNOTS, places=4)
        self.assertAlmostEqual(dir_s, 180.0, places=4)

        # Due West: uo = -1.0, vo = 0.0 m/s -> Direction = 270°, Speed = 1.9438 knots
        spd_w, dir_w = convert_current_vectors_to_speed_and_direction(-1.0, 0.0)
        self.assertAlmostEqual(spd_w, MS_TO_KNOTS, places=4)
        self.assertAlmostEqual(dir_w, 270.0, places=4)

        # North-East (45°): uo = 1.0, vo = 1.0 m/s
        spd_ne, dir_ne = convert_current_vectors_to_speed_and_direction(1.0, 1.0)
        self.assertAlmostEqual(spd_ne, math.sqrt(2.0) * MS_TO_KNOTS, places=4)
        self.assertAlmostEqual(dir_ne, 45.0, places=4)

        # Zero current: uo = 0.0, vo = 0.0 m/s -> Speed = 0.0
        spd_zero, _ = convert_current_vectors_to_speed_and_direction(0.0, 0.0)
        self.assertAlmostEqual(spd_zero, 0.0)

    def test_roundtrip_conversions(self):
        """Converts vectors to speed/dir and back to verify roundtrip numerical stability."""
        test_vectors = [
            (0.5, 1.2),
            (-0.8, 0.3),
            (-1.5, -2.0),
            (0.0, -0.7),
            (2.1, 0.0),
        ]
        for orig_uo, orig_vo in test_vectors:
            speed_knots, dir_deg = convert_current_vectors_to_speed_and_direction(orig_uo, orig_vo)
            uo_recalc, vo_recalc = convert_speed_and_direction_to_vectors(speed_knots, dir_deg)

            self.assertAlmostEqual(orig_uo, uo_recalc, places=5)
            self.assertAlmostEqual(orig_vo, vo_recalc, places=5)

    def test_mapping_to_environmental_data_model(self):
        """Verifies mapping of mock Copernicus variables into the existing EnvironmentalData model."""
        # Simulated Copernicus data point
        mock_cmems_currents = {"uo": 0.45, "vo": 0.85}  # m/s
        mock_cmems_waves = {"VHM0": 2.3, "VMDR": 240.0, "VTPK": 8.2}  # m, deg, s
        mock_wind = {"speed_knots": 18.5, "direction_deg": 235.0}

        cur_speed, cur_dir = convert_current_vectors_to_speed_and_direction(
            mock_cmems_currents["uo"], mock_cmems_currents["vo"]
        )

        env = EnvironmentalData(
            timestamp="2026-08-16T12:00:00Z",
            wind_speed=mock_wind["speed_knots"],
            wind_direction=mock_wind["direction_deg"],
            wave_height=mock_cmems_waves["VHM0"],
            wave_direction=mock_cmems_waves["VMDR"],
            wave_period=mock_cmems_waves["VTPK"],
            current_speed=cur_speed,
            current_direction=cur_dir,
        )

        self.assertAlmostEqual(env.wave_height, 2.3)
        self.assertAlmostEqual(env.wave_direction, 240.0)
        self.assertAlmostEqual(env.wave_period, 8.2)
        self.assertAlmostEqual(env.wind_speed, 18.5)
        self.assertAlmostEqual(env.wind_direction, 235.0)
        self.assertAlmostEqual(env.current_speed, math.sqrt(0.45**2 + 0.85**2) * MS_TO_KNOTS, places=4)
        self.assertGreater(env.current_direction, 0.0)
        self.assertLess(env.current_direction, 90.0)  # NE quadrant (uo > 0, vo > 0)


if __name__ == "__main__":
    unittest.main()
