"""Overlays and plots for checking results by eye. matplotlib is imported on first use."""

import numpy as np

from .units import to_mm

MAIN_COLOR = (0.89, 0.10, 0.11)
LATERAL_COLORS = [(0.22, 0.49, 0.72), (0.30, 0.69, 0.29), (0.60, 0.31, 0.64),
                  (1.00, 0.50, 0.00), (0.65, 0.34, 0.16), (0.97, 0.51, 0.75)]
SINGLE_COLOR = (0.12, 0.47, 0.71)
MASK_GRAY = 0.78


def _plt():
    import matplotlib.pyplot as plt
    return plt


def _canvas(mask, image=None):
    """RGB float canvas: the photo if given, otherwise root pixels in light gray on white."""
    if image is not None:
        return np.repeat(np.asarray(image, dtype=float)[:, :, None], 3, axis=2)
    canvas = np.ones(np.asarray(mask).shape + (3,))
    canvas[np.asarray(mask) > 0] = MASK_GRAY
    return canvas


def _paint(canvas, rc, color, offset=(0, 0)):
    canvas[rc[:, 0] + offset[0], rc[:, 1] + offset[1]] = color


def paint_root(canvas, root, offset=None):
    """Draw a root's skeleton onto an RGB canvas: main root red, laterals colored, single path blue."""
    offset = (root.bbox[0], root.bbox[2]) if offset is None else offset
    if root.branches:
        for i, b in enumerate(root.branches):
            _paint(canvas, b.skeleton_rc, LATERAL_COLORS[i % len(LATERAL_COLORS)], offset)
        _paint(canvas, root.main_root.skeleton_rc, MAIN_COLOR, offset)
    else:
        _paint(canvas, root.aggregated.skeleton_rc, SINGLE_COLOR, offset)
    return canvas


def plot_root(root, dpi=300, image=None, ax=None):
    """One root's crop with its skeleton, main root, and laterals, plus its key traits."""
    plt = _plt()
    min_r, max_r, min_c, max_c = root.bbox
    canvas = _canvas(root.crop, None if image is None else np.asarray(image)[min_r:max_r, min_c:max_c])
    paint_root(canvas, root, offset=(0, 0))
    if ax is None:
        _, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(canvas, interpolation="nearest")
    a, m = root.aggregated, root.main_root
    ax.set_title(f"length {to_mm(a.length, dpi):.2f} mm, diameter {to_mm(a.avg_diameter, dpi):.3f} mm, "
                 f"main root {to_mm(m.length, dpi):.2f} mm, {root.n_branches} lateral(s)", fontsize=9)
    ax.set_axis_off()
    return ax


def plot_overview(mask, roots, image=None, ax=None):
    """Whole image with every measured root outlined and numbered (ids match the table's 'root')."""
    plt = _plt()
    from matplotlib.patches import Rectangle
    canvas = _canvas(mask, image)
    for root in roots:
        paint_root(canvas, root)
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 10 * canvas.shape[0] / canvas.shape[1]))
    ax.imshow(canvas, interpolation="nearest")
    for i, root in enumerate(roots):
        min_r, max_r, min_c, max_c = root.bbox
        ax.add_patch(Rectangle((min_c, min_r), max_c - min_c, max_r - min_r, fill=False, lw=0.8, ec="k"))
        ax.text(min_c, min_r - 2, str(i), fontsize=7, color="k", va="bottom")
    ax.set_axis_off()
    return ax


def plot_depth_profile(profile, traits=("root_length_mm", "mean_diameter_mm"), axes=None):
    """Trait against depth for each tube, depth increasing downward."""
    plt = _plt()
    if axes is None:
        _, axes = plt.subplots(1, len(traits), figsize=(4 * len(traits), 6), sharey=True)
    axes = np.atleast_1d(axes)
    mid = (profile["depth_start_mm"] + profile["depth_end_mm"]) / 2.0
    for ax, trait in zip(axes, traits):
        for tube, part in profile.groupby("tube", sort=False):
            ax.plot(part[trait], mid[part.index] / 10.0, marker="o", ms=3, label=str(tube))
        ax.set_xlabel(trait.replace("_", " "))
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("soil depth (cm)")
    axes[0].invert_yaxis()
    if profile["tube"].nunique() > 1:
        axes[-1].legend(fontsize=8)
    return axes


PAINT_COLORS = [None, MAIN_COLOR] + LATERAL_COLORS + [SINGLE_COLOR]
PAINT_SINGLE = len(PAINT_COLORS) - 1


