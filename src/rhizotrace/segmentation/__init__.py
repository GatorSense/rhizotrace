"""Raw minirhizotron photos to root masks with the P-EnDe UNet (PlantRootSeg).

Optional extra: pip install rhizotrace[segmentation]. Whole-image inference only, so
memory scales with image size: about 2.4 GB of RAM or 2 GB of GPU memory per
megapixel (a 2550 x 2160 level image needs roughly 13 GB RAM or 11 GB GPU memory).
"""

import os

import numpy as np
from PIL import Image

from ..io import IMAGE_EXTENSIONS, list_images
from .weights import resolve_weights

# Operating point of Xu et al. (2020). On 100 PRMI switchgrass crops it gives pooled
# Dice 0.715, against 0.651 at 0.5.
DEFAULT_THRESHOLD = 0.7735
GB_PER_MEGAPIXEL = {"cpu": 2.4, "cuda": 2.0}   # measured on a 2550 x 2160 level image
NORMALIZE_MODES = ("per_image", "none")


def _torch():
    try:
        import torch
    except ImportError:
        raise ImportError("segmentation needs PyTorch: pip install rhizotrace[segmentation]") from None
    return torch


def available_memory_bytes(device):
    """Free memory on the device, or None when it cannot be determined."""
    torch = _torch()
    if device.type == "cuda":
        return torch.cuda.mem_get_info(device)[0]
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    return None


class Segmenter:
    """The P-EnDe UNet ready for inference.

    threshold applies to the sigmoid output after per-image min-max normalization
    (normalize='per_image', the default) or to the raw sigmoid (normalize='none').
    check_memory raises MemoryError before inference when the image will not fit.
    """

    def __init__(self, weights=None, device="auto", threshold=DEFAULT_THRESHOLD,
                 normalize="per_image", check_memory=True):
        torch = _torch()
        from .unet import UNet

        if normalize not in NORMALIZE_MODES:
            raise ValueError(f"normalize must be one of {NORMALIZE_MODES}")
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)
        self.threshold = threshold
        self.normalize = normalize
        self.check_memory = check_memory
        self.weights_path = resolve_weights(weights)
        self.model = UNet(num_classes=1, depth=5)
        self.model.load_state_dict(torch.load(self.weights_path, map_location=self.device, weights_only=True))
        self.model.to(self.device).eval()

    def memory_needed_bytes(self, shape):
        return GB_PER_MEGAPIXEL.get(self.device.type, 2.4) * shape[0] * shape[1] * 1e3

    def segment(self, image):
        """(H, W, 3) uint8 photo (gray and RGBA accepted) -> (H, W) uint8 mask, 255 = root."""
        torch = _torch()
        image = np.asarray(image)
        if image.ndim == 2:
            image = np.stack([image] * 3, axis=2)
        image = np.array(Image.fromarray(image).convert("RGB"))
        if self.check_memory:
            need, have = self.memory_needed_bytes(image.shape), available_memory_bytes(self.device)
            if have is not None and need > have:
                raise MemoryError(
                    f"a {image.shape[1]} x {image.shape[0]} image needs about {need / 1e9:.0f} GB on "
                    f"{self.device.type}, {have / 1e9:.1f} GB available. Use a GPU with more memory, a "
                    f"machine with more RAM, or smaller images (Segmenter(check_memory=False) to try anyway)."
                )
        x = torch.from_numpy(image).permute(2, 0, 1).float().div_(255).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            pred = torch.sigmoid(self.model(x)[0, 0])
            if self.normalize == "per_image":
                lo, hi = pred.min(), pred.max()
                if hi - lo > 0:
                    pred = (pred - lo) / (hi - lo)
            mask = (pred > self.threshold).cpu().numpy()
        return (mask * 255).astype(np.uint8)


def load_segmenter(weights=None, device="auto", threshold=DEFAULT_THRESHOLD, normalize="per_image"):
    """Segmenter with weights from a path or the RHIZOTRACE_WEIGHTS variable."""
    return Segmenter(weights, device, threshold, normalize)


def segment_image_file(path, out_path, segmenter):
    """Segment one photo file to a mask PNG, carrying the DPI tag over when present."""
    src = Image.open(path)
    mask = segmenter.segment(np.asarray(src.convert("RGB")))
    dpi = src.info.get("dpi")
    out = Image.fromarray(mask)
    if dpi:
        out.save(out_path, dpi=dpi)
    else:
        out.save(out_path)
    return mask


def segment_folder(folder, out_dir, segmenter=None, overwrite=False, extensions=IMAGE_EXTENSIONS,
                   progress=None):
    """Segment every photo in a folder into out_dir/<stem>.png. Existing masks are kept
    unless overwrite. Returns the mask paths in input order."""
    segmenter = segmenter or load_segmenter()
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for path in list_images(folder, extensions):
        out = os.path.join(out_dir, os.path.splitext(os.path.basename(path))[0] + ".png")
        if overwrite or not os.path.exists(out):
            segment_image_file(path, out, segmenter)
            if progress:
                progress(path, out)
        paths.append(out)
    return paths


def segment_tubes(tubes, out_dir, segmenter=None, overwrite=False, progress=None):
    """Segment each tube's photos into out_dir/<tube>/L<n>.png and record them as its masks.

    Tubes that already have masks are left alone. Photos stay attached for overlays.
    """
    segmenter = segmenter or load_segmenter()
    for tube in tubes:
        if tube.masks or not tube.images:
            continue
        tube_dir = os.path.join(out_dir, tube.name)
        os.makedirs(tube_dir, exist_ok=True)
        for level, path in tube.images.items():
            out = os.path.join(tube_dir, f"L{level}.png")
            if overwrite or not os.path.exists(out):
                segment_image_file(path, out, segmenter)
                if progress:
                    progress(path, out)
            tube.masks[level] = out
    return tubes
