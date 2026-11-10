"""Recombining skeleton pieces into branches, choosing the main root, insertion angles."""

from collections import deque
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

from .skeleton import order_pixels


@dataclass
class Branch:
    """A recombined skeleton path."""

    id: int
    pixels: list                    # ordered (row, col)
    merged_from: list               # original piece labels


@dataclass
class _Segment:
    """A skeleton piece, an edge of the junction graph.

    Its two ends are 'a' (first pixel of the ordered path) and 'b' (last pixel). Each end
    has an inward direction, pointing from that end into the piece, and the junction it
    touches, or None at a root tip.
    """

    id: int
    pixels: list
    direction_a: np.ndarray = None  # unit vector pointing into the segment from each end
    direction_b: np.ndarray = None
    junction_a: int = None          # junction id at each end, None = root tip
    junction_b: int = None
    merged_from: list = None

    def __post_init__(self):
        if not self.merged_from:
            self.merged_from = [self.id]

    def has_tip(self):
        return self.junction_a is None or self.junction_b is None


@dataclass
class _Junction:
    """A junction region, a node of the graph. connections names every piece end touching it."""

    id: int
    pixels: np.ndarray                          # (N, 2)
    connections: list = field(default_factory=list)  # (segment id, 'a' | 'b')


def _direction(pixels, end, k, mode):
    """Unit vector pointing into the path from one end ('a' = start, 'b' = end).

    endpoint: the straight line to the other end. local: the first k pixels from this end.
    hybrid: endpoint, unless it differs from local by more than 45 degrees.
    """
    if len(pixels) < 2:
        return np.array([0.0, 1.0])
    k = max(min(k, len(pixels) // 4, len(pixels) - 1), 1)
    p0, p1 = np.array(pixels[0]), np.array(pixels[-1])
    overall = p1 - p0 if end == "a" else p0 - p1
    local = (np.array(pixels[k]) - p0) if end == "a" else (np.array(pixels[-k - 1]) - p1)
    if mode == "endpoint":
        direction = overall
    elif mode == "local":
        direction = local
    else:
        o_norm, l_norm = np.linalg.norm(overall), np.linalg.norm(local)
        if o_norm < 1e-10 or l_norm < 1e-10:
            direction = local if l_norm >= o_norm else overall
        else:
            cos_a = np.dot(overall / o_norm, local / l_norm)
            direction = overall if np.degrees(np.arccos(np.clip(cos_a, -1, 1))) <= 45.0 else local
    norm = np.linalg.norm(direction)
    return direction / norm if norm >= 1e-10 else np.array([0.0, 1.0])


def _nearest_junction(j_labels, point, prox):
    """Lowest-id junction within Chebyshev distance prox of point, nearest first."""
    r, c = point
    for d in range(prox + 1):
        window = j_labels[max(0, r - d):r + d + 1, max(0, c - d):c + d + 1]
        hits = window[window > 0]
        if len(hits):
            return int(hits.min())
    return None


def _build(labeled, junction_mask, cfg):
    """The junction graph: segments (one per labeled piece) and junctions (one per region).

    Each segment end is linked to the nearest junction within junction_proximity_threshold
    pixels, in both directions: the segment records the junction at each end, and the
    junction records (segment id, end). An end with no junction that close is a root tip.
    """
    j_labels, _ = ndimage.label(junction_mask)
    junctions = {}
    for j, sl in enumerate(ndimage.find_objects(j_labels), start=1):
        if sl is not None:
            pixels = np.argwhere(j_labels[sl] == j) + [sl[0].start, sl[1].start]
            junctions[j] = _Junction(j, pixels)

    segments = {}
    prox = cfg.junction_proximity_threshold
    for label, sl in enumerate(ndimage.find_objects(labeled), start=1):
        if sl is None or label < 2:
            continue
        r0, c0 = sl[0].start, sl[1].start
        path = [(r + r0, c + c0) for r, c in order_pixels(labeled[sl] == label)]
        if len(path) < 2:
            continue
        seg = _Segment(int(label), path)
        seg.direction_a = _direction(path, "a", cfg.local_k, cfg.angle_mode)
        seg.direction_b = _direction(path, "b", cfg.local_k, cfg.angle_mode)
        for end, point in (("a", path[0]), ("b", path[-1])):
            j = _nearest_junction(j_labels, point, prox)
            if j is not None:
                setattr(seg, f"junction_{end}", j)
                junctions[j].connections.append((seg.id, end))
        segments[seg.id] = seg
    return segments, junctions


def _merge_angle(seg1, end1, seg2, end2):
    """Continuation angle at a shared junction, 180 = perfectly aligned.

    Each segment uses the direction of the end that touches the junction, so both vectors
    point away from it whichever way the segments were ordered. A root running straight
    through the junction gives two opposite vectors: 180 degrees.
    """
    d1 = seg1.direction_a if end1 == "a" else seg1.direction_b
    d2 = seg2.direction_a if end2 == "a" else seg2.direction_b
    return float(np.degrees(np.arccos(np.clip(np.dot(d1, d2), -1, 1))))


def _join(seg1, end1, seg2, end2, new_id, cfg):
    """One segment from two that meet at a junction: seg1 then seg2, keeping the far ends."""
    # orient seg1 to end at the junction and seg2 to start there
    pixels1 = list(seg1.pixels) if end1 == "b" else list(seg1.pixels[::-1])
    pixels2 = list(seg2.pixels) if end2 == "a" else list(seg2.pixels[::-1])
    combined = pixels1 + pixels2[1:] if len(pixels2) > 1 else pixels1
    merged = _Segment(new_id, combined, merged_from=seg1.merged_from + seg2.merged_from)
    # the new ends are the far ends of the two segments, with their junctions
    merged.junction_a = seg1.junction_b if end1 == "a" else seg1.junction_a
    merged.junction_b = seg2.junction_a if end2 == "b" else seg2.junction_b
    merged.direction_a = _direction(combined, "a", cfg.local_k, cfg.angle_mode)
    merged.direction_b = _direction(combined, "b", cfg.local_k, cfg.angle_mode)
    return merged


def merge_by_angle(labeled, junction_mask, cfg):
    """Join pieces that continue straight through a junction, working inward from root tips.

    Each junction is decided once. Its pairs of pieces are joined straightest first, each
    piece at most once there. A pair joins when its angle is within merge_angle_threshold
    of straight (180 degrees), or, when only two pieces meet, when it is at least
    force_merge_min_angle. A joined piece goes back in the queue while it still reaches
    an undecided junction.
    """
    segments, junctions = _build(labeled, junction_mask, cfg)
    if not segments:
        return []

    active = dict(segments)       # segments not yet absorbed into a join
    processed = set()             # junctions already decided
    next_id = max(active) + 1
    min_angle = 180 - cfg.merge_angle_threshold

    # start from the pieces that end in a root tip; a root that is all loops has none
    queue = deque(s.id for s in active.values() if s.has_tip()) or deque(active)
    while queue:
        sid = queue.popleft()
        if sid not in active:
            continue              # already joined into another segment
        current = active[sid]
        for j_id in (current.junction_a, current.junction_b):
            if j_id is None or j_id in processed:
                continue
            junction = junctions[j_id]
            here = [(s, e) for s, e in junction.connections if s in active]
            if len(here) < 2:
                processed.add(j_id)
                continue
            is_deg2 = len(here) == 2

            # continuation angle of every pair of pieces at this junction
            angles = {}
            for i in range(len(here)):
                for k in range(i + 1, len(here)):
                    (s1, e1), (s2, e2) = here[i], here[k]
                    if s1 != s2:
                        angles[(s1, s2)] = (_merge_angle(active[s1], e1, active[s2], e2), e1, e2)

            # straightest pair first; a piece joins at most once at this junction
            merged_here = set()
            for (s1, s2), (angle, e1, e2) in sorted(angles.items(), key=lambda x: -x[1][0]):
                if s1 in merged_here or s2 in merged_here or s1 not in active or s2 not in active:
                    continue
                if is_deg2 and cfg.force_merge_degree_2:
                    # only two pieces meet: a bend in one root, joined unless sharper than the floor
                    do_merge = angle >= cfg.force_merge_min_angle
                else:
                    do_merge = angle >= min_angle
                if not do_merge:
                    continue

                new = _join(active[s1], e1, active[s2], e2, next_id, cfg)
                next_id += 1
                # every junction the two pieces touched now lists the joined piece instead
                # (dict.fromkeys drops duplicates in a fixed order, so results do not vary)
                touched = {j for s in (active[s1], active[s2]) for j in (s.junction_a, s.junction_b)
                           if j is not None}
                del active[s1], active[s2]
                active[new.id] = new
                for jj_id in sorted(touched):
                    jj = junctions[jj_id]
                    updated = []
                    for cs, ce in jj.connections:
                        if cs in (s1, s2):
                            new_end = "a" if new.junction_a == jj_id else ("b" if new.junction_b == jj_id else None)
                            if new_end:
                                updated.append((new.id, new_end))
                        else:
                            updated.append((cs, ce))
                    jj.connections = list(dict.fromkeys(updated))
                # the joined piece is decided again at any junction still open at its ends
                for j_next in (new.junction_a, new.junction_b):
                    if j_next is not None and j_next not in processed:
                        queue.append(new.id)
                merged_here.update((s1, s2))
            processed.add(j_id)

    return [Branch(s.id, s.pixels, s.merged_from) for s in active.values()]


def merge_by_diameter(pieces, junction_mask, cfg):
    """Join pieces at a junction when their diameters and directions are similar.

    pieces: list of dicts with id, pixels, avg_diameter.
    """
    dilated = ndimage.binary_dilation(junction_mask, structure=np.ones((3, 3)), iterations=2)
    j_labels, n_junctions = ndimage.label(dilated, structure=np.ones((3, 3)))

    segments = [dict(p, merged_from=[p["id"]]) for p in pieces]
    for j in range(1, n_junctions + 1):
        j_pixels = set(map(tuple, np.argwhere(j_labels == j)))
        connected = [i for i, s in enumerate(segments) if s is not None and set(s["pixels"]) & j_pixels]
        if len(connected) < 2:
            continue
        connected.sort(key=lambda i: segments[i]["avg_diameter"], reverse=True)

        done = False
        for a in range(len(connected)):
            for b in range(a + 1, len(connected)):
                s1, s2 = segments[connected[a]], segments[connected[b]]
                d1, d2 = s1["avg_diameter"], s2["avg_diameter"]
                if max(d1, d2) < 1e-5:
                    continue
                sk1, sk2 = np.array(s1["pixels"]), np.array(s2["pixels"])
                if len(sk1) < 2 or len(sk2) < 2:
                    continue
                a1 = np.mean(np.degrees(np.arctan2(np.gradient(sk1[:, 1]), np.gradient(sk1[:, 0]))) % 360)
                a2 = np.mean(np.degrees(np.arctan2(np.gradient(sk2[:, 1]), np.gradient(sk2[:, 0]))) % 360)
                angle_diff = abs((a1 % 180) - (a2 % 180)) % 180
                if abs(d1 - d2) / max(d1, d2) <= cfg.diameter_ratio_threshold and angle_diff <= cfg.merge_angle_threshold:
                    segments[connected[a]] = {
                        "id": s1["id"], "pixels": s1["pixels"] + s2["pixels"],
                        "avg_diameter": (d1 + d2) / 2.0,
                        "merged_from": s1["merged_from"] + s2["merged_from"],
                    }
                    segments[connected[b]] = None
                    done = True
                    break
            if done:
                break

    return [Branch(s["id"], s["pixels"], s["merged_from"]) for s in segments if s is not None]


def select_main_root(lengths, diameters, connectivity, method, length_weight=0.7, diameter_weight=0.3):
    """Index of the main root among branches described by parallel lists."""
    if len(lengths) == 1:
        return 0
    if method == "length":
        return int(np.argmax(lengths))
    if method == "diameter":
        return int(np.argmax(diameters))
    if method == "connectivity":
        return int(np.argmax(connectivity))
    lengths, diameters = np.asarray(lengths, float), np.asarray(diameters, float)
    l_max = lengths.max() if lengths.max() > 0 else 1.0
    d_max = diameters.max() if diameters.max() > 0 else 1.0
    return int(np.argmax(length_weight * lengths / l_max + diameter_weight * diameters / d_max))


N_INSERTION = 10


def insertion_angle(main_path, branch_path):
    """Angle (deg) between a lateral's departure direction and the main root near the junction."""
    main = np.asarray(main_path)
    branch = np.asarray(branch_path)
    if len(branch) < 3 or len(main) < 3:
        return None
    d_start = np.min(np.sum((main - branch[0]) ** 2, axis=1))
    d_end = np.min(np.sum((main - branch[-1]) ** 2, axis=1))
    seg = branch[:N_INSERTION] if d_start <= d_end else branch[-N_INSERTION:][::-1]

    def mean_dir(pts):
        rads = np.arctan2(np.gradient(pts[:, 1].astype(float)), np.gradient(pts[:, 0].astype(float)))
        return np.arctan2(np.mean(np.sin(rads)), np.mean(np.cos(rads)))

    closest = int(np.argmin(np.sum((main - seg[0]) ** 2, axis=1)))
    half = N_INSERTION // 2
    main_seg = main[max(0, closest - half):min(len(main), closest + half)]
    if len(main_seg) < 2:
        return None
    diff = abs(np.degrees(mean_dir(seg)) - np.degrees(mean_dir(main_seg))) % 360
    return float(min(diff, 360 - diff))
