"""Integrity checks for the frozen reference fixtures (not pipeline tests)."""

import json

import numpy as np
import pandas as pd


def test_manifest_describes_fixtures(manifest):
    assert manifest["frozen_at"] and manifest["settings"]
    assert set(manifest["libraries"]) >= {"numpy", "scipy", "scikit-image"}
    assert set(manifest["tube"]["depth_config"]) == {"offset_cm", "tube_angle_deg", "depth_bin_size_mm"}


def test_every_mask_has_golden_outputs(data_dir, golden_dir, sample_names):
    assert len(sample_names) == 11
    for name in sample_names:
        stem = name.rsplit(".", 1)[0]
        assert (data_dir / "masks" / name).exists()
        assert (golden_dir / "traits" / f"{stem}.json").exists()
        assert (golden_dir / "traits" / f"{stem}.npz").exists()
        assert (golden_dir / "traits" / f"{stem}.meta.json").exists()


def test_golden_json_matches_csv_rows(golden_dir, sample_names):
    csv = pd.read_csv(golden_dir / "traits" / "results.csv")
    for name in sample_names:
        stem = name.rsplit(".", 1)[0]
        with open(golden_dir / "traits" / f"{stem}.json") as f:
            roots = json.load(f)
        assert roots
        expected = sum(2 + len(r["branches"]) for r in roots.values())
        assert (csv["image_name"] == stem).sum() == expected


def test_intermediates_consistent(golden_dir, sample_names):
    for name in sample_names:
        stem = name.rsplit(".", 1)[0]
        with open(golden_dir / "traits" / f"{stem}.meta.json") as f:
            meta = json.load(f)
        arrays = np.load(golden_dir / "traits" / f"{stem}.npz")
        for key, m in meta.items():
            skel = arrays[f"{key}/skeleton"]
            skel_rc = arrays[f"{key}/agg/skeleton_rc"]
            assert skel.sum() == len(skel_rc)
            assert len(arrays[f"{key}/agg/diameter_values"]) == len(skel_rc)
            assert len(m["branches"]) == m["n_branches"]


def test_tube_fixture(data_dir, golden_dir, manifest):
    tube = manifest["tube"]
    assert tube is not None
    gold = golden_dir / "depth" / tube["name"]
    for level in tube["levels"]:
        assert (data_dir / f"tube_{tube['name']}" / f"L{level}.png").exists()
        assert (gold / f"L{level}.json").exists()
    positions = json.load(open(gold / "level_positions.json"))
    assert [p["level"] for p in positions] == tube["levels"]
    assert (gold / "depth_profiles_per_level.csv").exists()
    assert (gold / "stitched.png").exists()
