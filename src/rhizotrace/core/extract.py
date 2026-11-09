"""Per-root trait extraction and the tidy output table."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import ndimage

from ..config import Config
from ..units import to_mm
from .branches import (Branch, insertion_angle, merge_by_angle, merge_by_diameter,
                       select_main_root)
from .diameter import distance_map, estimate_diameter, mean_diameter
from .junctions import prune_spurs, separate_branches
from .orientation import axis_orientation
from .skeleton import DEFAULT_ESTIMATOR, order_pixels, skeleton_length, skeletonize

CROP_PAD = 2


@dataclass
class Traits:
    """Measurements of one skeleton path (a whole root, its main root, or a lateral)."""

    skeleton_rc: np.ndarray         # (N, 2) row/col within the root crop
    diameter_values: np.ndarray     # px, one per skeleton pixel
    length: float                   # px
    angle: float                    # degrees
    avg_diameter: float             # px, rounded to 0.01
    id: int = None                  # branch id (None for the whole root)
    merged_from: list = None
    insertion_angle: float = None   # laterals only


@dataclass
class Root:
    """One connected root component and everything measured on it."""

    component_id: int
    bbox: tuple                     # (min_r, max_r, min_c, max_c) in the full image
    crop: np.ndarray                # binary crop of this component
    skeleton: np.ndarray            # the skeleton the whole-root row and depth profiles measure
    junction_mask: np.ndarray
    labeled_skeleton: np.ndarray
    merged: list                    # Branch objects after merging
    aggregated: Traits
    main_root: Traits
    branches: list = field(default_factory=list)   # laterals (Traits)

    @property
    def n_branches(self):
        return len(self.branches)


def _ordered_path(rc):
    """order_pixels on a path's own bounding box (same raster order, much less work)."""
    r0, c0 = rc.min(axis=0)
    local = np.zeros(rc.max(axis=0) - (r0, c0) + 1, dtype=np.uint8)
    local[rc[:, 0] - r0, rc[:, 1] - c0] = 1
    return [(r + r0, c + c0) for r, c in order_pixels(local)]


def _pixels_length(rc, estimator=DEFAULT_ESTIMATOR):
    """Length of an unordered skeleton pixel set, summed over its own steps.

    A merged branch is several segments with the junction pixels removed between
    them, so it is normally disconnected and often branches. Walking it as a single
    path measures only the first piece reached.
    """
    r0, c0 = rc.min(axis=0)
    local = np.zeros(rc.max(axis=0) - (r0, c0) + 1, dtype=np.uint8)
    local[rc[:, 0] - r0, rc[:, 1] - c0] = 1
    return skeleton_length(local, estimator)


def _traits(crop, dist, rc, cfg, **extra):
    path = _ordered_path(rc)
    values = estimate_diameter(crop, rc, dist=dist)
    return Traits(rc, values, _pixels_length(rc, cfg.length_estimator), axis_orientation(rc),
                  mean_diameter(values), **extra), path


def _padded_bbox(r0, r1, c0, c1, shape):
    """Crop window around a component: CROP_PAD before, CROP_PAD past its last row/col, clipped."""
    return (max(r0 - CROP_PAD, 0), min(r1 - 1 + CROP_PAD, shape[0]),
            max(c0 - CROP_PAD, 0), min(c1 - 1 + CROP_PAD, shape[1]))


def extract_root(component_mask, cfg: Config, component_id=0):
    """Measure one connected component given as a full-size binary mask. None if too small."""
    rows, cols = np.where(component_mask > 0)
    if len(rows) == 0:
        return None
    bbox = _padded_bbox(int(rows.min()), int(rows.max()) + 1, int(cols.min()), int(cols.max()) + 1,
                        component_mask.shape)
    min_r, max_r, min_c, max_c = bbox
    return _extract_crop((component_mask[min_r:max_r, min_c:max_c] > 0).astype(np.uint8), bbox, cfg, component_id)


MIN_MEASURABLE_PX = 2   # a single skeleton pixel has no length, at any min_root_length_mm


def _too_short(rc, cfg, length=None):
    """Whether a skeleton's measured length is under min_root_length_mm."""
    if len(rc) < MIN_MEASURABLE_PX:
        return True
    return (_pixels_length(rc, cfg.length_estimator) if length is None else length) < cfg.min_root_length_px()


