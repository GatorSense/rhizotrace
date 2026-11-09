"""min_root_length_mm thresholds measured length, not a skeleton pixel count.

The two disagree in both directions: a diagonal skeleton is longer than its pixel count,
and a merged branch with a junction gap is shorter. Length is the corner-count estimate,
so a straight orthogonal run of s steps measures 0.980 s.
"""

import numpy as np

import rhizotrace as rp
from rhizotrace.core.extract import _too_short
from rhizotrace.core.skeleton import ESTIMATORS

CFG = rp.Config(dpi=254, min_root_length_mm=5.0)   # 50 px
W_E = ESTIMATORS["corner"][0]                      # 0.980 per orthogonal step


def test_diagonal_under_50_pixels_is_kept():
    rc = np.array([(i, i) for i in range(40)])   # 40 px, length 39 * sqrt(2) = 55.2
    assert not _too_short(rc, CFG)


def test_straight_line_follows_its_length():
    steps = int(np.ceil(50 / W_E))                                          # 52 steps = 50.96 px
    assert _too_short(np.array([(0, c) for c in range(steps)]), CFG)        # 51 steps = 49.98 px
    assert not _too_short(np.array([(0, c) for c in range(steps + 1)]), CFG)


def test_gap_is_not_counted_as_length():
    # two 30 px bars: 60 pixels but only 58 px of length
    rc = np.array([(0, c) for c in range(30)] + [(5, c) for c in range(30)])
    assert _too_short(rc, rp.Config(dpi=254, min_root_length_mm=5.9))


def test_single_pixel_is_never_measured():
    assert _too_short(np.array([(3, 3)]), rp.Config(dpi=254, min_root_length_mm=0.0))
    assert not _too_short(np.array([(3, 3), (3, 4)]), rp.Config(dpi=254, min_root_length_mm=0.0))


def test_same_physical_threshold_at_every_dpi():
    for dpi in (120, 150, 300, 600):
        cfg = rp.Config(dpi=dpi)
        n = int(np.ceil(cfg.min_root_length_px() / W_E)) + 1   # shortest straight line at 0.5 mm
        assert not _too_short(np.array([(0, c) for c in range(n)]), cfg)
        assert _too_short(np.array([(0, c) for c in range(n - 1)]), cfg)
