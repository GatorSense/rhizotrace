"""Command line: traits (masks -> table), depth (tube levels -> profiles), stitch, segment."""

import argparse
import os
import sys

import pandas as pd
from PIL import Image

from . import __version__
from .config import Config, Scanner
from .core.extract import extract_roots, roots_to_frame
from .depth.profile import analyze_tube, profile_from_result
from .depth.scan import scan_tubes
from .depth.stitch import stitch
from .io import list_images, load_mask


def _add_config_args(p):
    d = Config()
    p.add_argument("--dpi", type=int, default=d.dpi, help=f"image resolution (default {d.dpi})")
    p.add_argument("--min-root-size", type=int, default=d.min_root_size,
                   help=f"ignore components smaller than this many px of area (default {d.min_root_size})")
    p.add_argument("--min-root-length-mm", type=float, default=d.min_root_length_mm,
                   help=f"ignore roots and branches shorter than this (default {d.min_root_length_mm})")
    p.add_argument("--merge", choices=("angle", "diameter", "none"), default=d.merge_method,
                   help=f"how skeleton pieces recombine at junctions (default {d.merge_method})")
    p.add_argument("--merge-angle", type=float, default=d.merge_angle_threshold,
                   help=f"angle merge threshold, deg (default {d.merge_angle_threshold})")
    p.add_argument("--root-selection", choices=("length", "diameter", "combined", "connectivity"),
                   default=d.root_selection, help=f"which branch is the main root (default {d.root_selection})")
    p.add_argument("--spur-length-diameters", type=float, default=d.spur_length_diameters,
                   help=f"prune terminal skeleton branches shorter than this many local diameters, 0 = off "
                        f"(default {d.spur_length_diameters})")


def _config(args):
    return Config(dpi=args.dpi, min_root_size=args.min_root_size,
                  min_root_length_mm=args.min_root_length_mm, merge_method=args.merge,
                  merge_angle_threshold=args.merge_angle, root_selection=args.root_selection,
                  spur_length_diameters=args.spur_length_diameters)


def _add_tube_args(p):
    p.add_argument("--tube-info", help="CSV with tube_id, offset_cm, angle")
    p.add_argument("--images", help="folder of raw photos matching the masks (for overlays; ignored with --segment)")
    p.add_argument("--offset-cm", type=float, help="offset for tubes missing from --tube-info")
    p.add_argument("--angle", type=float, help="insertion angle from vertical for tubes missing from --tube-info")
    p.add_argument("--session-pattern", help="regex with one group that separates sessions of the same tube")


def _add_segment_args(p, flag=True):
    if flag:
        p.add_argument("--segment", action="store_true",
                       help="inputs are photos: segment them into --masks first (rhizotrace[segmentation])")
        p.add_argument("--masks", metavar="DIR", help="where segmented masks go (default: masks/ next to the output)")
    from .segmentation import DEFAULT_THRESHOLD
    p.add_argument("--device", default="auto", help="auto | cpu | cuda (default auto)")
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                   help=f"segmentation threshold (default {DEFAULT_THRESHOLD})")
    p.add_argument("--weights", help="P-EnDe weights file (default: RHIZOTRACE_WEIGHTS)")


def _segmenter(args):
    from .segmentation import load_segmenter
    return load_segmenter(args.weights, args.device, args.threshold)


def _masks_dir(args):
    return args.masks or os.path.join(os.path.dirname(os.path.abspath(args.output)), "masks")


def _report(src, out):
    print(f"segmented {os.path.basename(src)} -> {out}")


def cmd_traits(args):
    cfg = _config(args)
    folder = args.folder
    if args.segment:
        from .segmentation import segment_folder
        folder = _masks_dir(args)
        segment_folder(args.folder, folder, _segmenter(args), progress=_report)
    files = list_images(folder)
    if not files:
        sys.exit(f"no images found in {folder}")
    frames = []
    if args.viz:
        os.makedirs(args.viz, exist_ok=True)
    for path in files:
        stem = os.path.splitext(os.path.basename(path))[0]
        mask = load_mask(path, cfg.mask_threshold)
        roots = extract_roots(mask, cfg)
        frames.append(roots_to_frame(roots, cfg.dpi, image=stem))
        print(f"{stem}: {len(roots)} roots")
        if args.viz:
            from .viz import _plt, plot_overview
            ax = plot_overview(mask, roots)
            ax.figure.savefig(os.path.join(args.viz, f"{stem}_overview.png"), dpi=150, bbox_inches="tight")
            _plt().close(ax.figure)
    df = pd.concat(frames, ignore_index=True)
    df.to_csv(args.output, index=False, float_format="%.4f")
    print(f"wrote {args.output} ({len(df)} rows)")


