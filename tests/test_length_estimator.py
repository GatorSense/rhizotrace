"""Skeleton length from step counts: the corner-count estimator and its alternatives.

The 8-connected chain code reads a straight line at angle t as cos t + 0.414 sin t of its
length, 5.4 percent long on average and 8.2 percent at 22.5 degrees. The corner-count
estimator (Vossepoel and Smeulders 1982; Dorst and Smeulders 1987) weights orthogonal
steps, diagonal steps and corners so that the average error vanishes. It is linear in
the counts, so pieces still add up to the whole.
"""

import numpy as np
import pytest
from pathlib import Path

import rhizotrace as rp
from rhizotrace.core.extract import _pixels_length
from rhizotrace.core.skeleton import (ESTIMATORS, SQRT2, path_length, skeleton_edges, skeleton_length,
                                   step_counts)

MASKS = ["sample1", "sample5", "sample9"]
NEW = ("corner", "kulpa", "chain_no_triangles")


def skel(*pixels, shape=(8, 8)):
    s = np.zeros(shape, bool)
    for r, c in pixels:
        s[r, c] = True
    return s


def test_an_l_triangle_is_two_steps_and_one_corner():
    """Two pixels joined orthogonally through a third and directly by a diagonal.

    The old edge sum counted all three edges, a loop. The diagonal is the long way
    round a corner and is not a step.
    """
    tri = skel((0, 0), (0, 1), (1, 1))
    for est in NEW:
        n_e, n_o, n_c, n_tri = step_counts(tri, ESTIMATORS[est][3])
        assert (n_e, n_o, n_c, n_tri) == (2, 0, 1, 1)
    assert skeleton_length(tri, "corner") == pytest.approx(2 * 0.980 - 0.091)
    assert skeleton_length(tri, "chain_no_triangles") == pytest.approx(2.0)
    # the uncorrected chain keeps the plain edge sum, loop included
    assert skeleton_length(tri, "chain") == pytest.approx(2 + SQRT2)


def test_straight_runs_have_no_corners():
    line = skel(*[(3, c) for c in range(8)])
    diag = skel(*[(i, i) for i in range(8)])
    assert step_counts(line)[:3] == (7, 0, 0)
    assert step_counts(diag)[:3] == (0, 7, 0)
    assert skeleton_length(line) == pytest.approx(7 * 0.980)
    assert skeleton_length(diag) == pytest.approx(7 * 1.406)
    assert skeleton_length(line, "chain") == 7.0
    assert skeleton_length(diag, "chain") == pytest.approx(7 * SQRT2)


def test_a_bend_is_one_corner_and_ends_and_junctions_are_none():
    bend = skel((0, 0), (0, 1), (0, 2), (1, 2), (2, 2))
    assert step_counts(bend)[:3] == (4, 0, 1)
    # a T: the junction pixel has three neighbours, the stem's first pixel touches the
    # bar's pixels diagonally only through the junction, so it is in line, not a corner
    tee = skel(*[(0, c) for c in range(5)], (1, 2), (2, 2))
    assert step_counts(tee)[:3] == (6, 0, 0)


def test_separate_pieces_add_up():
    a = skel((1, 0), (1, 1), (1, 2), (2, 3))
    b = skel((5, 0), (6, 1), (6, 2), (6, 3), (7, 4))
    for est in ESTIMATORS:
        assert skeleton_length(a | b, est) == pytest.approx(skeleton_length(a, est) + skeleton_length(b, est))


def test_path_length_agrees_with_the_pixel_set_on_a_chain():
    path = [(0, 0), (0, 1), (1, 2), (2, 2), (3, 3), (4, 4), (4, 5)]
    for est in ESTIMATORS:
        assert path_length(path, est) == pytest.approx(skeleton_length(skel(*path), est))


def test_edge_terms_sum_to_the_length():
    s = skel((2, 0), (2, 1), (2, 2), (2, 3), (2, 4), (0, 0), (1, 1), (3, 3), (4, 2))
    for est in ESTIMATORS:
        assert skeleton_edges(s, est)[:, 4].sum() == pytest.approx(skeleton_length(s, est))
    assert len(skeleton_edges(s, "chain")) == 12      # every adjacent pair once, triangles included


@pytest.mark.parametrize("stem", MASKS)
def test_chain_reproduces_the_old_edge_sum(stem):
    s = rp.skeletonize(rp.load_mask(Path(__file__).parent / "data" / "masks" / f"{stem}.png"))
    old = (np.sum(s[:, :-1] & s[:, 1:]) + np.sum(s[:-1, :] & s[1:, :])
           + (np.sum(s[:-1, :-1] & s[1:, 1:]) + np.sum(s[:-1, 1:] & s[1:, :-1])) * SQRT2)
    assert skeleton_length(s, "chain") == pytest.approx(old)


def test_unknown_estimator_is_rejected():
    with pytest.raises(ValueError):
        rp.Config(length_estimator="euclid")
    with pytest.raises(ValueError):
        skeleton_length(skel((0, 0), (0, 1)), "euclid")


def _by_bbox(roots):
    return {r.bbox: r for r in roots}


@pytest.mark.parametrize("stem", MASKS)
@pytest.mark.parametrize("pruning", [0.0, 1.0], ids=["unpruned", "pruned"])
def test_root_and_branch_counts_do_not_depend_on_the_estimator(stem, pruning):
    """Length feeds two decisions, the minimum-length filter and the spur test, so this
    is checked rather than assumed. Roots are matched by bounding box, not by index."""
    mask = rp.load_mask(Path(__file__).parent / "data" / "masks" / f"{stem}.png")
    runs = {est: _by_bbox(rp.extract_roots(mask, rp.Config(length_estimator=est, spur_length_diameters=pruning)))
            for est in ("chain", "corner", "kulpa")}
    assert runs["chain"].keys() == runs["corner"].keys() == runs["kulpa"].keys()
    for bbox, ref in runs["chain"].items():
        for est in ("corner", "kulpa"):
            other = runs[est][bbox]
            assert other.n_branches == ref.n_branches
            assert np.array_equal(other.aggregated.skeleton_rc, ref.aggregated.skeleton_rc)
            assert other.aggregated.length == pytest.approx(_pixels_length(ref.aggregated.skeleton_rc, est))
