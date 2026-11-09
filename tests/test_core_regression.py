"""Core trait extraction must reproduce the frozen reference fixtures."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import rhizotrace as rp
from rhizotrace.core.extract import _ordered_path, _pixels_length
from rhizotrace.core.orientation import axis_orientation
from rhizotrace.core.skeleton import path_angle, path_length

DATA = Path(__file__).parent / "data"
GOLDEN = DATA / "golden"
MANIFEST = json.load(open(GOLDEN / "manifest.json"))
SAMPLES = [n.rsplit(".", 1)[0] for n in MANIFEST["masks"]]
TUBE = MANIFEST["tube"]

CFG = rp.Config(dpi=300, spur_length_diameters=0.0, root_selection="diameter")   # the reference settings: no pruning, thickest branch as main root
pytestmark = pytest.mark.usefixtures("reference_length_filter")
ROUNDED_2 = 0.006      # the fixtures round these to 2 decimals
ROUNDED_4 = 6e-5       # the fixtures round mm values to 4 decimals


def _check_traits(t: rp.Traits, golden, dpi, arrays=None, prefix=None, length_deviates=False):
    """Compare a Traits object with a formatted golden dict (and raw arrays when available).

    Three intentional departures from the reference outputs are asserted in both
    halves: the new value matches its new definition, and the reference value is still
    exactly reproducible from the same pixels. That keeps the deviation confined to
    the definition, so any other drift still fails.

    length estimator: every length is the corner-count estimate of its pixels
    (Config.length_estimator, default "corner"); the uncorrected chain code of the same
    pixels, which is what the reference outputs hold, still equals the golden value.
    length_deviates: a merged branch's length is the edge sum of its own pixels, not
    the length of a single greedy walk that stops at the first junction gap.
    angle: the long axis of the pixel set in [0, 180), not the mean direction of that
    same greedy walk.
    """
    assert t.angle == pytest.approx(axis_orientation(t.skeleton_rc), abs=1e-9, nan_ok=True)
    assert path_angle(_ordered_path(t.skeleton_rc)) == pytest.approx(golden["angle"], abs=ROUNDED_2)
    assert t.length == pytest.approx(_pixels_length(t.skeleton_rc, CFG.length_estimator), abs=1e-9)
    chain = _pixels_length(t.skeleton_rc, "chain")
    if length_deviates:
        assert path_length(_ordered_path(t.skeleton_rc), "chain") == pytest.approx(golden["length"], abs=ROUNDED_2)
        assert chain >= golden["length"] - ROUNDED_2
    else:
        assert chain == pytest.approx(golden["length"], abs=ROUNDED_2)
        assert rp.units.to_mm(chain, dpi) == pytest.approx(golden["length_mm"], abs=ROUNDED_4)
    assert t.avg_diameter == pytest.approx(golden["avg_diameter"], abs=ROUNDED_2)
    valid = t.diameter_values[~np.isnan(t.diameter_values)]
    assert float(np.median(valid)) == pytest.approx(golden["diameter_median"], abs=ROUNDED_2)
    assert float(np.std(valid)) == pytest.approx(golden["diameter_std"], abs=ROUNDED_2)
    if "id" in golden:
        assert t.id == golden["id"]
        assert t.merged_from == golden["merged_from"]
    if "insertion_angle" in golden:
        assert t.insertion_angle == pytest.approx(golden["insertion_angle"], abs=ROUNDED_2)
    else:
        assert t.insertion_angle is None
    if arrays is not None:
        assert np.array_equal(t.skeleton_rc, arrays[f"{prefix}/skeleton_rc"])
        assert np.allclose(t.diameter_values, arrays[f"{prefix}/diameter_values"], equal_nan=True)


def _check_root(root: rp.Root, key, golden, meta=None, arrays=None):
    g_agg = golden["aggregated"]
    assert root.bbox == (g_agg["bbox"]["min_r"], g_agg["bbox"]["max_r"], g_agg["bbox"]["min_c"], g_agg["bbox"]["max_c"])
    if arrays is not None:
        assert np.array_equal(root.crop, arrays[f"{key}/cropped"])
        assert np.array_equal(root.skeleton.astype(np.uint8), arrays[f"{key}/skeleton"])
        assert np.array_equal(root.junction_mask.astype(np.uint8), arrays[f"{key}/junction_mask"])
        assert np.array_equal(root.labeled_skeleton, arrays[f"{key}/labeled_skeleton"])
        for j, branch in enumerate(root.merged):
            assert np.array_equal(np.asarray(branch.pixels), arrays[f"{key}/merged{j}/pixels"])
    if meta is not None:
        assert root.component_id == meta["component_id"]
        assert [(b.id, b.merged_from) for b in root.merged] == [(m["id"], m["merged_from"]) for m in meta.get("merged", [])]

    _check_traits(root.aggregated, g_agg, CFG.dpi, arrays, f"{key}/agg")
    assert root.n_branches == golden["main_root"]["number_of_branches"]
    # When no merged branch clears min_root_size the main root falls back to the whole
    # skeleton, which already used the edge sum, so only a real merged branch deviates.
    _check_traits(root.main_root, golden["main_root"], CFG.dpi,
                  arrays if "id" in golden["main_root"] else None, f"{key}/main",
                  length_deviates=root.main_root is not root.aggregated)
    assert len(root.branches) == len(golden["branches"])
    for j, (b, gb) in enumerate(zip(root.branches, golden["branches"])):
        _check_traits(b, gb, CFG.dpi, arrays, f"{key}/branch{j}", length_deviates=True)


def _check_frame(df, csv, image, roots):
    """The frame's lengths are the estimator's (Traits.length); the golden CSV holds the
    chain-code lengths, checked against the chain length of the same pixels."""
    ref = csv[csv["image_name"] == image].reset_index(drop=True)
    assert len(df) == len(ref)
    traits = [t for r in roots for t in [r.aggregated, r.main_root] + list(r.branches)]
    for i in range(len(ref)):
        row, g, t = df.iloc[i], ref.iloc[i], traits[i]
        assert row["root"] == int(g["root_id"].split("_")[1]) and row["type"] == g["type"]
        assert row["length_mm"] == pytest.approx(rp.units.to_mm(t.length, CFG.dpi), abs=1e-9)
        chain_mm = rp.units.to_mm(_pixels_length(t.skeleton_rc, "chain"), CFG.dpi)
        if g["type"] == "aggregated":
            assert chain_mm == pytest.approx(g["length_mm"], abs=ROUNDED_4)
        else:
            # intentional deviation, checked exactly in _check_traits
            assert chain_mm >= g["length_mm"] - ROUNDED_4
        for col in ("avg_diameter_mm", "diameter_median_mm", "diameter_std_mm"):
            assert row[col] == pytest.approx(g[col], abs=ROUNDED_4)
        for col in ("avg_diameter", "diameter_median", "diameter_std"):
            assert row[col] == pytest.approx(g[col], abs=ROUNDED_2)
        assert pd.isna(row["angle"]) or 0.0 <= row["angle"] < 180.0
        if g["type"] == "main_root":
            assert row["number_of_branches"] == g["number_of_branches"]
        if g["type"] == "branch":
            assert row["branch"] == g["branch_id"]
            if pd.notna(g["insertion_angle"]):
                assert row["insertion_angle"] == pytest.approx(g["insertion_angle"], abs=ROUNDED_2)


@pytest.mark.parametrize("stem", SAMPLES)
def test_sample_masks_match_reference(stem):
    mask = rp.load_mask(DATA / "masks" / f"{stem}.png")
    roots = rp.extract_roots(mask, CFG)
    golden = json.load(open(GOLDEN / "traits" / f"{stem}.json"))
    meta = json.load(open(GOLDEN / "traits" / f"{stem}.meta.json"))
    arrays = np.load(GOLDEN / "traits" / f"{stem}.npz")
    assert len(roots) == len(golden)
    for i, root in enumerate(roots):
        _check_root(root, f"root_{i}", golden[f"root_{i}"], meta[f"root_{i}"], arrays)
    _check_frame(rp.roots_to_frame(roots, CFG.dpi, stem), pd.read_csv(GOLDEN / "traits" / "results.csv"), stem, roots)


@pytest.mark.parametrize("level", TUBE["levels"])
def test_tube_levels_match_reference(level):
    mask = rp.load_mask(DATA / f"tube_{TUBE['name']}" / f"L{level}.png")
    roots = rp.extract_roots(mask, CFG)
    golden = json.load(open(GOLDEN / "depth" / TUBE["name"] / f"L{level}.json"))
    assert len(roots) == len(golden)
    for i, root in enumerate(roots):
        _check_root(root, f"root_{i}", golden[f"root_{i}"])
    _check_frame(rp.roots_to_frame(roots, CFG.dpi, f"L{level}"),
                 pd.read_csv(GOLDEN / "depth" / TUBE["name"] / "results.csv"), f"L{level}", roots)


def test_analyze_folder_matches_csv():
    df = rp.analyze_folder(DATA / "masks", CFG)
    csv = pd.read_csv(GOLDEN / "traits" / "results.csv")
    assert len(df) == len(csv)
    assert list(df.columns) == rp.core.extract.COLUMNS
