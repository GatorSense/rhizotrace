"""Spur pruning: what it removes, what it protects, and that it is on by default.

Every mask here is synthetic, so the true length and the true number of laterals are
known. A rotated bar has the staircase edges of a real mask and skeletonizes to a Y fork
at each square end, which is the artifact this feature targets. An axis-aligned bar does
not fork, so it isolates the lateral rule.
"""

import numpy as np
import pytest
from scipy import ndimage

import rhizotrace as rp
from rhizotrace.core.diameter import distance_map
from rhizotrace.core.junctions import _prune_pass, prune_spurs
from rhizotrace.core.skeleton import skeleton_length, skeletonize

DPI = 254          # 10 px per mm, so min_root_length_mm 0.5 is a 5 px floor
W = 21             # bar width in px
LENGTH = 201       # bar length in px
PAD = 6


def bar(length=LENGTH, width=W, extra_rows=0):
    """A horizontal bar with square-cut ends."""
    mask = np.zeros((width + 2 * PAD + extra_rows, length + 2 * PAD), dtype=np.uint8)
    mask[PAD:PAD + width, PAD:PAD + length] = 1
    return mask


def tilted_bar(angle=20):
    """The same bar rotated, so its edges are ragged like a real mask."""
    return (ndimage.rotate(bar(), angle, order=0, reshape=True) > 0).astype(np.uint8)


def with_lateral(lateral_length, lateral_width=5):
    """A bar with one lateral leaving the middle of its lower edge."""
    mask = bar(extra_rows=lateral_length)
    c = PAD + LENGTH // 2
    mask[PAD + W:PAD + W + lateral_length, c:c + lateral_width] = 1
    return mask


def cfg(**kw):
    return rp.Config(dpi=DPI, **kw)


def prune(mask, k=1.0, **kw):
    """The pruned skeleton alone; prune_spurs also returns the separation extract reuses."""
    return prune_spurs(skeletonize(mask), distance_map(mask), k, **kw)[0]


def only_root(mask, config):
    roots = rp.extract_roots(mask, config)
    assert len(roots) == 1
    return roots[0]


def test_default_config_prunes_at_one_local_diameter():
    assert rp.Config().spur_length_diameters == 1.0
    mask = tilted_bar()
    assert rp.extract_traits(mask, cfg()).equals(rp.extract_traits(mask, cfg(spur_length_diameters=1.0)))
    assert not rp.extract_traits(mask, cfg()).equals(rp.extract_traits(mask, cfg(spur_length_diameters=0.0)))


def test_blunt_ends_are_reported_as_branches_without_pruning():
    """The artifact this feature targets: a plain bar has no laterals but reports four."""
    assert only_root(tilted_bar(), cfg(spur_length_diameters=0.0)).n_branches == 4


def test_pruning_removes_the_end_forks():
    root = only_root(tilted_bar(), cfg(spur_length_diameters=1.0))
    assert root.n_branches == 0


def test_pruning_shortens_the_whole_root_towards_its_true_length():
    """Each unpruned end carries two arms of about 0.7 W where the root extends 0.5 W.
    Keeping one arm per end leaves the skeleton reaching a corner, so a little runs long."""
    plain = only_root(tilted_bar(), cfg(spur_length_diameters=0.0)).aggregated.length
    pruned = only_root(tilted_bar(), cfg(spur_length_diameters=1.0)).aggregated.length
    assert plain - pruned > W
    assert pruned < plain


def test_a_real_lateral_survives():
    root = only_root(with_lateral(3 * W), cfg(spur_length_diameters=1.0))
    assert root.n_branches == 1
    assert root.branches[0].length > 2 * W


