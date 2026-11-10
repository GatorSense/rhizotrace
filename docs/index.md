**Work in progress.** These pages are being written step by step; some steps have no page yet.

# How rhizotrace measures roots

rhizotrace takes binary root masks from minirhizotron tubes or other root images, or
photos through an optional segmentation step, and measures the length, diameter and
orientation of every root in them. Most image analysis tools report one total per image.
rhizotrace instead splits each root into its main root and its lateral branches, without
any user input, and measures each part.

There are two ways in. If you have photos, they are first segmented into root masks. If
you already have masks, start at "Input: binary masks". From there, every mask goes
through the same steps.

```
             /  images  /
                   │
                   ▼
┌────────────────────────────────────┐
│   Segment images into root masks   │
└────────────────────────────────────┘
                   │
                   ▼
       /  Input: binary masks  /
                   │
                   ▼
┌────────────────────────────────────┐
│       Read and binarize mask       │
└────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────┐
│  Split mask into individual roots  │
└────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────┐
│         Measure each root          │ ──►  /  Optional: annotated overview image  /
└────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────┐
│         Build trait table          │
└────────────────────────────────────┘
                   │
                   ▼
       /  Output: traits.csv  /
```

Rectangles are steps, slanted boxes are data.

## Steps

1. [Segment images into root masks](segmentation.md), only when starting from photos.
2. [Input masks: read and binarize](input_masks.md): what a mask must look like.
3. [Split mask into individual roots](split_roots.md).
4. [Measure each root](measure_roots.md): skeleton, spur pruning, junctions, merging into
   branches, main root, and the length, diameter and angle of each part.
5. [Output: the trait table](output.md), and the optional overview image.

## Other pages

- [Running rhizotrace](usage.md): each task, in a terminal and in Python.
- [Settings](settings.md): every setting and its default.
