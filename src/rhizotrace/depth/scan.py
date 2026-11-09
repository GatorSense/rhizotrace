"""Finding tubes and levels on disk and reporting what is there before any processing."""

import os
import re
from dataclasses import dataclass, field

from ..config import TubeInfo, load_tube_info
from ..io import list_images

# "L" and digits not embedded in a longer alphanumeric token: L1.png, _L05_, but not SOIL2.
LEVEL_PATTERN = r"(?<![A-Za-z0-9])L(\d+)(?![0-9])"
TUBE_PATTERN = r"(?<![A-Za-z0-9])(T\d+)(?![0-9])"


@dataclass
class Tube:
    name: str                       # grouping key (tube id, or tube id + session, or folder name)
    tube_id: str                    # key into the tube-info CSV
    masks: dict = field(default_factory=dict)    # level -> mask path
    images: dict = field(default_factory=dict)   # level -> photo path
    info: TubeInfo = None

    @property
    def levels(self):
        return sorted(set(self.masks) | set(self.images))

    @property
    def missing_levels(self):
        present = set(self.levels)
        return [n for n in range(1, max(present) + 1) if n not in present] if present else []


@dataclass
class TubeSet:
    tubes: dict
    unparsed: list = field(default_factory=list)      # files with no tube/level token
    duplicates: list = field(default_factory=list)    # (tube, level, path) seen more than once

    def __getitem__(self, name):
        return self.tubes[name]

    def __iter__(self):
        return iter(self.tubes.values())

    def __len__(self):
        return len(self.tubes)

    def report(self):
        lines = [f"{len(self.tubes)} tube(s)"]
        for tube in self.tubes.values():
            what = "masks" if tube.masks else "images"
            if tube.masks and tube.images:
                what = "masks + images"
            line = f"  {tube.name}: levels {tube.levels} ({what})"
            if tube.missing_levels:
                line += f", MISSING {tube.missing_levels}"
            if tube.info is None:
                line += ", no tube info (offset/angle)"
            lines.append(line)
        if self.duplicates:
            lines.append(f"  {len(self.duplicates)} duplicate level file(s) ignored (same tube and level); "
                         "use session_pattern or one folder per tube")
        if self.unparsed:
            lines.append(f"  {len(self.unparsed)} file(s) skipped: no tube/level token in the name")
        return "\n".join(lines)

    def __repr__(self):
        return self.report()


def _discover(folder, tube_pattern, level_pattern, session_pattern):
    """{group name: (tube_id, {level: path})} plus unparsed files and duplicates."""
    groups, unparsed, duplicates = {}, [], []

    def add(name, tube_id, level, path):
        _, levels = groups.setdefault(name, (tube_id, {}))
        if level in levels:
            duplicates.append((name, level, path))
        else:
            levels[level] = path

    folder = os.path.normpath(folder)
    files = list_images(folder)
    subdirs = sorted(d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d)))
    levels_only = []
    for path in files:
        base = os.path.basename(path)
        level, tube = re.search(level_pattern, base), re.search(tube_pattern, base)
        if level and not tube:
            levels_only.append((int(level.group(1)), path))
            continue
        if not level:
            unparsed.append(path)
            continue
        name = tube.group(1)
        if session_pattern:
            session = re.search(session_pattern, base)
            if session:
                name = f"{name}_{session.group(1)}"
        add(name, tube.group(1), int(level.group(1)), path)
    if not groups and levels_only:
        # The folder itself is one tube: L1.png, L2.png, ...
        d = os.path.basename(folder)
        tube = re.search(tube_pattern, d)
        for level, path in levels_only:
            add(d, tube.group(1) if tube else d, level, path)
    elif levels_only:
        unparsed += [p for _, p in levels_only]
    if not groups:
        for d in subdirs:
            tube = re.search(tube_pattern, d)
            for path in list_images(os.path.join(folder, d)):
                level = re.search(level_pattern, os.path.basename(path))
                if level:
                    add(d, tube.group(1) if tube else d, int(level.group(1)), path)
                else:
                    unparsed.append(path)
    return groups, unparsed, duplicates


def scan_tubes(masks=None, images=None, tube_info=None, tube_pattern=TUBE_PATTERN,
               level_pattern=LEVEL_PATTERN, session_pattern=None):
    """Inventory tubes from a folder of masks and/or a folder of photos.

    Files are grouped by the tube token in their names (flat folder), or by subfolder
    when the folder holds one directory per tube. tube_info is a CSV path or
    {tube_id: TubeInfo}. Print the result to see levels, gaps, and missing info.
    """
    if masks is None and images is None:
        raise ValueError("give a masks folder, an images folder, or both")
    if isinstance(tube_info, (str, os.PathLike)):
        tube_info = load_tube_info(tube_info)
    tube_info = tube_info or {}

    tubes, unparsed, duplicates = {}, [], []
    for kind, folder in (("masks", masks), ("images", images)):
        if folder is None:
            continue
        groups, bad, dup = _discover(str(folder), tube_pattern, level_pattern, session_pattern)
        unparsed += bad
        duplicates += dup
        for name, (tube_id, levels) in groups.items():
            tube = tubes.setdefault(name, Tube(name, tube_id))
            setattr(tube, kind, dict(sorted(levels.items())))
    for tube in tubes.values():
        tube.info = tube_info.get(tube.tube_id) or tube_info.get(tube.name)
    return TubeSet(dict(sorted(tubes.items())), unparsed, duplicates)
