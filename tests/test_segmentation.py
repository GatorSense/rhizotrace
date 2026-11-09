"""Segmentation extra: reproduces the frozen reference masks. Skipped without torch or weights."""

import json
import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

torch = pytest.importorskip("torch")

import rhizotrace as rp
from rhizotrace import segmentation as seg
from rhizotrace.segmentation import weights as W

DATA = Path(__file__).parent / "data" / "segmentation"
MANIFEST = json.load(open(DATA / "manifest.json"))
WEIGHTS = os.environ.get(W.ENV_VAR)

pytestmark = pytest.mark.skipif(WEIGHTS is None, reason="no P-EnDe weights (set RHIZOTRACE_WEIGHTS)")


@pytest.fixture(scope="module")
def segmenter():
    return seg.load_segmenter(WEIGHTS, device="cpu")


def agreement(a, b):
    return float(np.mean((a > 0) == (b > 0)))


@pytest.mark.parametrize("name", MANIFEST["names"])
def test_matches_reference_masks(segmenter, name):
    raw = np.asarray(Image.open(DATA / "raw" / f"{name}.png").convert("RGB"))
    golden = np.asarray(Image.open(DATA / "golden" / f"{name}.png"))
    mask = segmenter.segment(raw)
    assert mask.shape == golden.shape and mask.dtype == np.uint8
    assert agreement(mask, golden) >= 0.999


def test_weights_checksum():
    assert W.sha256_of(WEIGHTS) == MANIFEST["weights_sha256"] == W.SHA256


def test_segment_folder_and_tubes(segmenter, tmp_path):
    paths = seg.segment_folder(DATA / "raw", tmp_path / "masks", segmenter)
    assert len(paths) == len(MANIFEST["names"]) and all(os.path.exists(p) for p in paths)
    mtime = os.path.getmtime(paths[0])
    seg.segment_folder(DATA / "raw", tmp_path / "masks", segmenter)     # existing masks are kept
    assert os.path.getmtime(paths[0]) == mtime

    raws = sorted((DATA / "raw").glob("*.png"))
    tube = rp.Tube("T1", "T1", images={1: str(raws[0]), 2: str(raws[1])})
    tubes = seg.segment_tubes(rp.TubeSet({"T1": tube}), tmp_path / "tube_masks", segmenter)
    assert tubes["T1"].masks == {1: str(tmp_path / "tube_masks" / "T1" / "L1.png"),
                                 2: str(tmp_path / "tube_masks" / "T1" / "L2.png")}
    assert np.array_equal(rp.load_mask(tubes["T1"].masks[1]), rp.load_mask(paths[0]))


def test_memory_preflight(segmenter, monkeypatch):
    monkeypatch.setattr(seg, "available_memory_bytes", lambda device: 1_000_000)
    with pytest.raises(MemoryError, match="GB available"):
        segmenter.segment(np.zeros((720, 510, 3), np.uint8))
    assert segmenter.memory_needed_bytes((2160, 2550)) == pytest.approx(2.4e9 * 2160 * 2550 / 1e6)


def test_normalize_none_thresholds_raw_sigmoid():
    s = seg.load_segmenter(WEIGHTS, device="cpu", normalize="none", threshold=0.99)
    raw = np.asarray(Image.open(DATA / "raw" / f"{MANIFEST['names'][0]}.png").convert("RGB"))
    assert np.count_nonzero(s.segment(raw)) <= np.count_nonzero(seg.load_segmenter(WEIGHTS, "cpu").segment(raw))


def test_missing_weights_path():
    with pytest.raises(FileNotFoundError):
        W.resolve_weights("/nonexistent/P-EnDe-model.pth")
