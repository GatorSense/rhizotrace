"""Depth geometry, stitching, and binning against the frozen tube fixture."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PIL import Image

import rhizotrace as rp
from rhizotrace.depth.geometry import level_depth_cm, level_positions, stitched_depth_cm
from rhizotrace.depth.profile import analyze_tube, bin_profile, profile_from_result, skeleton_edges

DATA = Path(__file__).parent / "data"
MANIFEST = json.load(open(DATA / "golden" / "manifest.json"))
TUBE = MANIFEST["tube"]
GOLD = DATA / "golden" / "depth" / TUBE["name"]
DCFG = TUBE["depth_config"]
INFO = rp.TubeInfo("T121", DCFG["offset_cm"], DCFG["tube_angle_deg"])
SCANNER = rp.Scanner()
CFG = rp.Config(dpi=300, spur_length_diameters=0.0, root_selection="diameter")   # the reference settings: no pruning, thickest branch as main root
pytestmark = pytest.mark.usefixtures("reference_length_filter")


@pytest.fixture(scope="module")
def tubes():
    # tests/data has one folder per tube (tube_T121_...) next to unrelated folders.
    return rp.scan_tubes(DATA, tube_info={"T121": INFO})


@pytest.fixture(scope="module")
def tube(tubes):
    return tubes[f"tube_{TUBE['name']}"]


def test_scan_folder_per_tube(tubes, tube):
    assert len(tubes) == 1
    assert tube.tube_id == "T121"
    assert tube.levels == TUBE["levels"] and tube.missing_levels == []
    assert tube.info is INFO
    assert "MISSING" not in tubes.report()
    assert len(tubes.unparsed) == 11    # the sample masks carry no level token


def test_scan_single_tube_folder():
    tubes = rp.scan_tubes(DATA / f"tube_{TUBE['name']}", tube_info={"T121": INFO})
    tube = tubes[f"tube_{TUBE['name']}"]
    assert len(tubes) == 1 and tube.tube_id == "T121" and tube.levels == TUBE["levels"]
    assert tube.info is INFO and not tubes.unparsed


def test_level_positions_match_reference():
    golden = json.load(open(GOLD / "level_positions.json"))
    ours = level_positions(INFO, SCANNER, len(golden))
    fields = ("level", "tube_top_cm", "tube_bottom_cm", "soil_top_cm", "soil_bottom_cm")
    for p, g in zip(ours, golden):
        for k in fields:
            assert getattr(p, k) == pytest.approx(g[k])


def test_stitched_mask_matches_reference(tube):
    stitched = rp.stitch(tube, SCANNER, CFG.dpi)
    golden = np.asarray(Image.open(GOLD / "stitched.png").convert("L"))
    assert stitched.image.shape == golden.shape
    assert np.array_equal(stitched.image, golden)


def test_stitched_depth_equals_level_depth(tube):
    stitched = rp.stitch(tube, SCANNER, CFG.dpi)
    positions = {p.level: p for p in level_positions(INFO, SCANNER, max(stitched.levels))}
    for level in stitched.levels:
        a, b = stitched.slice_of(level)
        cols = np.linspace(a, b - 1, 7)
        raw = cols - a + stitched.offsets[stitched.levels.index(level)]
        assert np.allclose(stitched_depth_cm(cols, stitched, positions, CFG.dpi, INFO.angle_deg),
                           level_depth_cm(raw, positions[level], CFG.dpi, INFO.angle_deg))


@pytest.mark.parametrize("level", TUBE["levels"])
def test_per_level_binning_matches_reference(level, tube):
    mask = rp.load_mask(tube.masks[level])
    roots = rp.extract_roots(mask, CFG)
    positions = level_positions(INFO, SCANNER, len(TUBE["levels"]))
    depth_mm = lambda px: level_depth_cm(px, positions[level - 1], CFG.dpi, INFO.angle_deg) * 10.0
    ours = bin_profile(roots, depth_mm, mask.shape[1], CFG.dpi, DCFG["depth_bin_size_mm"])
    golden = pd.read_csv(GOLD / "depth_profiles_per_level.csv")
    golden = golden[golden["image_name"] == f"L{level}"].reset_index(drop=True)
    assert len(ours) == len(golden)
    assert np.allclose(ours["depth_start_mm"], golden["depth_bin_start_mm"], atol=1e-4)
    assert np.allclose(ours["mean_diameter_mm"], golden["avg_diameter_mm"], atol=6e-5, equal_nan=True)
    assert (ours["n_roots"] == golden["num_roots"]).all()
    assert (ours["n_skeleton_px"] == golden["total_pixels"]).all()


def test_skeleton_edges_total_length():
    skel = np.zeros((5, 5), bool)
    skel[2, 0:5] = True                    # 4 horizontal edges
    skel[0, 0], skel[1, 1] = True, True    # (0,0)-(1,1), and (1,1) touches (2,0), (2,1), (2,2)
    skel[3, 3], skel[4, 2] = True, True    # (3,3) touches (2,2), (2,3), (2,4), and (4,2)
    edges = skeleton_edges(skel, "chain")
    assert len(edges) == 12
    assert np.isclose(edges[:, 4].sum(), rp.skeleton_length(skel, "chain"))
    # the default estimator drops the triangle diagonals and adds corner terms
    assert np.isclose(skeleton_edges(skel)[:, 4].sum(), rp.skeleton_length(skel))


def test_tube_profile_conserves_length(tube):
    result = analyze_tube(tube, CFG, SCANNER)
    profile = profile_from_result(result, bin_mm=10.0)
    total = sum(rp.units.to_mm(r.aggregated.length, CFG.dpi) for r in result.roots)
    assert profile["root_length_mm"].sum() == pytest.approx(total)
    assert profile["n_skeleton_px"].sum() == sum(len(r.aggregated.skeleton_rc) for r in result.roots)
    assert profile["depth_start_mm"].iloc[0] >= 0      # opening region trimmed, starts below the surface
    assert profile["depth_end_mm"].iloc[-1] > 1000     # 8 levels reach past 1 m
    assert (profile["tube"] == tube.name).all()
