# Segment images into root masks

This step is only needed when you start from photos rather than masks. It turns each photo
into a binary root mask with a UNet model, P-EnDe, from the PlantRootSeg project (Xu et
al., 2020). The model was pre-trained on peanut minirhizotron images and then fine-tuned
on switchgrass. On other species, cameras or soils, expect some errors in the masks. Look
at the masks before measuring them, try a different threshold, or clean the masks up
before running the rest of the pipeline.

## Install and weights

```
pip install "rhizotrace[segmentation]"
```

This adds PyTorch. The model weights (124 MB) are not part of the package. Download
`P-EnDe-model.pth` from the
[PlantRootSeg repository](https://github.com/GatorSense/PlantRootSeg/tree/master/Models)
([direct link](https://media.githubusercontent.com/media/GatorSense/PlantRootSeg/master/Models/P-EnDe-model.pth)),
then point at the file with `--weights` on the command line, `weights=` in Python, or the
`RHIZOTRACE_WEIGHTS` environment variable:

```
export RHIZOTRACE_WEIGHTS=/path/to/P-EnDe-model.pth
```

The file's SHA-256 is `0ad6298eb63508c09a6c3aa14fc0a715627425f992bf4ae552b03941ba4c5aaf`.
Cloning PlantRootSeg without Git LFS gives a small pointer file instead of the weights;
rhizotrace recognizes it and says so.

## Running it

From the command line:

```
rhizotrace segment photos/ -o masks/                  # photos to masks only
rhizotrace traits photos/ --segment -o traits.csv     # segment, then measure
```

With `--segment`, the masks are written to `masks/` next to the output file, or to the
folder given with `--masks`. `--device` picks `cpu` or `cuda` (default: a GPU if there is
one).

From Python:

```python
from rhizotrace import segmentation as seg

model = seg.load_segmenter("P-EnDe-model.pth", device="auto")
mask = model.segment(photo)                       # (H, W, 3) uint8 photo -> 255 = root
seg.segment_folder("photos/", "masks/", model)    # one mask PNG per photo
```

Masks are always written to disk. The expensive step runs once, you can look at the
masks, and reruns reuse them: a mask that already exists is not segmented again unless you
pass `--overwrite` to `rhizotrace segment` (`overwrite=True` in Python).

## Threshold

The model gives each pixel a root probability. The pixel is root when that value, after
scaling each image to the range 0 to 1, is above the threshold. The default is 0.7735, the
operating point of Xu et al. (2020). Change it with `--threshold` or
`load_segmenter(threshold=...)`. A lower threshold marks more pixels as root, a higher one
fewer. In Python, `normalize="none"` applies the threshold to the model's raw output
instead of the scaled one.

On 100 switchgrass reference masks from the PRMI dataset, the masks overlap the
references with a pooled Dice score of about 0.71 at the default threshold and 0.65 at
0.5 ([tools/evaluate_segmentation.py](https://github.com/GatorSense/rhizotrace/blob/main/tools/evaluate_segmentation.py)).
The best threshold for your images may differ.

## Hardware

The model runs on the whole image at once, so memory grows with image size: about 2.4 GB
of RAM or 2 GB of GPU memory per megapixel. Measured on one 2550 x 2160 image (5.5
megapixels):

| Device | Seconds per image | Peak memory |
|---|---|---|
| GPU (NVIDIA L4, 24 GB) | 0.8 | 9.3 GB GPU |
| CPU, 16 threads | 9.0 | 11.6 GB RAM |
| CPU, 4 threads | 16.6 | 11.6 GB RAM |

For full-size minirhizotron images, use a GPU with at least 12 GB (16 GB recommended; a
free Colab T4 works), or a machine with 32 GB of RAM (16 GB is borderline). Smaller or
cropped images run anywhere. Before each image, rhizotrace checks free memory with the
rule above and stops with a plain message instead of crashing part way through.

## After segmenting

The masks then go through the same steps as masks you bring yourself, starting with
[Input masks](input_masks.md). Two common clean-ups help:

- **Fill small holes.** A hole in a mask becomes a loop in the skeleton, which adds
  junctions and branches (see [Skeletonize](skeletonize.md)). rhizotrace does not fill
  holes.
- **Remove specks.** Small false detections are dropped anyway when they are below
  `min_root_size` pixels (see [Split mask into individual roots](split_roots.md)), but
  larger ones are measured as roots.

## References

Xu, W., Yu, G., Zare, A., Zurweller, B., Rowland, D. L., Reyes-Cabrera, J., Fritschi,
F. B., Matamala, R., & Juenger, T. E. (2020). Overcoming small minirhizotron datasets using
transfer learning. *Computers and Electronics in Agriculture*, 175, 105466.
https://doi.org/10.1016/j.compag.2020.105466
