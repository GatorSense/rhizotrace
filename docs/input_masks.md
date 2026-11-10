# Input masks

If you already have root masks, they need to meet a few requirements. A mask that does
not meet them does not raise an error. It gives misleading results instead.

## Requirements

1. **Roots are bright on a dark background.** Brightness decides what counts as root.
   Binary masks are handled automatically: any mask with exactly two values (0 and 1,
   0 and 255, 0 and 65535) takes the brighter value as root. A mask with dark roots on
   a white background is read inverted, so the background is measured as roots.
2. **Grayscale masks are thresholded at the midpoint.** A pixel with a gray value of 128
   or more (out of 255) is root, anything darker is background. Color images are
   converted to grayscale first. To change the threshold, use
   `Config(mask_threshold=...)` in Python, as a fraction between 0 and 1. The default
   is 0.5.
3. **Use a lossless format.** PNG or TIFF is recommended. JPEG is accepted, but its
   compression changes pixel values near edges, which can shift root boundaries.
4. **Set the resolution.** rhizotrace does not read DPI from the image file. Pass it
   with `--dpi` on the command line or `Config(dpi=...)` in Python. The default is
   300. Every length and diameter is converted from pixels to millimeters with this
   value, so a wrong DPI scales every result. A 150 DPI image run at the default gives
   lengths and diameters half their true size.

## Files

- Accepted formats: `.png`, `.tif`, `.tiff`, `.jpg`, `.jpeg`, `.bmp`.
- All masks go in one folder. Subfolders are not searched, and hidden files are skipped.
- Files are processed in name order.
- Each file's name, without its extension, becomes the `image` column of the output.

## What happens on reading

Each mask is read, converted to grayscale, and binarized as described above. The result
has two values: 255 for root and 0 for background. This binary mask is what the next
step, [Split mask into individual roots](split_roots.md), works on.

---

← [Segment images into root masks](segmentation.md) · [Overview](index.md) · [Split mask into individual roots](split_roots.md) →
