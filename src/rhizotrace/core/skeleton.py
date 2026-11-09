"""Skeletonization, path ordering, length and direction of skeleton paths."""

import numpy as np
from skimage.morphology import skeletonize as _skeletonize

NEIGHBORS_8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
SQRT2 = float(np.sqrt(2))

# Length of a skeleton from its step counts: w_e per orthogonal step, w_o per diagonal
# step, w_c per corner, and whether a diagonal step that shortcuts an orthogonal pair is
# dropped (see _adjacency). "corner" is Vossepoel and Smeulders (1982), Table 3,
# 8-connectivity without constraints, the form of Dorst and Smeulders (1987), Eq. 24.
# "kulpa" is Kulpa (1977). "chain" is the uncorrected 8-connected chain code, every
# edge counted.
ESTIMATORS = {
    "corner": (0.980, 1.406, -0.091, True),
    "kulpa": (0.948, 0.948 * SQRT2, 0.0, True),
    "chain_no_triangles": (1.0, SQRT2, 0.0, True),
    "chain": (1.0, SQRT2, 0.0, False),
}
DEFAULT_ESTIMATOR = "corner"


def neighbors_8(r, c):
    return [(r + dr, c + dc) for dr, dc in NEIGHBORS_8]


def skeletonize(mask):
    """Boolean skeleton of a binary mask (nonzero = object)."""
    return _skeletonize(np.asarray(mask) > 0)


def count_neighbors(skeleton, r, c):
    rows, cols = skeleton.shape
    return sum(1 for nr, nc in neighbors_8(r, c)
               if 0 <= nr < rows and 0 <= nc < cols and skeleton[nr, nc])


def order_pixels(skeleton):
    """Skeleton pixels as an ordered (row, col) path.

    Starts at the first endpoint in raster order (first pixel if the skeleton is a
    loop) and walks 8-connected neighbors, so lengths and directions follow the path
    rather than raster order.
    """
    skel = np.asarray(skeleton).astype(bool)
    rows, cols = skel.shape
    pixels = [(int(r), int(c)) for r, c in zip(*np.where(skel))]
    if not pixels:
        return []
    start = next(((r, c) for r, c in pixels if count_neighbors(skel, r, c) == 1), pixels[0])
    path = [start]
    visited = {start}
    while True:
        r, c = path[-1]
        for nr, nc in neighbors_8(r, c):
            if 0 <= nr < rows and 0 <= nc < cols and skel[nr, nc] and (nr, nc) not in visited:
                path.append((nr, nc))
                visited.add((nr, nc))
                break
        else:
            return path


def _shifted(skel, dr, dc):
    """True where the pixel at (r + dr, c + dc) is on the skeleton."""
    out = np.zeros_like(skel)
    h, w = skel.shape
    out[max(0, -dr):h - max(0, dr), max(0, -dc):w - max(0, dc)] = \
        skel[max(0, dr):h - max(0, -dr), max(0, dc):w - max(0, -dc)]
    return out


def _adjacency(skel, drop_triangles):
    """Per direction, the skeleton pixels that have a neighbor that way.

    With drop_triangles, a diagonal step whose two pixels share an orthogonal skeleton
    neighbor is not a step: the path runs through that neighbor, and counting the
    diagonal as well would measure a three-pixel triangle as a loop.
    """
    nb = {}
    for dr, dc in NEIGHBORS_8:
        nb[(dr, dc)] = skel & _shifted(skel, dr, dc)
        if drop_triangles and dr and dc:
            nb[(dr, dc)] &= ~(_shifted(skel, dr, 0) | _shifted(skel, 0, dc))
    return nb


def step_counts(skeleton, drop_triangles=True):
    """(n_e, n_o, n_c, n_triangles): orthogonal steps, diagonal steps, corners, and the
    diagonal steps the triangle rule dropped.

    A corner is a pixel with exactly two neighbors whose two steps are not in line.
    End pixels have one neighbor and junction pixels three or more, so neither is a
    corner: the estimator was fitted on single chains, and a junction has no single
    direction to turn from.
    """
    skel = np.asarray(skeleton).astype(bool)
    nb = _adjacency(skel, drop_triangles)
    n_e = int(nb[(0, 1)].sum() + nb[(1, 0)].sum())
    n_o = int(nb[(1, 1)].sum() + nb[(1, -1)].sum())
    degree = sum(nb[d].astype(np.uint8) for d in NEIGHBORS_8)
    in_line = np.zeros_like(skel)
    for k in range(4):
        in_line |= nb[NEIGHBORS_8[k]] & nb[NEIGHBORS_8[7 - k]]
    n_c = int(((degree == 2) & ~in_line).sum())
    n_tri = 0
    if drop_triangles:
        for dr, dc in ((1, 1), (1, -1)):
            n_tri += int((skel & _shifted(skel, dr, dc) & ~nb[(dr, dc)]).sum())
    return n_e, n_o, n_c, n_tri


def _weights(estimator):
    try:
        return ESTIMATORS[estimator]
    except KeyError:
        raise ValueError(f"unknown length estimator {estimator!r}; choose from {sorted(ESTIMATORS)}") from None


