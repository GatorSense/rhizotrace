# Command line

Everything runs through one command, `rhizotrace`, followed by what to do:

| Command | What it does |
|---|---|
| `rhizotrace samples` | copies the sample masks and photos into a folder, to try the package on |
| `rhizotrace traits` | measures every root in a folder of masks and writes the trait table |
| `rhizotrace segment` | turns a folder of photos into root masks |
| `rhizotrace depth` | stitches the levels of each tube and profiles traits by soil depth (experimental) |
| `rhizotrace stitch` | stitches the levels of each tube into one image |

`rhizotrace <command> --help` lists every option of a command. `rhizotrace --version`
prints the installed version.

## samples

```
rhizotrace samples [folder]
```

Copies the three sample masks and their photos into `folder/masks/` and `folder/photos/`
(default folder: `samples`). The masks are at 300 DPI, the default.

## traits

```
rhizotrace traits masks/ -o traits.csv --viz overviews/
```

Measures every mask in the folder and writes one table for all of them. See
[Output](output.md) for its rows and columns.

| Option | Default | |
|---|---|---|
| `folder` | | folder of masks, or of photos with `--segment` |
| `-o`, `--output` | `traits.csv` | the trait table |
| `--viz DIR` | off | also save an annotated overview image per mask into `DIR` |

Plus the [measurement settings](#measurement-settings) and the
[segmentation options](#segmentation-options).

## segment

```
rhizotrace segment photos/ -o masks/
```

Writes one mask PNG per photo. Needs `pip install "rhizotrace[segmentation]"` and the
model weights; see [Segment images into root masks](segmentation.md).

| Option | Default | |
|---|---|---|
| `folder` | | folder of photos |
| `-o`, `--output` | `masks` | folder for the masks |
| `--overwrite` | off | segment again photos whose mask already exists |

Plus `--device`, `--threshold` and `--weights` from the
[segmentation options](#segmentation-options).

## depth

Experimental; see [Depth profiles](depth.md).

```
rhizotrace depth masks/ --tube-info tubes.csv -o profiles.csv --overlay qc/
```

| Option | Default | |
|---|---|---|
| `folder` | | level masks, or photos with `--segment`: one folder with tube and level in the file names (`T462_L2`), one folder per tube, or one tube's `L1`, `L2`, ... files |
| `-o`, `--output` | `depth_profiles.csv` | the depth profiles |
| `--traits-output CSV` | off | also save the per-root traits measured on the stitched tubes |
| `--bin-mm` | 10 | depth bin size, in mm |
| `--overlay DIR` | off | save a check image per tube into `DIR` |
| `--tube-info CSV` | | per-tube offsets and angles: columns `tube_id`, `offset_cm`, optional `angle` |
| `--offset-cm`, `--angle` | | offset and insertion angle for tubes missing from `--tube-info` |
| `--images DIR` | | photos matching the masks, drawn under the overlays |
| `--session-pattern REGEX` | | separates sessions of the same tube; one regex group |

Plus the [measurement settings](#measurement-settings) and the
[segmentation options](#segmentation-options).

## stitch

```
rhizotrace stitch masks/ -o stitched/
```

Joins the levels of each tube into one image, `<tube>_stitched.png`.

| Option | Default | |
|---|---|---|
| `folder` | | folder of level images |
| `-o`, `--output` | `stitched` | output folder |
| `--photos` | off | the inputs are photos, not masks |
| `--dpi` | 300 | image resolution |
| `--session-pattern REGEX` | | as for `depth` |

## Measurement settings

Used by `traits` and `depth`.

| Option | Default | |
|---|---|---|
| `--dpi` | 300 | image resolution; never read from the file. See [Input masks](input_masks.md) |
| `--min-root-size` | 50 | ignore blobs smaller than this many pixels of area. See [Split mask into individual roots](split_roots.md) |
| `--min-root-length-mm` | 0.5 | ignore roots and branches shorter than this |
| `--spur-length-diameters` | 1.0 | prune spurs shorter than this many local diameters; 0 turns pruning off. See [Prune spurs](prune_spurs.md) |
| `--merge` | `angle` | how pieces are joined into branches: `angle`, `diameter` or `none`. See [Merge](merge.md) |
| `--merge-angle` | 30 | how far from straight, in degrees, two pieces can be and still join |
| `--root-selection` | `length` | which branch is the main root: `length`, `diameter`, `combined` or `connectivity`. See [Choose main root](main_root.md) |

Other settings are available only from Python; see [Python](python.md).

## Segmentation options

Used by `segment`, and by `traits` and `depth` with `--segment`.

| Option | Default | |
|---|---|---|
| `--segment` | off | (`traits`, `depth`) the inputs are photos: segment them first |
| `--masks DIR` | `masks/` next to the output | (`traits`, `depth`) where the segmented masks go |
| `--weights FILE` | `RHIZOTRACE_WEIGHTS` | the model weights file |
| `--device` | `auto` | `cpu`, `cuda`, or `auto` for a GPU when there is one |
| `--threshold` | 0.7735 | segmentation threshold. See [Threshold](segmentation.md#threshold) |
