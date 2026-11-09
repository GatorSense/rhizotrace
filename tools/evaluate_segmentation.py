"""Dice of the segmenter against PRMI reference masks, for both normalization modes.

Usage: python tools/evaluate_segmentation.py --names-from DIR --images DIR --masks DIR [--out CSV]
  names-from: folder whose GT_*.png names select the subset
  images:     PRMI raw images (names without the GT_ prefix)
  masks:      PRMI reference masks (GT_ names)
"""

import argparse
import os

import numpy as np
import pandas as pd
from PIL import Image

from rhizotrace.segmentation import load_segmenter


def dice(pred, ref):
    p, r = pred > 0, ref > 0
    denom = p.sum() + r.sum()
    return 1.0 if denom == 0 else 2.0 * np.logical_and(p, r).sum() / denom


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--names-from", required=True)
    p.add_argument("--images", required=True)
    p.add_argument("--masks", required=True)
    p.add_argument("--weights")
    p.add_argument("--device", default="auto")
    p.add_argument("--out")
    args = p.parse_args()

    names = sorted(f[:-4] for f in os.listdir(args.names_from) if f.endswith(".png"))
    raws = {n: np.asarray(Image.open(os.path.join(args.images, n[3:] + ".png")).convert("RGB")) for n in names}
    refs = {n: np.asarray(Image.open(os.path.join(args.masks, n + ".png")).convert("L")) for n in names}

    settings = [("per_image", 0.5), ("per_image", 0.7735), ("none", 0.5), ("none", 0.7735), ("none", 0.9)]
    rows = []
    for normalize, threshold in settings:
        s = load_segmenter(args.weights, args.device, threshold, normalize)
        inter = tp = fp = fn = 0
        per_image = []
        for n in names:
            pred = s.segment(raws[n]) > 0
            ref = refs[n] > 0
            per_image.append(dice(pred, ref))
            tp += np.logical_and(pred, ref).sum()
            fp += np.logical_and(pred, ~ref).sum()
            fn += np.logical_and(~pred, ref).sum()
        empty_ref = [n for n in names if refs[n].max() == 0]
        rows.append({
            "normalize": normalize, "threshold": threshold,
            "pooled_dice": 2 * tp / (2 * tp + fp + fn), "mean_dice": float(np.mean(per_image)),
            "median_dice": float(np.median(per_image)),
            "n_images": len(names), "n_empty_reference": len(empty_ref),
        })
        print(rows[-1])
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    if args.out:
        df.to_csv(args.out, index=False, float_format="%.4f")


if __name__ == "__main__":
    main()
