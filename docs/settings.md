# Settings

Every setting has a default, so you only set the ones you want to change. On the command
line a setting is an option, such as `--dpi 150`. In Python it is a keyword of `Config`,
such as `rhizotrace.Config(dpi=150)`, passed to the function doing the work. Some
settings exist only in Python.

## Main settings

| Setting | Command line | Default | What it does |
|---|---|---|---|
| `dpi` | `--dpi` | 300 | image resolution in pixels per inch. Never read from the file, and every length and diameter depends on it. See [Input masks](input_masks.md) |
| `min_root_size` | `--min-root-size` | 50 | blobs with fewer pixels than this are not measured. See [Split mask into individual roots](split_roots.md) |
| `min_root_length_mm` | `--min-root-length-mm` | 0.5 | roots and branches shorter than this, in mm, are dropped |
| `spur_length_diameters` | `--spur-length-diameters` | 1.0 | spurs shorter than this many local diameters are pruned; 0 turns pruning off. See [Prune spurs](prune_spurs.md) |
| `merge_method` | `--merge` | `angle` | how pieces are joined into branches: `angle`, `diameter` or `none`. See [Merge](merge.md) |
| `merge_angle_threshold` | `--merge-angle` | 30 | how far from straight, in degrees, two pieces can be and still join |
| `root_selection` | `--root-selection` | `length` | which branch is the main root: `length`, `diameter`, `combined` or `connectivity`. See [Choose main root](main_root.md) |

## Advanced settings (Python only)

| Setting | Default | What it does |
|---|---|---|
| `mask_threshold` | 0.5 | gray level, as a fraction, above which a pixel of a grayscale mask is root. Masks with only two values ignore it. See [Input masks](input_masks.md) |
| `length_estimator` | `corner` | how length is computed from the skeleton: `corner`, `kulpa`, `chain_no_triangles` or `chain`. See [Length](measurements.md#length) |
| `junction_dilation_iterations` | 1 | how many pixels each junction is widened before the skeleton is cut. See [Split skeleton at junctions](split_junctions.md) |
| `junction_proximity_threshold` | 2 | how close, in pixels, a piece's end must be to a junction to count as touching it |
| `angle_mode` | `endpoint` | how a piece's direction is taken for merging: `endpoint`, `local` or `hybrid`. See [Merge](merge.md#settings) |
| `local_k` | 10 | pixels used for a piece's direction in the `local` and `hybrid` modes |
| `force_merge_degree_2` | `True` | join the two pieces at a junction where only two meet, if their angle is at least `force_merge_min_angle` |
| `force_merge_min_angle` | 90 | smallest angle, in degrees, at which two pieces meeting alone are joined |
| `diameter_ratio_threshold` | 0.3 | `diameter` merging: join pieces whose diameters differ by at most this fraction |
| `length_weight`, `diameter_weight` | 0.7, 0.3 | `combined` main root selection: the weights of length and diameter |
| `insertion_reach_px` | 15 | pixels beyond the root's local radius, on each side of a junction, that set the directions for the insertion angle. See [Choose main root](main_root.md) |

## Segmentation settings

These belong to the segmentation model, not to `Config`. In Python they are arguments of
`rhizotrace.segmentation.load_segmenter`. See [Segment images into root masks](segmentation.md).

| Setting | Command line | Default | What it does |
|---|---|---|---|
| `weights` | `--weights` | `RHIZOTRACE_WEIGHTS` | the model weights file |
| `device` | `--device` | `auto` | `cpu`, `cuda`, or `auto` for a GPU when there is one |
| `threshold` | `--threshold` | 0.7735 | a pixel is root above this value |
| `normalize` | Python only | `per_image` | scale each image's output to 0 to 1 before the threshold; `none` uses the raw output |

---

[Overview](index.md) · [Running rhizotrace](usage.md)
