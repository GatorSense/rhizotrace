"""Junction detection, branch separation and spur pruning on a skeleton."""

import numpy as np
from scipy import ndimage

from .skeleton import DEFAULT_ESTIMATOR, NEIGHBORS_8, _shifted, labeled_lengths

# 11 base patterns, each rotated 4 times: 44 hit-or-miss structuring elements.
JUNCTION_ELEMENTS = [
    np.array([[0, 1, 0], [1, 1, 1], [0, 0, 0]]),  # T
    np.array([[1, 0, 1], [0, 1, 0], [1, 0, 0]]),  # Y
    np.array([[1, 0, 1], [0, 1, 0], [0, 1, 0]]),  # Y variant
    np.array([[0, 1, 0], [1, 1, 0], [0, 0, 1]]),  # fork
    np.array([[0, 0, 1], [1, 1, 1], [0, 1, 0]]),  # T rotated
    np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]),  # cross
    np.array([[1, 0, 1], [0, 1, 0], [1, 0, 1]]),  # X
    np.array([[1, 0, 1], [1, 1, 0], [0, 1, 0]]),
    np.array([[1, 0, 1], [0, 1, 1], [0, 1, 0]]),
    np.array([[1, 0, 1], [1, 1, 0], [1, 0, 0]]),
    np.array([[1, 0, 1], [0, 1, 1], [0, 0, 1]]),
]
JUNCTION_PATTERNS = [np.rot90(se, k) for se in JUNCTION_ELEMENTS for k in range(4)]

EIGHT_CONNECTED = np.ones((3, 3), dtype=bool)


def _junction_codes():
    """Which 8-neighbor codes (bit k = neighbor k of NEIGHBORS_8 present) are junctions.

    A hit-or-miss match of a 3 x 3 pattern is an exact match of the pixel's neighborhood,
    pixels outside the image counting as background, so the 44 patterns are a 256-entry
    table. Same result as ndimage.binary_hit_or_miss over every pattern.
    """
    table = np.zeros(256, dtype=bool)
    for pattern in JUNCTION_PATTERNS:
        code = 0
        for k, (dr, dc) in enumerate(NEIGHBORS_8):
            if pattern[1 + dr, 1 + dc]:
                code |= 1 << k
        table[code] = True
    return table


JUNCTION_CODES = _junction_codes()


def detect_junctions(skeleton):
    """Boolean mask of skeleton pixels matching any of the 44 junction patterns."""
    skel = np.asarray(skeleton).astype(bool)
    code = np.zeros(skel.shape, dtype=np.uint8)
    for k, (dr, dc) in enumerate(NEIGHBORS_8):
        code |= _shifted(skel, dr, dc).astype(np.uint8) << k
    return skel & JUNCTION_CODES[code]


def separate_branches(skeleton, dilation_iterations=1):
    """Cut the skeleton at (dilated) junctions and label the remaining pieces.

    Returns (labeled, junction_mask): labeled has one integer label >= 2 per branch and
    0 elsewhere; junction_mask is the dilated junction region that was removed.
    """
    skel = np.asarray(skeleton).astype(bool)
    junctions = ndimage.binary_dilation(detect_junctions(skel), iterations=dilation_iterations)
    pieces = skel & ~junctions
    labeled, _ = ndimage.label(pieces, structure=EIGHT_CONNECTED)
    labeled[labeled > 0] += 1   # branch labels start at 2; label 1 is never used
    return labeled, junctions


NEIGHBOR_KERNEL = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], dtype=np.uint8)


def _free_ended(skel, labeled):
    """Labels of the pieces that run out to a free end of the skeleton.

    Counted on the whole skeleton, not on the cut pieces: every piece ends at a junction
    once it is cut. A piece that leaves a junction and returns to the same one, which is
    what a small hole in the mask produces, has no free end and is not a spur. Cutting
    both sides of such a loop would break the root in two.
    """
    counts = ndimage.convolve(skel.astype(np.uint8), NEIGHBOR_KERNEL, mode="constant")
    return {int(v) for v in np.unique(labeled[skel & (counts <= 1)]) if v >= 2}


def _simple_point_codes():
    """Which 8-neighbor codes leave their neighbors 8-connected once the center is gone.

    A cut spur can leave a pixel hanging off the remaining path with three neighbors,
    so counting neighbors is not enough to recognize a stump; the neighbors must form
    at most one component in the 3 x 3 ring.
    """
    table = np.zeros(256, dtype=bool)
    for code in range(256):
        window = np.zeros((3, 3), dtype=bool)
        for k, (dr, dc) in enumerate(NEIGHBORS_8):
            window[1 + dr, 1 + dc] = bool(code >> k & 1)
        _, n = ndimage.label(window, structure=EIGHT_CONNECTED)
        table[code] = n <= 1
    return table


