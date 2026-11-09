"""Smoke tests: plots render and the CLI runs end to end on the fixtures."""

import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import pytest

import rhizotrace as rp
from rhizotrace import viz
from rhizotrace.cli import main

matplotlib.use("Agg")

DATA = Path(__file__).parent / "data"
MANIFEST = json.load(open(DATA / "golden" / "manifest.json"))
TUBE = MANIFEST["tube"]
TUBE_DIR = DATA / f"tube_{TUBE['name']}"


@pytest.fixture(scope="module")
def sample_roots():
    mask = rp.load_mask(DATA / "masks" / "sample1.png")
    return mask, rp.extract_roots(mask, rp.Config(dpi=300))


@pytest.fixture(scope="module")
def short_tube():
    # Two levels only, to keep the stitched image small.
    tube = rp.Tube("short", "T121", masks={1: str(TUBE_DIR / "L1.png"), 2: str(TUBE_DIR / "L2.png")},
                   info=rp.TubeInfo("T121", 17.7, 30.0))
    return rp.analyze_tube(tube, rp.Config(dpi=300), rp.Scanner())


def test_plot_root_and_overview(sample_roots):
    mask, roots = sample_roots
    ax = viz.plot_root(roots[0])
    assert ax.get_title()
    ax = viz.plot_overview(mask, roots)
    assert len(ax.patches) == len(roots)


def test_plot_depth_profile(short_tube):
    profile = rp.profile_from_result(short_tube, bin_mm=10.0)
    axes = viz.plot_depth_profile(profile)
    assert len(axes) == 2 and axes[0].yaxis_inverted()


def test_depth_overlay(short_tube, tmp_path):
    out = tmp_path / "overlay.png"
    fig = viz.depth_overlay(short_tube, rows=2, save_to=out)
    assert out.exists() and len(fig.axes) == 2


def test_cli_traits(tmp_path, reference_length_filter):
    out = tmp_path / "traits.csv"
    # the golden rows were frozen without pruning
    main(["traits", str(DATA / "masks"), "-o", str(out), "--viz", str(tmp_path / "viz"),
          "--spur-length-diameters", "0"])
    df = pd.read_csv(out)
    golden = pd.read_csv(DATA / "golden" / "traits" / "results.csv")
    assert len(df) == len(golden)
    assert (tmp_path / "viz" / "sample1_overview.png").exists()


def test_cli_stitch(tmp_path):
    main(["stitch", str(DATA), "-o", str(tmp_path)])
    assert (tmp_path / f"tube_{TUBE['name']}_stitched.png").exists()


def test_cli_depth(tmp_path):
    out = tmp_path / "profiles.csv"
    main(["depth", str(DATA), "-o", str(out), "--offset-cm", "17.7", "--angle", "30",
          "--traits-output", str(tmp_path / "traits.csv"), "--overlay", str(tmp_path / "qc")])
    profile = pd.read_csv(out)
    assert set(profile["tube"]) == {f"tube_{TUBE['name']}"}
    assert profile["root_length_mm"].sum() > 0
    assert (tmp_path / "traits.csv").exists()
    assert (tmp_path / "qc" / f"tube_{TUBE['name']}_overlay.png").exists()


def test_cli_depth_requires_offset(tmp_path):
    with pytest.raises(ValueError, match="offset_cm"):
        main(["depth", str(DATA), "-o", str(tmp_path / "p.csv")])
