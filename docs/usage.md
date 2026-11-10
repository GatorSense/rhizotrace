# Running rhizotrace

Each task below shows the command to type in a terminal and the same in Python, for a
script or a Jupyter notebook. Use whichever you prefer; the results are the same. The
Python lines assume `import rhizotrace as rp`. In a notebook, a terminal command also runs
in a cell with `!` in front of it, such as `!rhizotrace samples`.

## Try it on the sample images

The package includes three sample root masks and the photos they came from, at 300 DPI.
They are a quick way to check that everything works and to see what the output looks
like before running your own images. Measuring them takes a few seconds.

**Terminal**

```bash
rhizotrace samples                          # copies them into samples/masks and samples/photos
rhizotrace traits samples/masks -o traits.csv
```

**Python** (a script or a Jupyter notebook)

```python
masks = rp.sample_masks()                   # folder of the sample masks
table = rp.analyze_folder(masks, rp.Config(dpi=300))
```

The table has 79 rows: every root in the three masks, its main root, and its branches.

## Measure a folder of masks

This is the main task. rhizotrace reads every mask in the folder, finds each root, and
measures it. The result is one table for all masks, with an `image` column naming the mask
each row came from. [Output](output.md) explains its rows and columns.

Before running your own masks, check [Input masks](input_masks.md): roots must be bright
on a dark background, and the resolution must be given with `--dpi` or `Config(dpi=...)`,
because it is never read from the files.

**Terminal**

```bash
rhizotrace traits masks/ -o traits.csv --dpi 300
```

**Python**

```python
table = rp.analyze_folder("masks/", rp.Config(dpi=300))
table.to_csv("traits.csv", index=False)
```

## Measure one mask

In Python you can also measure a single mask, for example to try settings on one image
before running a whole folder. `image` fills the table's `image` column.

**Python**

```python
mask = rp.load_mask("masks/T462_L2.png")
table = rp.extract_traits(mask, rp.Config(dpi=300), image="T462_L2")
```

## Change a setting

Every setting has a default, so only the ones you want to change need to be given. On the
command line a setting is an option; in Python it is a keyword of `Config`. This example
drops roots shorter than 1 mm and turns spur pruning off.

**Terminal**

```bash
rhizotrace traits masks/ -o traits.csv --min-root-length-mm 1 --spur-length-diameters 0
```

**Python**

```python
cfg = rp.Config(dpi=300, min_root_length_mm=1, spur_length_diameters=0)
table = rp.analyze_folder("masks/", cfg)
```

[Settings](settings.md) lists every setting, its default, and what it changes.

## Visualize the results

An overview image shows what rhizotrace measured in a mask: each root it found is boxed
and numbered with its `root` value in the table, its main root is drawn in red and its
branches in other colors. Gray areas without a box were too small or too short to
measure. Looking at a few of these is the quickest way to check the results. See
[Overview image](output.md#overview-image) for an example.

**Terminal**

```bash
rhizotrace traits masks/ -o traits.csv --viz overviews/
```

This saves `<mask>_overview.png` for every mask into `overviews/`.

**Python**

```python
from rhizotrace import viz

roots = rp.extract_roots(mask, cfg)
ax = viz.plot_overview(mask, roots)          # the same overview image
ax.figure.savefig("overview.png", dpi=150)
viz.plot_root(roots[0], dpi=cfg.dpi)         # one root up close, with its traits in the title
```

## Start from photos

If you have photos rather than masks, rhizotrace can segment them into masks first, with
a model trained on minirhizotron images. This needs the segmentation extra,
`pip install "rhizotrace[segmentation]"`, and the model weights; see
[Segment images into root masks](segmentation.md). Look at the masks before trusting the
measurements: the model makes mistakes on images unlike the ones it was trained on.

**Terminal**

```bash
rhizotrace traits photos/ --segment --weights P-EnDe-model.pth -o traits.csv
```

The masks are written to `masks/` next to `traits.csv` and then measured. To segment
without measuring, use `rhizotrace segment photos/ -o masks/`.

**Python**

```python
from rhizotrace import segmentation as seg

model = seg.load_segmenter("P-EnDe-model.pth")
seg.segment_folder("photos/", "masks/", model)
table = rp.analyze_folder("masks/", rp.Config(dpi=300))
```

## Profile roots by depth along a tube

For minirhizotron tubes imaged in several levels, rhizotrace can join the levels of each
tube into one image and report root length and diameter by soil depth. This is
experimental: `rhizotrace depth` and `rhizotrace stitch`. See [Depth profiles](depth.md).

## Command options

Besides the [settings](settings.md), each command has a few options of its own, mostly
for where its input and output go. `rhizotrace <command> --help` lists them all.

| Command | Option | Default | |
|---|---|---|---|
| `samples` | `folder` | `samples` | where the samples are copied |
| `traits` | `folder` | | folder of masks, or of photos with `--segment` |
| | `-o`, `--output` | `traits.csv` | the trait table |
| | `--viz DIR` | off | also save an overview image per mask |
| | `--segment` | off | the inputs are photos: segment them first |
| | `--masks DIR` | `masks/` next to the output | where segmented masks go |
| `segment` | `folder` | | folder of photos |
| | `-o`, `--output` | `masks` | folder for the masks |
| | `--overwrite` | off | segment again photos whose mask already exists |

`depth` and `stitch` are covered on [Depth profiles](depth.md).

## Working with the results in code

The table is enough for most analyses. If you need more, such as the skeleton of a root or
the pixels of each branch, `extract_roots` returns the objects behind the table, one per
root:

**Python**

```python
roots = rp.extract_roots(mask, cfg)
root = roots[0]
root.aggregated         # the whole root
root.main_root          # its main root
root.branches           # its laterals, a list
root.bbox               # where it is in the mask: (min_row, max_row, min_col, max_col)
```

`aggregated`, `main_root` and each branch carry the same measurements, in pixels:
`length`, `avg_diameter`, `angle`, `diameter_values` (one per skeleton pixel) and
`skeleton_rc`, the skeleton pixels as (row, column) within the root's crop. Branches also
carry `insertion_angle`. `rp.units.to_mm(value, dpi)` converts pixels to millimeters, and
`rp.roots_to_frame(roots, dpi)` turns the roots into the table.
