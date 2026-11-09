# Split mask into individual roots

Every mask is split into individual roots with connected component labeling from
SciPy ([`scipy.ndimage.label`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.label.html);
Virtanen et al., 2020). <!-- TODO(verify): Virtanen et al. 2020, Nature Methods 17, 261-272 -->
A blob is a group of root pixels connected to each other. Labeling gives every pixel
in a blob the same number, and each blob a different number. Small blobs are dropped.
Each remaining blob is then cut out of the mask and passed on to be measured on its own.

## What counts as one root

One blob is one root in the output. Two root pixels belong to the same blob when you can
walk from one to the other through root pixels, stepping up, down, left, or right.
Diagonal steps do not count.

```
mask                 labels
1 1 0 0 0 0          1 1 0 0 0 0
1 1 0 0 1 0          1 1 0 0 2 0
0 0 1 0 1 0          0 0 3 0 2 0
0 0 0 0 1 1          0 0 0 0 2 2
0 1 0 0 0 0          0 4 0 0 0 0
```

The pixel labeled 3 touches blob 1 only at a corner, so it is a separate root.

Two consequences:

- Roots that touch only at a corner are measured as separate roots.
- Roots that touch or cross along an edge form one blob, and are measured as one root.

## Small blobs are dropped

Blobs with fewer than `min_root_size` pixels of area are ignored. The default is 50.
Set it with `--min-root-size` on the command line or `Config(min_root_size=...)` in Python.

This threshold is in pixels, not millimeters, so the physical size it removes depends on
image resolution. At 300 DPI, 50 pixels is about 0.36 mm². At 150 DPI it is about 1.43 mm².
Adjust it when your images are not at 300 DPI.

A root can also be dropped later for being too short. That filter is in millimeters and
is described in [Measure each root](measure_roots.md).

## Each root is measured on its own

Each root is cut out as a rectangle around it, with a small margin. Any part of another
root that falls inside that rectangle is removed from the cutout. A neighboring root
therefore never affects the measurements of another.
