# Length, diameter and angle

For each root, three things are measured on the whole skeleton, branches included:
length, diameter, and angle. These make the `aggregated` row of the output. Each branch
is later measured the same way, on its own part of the skeleton.

All three are computed in pixels and converted to millimeters with the image resolution
(see [Input masks](input_masks.md)). The output has both.

## Length

The skeleton is a chain of pixels, so its length comes from the steps between them.
Instead of counting every straight step as 1 and every diagonal step as √2, rhizotrace
also counts the corners where the path changes direction, and gives each a small negative
weight. Simple counting overestimates length, because a pixel line at most angles
zigzags between straight and diagonal steps. The corner weights remove most of that
excess.

Straight lines 200 px long, drawn at different angles, measured with each estimator:

| Angle | corner (default) | kulpa | chain_no_triangles | chain |
|---|---|---|---|---|
| 0° | -2.00% | -5.20% | 0.00% | 0.00% |
| 10° | +0.76% | +0.21% | +5.70% | +5.70% |
| 22.5° | -0.15% | +2.61% | +8.24% | +8.24% |
| 30° | -0.48% | +1.73% | +7.31% | +7.31% |
| 45° | -0.58% | -5.20% | 0.00% | 0.00% |

The `corner` weights were fitted to be accurate on average over all angles, so they are
slightly short at exactly 0° and close everywhere else.

- `corner`: Vossepoel and Smeulders (1982), in the form of Dorst and Smeulders (1987). The default.
- `kulpa`: Kulpa (1977).
- `chain_no_triangles`: straight steps 1, diagonal steps √2.
- `chain`: the same, and also counts diagonal shortcuts (see below).

<!-- TODO(verify): Vossepoel, A. M., & Smeulders, A. W. M. (1982). Vector code probability and metrication error in the representation of straight lines of finite length. Computer Graphics and Image Processing, 20(4), 347-364. -->
<!-- TODO(verify): Dorst, L., & Smeulders, A. W. M. (1987). Length estimators for digitized contours. Computer Vision, Graphics, and Image Processing, 40(3), 311-333. -->
<!-- TODO(verify): Kulpa, Z. (1977). Area and perimeter measurement of blobs in discrete binary pictures. Computer Graphics and Image Processing, 6(5), 434-451. -->

Choose one with `Config(length_estimator=...)` in Python.

**Diagonal shortcuts.** Thinning often leaves staircase steps where three pixels all touch
each other:

```
. # # . .
. . # # .
```

The path runs along the straight steps. The diagonal between the first and third pixel
is a shortcut that is not part of the path. Counting every touching pair measures this
4-pixel step as 5.83 px. Dropping the shortcuts measures it as 3.0 px. Every estimator
except `chain` drops them.

**Tips.** The skeleton stops about one root radius before each tip
(see [Skeletonize](skeletonize.md)), so a root's length comes out about one diameter short.

## Diameter

At every skeleton pixel, the diameter is twice the distance to the nearest background
pixel. The skeleton runs down the middle of the root, so that distance is the root's
radius there. The root's diameter is the mean of these values along the skeleton. The
output also gives their median and standard deviation.

Distances are measured between pixel centers, so a root with an odd width in pixels reads
one pixel thicker than it is:

| True width (px) | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Measured diameter (px) | 2 | 2 | 4 | 4 | 6 | 6 | 8 | 8 | 10 | 10 |

This is negligible on thick roots and large on very thin ones: a 3 px root reads 33% too
thick.

## Angle

The angle is the direction of the root's long axis: the direction in which its skeleton
pixels spread the most (principal component analysis of their positions). It is measured
from the image's horizontal, counterclockwise, and runs from 0 to 180 degrees.

| Shape | Angle |
|---|---|
| horizontal | 0 |
| bottom-left to top-right | 45 |
| vertical | 90 |
| top-left to bottom-right | 135 |

The angle is an axis, not a direction: a root at 30 degrees and one at 210 degrees are the
same root. For a curved or heavily branched root it gives the overall trend, not any
local direction.

## Length per width

The `aggregated` row also reports `length_per_width`: total length divided by mean
diameter. A root is long and thin, so this runs to tens or hundreds. A compact blob that
is not a root gives only a few.

## Output columns

| Column | Meaning |
|---|---|
| `length_mm`, `length` | skeleton length, mm and px |
| `avg_diameter_mm`, `avg_diameter` | mean diameter along the skeleton |
| `diameter_median_mm`, `diameter_median` | median diameter along the skeleton |
| `diameter_std_mm`, `diameter_std` | standard deviation of the diameter |
| `angle` | long axis, degrees in [0, 180) |
| `length_per_width` | length over mean diameter, `aggregated` row only |
