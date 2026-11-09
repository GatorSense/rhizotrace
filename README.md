# rhizotrace

2D root phenotyping for minirhizotron imagery. Takes binary root masks and returns
per-root traits: length, diameter, angle, main root vs lateral branches, and soil-depth
profiles along a tube. Photos can be segmented into masks with the optional
segmentation extra.

**Status: 0.1.0, alpha.** Per-root traits, segmentation of raw photos, visualization
and the command line are in place. Depth profiling is experimental. A paper describing
the methods and their validation is in preparation.

## Install

```
pip install rhizotrace
pip install "rhizotrace[segmentation]"   # adds PyTorch for the segmentation model
```

For development, dependencies are managed with [uv](https://docs.astral.sh/uv/):

```
uv sync            # creates .venv with the package and dev tools
uv run pytest
```

Add `--extra segmentation` to `uv sync` to keep PyTorch; a plain `uv sync` removes it.
Plain pip works too: `pip install -e .`

Python 3.10 or newer.

## Your masks

- Roots must be bright on a dark background. Binary masks of any two values (0 and 1,
  0 and 255, ...) are read with the brighter value as root; grayscale masks are
  thresholded at the midpoint.
- The resolution is never read from the image file. Pass it with `Config(dpi=...)` or
  `--dpi` (default 300). A wrong value scales every length and diameter.
- Small holes in a mask become loops in the skeleton, which add junctions and branches.
  Fill holes that are not real gaps before running.

## Traits from masks

```python
import rhizotrace as rt

cfg = rt.Config(dpi=300)                 # see Config for the other knobs
mask = rt.load_mask("root.png")          # any image, thresholded to 255 = root
traits = rt.extract_traits(mask, cfg)    # tidy DataFrame

traits[traits.type == "main_root"]       # one row per root: its main axis
traits[traits.type == "branch"]          # one row per lateral, with insertion_angle
traits[traits.type == "aggregated"]      # whole-root skeleton (all branches together)

df = rt.analyze_folder("masks/", cfg)    # same table across a folder, 'image' column filled
```

Columns: `image, root, type, branch, length_mm, avg_diameter_mm, diameter_median_mm,
diameter_std_mm, angle, insertion_angle, number_of_branches, length_per_width` plus the
same lengths and diameters in pixels. `angle` is the root's long axis in degrees,
[0, 180), 0 = right, counterclockwise. `insertion_angle` is the unsigned angle between a
lateral and its main root at the junction. `length_per_width` is filled on the
aggregated row only.

Defaults: terminal skeleton spurs shorter than one local diameter are pruned
(`spur_length_diameters`, 0 = off), skeleton length uses the corner-count estimator
(`length_estimator`), roots and laterals under 0.5 mm are dropped
(`min_root_length_mm`), and the longest branch is the main root (`root_selection`).

To see what was measured:

```python
roots = rt.extract_roots(mask, cfg)      # Root objects with skeletons and branches
from rhizotrace import viz
viz.plot_overview(mask, roots)           # numbered boxes match traits['root']
viz.plot_root(roots[0], dpi=cfg.dpi)
```

## Depth profiles along a tube

**Experimental.** Depth profiling runs end to end but has not been validated against
measured root depth.

Level images of a tube are discovered from file names (`..._T462_L2_...`), from one
folder per tube (`T462/L1.png, L2.png, ...`), or from a folder that is itself one tube
(`L1.png, L2.png, ...`). Offsets are measured per tube, so they come from a small CSV:

```
tube_id,offset_cm,angle
T462,17.7,30
```

```python
tubes = rt.scan_tubes("masks/", tube_info="tubes.csv")
print(tubes)                                       # levels found, gaps, missing info
profiles = rt.depth_profile(tubes, cfg, bin_mm=10)  # per tube, per depth bin
viz.plot_depth_profile(profiles)

result = rt.analyze_tube(tubes["T462"], cfg)       # stitched image + measured roots
viz.depth_overlay(result, save_to="T462_qc.png")   # roots numbered, depth ruler in cm
result.traits()                                    # per-root table on the stitched tube
```

Profile columns: `tube, depth_start_mm, depth_end_mm, root_length_mm, mean_diameter_mm,
median_diameter_mm, n_roots, n_skeleton_px`. Depth is real vertical soil depth from the
tube geometry (`Scanner` holds the camera constants; change it only for another system).
The per-root table from `result.traits()` adds `depth_direction`, the root axis signed to
point deeper into the soil.

## Starting from photos: segmentation

Most minirhizotron datasets are photographs, not masks. The optional extra runs the
PlantRootSeg P-EnDe UNet (Xu et al. 2020, see [NOTICE](https://github.com/GatorSense/rhizotrace/blob/main/NOTICE)):

```
pip install "rhizotrace[segmentation]"     # or: uv sync --extra segmentation
```

The weights (124 MB) are not part of the package. Download `P-EnDe-model.pth` from the
[PlantRootSeg repository](https://github.com/GatorSense/PlantRootSeg/tree/master/Models)
([direct link](https://media.githubusercontent.com/media/GatorSense/PlantRootSeg/master/Models/P-EnDe-model.pth)),
then point at the file with `weights=` in Python, `--weights` on the command line, or the
`RHIZOTRACE_WEIGHTS` environment variable. Its SHA-256 is
`0ad6298eb63508c09a6c3aa14fc0a715627425f992bf4ae552b03941ba4c5aaf`. Cloning PlantRootSeg
without Git LFS gives a small pointer file instead of the weights.

```python
from rhizotrace import segmentation as seg

model = seg.load_segmenter("P-EnDe-model.pth", device="auto")   # cuda if available, else cpu
mask = model.segment(photo)                       # (H, W, 3) uint8 -> 255 = root
seg.segment_folder("photos/", "masks/", model)    # writes one mask PNG per photo

tubes = rt.scan_tubes(images="photos/", tube_info="tubes.csv")
seg.segment_tubes(tubes, "masks/", model)         # masks per level; photos kept for overlays
profiles = rt.depth_profile(tubes, cfg)
```

Masks are always written to disk, so the expensive step runs once, you can look at the
masks, and reruns reuse them. The model runs on the whole image (no tiling), so memory
grows with image size, roughly 2.4 GB of RAM or 2 GB of GPU memory per megapixel.
Measured on one 2550 x 2160 level image (5.5 MP):

| device | seconds per image | peak memory |
|---|---|---|
| GPU (NVIDIA L4, 24 GB) | 0.8 | 9.3 GB GPU |
| CPU, 16 threads | 9.0 | 11.6 GB RAM |
| CPU, 4 threads | 16.6 | 11.6 GB RAM |

So for full tube images use a GPU with at least 12 GB (16 GB recommended; a free Colab
T4 works), or a machine with 32 GB of RAM (16 GB is borderline for a single level).
Cropped or lower-resolution images run anywhere. The segmenter checks free memory before
each image, using the per-megapixel rule above, and stops with a plain message rather
than crashing part way through.

`threshold` (default 0.7735, the operating point from Xu et al. 2020) applies to the
sigmoid output after per-image min-max normalization; `normalize="none"` thresholds the
raw sigmoid instead. On 100 PRMI switchgrass reference masks the P-EnDe model reaches a
pooled Dice of about 0.71 at the default and 0.65 at threshold 0.5, with or without
normalization ([tools/evaluate_segmentation.py](https://github.com/GatorSense/rhizotrace/blob/main/tools/evaluate_segmentation.py)).

## Command line

```
rhizotrace traits masks/ -o traits.csv --viz overviews/
rhizotrace traits photos/ --segment -o traits.csv        # masks written to masks/ next to the CSV
rhizotrace depth masks/ --tube-info tubes.csv -o profiles.csv --overlay qc/ --traits-output tube_traits.csv
rhizotrace depth photos/ --segment --tube-info tubes.csv -o profiles.csv --overlay qc/
rhizotrace segment photos/ -o masks/ --device cuda
rhizotrace stitch masks/ -o stitched/
```

The `--segment` and `segment` commands find the weights through `--weights` or
`RHIZOTRACE_WEIGHTS`, e.g. `export RHIZOTRACE_WEIGHTS=/path/to/P-EnDe-model.pth`.

## Repository layout

The PyPI package is `src/rhizotrace`. The repository also holds:

- `tests/`: the regression suite and its fixtures.
- `tools/`: segmentation benchmark and evaluation, and the script that draws the docs figures.

## Regression fixtures

`tests/data/` holds reference outputs frozen for a set of sample masks, one stitched tube
and four segmentation crops (settings in `tests/data/golden/manifest.json`). The tests
compare against them to catch unintended drift; intentional changes are reviewed and
re-baselined.

## Citing

A paper is in preparation. Until then, cite this repository,
https://github.com/GatorSense/rhizotrace, and the version you used. If you use the
segmentation model, also cite:

Xu, W., Yu, G., Zare, A., Zurweller, B., Rowland, D. L., Reyes-Cabrera, J.,
Fritschi, F. B., Matamala, R., & Juenger, T. E. (2020). Overcoming small
minirhizotron datasets using transfer learning. Computers and Electronics in
Agriculture, 175, 105466. https://doi.org/10.1016/j.compag.2020.105466

## License

MPL-2.0. See [LICENSE](https://github.com/GatorSense/rhizotrace/blob/main/LICENSE) and [NOTICE](https://github.com/GatorSense/rhizotrace/blob/main/NOTICE).
