MM_PER_INCH = 25.4


def to_mm(px, dpi):
    return px * MM_PER_INCH / dpi


def to_px(mm, dpi):
    return mm * dpi / MM_PER_INCH