def _extract_crop(crop, bbox, cfg, component_id):
    est = cfg.length_estimator
    skeleton = skeletonize(crop)
    skel_rc = np.argwhere(skeleton)
    if _too_short(skel_rc, cfg, length=skeleton_length(skeleton, est)):
        return None

    dist = distance_map(crop)
    # Every measurement, the whole-root row included, is made on the pruned skeleton.
    if cfg.spur_length_diameters:
        skeleton, labeled, junction_mask = prune_spurs(skeleton, dist, cfg.spur_length_diameters,
                                                       cfg.junction_dilation_iterations, estimator=est)
        skel_rc = np.argwhere(skeleton)
        if _too_short(skel_rc, cfg, length=skeleton_length(skeleton, est)):
            return None
    else:
        labeled, junction_mask = separate_branches(skeleton, cfg.junction_dilation_iterations)

    agg_values = estimate_diameter(crop, skel_rc, dist=dist)
    aggregated = Traits(skel_rc, agg_values, skeleton_length(skeleton, est), axis_orientation(skel_rc),
                        mean_diameter(agg_values))

    labels = np.unique(labeled)
    labels = labels[labels >= 2]

    # a root with nothing to decompose is its own main root
    root = Root(component_id, bbox, crop, skeleton, junction_mask, labeled, [], aggregated, aggregated)
    if len(labels) <= 1:
        return root

    # angle merging sees every piece; the other methods drop short pieces first
    if cfg.merge_method == "angle":
        merged = merge_by_angle(labeled, junction_mask, cfg)
    else:
        pieces = []
        for label in labels:
            rc = np.argwhere(labeled == label)
            if _too_short(rc, cfg):
                continue
            piece = {"id": int(label), "pixels": list(map(tuple, rc.tolist()))}
            if cfg.merge_method == "diameter":
                piece["avg_diameter"] = mean_diameter(estimate_diameter(crop, rc, dist=dist))
            pieces.append(piece)
        if cfg.merge_method == "diameter":
            merged = merge_by_diameter(pieces, junction_mask, cfg)
        else:
            merged = [Branch(p["id"], p["pixels"], [p["id"]]) for p in pieces]
    root.merged = merged

    features, paths = [], []
    for branch in merged:
        rc = np.asarray(branch.pixels, dtype=np.int64).reshape(-1, 2)
        if _too_short(rc, cfg):
            continue
        traits, path = _traits(crop, dist, rc, cfg, id=branch.id, merged_from=list(branch.merged_from))
        features.append(traits)
        paths.append(path)
    if not features:
        return root

    main_idx = select_main_root(
        [f.length for f in features], [f.avg_diameter for f in features],
        [len(f.merged_from) for f in features], cfg.root_selection,
        cfg.length_weight, cfg.diameter_weight,
    )
    root.main_root = features[main_idx]
    for i, f in enumerate(features):
        if i != main_idx:
            f.insertion_angle = insertion_angle(paths[main_idx], paths[i])
            root.branches.append(f)
    return root


def extract_roots(mask, cfg: Config):
    """Measure every connected component of a binary mask. Returns a list of Root."""
    labeled, _ = ndimage.label(np.asarray(mask) > 0)
    roots = []
    for component_id, sl in enumerate(ndimage.find_objects(labeled), start=1):
        if int(np.count_nonzero(labeled[sl] == component_id)) < cfg.min_root_size:
            continue
        bbox = _padded_bbox(sl[0].start, sl[0].stop, sl[1].start, sl[1].stop, labeled.shape)
        min_r, max_r, min_c, max_c = bbox
        crop = (labeled[min_r:max_r, min_c:max_c] == component_id).astype(np.uint8)
        root = _extract_crop(crop, bbox, cfg, component_id)
        if root is not None:
            roots.append(root)
    return roots


TRAIT_COLUMNS = ["length_mm", "avg_diameter_mm", "diameter_median_mm", "diameter_std_mm",
                 "angle", "insertion_angle", "number_of_branches", "length_per_width",
                 "length", "avg_diameter", "diameter_median", "diameter_std"]
COLUMNS = ["image", "root", "type", "branch"] + TRAIT_COLUMNS


def _row(t: Traits, dpi):
    valid = t.diameter_values[~np.isnan(t.diameter_values)]
    median = float(np.median(valid)) if len(valid) else np.nan
    std = float(np.std(valid)) if len(valid) else np.nan
    return {
        "length_mm": to_mm(t.length, dpi), "avg_diameter_mm": to_mm(t.avg_diameter, dpi),
        "diameter_median_mm": to_mm(median, dpi), "diameter_std_mm": to_mm(std, dpi),
        "angle": t.angle, "insertion_angle": t.insertion_angle,
        "length": t.length, "avg_diameter": t.avg_diameter, "diameter_median": median, "diameter_std": std,
    }


def _length_per_width(t: Traits):
    """Total skeleton length in units of mean width.

    A root is a long thin cylinder, so it runs to tens or hundreds. A compact object
    is only a few. Reported on the whole-root row only: the total length sums every
    branch, so the ratio grows with branching, and the same number on a single branch
    means something else entirely.
    """
    return float(t.length / t.avg_diameter) if t.avg_diameter > 0 else np.nan


def roots_to_frame(roots, dpi, image=""):
    """Tidy table: one row per root for 'aggregated' and 'main_root', one per lateral 'branch'."""
    rows = []
    for i, root in enumerate(roots):
        base = {"image": image, "root": i}
        rows.append({**base, "type": "aggregated", "branch": None,
                     "number_of_branches": root.n_branches,
                     "length_per_width": _length_per_width(root.aggregated),
                     **_row(root.aggregated, dpi)})
        rows.append({**base, "type": "main_root", "branch": None,
                     "number_of_branches": root.n_branches, **_row(root.main_root, dpi)})
        for j, b in enumerate(root.branches):
            rows.append({**base, "type": "branch", "branch": j, "number_of_branches": None, **_row(b, dpi)})
    df = pd.DataFrame(rows, columns=COLUMNS)
    for col in TRAIT_COLUMNS:
        df[col] = df[col].astype("Int64" if col == "number_of_branches" else "float64")
    df["branch"] = df["branch"].astype("Int64")
    return df


def extract_traits(mask, cfg: Config = None, image=""):
    """Traits of every root in a binary mask as a tidy DataFrame."""
    cfg = cfg or Config()
    return roots_to_frame(extract_roots(mask, cfg), cfg.dpi, image)
