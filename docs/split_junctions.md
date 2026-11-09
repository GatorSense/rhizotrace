# Split skeleton at junctions

To get the individual branches of a root, the skeleton is first cut where it splits.
Each skeleton pixel is checked against its 8 neighbors. A pixel is a junction when its
neighbors match one of a fixed list of 44 patterns: T, Y and X shapes and their
rotations, the places where the line splits into arms. The junctions are then widened
and removed, which cuts the skeleton into separate pieces.

The pieces are not branches yet. A root that runs straight through a junction is cut
there too, so [merging](measure_roots.md) later joins pieces back into branches.

When [spur pruning](prune_spurs.md) is on, this step runs inside every pruning pass.

```
              /  Skeleton  /
                     │
                     ▼
┌────────────────────────────────────────┐
│          Find junction pixels          │
│       (match neighbor patterns)        │
└────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────┐
│    Widen each junction by one pixel    │
└────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────┐
│      Remove the widened junctions      │
└────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────┐
│      Number the remaining pieces       │
└────────────────────────────────────────┘
                     │
                     ▼
      /  Pieces + junction regions  /
```

## Why the junctions are widened

Removing only the junction pixel does not cut the skeleton. The arms still touch each
other diagonally, and pieces are counted with diagonal contact as connected:

```
skeleton            junction pixel removed     widened, then removed
1 1 1 1 1 1 1       1 1 1 . 1 1 1              2 2 . . . 3 3
      1                   1                          .
      1                   1                          4
      1                   1                          4
```

Removing only the junction pixel leaves one piece (middle). Widening the junction by one
pixel first, to the junction and its four direct neighbors, leaves three separate pieces
(right).

The width is set with `Config(junction_dilation_iterations=...)` in Python. The default
is 1.

## What the pieces leave out

The removed junction pixels belong to no piece. The length of each branch therefore
leaves out its junction region, while the whole-root length includes it. The branch
lengths of a root add up to slightly less than its total length.
