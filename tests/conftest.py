import json
from pathlib import Path

import pytest

from rhizotrace.core import extract

DATA_DIR = Path(__file__).parent / "data"
GOLDEN_DIR = DATA_DIR / "golden"


@pytest.fixture(scope="session")
def data_dir():
    return DATA_DIR


@pytest.fixture(scope="session")
def golden_dir():
    return GOLDEN_DIR


@pytest.fixture(scope="session")
def manifest():
    with open(GOLDEN_DIR / "manifest.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def sample_names(manifest):
    return manifest["masks"]


@pytest.fixture(scope="module")
def reference_length_filter():
    """The reference outputs dropped skeletons under a flat 50 pixels; the package thresholds
    measured length. Fixture comparisons pin the flat rule so every other stage is still
    checked exactly. test_length_filter.py covers the package rule."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(extract, "_too_short", lambda rc, cfg, length=None: len(rc) < 50)
        yield