def cmd_depth(args):
    cfg = _config(args)
    if args.segment:
        from .segmentation import segment_tubes
        tubes = scan_tubes(images=args.folder, tube_info=args.tube_info, session_pattern=args.session_pattern)
        print(tubes.report())
        segment_tubes(tubes, _masks_dir(args), _segmenter(args), progress=_report)
    else:
        tubes = scan_tubes(args.folder, images=args.images, tube_info=args.tube_info,
                           session_pattern=args.session_pattern)
        print(tubes.report())
    if len(tubes) == 0:
        sys.exit("no tubes found")
    profiles, traits = [], []
    if args.overlay:
        os.makedirs(args.overlay, exist_ok=True)
    for tube in tubes:
        result = analyze_tube(tube, cfg, Scanner(), args.offset_cm, args.angle)
        profiles.append(profile_from_result(result, args.bin_mm))
        traits.append(result.traits())
        print(f"{tube.name}: {len(result.roots)} roots, {len(profiles[-1])} depth bins")
        if args.overlay:
            from .viz import depth_overlay
            photos = stitch(tube, Scanner(), cfg.dpi, kind="images") if tube.images else None
            depth_overlay(result, photos, save_to=os.path.join(args.overlay, f"{tube.name}_overlay.png"))
    pd.concat(profiles, ignore_index=True).to_csv(args.output, index=False, float_format="%.4f")
    print(f"wrote {args.output}")
    if args.traits_output:
        pd.concat(traits, ignore_index=True).to_csv(args.traits_output, index=False, float_format="%.4f")
        print(f"wrote {args.traits_output}")


def cmd_stitch(args):
    kind = "images" if args.photos else "masks"
    tubes = scan_tubes(**{kind: args.folder}, session_pattern=args.session_pattern)
    print(tubes.report())
    os.makedirs(args.output, exist_ok=True)
    for tube in tubes:
        stitched = stitch(tube, Scanner(), args.dpi, kind=kind)
        img = stitched.image if kind == "masks" else (stitched.image * 255).astype("uint8")
        path = os.path.join(args.output, f"{tube.name}_stitched.png")
        Image.fromarray(img).save(path)
        print(f"{path}: {img.shape[1]} x {img.shape[0]} px, levels {stitched.levels}")


def cmd_segment(args):
    from .segmentation import segment_folder
    paths = segment_folder(args.folder, args.output, _segmenter(args), overwrite=args.overwrite, progress=_report)
    print(f"{len(paths)} masks in {args.output}")


def build_parser():
    p = argparse.ArgumentParser(prog="rhizotrace", description="2D root phenotyping from minirhizotron images.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    t = sub.add_parser("traits", help="measure every root in a folder of masks (or photos with --segment)")
    t.add_argument("folder", help="folder of binary masks, or of photos with --segment")
    t.add_argument("-o", "--output", default="traits.csv")
    t.add_argument("--viz", metavar="DIR", help="save an annotated overview image per mask")
    _add_config_args(t)
    _add_segment_args(t)
    t.set_defaults(func=cmd_traits)

    d = sub.add_parser("depth", help="stitch tube levels and profile traits by soil depth")
    d.add_argument("folder", help="level masks (or photos with --segment): flat with T###/L# names, "
                                  "one folder per tube, or one tube's L1..Ln files")
    d.add_argument("-o", "--output", default="depth_profiles.csv")
    d.add_argument("--traits-output", metavar="CSV", help="also save per-root traits on the stitched tubes")
    d.add_argument("--bin-mm", type=float, default=10.0, help="depth bin size (default 10 mm)")
    d.add_argument("--overlay", metavar="DIR", help="save a QC overlay image per tube")
    _add_tube_args(d)
    _add_config_args(d)
    _add_segment_args(d)
    d.set_defaults(func=cmd_depth)

    s = sub.add_parser("stitch", help="stitch tube levels into one image per tube")
    s.add_argument("folder", help="folder of level images")
    s.add_argument("-o", "--output", default="stitched")
    s.add_argument("--photos", action="store_true", help="inputs are photos, not masks")
    s.add_argument("--dpi", type=int, default=300)
    s.add_argument("--session-pattern", help="regex with one group that separates sessions of the same tube")
    s.set_defaults(func=cmd_stitch)

    g = sub.add_parser("segment", help="photos -> root masks with the P-EnDe UNet (rhizotrace[segmentation])")
    g.add_argument("folder", help="folder of photos")
    g.add_argument("-o", "--output", default="masks")
    g.add_argument("--overwrite", action="store_true", help="redo masks that already exist")
    _add_segment_args(g, flag=False)
    g.set_defaults(func=cmd_segment)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    args.func(args)


if __name__ == "__main__":
    main()
