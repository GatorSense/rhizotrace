# rhizotrace

Measures roots in minirhizotron images. You give it binary root masks; it returns one
table with every root's length, diameter, angle, main axis and lateral branches (and,
if you ask for it, an annotated image per mask showing what was measured). If you only
have photos, an optional step segments them into masks first.

## Install

Python 3.10 or newer.

    pip install rhizotrace
    pip install "rhizotrace[segmentation]"   # also installs PyTorch, for photos

## Quick start

The package includes three sample images, each as a photo and its root mask:

    rhizotrace samples                                              # copies the sample images into samples/
    rhizotrace traits samples/masks -o traits.csv                   # measures the masks, writes the table
    rhizotrace traits samples/masks -o traits.csv --viz overviews   # optional: also saves a visualization of each mask's results

This takes a few seconds. The outputs:

- `traits.csv`: one row per measured object, 79 rows for these masks. The `image`
  column is the mask file name, `root` numbers the roots in that mask, and `type` says
  what the row is: `aggregated` (the whole root), `main_root` (its main axis) or
  `branch` (one lateral). Lengths and diameters are in millimeters.
- `overviews/`, with `--viz`: one image per mask. Each measured root is boxed and
  numbered with its `root` value. The main root is drawn in red, laterals in other
  colors, and root pixels that were too small to measure stay plain gray.

The sample masks were scanned at 300 DPI, which is the default. For your own images
pass the real value with `--dpi`; every length and diameter depends on it.

## Next steps

- [Your own masks](https://github.com/GatorSense/rhizotrace/blob/main/docs/input_masks.md): what a mask must look like, and the one setting you must get right.
- [Starting from photos](https://github.com/GatorSense/rhizotrace/blob/main/docs/segmentation.md): the segmentation model, its weights, and what hardware it needs.
- [Running rhizotrace](https://github.com/GatorSense/rhizotrace/blob/main/docs/usage.md): each task, in a terminal and in Python.
- [Settings](https://github.com/GatorSense/rhizotrace/blob/main/docs/settings.md): every setting and its default.
- [How the measurements are made](https://github.com/GatorSense/rhizotrace/blob/main/docs/index.md): the pipeline step by step.

Problems and questions: [GitHub Issues](https://github.com/GatorSense/rhizotrace/issues).

## Citing

A paper is in preparation. Until then, cite this repository and the version you used
(see `CITATION.cff` or the "Cite this repository" button on GitHub). If you use the
segmentation model, also cite Xu et al. (2020), listed in
[NOTICE](https://github.com/GatorSense/rhizotrace/blob/main/NOTICE).

## License

MPL-2.0. See [LICENSE](https://github.com/GatorSense/rhizotrace/blob/main/LICENSE) and
[NOTICE](https://github.com/GatorSense/rhizotrace/blob/main/NOTICE).