def labeled_lengths(labeled, estimator=DEFAULT_ESTIMATOR):
    """skeleton_length of every labeled piece at once, as {label: length}.

    Pieces are 8-connected components, so no step, corner or triangle ever spans two
    labels and the per-piece counts are the counts of the whole array split by label.
    """
    labeled = np.asarray(labeled)
    w_e, w_o, w_c, drop = _weights(estimator)
    skel = labeled > 0
    nb = _adjacency(skel, drop)
    n = int(labeled.max()) + 1
    n_e = np.bincount(labeled[nb[(0, 1)]], minlength=n) + np.bincount(labeled[nb[(1, 0)]], minlength=n)
    n_o = np.bincount(labeled[nb[(1, 1)]], minlength=n) + np.bincount(labeled[nb[(1, -1)]], minlength=n)
    degree = sum(nb[d].astype(np.uint8) for d in NEIGHBORS_8)
    in_line = np.zeros_like(skel)
    for k in range(4):
        in_line |= nb[NEIGHBORS_8[k]] & nb[NEIGHBORS_8[7 - k]]
    n_c = np.bincount(labeled[(degree == 2) & ~in_line], minlength=n)
    lengths = w_e * n_e + w_o * n_o + w_c * n_c
    return {int(label): float(lengths[label]) for label in np.unique(labeled) if label > 0}


def skeleton_length(skeleton, estimator=DEFAULT_ESTIMATOR):
    """Length of a whole skeleton, branches included, from its step and corner counts.

    Each pixel pair counts once. The estimator is linear in the counts, so the lengths
    of the pieces of a skeleton sum to the length of the skeleton, apart from the pixels
    that are in no piece.
    """
    w_e, w_o, w_c, drop = _weights(estimator)
    n_e, n_o, n_c, _ = step_counts(skeleton, drop)
    return float(w_e * n_e + w_o * n_o + w_c * n_c)


def skeleton_edges(skeleton, estimator=DEFAULT_ESTIMATOR):
    """Every term of skeleton_length as (r1, c1, r2, c2, length), for binning length by
    position. Steps are pixel pairs; a corner is a term on its own pixel (r1 = r2,
    c1 = c2) with the corner weight."""
    w_e, w_o, w_c, drop = _weights(estimator)
    skel = np.asarray(skeleton).astype(bool)
    nb = _adjacency(skel, drop)
    out = []
    for (dr, dc), w in (((0, 1), w_e), ((1, 0), w_e), ((1, 1), w_o), ((1, -1), w_o)):
        r, c = np.nonzero(nb[(dr, dc)])
        out.append(np.column_stack([r, c, r + dr, c + dc, np.full(len(r), w)]))
    if w_c:
        degree = sum(nb[d].astype(np.uint8) for d in NEIGHBORS_8)
        in_line = np.zeros_like(skel)
        for k in range(4):
            in_line |= nb[NEIGHBORS_8[k]] & nb[NEIGHBORS_8[7 - k]]
        r, c = np.nonzero((degree == 2) & ~in_line)
        out.append(np.column_stack([r, c, r, c, np.full(len(r), w_c)]))
    return np.concatenate(out) if out else np.zeros((0, 5))


def free_ends(skeleton):
    """Boolean mask of skeleton pixels with at most one 8-neighbor: the free ends."""
    skel = np.asarray(skeleton).astype(bool)
    degree = sum(_shifted(skel, dr, dc).astype(np.uint8) for dr, dc in NEIGHBORS_8)
    return skel & (degree <= 1)


def path_length(pixels, estimator=DEFAULT_ESTIMATOR):
    """Length of an ordered path with the same estimator as skeleton_length.

    Consecutive pixels one step apart are orthogonal or diagonal steps and a change of
    direction between two steps is a corner. A longer jump counts its Euclidean length.
    """
    if len(pixels) < 2:
        return float(len(pixels))
    w_e, w_o, w_c, _ = _weights(estimator)
    steps = np.diff(np.asarray(pixels, dtype=np.int64), axis=0)
    size = np.abs(steps).max(axis=1)
    orth = (size == 1) & (np.abs(steps).sum(axis=1) == 1)
    diag = (size == 1) & ~orth
    jumps = steps[size > 1]
    corners = int(np.any(steps[1:] != steps[:-1], axis=1).sum())
    return float(w_e * orth.sum() + w_o * diag.sum() + w_c * corners
                 + np.sqrt((jumps ** 2).sum(axis=1)).sum())


def path_angle(pixels):
    """Mean direction of an ordered path in degrees: 0 = right, counterclockwise, image up = +y."""
    if len(pixels) < 3:
        return 0.0
    pts = np.asarray(pixels, dtype=float)
    d_row = np.gradient(pts[:, 0])
    d_col = np.gradient(pts[:, 1])
    rads = np.arctan2(-d_row, d_col)
    deg = np.degrees(np.arctan2(np.mean(np.sin(rads)), np.mean(np.cos(rads)))) % 360.0
    # a tiny negative angle wraps to exactly 360.0 in float64; keep the range half open
    return float(deg) if deg < 360.0 else 0.0
