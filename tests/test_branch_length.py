"""Branch length is the edge sum of a branch's own pixels, not a single walk through them.

A merged branch is several skeleton segments with the dilated junction pixels removed
between them, so it is normally disconnected and often branches. Walking it as one path
stops at the first gap and measured about half the true length.
"""

import numpy as np
import pytest

import rhizotrace as rp
from reference_walk import ordered_path
from rhizotrace.core.extract import _pixels_length
from rhizotrace.core.skeleton import path_length

MASKS = ["sample1", "sample5", "sample9"]


def straight_root_with_lateral():
    """A 201 px straight bar (200 unit steps) with one diagonal lateral crossing it."""
    m = np.zeros((120, 220), np.uint8)
    m[58:63, 10:211] = 1
    for i in range(40):
        m[60 + i:65 + i, 110 + i:115 + i] = 1
    return m * 255


def test_merged_branch_recovers_a_known_length():
    roots = rp.extract_roots(straight_root_with_lateral(), rp.Config(dpi=254, min_root_size=5))
    parts = [roots[0].main_root] + list(roots[0].branches)
    axis = max(parts, key=lambda t: len(t.skeleton_rc))
    # 200 steps of true axis at 0.980 per orthogonal step, less the dilated junction
    # pixels that separation removed
    assert 190 * 0.980 <= axis.length <= 200 * 0.980 + 1e-9
    # the old single walk stopped at the junction gap
    assert path_length(ordered_path(axis.skeleton_rc)) < 0.6 * axis.length


@pytest.mark.parametrize("stem", MASKS)
def test_length_is_the_edge_sum_of_its_own_pixels(stem):
    from pathlib import Path
    mask = rp.load_mask(Path(__file__).parent / "data" / "masks" / f"{stem}.png")
    for root in rp.extract_roots(mask, rp.Config()):
        for t in [root.main_root] + list(root.branches):
            assert t.length == pytest.approx(_pixels_length(t.skeleton_rc), abs=1e-9)


@pytest.mark.parametrize("stem", MASKS)
@pytest.mark.parametrize("cfg", [rp.Config(spur_length_diameters=0.0), rp.Config()],
                         ids=["unpruned", "pruned"])
def test_parts_never_exceed_the_whole(stem, cfg):
    from pathlib import Path
    mask = rp.load_mask(Path(__file__).parent / "data" / "masks" / f"{stem}.png")
    for root in rp.extract_roots(mask, cfg):
        if root.main_root is root.aggregated:
            continue
        parts = root.main_root.length + sum(b.length for b in root.branches)
        assert parts <= root.aggregated.length + 1e-9


def test_angle_is_an_axis_in_the_documented_range():
    from pathlib import Path
    for stem in MASKS:
        mask = rp.load_mask(Path(__file__).parent / "data" / "masks" / f"{stem}.png")
        df = rp.extract_traits(mask, rp.Config(), image=stem)
        a = df.angle.dropna()
        assert ((a >= 0) & (a < 180)).all()


def test_angle_survives_flipping_the_image():
    """The axis is a property of the root, so a vertical flip maps it to -angle.

    Roots are matched by position, not by index: labelling renumbers components in
    raster order, so after a flip index i is a different root. Thinning itself is not
    flip symmetric on a tiny root (a 24 px skeleton comes back with 29 px), so only
    roots with a skeleton long enough to carry a stable axis are compared.
    """
    from pathlib import Path
    mask = rp.load_mask(Path(__file__).parent / "data" / "masks" / "sample1.png")
    height = mask.shape[0]
    before = rp.extract_roots(mask, rp.Config())
    after = rp.extract_roots(mask[::-1].copy(), rp.Config())
    assert len(before) == len(after)

    def centre(root):
        return (root.aggregated.skeleton_rc + np.array([root.bbox[0], root.bbox[2]])).mean(axis=0)

    centres = np.array([centre(r) for r in after])
    for root in before:
        if len(root.aggregated.skeleton_rc) < 50:
            continue
        r0, c0 = centre(root)
        target = np.array([height - 1 - r0, c0])
        match = after[int(np.argmin(((centres - target) ** 2).sum(axis=1)))]
        x, y = root.aggregated.angle, match.aggregated.angle
        if not (np.isfinite(x) and np.isfinite(y)):
            continue
        expected = (-x) % 180
        assert min(abs(y - expected), 180 - abs(y - expected)) < 3.0


def test_depth_direction_is_the_axis_pointing_deeper():
    from pathlib import Path
    tube = Path(__file__).parent / "data" / "tube_T121_2018-04-17"
    result = rp.analyze_tube(next(iter(rp.scan_tubes(tube))), rp.Config(), rp.Scanner(),
                             offset_cm=17.7, angle_deg=30)
    df = result.traits()
    assert "depth_direction" not in rp.extract_traits(
        rp.load_mask(Path(__file__).parent / "data" / "masks" / "sample1.png"), rp.Config()).columns
    d = df.depth_direction.dropna()
    assert ((d >= 0) & (d < 360)).all()
    assert np.allclose(d % 180, df.loc[d.index, "angle"], atol=1e-6)
    # deeper is to the right in a stitched tube, so the signed axis never points left
    assert (np.cos(np.radians(d)) >= -1e-9).all()


def test_length_per_width_is_whole_root_only():
    """The ratio means something different on a branch, so only the root row carries it."""
    from pathlib import Path
    for stem in MASKS:
        mask = rp.load_mask(Path(__file__).parent / "data" / "masks" / f"{stem}.png")
        df = rp.extract_traits(mask, rp.Config(), image=stem)
        agg = df[df.type == "aggregated"]
        assert agg.length_per_width.notna().all()
        assert df[df.type != "aggregated"].length_per_width.isna().all()
        expected = agg.length_mm / agg.avg_diameter_mm
        assert np.allclose(agg.length_per_width, expected, rtol=1e-9)


def test_length_per_width_separates_a_root_from_a_blob():
    """A bar many widths long scores high; a filled square scores low.

    The square is rotated because a perfect axis-aligned one thins to three pixels and
    is discarded. The compact objects in the PRMI masks are rotated squares, and this
    one lands at about 5, matching them.
    """
    from scipy import ndimage
    cfg = rp.Config(dpi=254)

    def lpw(m):
        df = rp.extract_traits(m * 255, cfg)
        return df[df.type == "aggregated"].length_per_width.iloc[0]

    bar = np.zeros((160, 240), np.uint8)
    bar[78:83, 20:221] = 1
    square = np.zeros((160, 160), np.uint8)
    square[50:110, 60:120] = 1
    square = (ndimage.rotate(square.astype(float), 30, reshape=False, order=0) > 0.5).astype(np.uint8)

    assert lpw(bar) > 30
    assert lpw(square) < 10
