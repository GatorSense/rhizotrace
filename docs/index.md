**Work in progress.** These pages are being written step by step; some steps have no page yet.

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
