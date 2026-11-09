"""Diameter along the skeleton."""

import numpy as np
from scipy.ndimage import distance_transform_edt


def distance_map(mask):
    """Distance from each root pixel to the nearest background pixel. Compute once per root."""
    return distance_transform_edt(np.asarray(mask) > 0)


def distance_transform_diameter(mask, skeleton_rc, dist=None):
    """Diameter at each skeleton pixel: twice the distance to the nearest background pixel."""
    dist = distance_map(mask) if dist is None else dist
    return 2.0 * dist[skeleton_rc[:, 0], skeleton_rc[:, 1]]


METHODS = {"distance_transform": distance_transform_diameter}


def estimate_diameter(mask, skeleton_rc, method="distance_transform", **precomputed):
    """Per-pixel diameter values (px) along skeleton_rc, an (N, 2) array of (row, col)."""
    try:
        return METHODS[method](mask, skeleton_rc, **precomputed)
    except KeyError:
        raise ValueError(f"unknown diameter method {method!r}; available: {sorted(METHODS)}") from None


def mean_diameter(values):
    """NaN-aware mean, rounded to 0.01 px. The rounded value is what main-root selection compares."""
    valid = values[~np.isnan(values)]
    return float(np.mean(valid).round(2)) if len(valid) else float("nan")
