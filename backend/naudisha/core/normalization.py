"""
Normalization and clamping utilities for NauDisha scoring functions.
Ensures all cost scores map predictably to [0.0, 1.0] where 0 is best and 1 is worst.
"""

from typing import Union


def clamp(value: float, min_bound: float = 0.0, max_bound: float = 1.0) -> float:
    """
    Clamps a floating point value between min_bound and max_bound.

    Args:
        value: Numeric input value.
        min_bound: Minimum allowable limit.
        max_bound: Maximum allowable limit.

    Returns:
        Clamped float value within [min_bound, max_bound].
    """
    if min_bound > max_bound:
        min_bound, max_bound = max_bound, min_bound
    return max(min_bound, min(max_bound, float(value)))


def normalize_min_max(
    value: float,
    min_val: float,
    max_val: float,
    invert: bool = False,
) -> float:
    """
    Normalizes a numerical value into the standard [0.0, 1.0] cost score interval.

    Standard Convention (invert=False):
        - value <= min_val  -> 0.0 (Best condition / lowest penalty)
        - value >= max_val  -> 1.0 (Worst condition / highest penalty)
        - min_val < value < max_val -> Linear interpolation

    Inverted Convention (invert=True, e.g. for speed boosts / tailwinds):
        - value <= min_val  -> 1.0 (Worst condition)
        - value >= max_val  -> 0.0 (Best condition)
        - min_val < value < max_val -> Inverted linear interpolation

    Args:
        value: The raw physical or derived metric value.
        min_val: Reference lower bound.
        max_val: Reference upper bound.
        invert: If True, reverses polarity (higher value becomes lower cost score).

    Returns:
        Clamped float score in [0.0, 1.0].
    """
    if max_val == min_val:
        # Avoid division by zero: if bounds are identical, return default 0.0
        return 0.0

    # Ensure correct ordering
    if min_val > max_val:
        min_val, max_val = max_val, min_val
        invert = not invert

    # Compute normalized ratio
    normalized = (value - min_val) / (max_val - min_val)
    clamped_norm = clamp(normalized, 0.0, 1.0)

    if invert:
        return 1.0 - clamped_norm
    return clamped_norm