SIMPLE_POINT_CODES = _simple_point_codes()


def _neighbour_code(skel, r, c):
    rows, cols = skel.shape
    code = 0
    for k, (dr, dc) in enumerate(NEIGHBORS_8):
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols and skel[nr, nc]:
            code |= 1 << k
    return code


def _is_removable(skel, r, c):
    """Whether dropping this pixel leaves its neighbors connected (a simple point)."""
    return bool(SIMPLE_POINT_CODES[_neighbour_code(skel, r, c)])


def _grown(sl, shape):
    """A find_objects slice widened by one pixel, clipped to the array."""
    return tuple(slice(max(s.start - 1, 0), min(s.stop + 1, n)) for s, n in zip(sl, shape))


def _incidence(labeled, j_labels, dist):
    """Per junction: the pieces touching it and the diameter there. Also piece -> junctions."""
    incident, diameters, touches = {}, {}, {}
    for j, sl in enumerate(ndimage.find_objects(j_labels), start=1):
        if sl is None:
            continue
        grown = _grown(sl, j_labels.shape)
        region = j_labels[grown] == j
        near = ndimage.binary_dilation(region, structure=EIGHT_CONNECTED)
        labels = [int(v) for v in np.unique(labeled[grown][near]) if v >= 2]
        incident[j] = labels
        diameters[j] = 2.0 * float(dist[grown][region].max())
        for label in labels:
            touches.setdefault(label, set()).add(j)
    return incident, diameters, touches


def _peel_stubs(skel, touched):
    """Remove the stump a cut spur leaves inside its junction, down to the path that stays.

    Only pixels of junctions that lost a branch are considered, and only ones whose
    removal keeps the rest connected, so the branches that remain still meet.
    """
    skel = skel.copy()
    candidates = np.argwhere(skel & touched)
    changed = True
    while changed:
        changed = False
        for r, c in candidates:
            if skel[r, c] and _is_removable(skel, r, c):
                skel[r, c] = False
                changed = True
    return skel


def _prune_pass(skel, dist, k, dilation_iterations, estimator):
    """One pass of the rule. Returns (skeleton, labeled, junction_mask, pruned_anything)."""
    labeled, junction_mask = separate_branches(skel, dilation_iterations)
    j_labels, n_junctions = ndimage.label(junction_mask)
    if n_junctions == 0:
        return skel, labeled, junction_mask, False
    lengths = labeled_lengths(labeled, estimator)
    incident, diameters, touches = _incidence(labeled, j_labels, dist)
    free_ended = _free_ended(skel, labeled)

    removed, touched_junctions = set(), []
    for j, labels in incident.items():
        if len(labels) < 2:
            continue
        limit = k * diameters[j]
        short = [p for p in labels
                 if p in free_ended and len(touches[p]) == 1 and lengths[p] < limit]
        rest = [p for p in labels if p not in short]
        keep = max(0, 2 - len(rest))
        short.sort(key=lambda p: lengths[p], reverse=True)
        if short[keep:]:
            removed.update(short[keep:])
            touched_junctions.append(j)
    if not removed:
        return skel, labeled, junction_mask, False
    pruned = skel & ~np.isin(labeled, sorted(removed))
    return _peel_stubs(pruned, np.isin(j_labels, touched_junctions)), labeled, junction_mask, True


def prune_spurs(skeleton, dist, k, dilation_iterations=1, estimator=DEFAULT_ESTIMATOR):
    """Remove terminal skeleton branches shorter than k local diameters, to convergence.

    Returns (skeleton, labeled, junction_mask); the separation of the final skeleton is
    returned so the caller does not recompute it.

    A terminal branch touches one junction and has a free end. Its threshold is k times
    the diameter at that junction (twice the largest distance to the background there).
    Every junction keeps at least two branches, so a blunt tip keeps its longest fork
    arm and no root is pruned away entirely. Removing a spur can expose another (a stub
    that carried a crossbar), so passes repeat until nothing is removed.

    Pruning the pixels rather than the segment graph is what lets the remaining pieces
    rejoin: with the spur gone the branch point is an ordinary path pixel, so the
    junction and its removed pixels return to the branch under every merge method.

    dist is the distance map of the root crop. Branch lengths use the same estimator as
    every other length (config length_estimator).
    """
    skel = np.asarray(skeleton).astype(bool)
    while True:
        skel, labeled, junction_mask, pruned = _prune_pass(skel, dist, k, dilation_iterations, estimator)
        if not pruned:
            return skel, labeled, junction_mask
