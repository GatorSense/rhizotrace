"""Pixel position along a tube to real vertical soil depth."""

import math
from dataclasses import dataclass

import numpy as np

from ..config import Scanner, TubeInfo

CM_PER_INCH = 2.54


@dataclass
class LevelPosition:
    """Where one camera level sits, in cm. tube_* is distance along the tube from the
    soil surface, soil_* is vertical depth. Negative values are above the surface."""

    level: int
    tube_top_cm: float
    tube_bottom_cm: float
    soil_top_cm: float
    soil_bottom_cm: float


def cos_factor(angle_deg):
    return math.cos(math.radians(angle_deg))


def level_positions(tube: TubeInfo, scanner: Scanner, n_levels):
    """Positions of levels 1..n_levels. Level n starts overlap_cm above where level n-1 ends."""
    factor = cos_factor(tube.angle_deg)
    positions = []
    for n in range(1, n_levels + 1):
        tube_top = scanner.camera_start_cm - tube.offset_cm if n == 1 else positions[-1].tube_bottom_cm - scanner.overlap_cm
        tube_bottom = tube_top + scanner.level_height_cm
        soil_top, soil_bottom = tube_top * factor, tube_bottom * factor
        positions.append(LevelPosition(n, tube_top, tube_bottom, soil_top, soil_bottom))
    return positions


def px_to_cm(px, dpi):
    return np.asarray(px, dtype=float) * CM_PER_INCH / dpi


def level_depth_cm(px, position: LevelPosition, dpi, angle_deg):
    """Soil depth of pixel positions along the depth axis of one raw level image."""
    return (position.tube_top_cm + px_to_cm(px, dpi)) * cos_factor(angle_deg)


def stitched_depth_cm(px, stitched, positions, dpi, angle_deg):
    """Soil depth of pixel positions along the depth axis of a stitched image.

    stitched: Stitched (slice starts and raw offsets per level).
    positions: {level: LevelPosition}.
    """
    px = np.asarray(px, dtype=float)
    idx = np.clip(np.searchsorted(stitched.starts[1:], px, side="right"), 0, len(stitched.levels) - 1)
    raw_px = px - stitched.starts[idx] + stitched.offsets[idx]
    tube_tops = np.array([positions[level].tube_top_cm for level in stitched.levels])
    return (tube_tops[idx] + px_to_cm(raw_px, dpi)) * cos_factor(angle_deg)
