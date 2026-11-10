# Measure each root

Each root found in a mask is measured on its own. Its shape is first thinned to a skeleton,
a line one pixel wide down its middle. False twigs are pruned from the skeleton, and it is
cut where it splits. The pieces are then joined back into branches, and one branch is
chosen as the main root. Length, diameter and angle are measured for the whole root, the
main root and each branch.

```
          /  One root (cutout)  /
                     │
                     ▼
┌────────────────────────────────────────┐
│  Skeletonize: thin to a 1-pixel line   │
└────────────────────────────────────────┘
                     │
          too short? ──► dropped
                     │ no
                     ▼
┌────────────────────────────────────────┐
│ Measure root thickness at every pixel  │
└────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────┐
│      Prune spurs (on by default)       │
└────────────────────────────────────────┘
                     │
      too short now? ──► dropped
                     │ no
                     ▼
┌────────────────────────────────────────┐
│      Split skeleton at junctions       │
│     (runs inside pruning when on)      │
└────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────┐
│           Measure whole root           │ ──►  /  aggregated row  /
└────────────────────────────────────────┘
                     │
     only one piece? ──► done: whole root is the main root
                     │ no
                     ▼
┌────────────────────────────────────────┐
│       Merge pieces into branches       │
└────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────┐
│          Measure each branch           │ ──►  short branches dropped
└────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────┐
│            Choose main root            │
└────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────┐
│        Measure insertion angles        │
│            of the laterals             │
└────────────────────────────────────────┘
                     │
                     ▼
      /  main_root and branch rows  /
```

Rectangles are steps, slanted boxes are data. A root is dropped when its skeleton is shorter
than `min_root_length_mm` (0.5 mm by default), before or after spur pruning.

## Steps

1. [Skeletonize: thin to a 1-pixel line](skeletonize.md)
2. [Measure root thickness at every pixel](measurements.md#diameter)
3. [Prune spurs](prune_spurs.md)
4. [Split skeleton at junctions](split_junctions.md)
5. [Measure whole root](measurements.md): length, diameter and angle
6. [Merge pieces into branches](merge.md)
7. [Measure each branch](measurements.md#branches)
8. [Choose main root](main_root.md)
9. [Measure insertion angles](main_root.md#insertion-angle)

The results go into the [trait table](output.md).

---

← [Split mask into individual roots](split_roots.md) · [Overview](index.md) · [Skeletonize](skeletonize.md) →
