"""User-facing settings: trait extraction (Config), camera hardware (Scanner), per-tube info."""

from dataclasses import dataclass

import pandas as pd

from .core.skeleton import ESTIMATORS

MERGE_METHODS = ("angle", "diameter", "none")
ROOT_SELECTIONS = ("length", "diameter", "combined", "connectivity")
ANGLE_MODES = ("endpoint", "local", "hybrid")
DEFAULT_ANGLE_DEG = 30.0           # tube insertion angle from vertical


@dataclass
class Config:
    """Trait extraction settings. Most users only touch the first block."""

    dpi: int = 300                     # image resolution, px per inch
    min_root_size: int = 50            # ignore connected components smaller than this, px of area
    min_root_length_mm: float = 0.5    # ignore roots and branches whose measured length is under this
    merge_method: str = "angle"        # how skeleton segments recombine at junctions
    merge_angle_threshold: float = 30.0  # angle merge: join if continuation angle >= 180 - this
    root_selection: str = "length"     # which branch is the main root: length | diameter | combined | connectivity
    spur_length_diameters: float = 1.0  # prune terminal skeleton branches shorter than this many
                                        # local diameters; 0 = off

    # Advanced.
    mask_threshold: float = 0.5        # binarization threshold for grayscale masks
    angle_mode: str = "endpoint"       # segment direction: endpoint | local | hybrid
    local_k: int = 10                  # pixels used for local direction
    force_merge_degree_2: bool = True  # always join the two segments at a 2-way junction
    force_merge_min_angle: float = 90.0  # unless their angle is below this (0 = no floor)
    junction_dilation_iterations: int = 1
    junction_proximity_threshold: int = 2  # max Chebyshev distance linking a segment end to a junction
    diameter_ratio_threshold: float = 0.3  # diameter merge: join if |d1-d2| / max(d1,d2) <= this
    length_weight: float = 0.7         # combined selection weights
    diameter_weight: float = 0.3
    length_estimator: str = "corner"   # skeleton length from step counts: corner | kulpa |
                                       # chain_no_triangles | chain (see core.skeleton.ESTIMATORS)
    insertion_reach_px: int = 15       # insertion angle: pixels beyond the local radius, on each side
                                       # of the junction, that set the lateral's and main root's direction

    def __post_init__(self):
        if self.merge_method not in MERGE_METHODS:
            raise ValueError(f"merge_method must be one of {MERGE_METHODS}, got {self.merge_method!r}")
        if self.root_selection not in ROOT_SELECTIONS:
            raise ValueError(f"root_selection must be one of {ROOT_SELECTIONS}, got {self.root_selection!r}")
        if self.angle_mode not in ANGLE_MODES:
            raise ValueError(f"angle_mode must be one of {ANGLE_MODES}, got {self.angle_mode!r}")
        if self.dpi <= 0:
            raise ValueError("dpi must be positive")
        if self.min_root_length_mm < 0:
            raise ValueError("min_root_length_mm must not be negative")
        if self.spur_length_diameters < 0:
            raise ValueError("spur_length_diameters must not be negative")
        if self.length_estimator not in ESTIMATORS:
            raise ValueError(f"length_estimator must be one of {sorted(ESTIMATORS)}, got {self.length_estimator!r}")
        if self.insertion_reach_px <= 0:
            raise ValueError("insertion_reach_px must be positive")

    def min_root_length_px(self):
        """min_root_length_mm as a length in pixels at this dpi, unrounded."""
        return self.min_root_length_mm * self.dpi / 25.4


@dataclass
class Scanner:
    """Minirhizotron camera geometry. Defaults are the scanner the package was developed on
    (21.59 x 18.0 cm levels, 1.27 cm overlap); change them for another camera."""

    level_height_cm: float = 21.59     # extent of one level image along the tube
    level_width_cm: float = 18.0       # extent across the tube
    overlap_cm: float = 1.27           # consecutive levels share this much
    camera_start_cm: float = 11.5      # tube opening to where imaging begins
    l1_start_trim_px: int = 1500       # opening artifact discarded from the start of L1
    level_end_trim_px: int = 75        # sensor-edge artifact discarded from the end of every level


@dataclass
class TubeInfo:
    """One tube. The CSV column 'angle' fills angle_deg."""

    tube_id: str
    offset_cm: float                   # tube protrusion above the soil surface, along the tube
    angle_deg: float = DEFAULT_ANGLE_DEG


def load_tube_info(path) -> dict:
    """Read a per-tube CSV (columns: tube_id, offset_cm, optional angle) into {tube_id: TubeInfo}."""
    df = pd.read_csv(path)
    missing = {"tube_id", "offset_cm"} - set(df.columns)
    if missing:
        raise ValueError(f"tube info CSV is missing columns: {sorted(missing)}")
    tubes = {}
    for row in df.itertuples(index=False):
        angle = getattr(row, "angle", DEFAULT_ANGLE_DEG)
        tubes[str(row.tube_id)] = TubeInfo(str(row.tube_id), float(row.offset_cm),
                                           DEFAULT_ANGLE_DEG if pd.isna(angle) else float(angle))
    return tubes
