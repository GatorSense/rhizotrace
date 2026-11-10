"""Insertion angle: pixel sets at the junction, 0 to 90, only for branches that meet the
main root.

The reference outputs ordered each path by a greedy walk from its raster-first endpoint,
so the main root's direction sign was arbitrary and the walk stopped at the first junction
gap (tests/reference_walk.py).
"""

import numpy as np
import pytest
from skimage.draw import line
from skimage.morphology import dilation, disk

import rhizotrace as rp
from reference_walk import ordered_path, walk_insertion_angle

MAIN = (30, 10, 30, 210)


def drawn(segments, shape=(140, 240)):
    m = np.zeros(shape, bool)
    for r0, c0, r1, c1 in segments:
        rr, cc = line(r0, c0, r1, c1)
        m[rr, cc] = True
    return (dilation(m, disk(2)) * 255).astype(np.uint8)


def only_root(segments, cfg=rp.Config()):
    roots = rp.extract_roots(drawn(segments), cfg)
    assert len(roots) == 1
    return roots[0]


def angles(segments, cfg=rp.Config()):
    return [b.insertion_angle for b in only_root(segments, cfg).branches]


def test_mirror_images_read_the_same():
    assert angles([MAIN, (30, 60, 90, 120)]) == pytest.approx([45.0], abs=1.0)
    assert angles([MAIN, (30, 160, 90, 100)]) == pytest.approx([45.0], abs=1.0)


def test_reference_walk_read_mirror_images_differently():
    def walk(segments):
        root = only_root(segments)
        return walk_insertion_angle(ordered_path(root.main_root.skeleton_rc), ordered_path(root.branches[0].skeleton_rc))
    assert abs(walk([MAIN, (30, 60, 90, 120)]) - walk([MAIN, (30, 160, 90, 100)])) > 60


@pytest.mark.parametrize("lateral, truth", [((30, 60, 70, 130), 29.7), ((30, 60, 100, 100), 60.3),
                                            ((30, 110, 100, 110), 90.0)])
def test_known_angles(lateral, truth):
    assert angles([MAIN, lateral]) == pytest.approx([truth], abs=1.0)


def test_lateral_beyond_the_first_junction():
    # the reference walk of the main root stopped at the first junction; the pixel sets do not
    assert angles([MAIN, (30, 60, 100, 60), (30, 160, 90, 100)]) == pytest.approx([90.0, 45.0], abs=1.0)


def test_branch_off_a_lateral_has_no_angle_on_the_main_root():
    found = angles([MAIN, (30, 80, 100, 150), (65, 115, 65, 190)])
    assert sorted(a is None for a in found) == [False, True]
    assert next(a for a in found if a is not None) == pytest.approx(45.0, abs=1.0)


def test_crossing_root_is_measured_at_the_crossing():
    assert angles([MAIN, (5, 95, 110, 140)]) == pytest.approx([67.6], abs=1.5)


def test_short_lateral():
    assert angles([MAIN, (30, 110, 38, 118)]) == pytest.approx([45.0], abs=2.0)


@pytest.mark.parametrize("stem", ["sample1", "sample5", "sample9"])
def test_range_on_sample_masks(stem, data_dir):
    mask = rp.load_mask(data_dir / "masks" / f"{stem}.png")
    for root in rp.extract_roots(mask, rp.Config()):
        for b in root.branches:
            assert b.insertion_angle is None or 0.0 <= b.insertion_angle <= 90.0


def test_config_rejects_zero_reach():
    with pytest.raises(ValueError):
        rp.Config(insertion_reach_px=0)
