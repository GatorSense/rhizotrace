"""Joining level images of one tube into a single continuous image along the depth axis."""

from dataclasses import dataclass

import numpy as np

from ..config import Scanner
from ..io import load_image, load_mask
from .geometry import CM_PER_INCH


@dataclass
class Stitched:
    image: np.ndarray
    levels: list            # level number of each slice, in order
    starts: np.ndarray      # slice start columns in the stitched image, length len(levels) + 1
    offsets: np.ndarray     # column in the raw level image where each slice begins

    def slice_of(self, level):
        i = self.levels.index(level)
        return int(self.starts[i]), int(self.starts[i + 1])


def overlap_trim_px(scanner: Scanner, dpi):
    return int(round(scanner.overlap_cm * dpi / CM_PER_INCH))


def stitch_arrays(level_images, scanner: Scanner, dpi):
    """Stitch {level: array} (depth along columns) after trimming artifacts and overlap.

    Level 1 loses l1_start_trim_px at its start, every later level loses the overlap
    with the level above, and every level loses level_end_trim_px at its end. Missing
    levels are left out; depth mapping still places each present level.
    """
    if not level_images:
        raise ValueError("no level images to stitch")
    overlap = overlap_trim_px(scanner, dpi)
    levels = sorted(level_images)
    slices, offsets = [], []
    for level in levels:
        img = level_images[level]
        start = scanner.l1_start_trim_px if level == 1 else overlap
        end = img.shape[1] - scanner.level_end_trim_px if scanner.level_end_trim_px > 0 else img.shape[1]
        if start >= end:
            raise ValueError(f"level {level}: trims ({start} + {scanner.level_end_trim_px}) exceed width {img.shape[1]}")
        slices.append(img[:, start:end])
        offsets.append(start)
    heights = {s.shape[0] for s in slices}
    if len(heights) > 1:
        raise ValueError(f"level images differ in height: {sorted(heights)}")
    starts = np.concatenate([[0], np.cumsum([s.shape[1] for s in slices])])
    return Stitched(np.concatenate(slices, axis=1), levels, starts, np.array(offsets))


def stitch(tube, scanner: Scanner = None, dpi=300, kind="masks", threshold=0.5):
    """Stitch a Tube's mask (kind='masks') or photo (kind='images') levels."""
    scanner = scanner or Scanner()
    files = tube.masks if kind == "masks" else tube.images
    if not files:
        raise ValueError(f"tube {tube.name} has no {kind}")
    load = (lambda p: load_mask(p, threshold)) if kind == "masks" else load_image
    return stitch_arrays({level: load(path) for level, path in files.items()}, scanner, dpi)