def _blocks(arr, stride, reduce, fill):
    """Downsample by stride x stride blocks with a reducer (np.max or np.mean)."""
    h, w = arr.shape[:2]
    hp, wp = -(-h // stride) * stride, -(-w // stride) * stride
    pad = [(0, hp - h), (0, wp - w)] + [(0, 0)] * (arr.ndim - 2)
    padded = np.pad(arr, pad, constant_values=fill)
    shape = (hp // stride, stride, wp // stride, stride) + padded.shape[2:]
    return reduce(padded.reshape(shape), axis=(1, 3))


def depth_overlay(result, photos=None, rows=None, stride=None, tick_cm=5, save_to=None):
    """QC view of a stitched tube: the strip cut into rows, roots painted and numbered, depth ruler.

    photos: optional Stitched of the raw images (same geometry) to draw on instead of the mask.
    rows: how many rows to cut the strip into (default: as many as make each row about 3:1). stride: display
    downsampling; skeletons stay visible because painted pixels win within each block.
    Root numbers match result.traits()['root'].
    """
    plt = _plt()
    stitched = result.stitched
    h, w = stitched.image.shape[:2]
    rows = rows or max(1, round(w / (h * 3.0)))
    stride = stride or max(1, int(np.ceil(h / 540)))

    paint = np.zeros((h, w), dtype=np.uint8)
    for root in result.roots:
        offset = (root.bbox[0], root.bbox[2])
        if root.branches:
            for i, b in enumerate(root.branches):
                _paint(paint, b.skeleton_rc, 2 + i % len(LATERAL_COLORS), offset)
            _paint(paint, root.main_root.skeleton_rc, 1, offset)
        else:
            _paint(paint, root.aggregated.skeleton_rc, PAINT_SINGLE, offset)
    if photos is None:
        gray = np.where(np.asarray(stitched.image) > 0, np.float32(MASK_GRAY), np.float32(1.0))
    else:
        gray = np.asarray(photos.image, dtype=np.float32)
    small = np.repeat(_blocks(gray, stride, np.mean, 1.0)[:, :, None], 3, axis=2)
    paint_small = _blocks(paint, stride, np.max, 0)
    for value in np.unique(paint_small[paint_small > 0]):
        small[paint_small == value] = PAINT_COLORS[value]

    hs, ws = small.shape[:2]
    row_w = -(-ws // rows)
    fig_w = 16.0
    fig, axes = plt.subplots(rows, 1, figsize=(fig_w, rows * (fig_w * hs / row_w + 0.45) + 0.6), squeeze=False)
    depth_cm = result.depth_mm(np.arange(w)) / 10.0
    for r, ax in enumerate(axes[:, 0]):
        x0, x1 = r * row_w, min(ws, (r + 1) * row_w)
        ax.imshow(small[:, x0:x1], interpolation="nearest")
        cols = np.arange(x0 * stride, min(w, x1 * stride))
        d = depth_cm[cols]
        ticks = np.arange(np.ceil(d[0] / tick_cm) * tick_cm, d[-1], tick_cm)
        ax.set_xticks(np.interp(ticks, d, cols) / stride - x0)
        ax.set_xticklabels([f"{t:g}" for t in ticks], fontsize=7)
        for level, start in zip(stitched.levels, stitched.starts[:-1]):
            xs = start / stride - x0
            if 0 <= xs < x1 - x0:
                ax.axvline(xs, color="k", ls="--", lw=0.6)
                ax.text(xs + 3, 3, f"L{level}", fontsize=7, va="top")
        for i, root in enumerate(result.roots):
            min_r, _, min_c, _ = root.bbox
            xs = min_c / stride - x0
            if 0 <= xs < x1 - x0:
                ax.text(xs, min_r / stride, str(i), fontsize=6, color="k", va="bottom", ha="left",
                        bbox=dict(fc="white", ec="none", alpha=0.6, pad=0.3))
        ax.set_xlim(0, row_w)
        ax.set_yticks([])
    axes[-1, 0].set_xlabel("soil depth (cm)")
    fig.suptitle(f"{result.tube.name}: offset {result.info.offset_cm} cm, angle {result.info.angle_deg} deg, "
                 f"{len(result.roots)} roots, levels {stitched.levels}", fontsize=10)
    fig.tight_layout()
    if save_to:
        fig.savefig(save_to, dpi=150)
        plt.close(fig)
    return fig
