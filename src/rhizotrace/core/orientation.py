"""Root orientation.

axis_orientation is the 'angle' column of the trait table. depth_direction is the same axis
signed against the soil surface, reported only where tube geometry makes "deeper" a
real direction rather than a convention.
"""

import numpy as np


def principal_axis(rc):
    """Unit vector (d_row, d_col) along the long axis of a skeleton pixel set."""
    rc = np.asarray(rc, dtype=float).reshape(-1, 2)
    if len(rc) < 2:
        return None
    w, v = np.linalg.eigh(np.cov((rc - rc.mean(axis=0)).T))
    return v[:, int(np.argmax(w))]


def axis_orientation(rc):
    """Long axis of a skeleton pixel set, degrees in [0, 180). 0 = right, counterclockwise.

    An axis, not an arrow. A root has no intrinsic start, so theta and theta + 180
    describe the same root and only the axis is well defined.
    """
    v = principal_axis(rc)
    if v is None:
        return float("nan")
    return float(np.degrees(np.arctan2(-v[0], v[1])) % 180)


def depth_direction(rc, depth=(0.0, 1.0)):
    """Long axis signed to point away from the soil surface, degrees in [0, 360).

    depth is the image-space unit vector of increasing soil depth as (d_row, d_col).
    The default runs along the horizontal axis, which is how a stitched tube is laid
    out. A root exactly perpendicular to the depth axis has no deeper end, so the tie
    is broken on the remaining component to keep the value deterministic.
    """
    v = principal_axis(rc)
    if v is None:
        return float("nan")
    d = np.asarray(depth, dtype=float)
    along = float(np.dot(v, d))
    if along < 0 or (along == 0 and float(np.dot(v, [-d[1], d[0]])) < 0):
        v = -v
    return float(np.degrees(np.arctan2(-v[0], v[1])) % 360)
