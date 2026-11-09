"""2D root phenotyping from minirhizotron masks."""

from importlib.metadata import PackageNotFoundError, version as _version

from . import units
from .config import Config, Scanner, TubeInfo, load_tube_info
from .core.branches import merge_by_angle, merge_by_diameter, select_main_root
from .core.diameter import estimate_diameter
from .core.extract import Root, Traits, extract_root, extract_roots, extract_traits, roots_to_frame
from .core.junctions import detect_junctions, separate_branches
from .core.skeleton import (ESTIMATORS, free_ends, order_pixels, path_length, skeleton_edges, skeleton_length,
                            skeletonize, step_counts)
from .depth.geometry import LevelPosition, level_positions
from .depth.profile import TubeResult, analyze_tube, bin_profile, depth_profile, profile_from_result
from .depth.scan import Tube, TubeSet, scan_tubes
from .depth.stitch import Stitched, stitch, stitch_arrays
from .io import analyze_folder, load_image, load_mask

try:
    __version__ = _version("rhizotrace")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "Config", "Scanner", "TubeInfo", "load_tube_info", "units",
    "load_mask", "load_image", "extract_traits", "extract_roots", "extract_root", "roots_to_frame",
    "analyze_folder", "Root", "Traits",
    "skeletonize", "order_pixels", "path_length", "skeleton_length", "skeleton_edges", "step_counts",
    "free_ends", "ESTIMATORS",
    "detect_junctions", "separate_branches", "merge_by_angle", "merge_by_diameter",
    "select_main_root", "estimate_diameter",
    "scan_tubes", "Tube", "TubeSet", "stitch", "stitch_arrays", "Stitched",
    "analyze_tube", "depth_profile", "profile_from_result", "bin_profile", "TubeResult",
    "level_positions", "LevelPosition",
]
