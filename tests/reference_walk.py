"""The walk-based definitions the reference outputs were made with, kept so the fixtures
stay exactly reproducible from the same pixels. Not used by the package.

A path is ordered by a greedy walk from its raster-first endpoint. That walk stops at
the first junction gap of a merged branch and its direction sign follows raster order.
"""

import numpy as np

from rhizotrace.core.skeleton import order_pixels

N_INSERTION = 10


def ordered_path(rc):
    """order_pixels on a pixel set's own bounding box."""
    r0, c0 = rc.min(axis=0)
    local = np.zeros(rc.max(axis=0) - (r0, c0) + 1, dtype=np.uint8)
    local[rc[:, 0] - r0, rc[:, 1] - c0] = 1
    return [(r + r0, c + c0) for r, c in order_pixels(local)]


def walk_insertion_angle(main_path, branch_path):
    """0 to 180 degrees between the lateral's first N_INSERTION walk pixels and the main
    root's walk around the pixel nearest to them."""
    main = np.asarray(main_path)
    branch = np.asarray(branch_path)
    if len(branch) < 3 or len(main) < 3:
        return None
    d_start = np.min(np.sum((main - branch[0]) ** 2, axis=1))
    d_end = np.min(np.sum((main - branch[-1]) ** 2, axis=1))
    seg = branch[:N_INSERTION] if d_start <= d_end else branch[-N_INSERTION:][::-1]

    def mean_dir(pts):
        rads = np.arctan2(np.gradient(pts[:, 1].astype(float)), np.gradient(pts[:, 0].astype(float)))
        return np.arctan2(np.mean(np.sin(rads)), np.mean(np.cos(rads)))

    closest = int(np.argmin(np.sum((main - seg[0]) ** 2, axis=1)))
    half = N_INSERTION // 2
    main_seg = main[max(0, closest - half):min(len(main), closest + half)]
    if len(main_seg) < 2:
        return None
    diff = abs(np.degrees(mean_dir(seg)) - np.degrees(mean_dir(main_seg))) % 360
    return float(min(diff, 360 - diff))
