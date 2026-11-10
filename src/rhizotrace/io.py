"""Reading masks and images, batch runs over folders."""

import os
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from .config import Config
from .core.extract import COLUMNS, extract_traits

IMAGE_EXTENSIONS = (".png", ".tif", ".tiff", ".jpg", ".jpeg", ".bmp")


def sample_masks():
    """Folder of the three sample root masks shipped with the package (300 DPI)."""
    return Path(__file__).parent / "samples" / "masks"


def sample_photos():
    """Folder of the photos the sample masks were drawn on."""
    return Path(__file__).parent / "samples" / "photos"


def load_mask(path, threshold=0.5):
    """Binary root mask as uint8 (255 = root). Any image is read as grayscale and thresholded.

    An image with exactly two gray values takes the brighter one as root whatever the
    threshold, so masks saved as 0/1 load the same as 0/255.
    """
    gray = np.asarray(Image.open(path).convert("L"))
    values = np.flatnonzero(np.bincount(gray.ravel(), minlength=256))
    if len(values) == 2:
        return ((gray == values[1]) * 255).astype(np.uint8)
    return ((gray / 255.0 > threshold) * 255).astype(np.uint8)


def load_image(path):
    """Grayscale image scaled to [0, 1], for overlays."""
    return np.asarray(Image.open(path).convert("L"), dtype=np.float64) / 255.0


def list_images(folder, extensions=IMAGE_EXTENSIONS):
    return sorted(os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith(extensions) and not f.startswith("."))


def analyze_folder(folder, cfg: Config = None, extensions=IMAGE_EXTENSIONS):
    """extract_traits over every mask in a folder; the 'image' column holds each file's stem."""
    cfg = cfg or Config()
    frames = []
    for path in list_images(folder, extensions):
        stem = os.path.splitext(os.path.basename(path))[0]
        frames.append(extract_traits(load_mask(path, cfg.mask_threshold), cfg, image=stem))
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    return pd.concat(frames, ignore_index=True)
