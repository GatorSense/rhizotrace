"""Depth-binned root traits along a tube."""

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config import DEFAULT_ANGLE_DEG, Config, Scanner, TubeInfo
from ..core.extract import extract_roots, roots_to_frame
from ..core.orientation import depth_direction
from ..core.skeleton import DEFAULT_ESTIMATOR, skeleton_edges
from ..units import to_mm
from .geometry import level_positions, stitched_depth_cm
from .stitch import stitch

PROFILE_COLUMNS = ["tube", "depth_start_mm", "depth_end_mm", "root_length_mm",
                   "mean_diameter_mm", "median_diameter_mm", "n_roots", "n_skeleton_px"]


@dataclass
class TubeResult:
    """A tube stitched and measured. Depth of any stitched-image column via depth_mm()."""

    tube: object
    info: TubeInfo
    stitched: object
    roots: list
    positions: dict         # level -> LevelPosition
    dpi: int
    length_estimator: str = DEFAULT_ESTIMATOR

    def depth_mm(self, px):
        return stitched_depth_cm(px, self.stitched, self.positions, self.dpi, self.info.angle_deg) * 10.0

    def traits(self):
        """Tidy traits plus depth_direction: the root axis signed to point deeper.

        Only meaningful here. A bare mask carries no soil-depth axis, so signing the
        axis outside a tube would be an arbitrary convention.
        """
        df = roots_to_frame(self.roots, self.dpi, image=self.tube.name)
        directions = []
        for root in self.roots:
            directions.append(depth_direction(root.aggregated.skeleton_rc))
            directions.append(depth_direction(root.main_root.skeleton_rc))
            directions.extend(depth_direction(b.skeleton_rc) for b in root.branches)
        df["depth_direction"] = directions
        return df


def _resolve_info(tube, offset_cm, angle_deg):
    if tube.info is not None:
        return tube.info
    if offset_cm is None:
        raise ValueError(f"tube {tube.name}: no offset_cm. Provide a tube-info CSV or offset_cm=")
    return TubeInfo(tube.tube_id, offset_cm, DEFAULT_ANGLE_DEG if angle_deg is None else angle_deg)


def analyze_tube(tube, cfg: Config = None, scanner: Scanner = None, offset_cm=None, angle_deg=None):
    """Stitch a tube's masks, measure every root on the stitched image."""
    cfg = cfg or Config()
    scanner = scanner or Scanner()
    info = _resolve_info(tube, offset_cm, angle_deg)
    stitched = stitch(tube, scanner, cfg.dpi, kind="masks", threshold=cfg.mask_threshold)
    positions = {p.level: p for p in level_positions(info, scanner, max(stitched.levels))}
    roots = extract_roots(stitched.image, cfg)
    return TubeResult(tube, info, stitched, roots, positions, cfg.dpi, cfg.length_estimator)


def bin_edges(depth_min_mm, depth_max_mm, bin_mm):
    start = math.floor(depth_min_mm / bin_mm) * bin_mm
    return np.arange(start, depth_max_mm + bin_mm, bin_mm)


def bin_profile(roots, depth_mm_of, extent_px, dpi, bin_mm, tube="", estimator=DEFAULT_ESTIMATOR):
    """Bin root traits by depth.

    depth_mm_of maps positions along the depth axis (columns, may be fractional) to
    depth in mm. extent_px is the image width, so bins span the whole image even where
    no root is found. Per-bin length sums the terms of the length estimator by their
    midpoint depth, so root_length_mm totals exactly the aggregated root lengths.
    """
    if extent_px <= 0:
        return pd.DataFrame(columns=PROFILE_COLUMNS)
    full = depth_mm_of(np.arange(extent_px))
    edges = bin_edges(float(full.min()), float(full.max()), bin_mm)
    n_bins = len(edges) - 1
    if n_bins <= 0:
        return pd.DataFrame(columns=PROFILE_COLUMNS)

    def bin_of(depth):
        return np.clip(np.digitize(depth, edges) - 1, 0, n_bins - 1)

    length = np.zeros(n_bins)
    pixels = np.zeros(n_bins, dtype=int)
    root_hits = np.zeros(n_bins, dtype=int)
    diameters = [[] for _ in range(n_bins)]
    for root in roots:
        min_r, _, min_c, _ = root.bbox
        rc = root.aggregated.skeleton_rc
        b = bin_of(depth_mm_of(rc[:, 1] + min_c))
        values = to_mm(root.aggregated.diameter_values, dpi)
        for i, d in zip(b, values):
            if not np.isnan(d):
                diameters[i].append(d)
        np.add.at(pixels, b, 1)
        root_hits[np.unique(b)] += 1
        e = skeleton_edges(root.skeleton, estimator)
        if len(e):
            mid = (e[:, 1] + e[:, 3]) / 2.0 + min_c
            np.add.at(length, bin_of(depth_mm_of(mid)), to_mm(e[:, 4], dpi))

    rows = []
    for i in range(n_bins):
        d = diameters[i]
        rows.append({
            "tube": tube, "depth_start_mm": edges[i], "depth_end_mm": edges[i + 1],
            "root_length_mm": length[i],
            "mean_diameter_mm": float(np.mean(d)) if d else np.nan,
            "median_diameter_mm": float(np.median(d)) if d else np.nan,
            "n_roots": int(root_hits[i]), "n_skeleton_px": int(pixels[i]),
        })
    return pd.DataFrame(rows, columns=PROFILE_COLUMNS)


def profile_from_result(result: TubeResult, bin_mm=10.0):
    return bin_profile(result.roots, result.depth_mm, result.stitched.image.shape[1],
                       result.dpi, bin_mm, tube=result.tube.name, estimator=result.length_estimator)


def depth_profile(tubes, cfg: Config = None, scanner: Scanner = None, bin_mm=10.0,
                  offset_cm=None, angle_deg=None):
    """Depth-binned traits for every tube in a TubeSet (or one Tube). Stitches internally."""
    tube_list = [tubes] if hasattr(tubes, "masks") else list(tubes)
    frames = [profile_from_result(analyze_tube(t, cfg, scanner, offset_cm, angle_deg), bin_mm)
              for t in tube_list]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=PROFILE_COLUMNS)
