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