def test_a_lateral_shorter_than_the_local_diameter_goes():
    assert only_root(with_lateral(W // 2), cfg(spur_length_diameters=0.0)).n_branches == 1
    assert only_root(with_lateral(W // 2), cfg(spur_length_diameters=1.0)).n_branches == 0


def test_threshold_scales_with_k():
    mask = with_lateral(3 * W // 2)
    assert only_root(mask, cfg(spur_length_diameters=1.0)).n_branches == 1
    assert only_root(mask, cfg(spur_length_diameters=2.0)).n_branches == 0


@pytest.mark.parametrize("merge_method", ["angle", "diameter", "none"])
def test_the_root_is_one_piece_again_after_a_spur_is_cut(merge_method):
    """Pruning pixels, not segments, dissolves the junction, so the two halves of the bar
    rejoin under every merge method rather than relying on the degree-2 force merge."""
    root = only_root(with_lateral(W // 2), cfg(spur_length_diameters=1.0, merge_method=merge_method))
    assert root.n_branches == 0
    # no junction survives, so the main root is the whole pruned skeleton, junction pixels included
    assert root.main_root.length == root.aggregated.length


def test_iteration_reaches_a_spur_that_itself_forks():
    """A stub carrying a crossbar: the two arms go first, then the stub they exposed.

    One pass of the rule cannot remove the stub, because with its arms attached it is
    not a terminal branch. The second pass finds it exposed.
    """
    mask = bar(extra_rows=12)
    mask[PAD + W:PAD + W + 6, 100:103] = 1
    mask[PAD + W + 6:PAD + W + 9, 96:107] = 1
    skel, dist = skeletonize(mask), distance_map(mask)
    one_pass, _, _, pruned_anything = _prune_pass(skel, dist, 1.0, 1, "corner")
    assert pruned_anything
    converged = prune(mask, 1.0)
    assert skeleton_length(converged) < skeleton_length(one_pass) < skeleton_length(skel)
    assert only_root(mask, cfg(spur_length_diameters=1.0)).n_branches == 0


def test_a_junction_always_keeps_two_branches():
    """A small cross is all short terminal branches; pruning must leave a path, not nothing."""
    mask = np.zeros((31, 31), dtype=np.uint8)
    mask[13:18, 3:28] = 1
    mask[3:28, 13:18] = 1
    pruned = prune(mask, 3.0)
    assert skeleton_length(pruned) > 0
    assert only_root(mask, cfg(spur_length_diameters=3.0)).aggregated.length > 0


def test_the_whole_root_row_is_measured_on_the_pruned_skeleton():
    mask = with_lateral(W // 2)
    plain = only_root(mask, cfg(spur_length_diameters=0.0))
    pruned = only_root(mask, cfg())
    assert pruned.aggregated.length < plain.aggregated.length
    assert len(pruned.aggregated.skeleton_rc) < len(plain.aggregated.skeleton_rc)
    assert pruned.main_root is pruned.aggregated      # nothing left to decompose


def ring_with_tails():
    """A root that runs into a small hole and out again, plus a spur. The two sides of the
    hole have no free end, so neither is a spur, and cutting both would break the root."""
    mask = np.zeros((60, 160), dtype=np.uint8)
    mask[25:36, 10:150] = 1
    mask[28:33, 70:100] = 0            # the hole
    mask[36:42, 40:44] = 1             # a short spur on the lower edge
    return mask


def test_a_hole_is_not_a_spur():
    mask = ring_with_tails()
    pruned = prune(mask, 1.0)
    before, n_before = ndimage.label(skeletonize(mask), structure=np.ones((3, 3)))
    after, n_after = ndimage.label(pruned, structure=np.ones((3, 3)))
    assert n_after == n_before == 1


@pytest.mark.parametrize("stem", ["sample1", "sample5", "sample9"])
def test_pruning_never_breaks_a_root_apart(stem):
    """Pruning removes free ends only, so a root must not fall into more components."""
    from pathlib import Path
    mask = rp.load_mask(Path(__file__).parent / "data" / "masks" / f"{stem}.png")
    for root in rp.extract_roots(mask, rp.Config(spur_length_diameters=0.0)):
        pruned, _, _ = prune_spurs(root.skeleton, distance_map(root.crop), 1.0)
        _, before = ndimage.label(root.skeleton, structure=np.ones((3, 3)))
        _, after = ndimage.label(pruned, structure=np.ones((3, 3)))
        assert after <= before
