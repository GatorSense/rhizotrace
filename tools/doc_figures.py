"""Figures for the docs pages, written to docs/images/ at most 400 px wide.

Usage: python tools/doc_figures.py
"""

import os

import matplotlib
import numpy as np
from scipy import ndimage
from skimage.draw import disk, line
from skimage.morphology import dilation
from skimage.morphology import disk as disk_se

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import rhizotrace as rp
from rhizotrace.core.diameter import distance_map
from rhizotrace.core.extract import _padded_bbox
from rhizotrace.core.junctions import prune_spurs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "images")
MASK_GRAY, SKELETON, REMOVED = 0.8, (0.89, 0.10, 0.11), (0.12, 0.47, 0.71)
WIDTH_IN, DPI = 4.0, 100


def _canvas(mask, skeleton, removed=None):
    img = np.ones(mask.shape + (3,))
    img[mask] = MASK_GRAY
    img[skeleton] = SKELETON
    if removed is not None:
        img[removed] = REMOVED
    return img


def _panel(ax, img, title, ends=None):
    ax.imshow(img, interpolation="nearest")
    if ends is not None:
        ax.scatter(ends[:, 1], ends[:, 0], s=14, facecolors="none", edgecolors="k", linewidths=0.8)
    ax.set_title(title, fontsize=7)
    ax.set_xticks([])
    ax.set_yticks([])


def _bar(r, x0=15, x1=75, y=20, shape=(40, 90), rounded=True):
    m = np.zeros(shape, bool)
    m[y - r:y + r + 1, x0:x1 + 1] = True
    if rounded:
        for x in (x0, x1):
            rr, cc = disk((y, x), r + 0.5, shape=shape)
            m[rr, cc] = True
    return m


def skeleton_behaviors():
    rounded = _bar(5)
    holed = _bar(6, rounded=False)
    holed[19:22, 43:47] = False
    bumpy = _bar(5)
    rr, cc = disk((14, 40), 2.5, shape=bumpy.shape)
    bumpy[rr, cc] = True
    lateral = np.zeros((40, 90), bool)
    rr, cc = line(20, 10, 20, 80)
    lateral[rr, cc] = True
    rr, cc = line(20, 45, 36, 61)
    lateral[rr, cc] = True
    lateral = dilation(lateral, disk_se(3))
    shapes = [("Skeleton stops short of the tips", rounded), ("A hole becomes a loop", holed),
              ("A bump on the edge becomes a spur", bumpy), ("A real lateral looks the same", lateral)]
    fig, axes = plt.subplots(len(shapes), 1, figsize=(WIDTH_IN, 1.25 * len(shapes)))
    for ax, (title, m) in zip(axes, shapes):
        sk = rp.skeletonize(m)
        _panel(ax, _canvas(m, sk), title, np.argwhere(rp.free_ends(sk)))
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "skeleton_behaviors.png"), dpi=DPI)
    plt.close(fig)


def tip_fork():
    mask = rp.load_mask(os.path.join(ROOT, "tests", "data", "masks", "sample11.png"))
    lab, _ = ndimage.label(mask > 0)
    sl = ndimage.find_objects(lab)[0]
    b = _padded_bbox(sl[0].start, sl[0].stop, sl[1].start, sl[1].stop, lab.shape)
    crop = lab[b[0]:b[1], b[2]:b[3]] == 1
    sk = rp.skeletonize(crop)
    pruned, _, _ = prune_spurs(sk, distance_map(crop), 1.0)
    rows = np.flatnonzero(crop[:, -30:].any(axis=1))
    img = _canvas(crop, pruned, sk & ~pruned)[max(rows[0] - 2, 0):rows[-1] + 3, -30:]
    fig, ax = plt.subplots(figsize=(WIDTH_IN * 0.6, WIDTH_IN * 0.6 * img.shape[0] / img.shape[1] + 0.3))
    _panel(ax, img, "Ragged tip: blue fork arm is pruned")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "skeleton_tip_fork.png"), dpi=DPI)
    plt.close(fig)


def prune_example():
    h, w = 50, 130
    m = np.zeros((h, w), bool)
    m[17:26, 8:122] = True
    rr, cc = disk((16, 40), 3.2, shape=m.shape)
    m[rr, cc] = True
    t = np.zeros_like(m)
    rr, cc = line(21, 75, 46, 95)
    t[rr, cc] = True
    m |= dilation(t, disk_se(2))
    m[21, 104:107] = False
    sk = rp.skeletonize(m)
    pruned, _, _ = prune_spurs(sk, distance_map(m), 1.0)
    fig, axes = plt.subplots(2, 1, figsize=(WIDTH_IN, 3.2))
    _panel(axes[0], _canvas(m, sk), "Before pruning")
    _panel(axes[1], _canvas(m, pruned, sk & ~pruned), "After pruning: blue is removed")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "prune_example.png"), dpi=DPI)
    plt.close(fig)


def merge_example():
    h, w = 110, 170
    m = np.zeros((h, w), bool)
    for r0, c0, r1, c1 in ((55, 5, 55, 165), (55, 60, 100, 85), (10, 110, 100, 130)):
        rr, cc = line(r0, c0, r1, c1)
        m[rr, cc] = True
    m = dilation(m, disk_se(2))
    cfg = rp.Config()
    sk, labeled, jmask = prune_spurs(rp.skeletonize(m), distance_map(m), cfg.spur_length_diameters)
    pieces = [[p] for p in np.unique(labeled) if p >= 2]
    branches = [b.merged_from for b in rp.merge_by_angle(labeled, jmask, cfg)]
    colors = plt.get_cmap("tab10")
    fig, axes = plt.subplots(2, 1, figsize=(WIDTH_IN, 5.0))
    for ax, groups, title in ((axes[0], pieces, "Pieces after splitting at junctions"),
                              (axes[1], branches, "Branches after merging")):
        img = np.ones((h, w, 3))
        img[m] = MASK_GRAY
        for i, group in enumerate(groups):
            img[np.isin(labeled, group)] = colors(i % 10)[:3]
        img[sk & jmask] = 0
        _panel(ax, img, title)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "merge_example.png"), dpi=DPI)
    plt.close(fig)


def overview_example():
    from rhizotrace.viz import plot_overview
    mask = rp.load_mask(rp.sample_masks() / "sample1.png")
    rows = np.flatnonzero(mask.any(axis=1))
    mask = mask[max(rows[0] - 20, 0):rows[-1] + 20]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, WIDTH_IN * mask.shape[0] / mask.shape[1]))
    plot_overview(mask, rp.extract_roots(mask, rp.Config()), ax=ax)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "overview_example.png"), dpi=DPI)
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    skeleton_behaviors()
    tip_fork()
    prune_example()
    merge_example()
    overview_example()
