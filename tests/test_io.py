import numpy as np
import pytest
from PIL import Image

import rhizotrace as rp

ROOT = np.array([[0, 1, 1], [0, 1, 0], [0, 0, 0]], dtype=bool)


@pytest.mark.parametrize("dtype, high", [(np.uint8, 1), (np.uint8, 255), (np.uint16, 1), (np.uint16, 65535)])
def test_two_valued_mask_brighter_value_is_root(tmp_path, dtype, high):
    path = tmp_path / "mask.png"
    Image.fromarray((ROOT * high).astype(dtype)).save(path)
    assert np.array_equal(rp.load_mask(path), ROOT * np.uint8(255))


def test_grayscale_mask_is_thresholded(tmp_path):
    path = tmp_path / "mask.png"
    Image.fromarray(np.array([[0, 100, 128, 255]], dtype=np.uint8)).save(path)
    assert rp.load_mask(path).tolist() == [[0, 0, 255, 255]]
    assert rp.load_mask(path, threshold=0.3).tolist() == [[0, 255, 255, 255]]
