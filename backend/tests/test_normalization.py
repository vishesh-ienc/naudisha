"""
Unit tests for min-max normalization and clamping:
- standard normalization
- inverted normalization
- boundary clamping [0.0, 1.0]
- edge cases (equal min and max)
"""

import unittest

from naudisha.core.normalization import clamp, normalize_min_max


class TestNormalization(unittest.TestCase):
    """Test suite for normalization functions."""

    def test_clamp(self):
        """Clamp restricts values to [min_bound, max_bound]."""
        self.assertEqual(clamp(0.5, 0.0, 1.0), 0.5)
        self.assertEqual(clamp(-5.0, 0.0, 1.0), 0.0)
        self.assertEqual(clamp(10.0, 0.0, 1.0), 1.0)
        self.assertEqual(clamp(15.0, 10.0, 20.0), 15.0)
        self.assertEqual(clamp(5.0, 10.0, 20.0), 10.0)
        self.assertEqual(clamp(25.0, 10.0, 20.0), 20.0)

    def test_normalize_standard(self):
        """Standard normalization maps min to 0.0 and max to 1.0."""
        # Exact min
        self.assertEqual(normalize_min_max(10.0, min_val=10.0, max_val=20.0), 0.0)
        # Exact max
        self.assertEqual(normalize_min_max(20.0, min_val=10.0, max_val=20.0), 1.0)
        # Midpoint
        self.assertAlmostEqual(normalize_min_max(15.0, min_val=10.0, max_val=20.0), 0.5)
        # Below min (clamped to 0.0)
        self.assertEqual(normalize_min_max(5.0, min_val=10.0, max_val=20.0), 0.0)
        # Above max (clamped to 1.0)
        self.assertEqual(normalize_min_max(25.0, min_val=10.0, max_val=20.0), 1.0)

    def test_normalize_inverted(self):
        """Inverted normalization maps min to 1.0 and max to 0.0."""
        # Exact min -> 1.0
        self.assertEqual(normalize_min_max(10.0, min_val=10.0, max_val=20.0, invert=True), 1.0)
        # Exact max -> 0.0
        self.assertEqual(normalize_min_max(20.0, min_val=10.0, max_val=20.0, invert=True), 0.0)
        # Midpoint -> 0.5
        self.assertAlmostEqual(normalize_min_max(15.0, min_val=10.0, max_val=20.0, invert=True), 0.5)
        # Below min -> clamped to 1.0
        self.assertEqual(normalize_min_max(5.0, min_val=10.0, max_val=20.0, invert=True), 1.0)
        # Above max -> clamped to 0.0
        self.assertEqual(normalize_min_max(25.0, min_val=10.0, max_val=20.0, invert=True), 0.0)

    def test_normalize_equal_bounds(self):
        """Equal bounds returns 0.0 safely without zero-division."""
        self.assertEqual(normalize_min_max(15.0, min_val=10.0, max_val=10.0), 0.0)


if __name__ == "__main__":
    unittest.main()
