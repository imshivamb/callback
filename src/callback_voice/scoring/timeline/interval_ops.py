from callback_voice.scoring.timeline.segment import Segment


def overlapping(segments: list[Segment], window: Segment) -> list[Segment]:
    """Segments that overlap ``window`` at all."""
    return [s for s in segments if s.overlap(window) > 0]


def intersect(a: list[Segment], b: list[Segment]) -> list[Segment]:
    """Pairwise intersections of two sorted, non-overlapping segment lists."""
    out: list[Segment] = []
    i = j = 0
    while i < len(a) and j < len(b):
        start, end = max(a[i].start_s, b[j].start_s), min(a[i].end_s, b[j].end_s)
        if end > start:
            out.append(Segment(start, end))
        if a[i].end_s < b[j].end_s:
            i += 1
        else:
            j += 1
    return out


def subtract(segments: list[Segment], holes: list[Segment]) -> list[Segment]:
    """``segments`` with every part covered by ``holes`` removed."""
    out: list[Segment] = []
    for seg in segments:
        pieces = [seg]
        for hole in holes:
            next_pieces: list[Segment] = []
            for p in pieces:
                if hole.end_s <= p.start_s or hole.start_s >= p.end_s:
                    next_pieces.append(p)
                    continue
                if hole.start_s > p.start_s:
                    next_pieces.append(Segment(p.start_s, hole.start_s))
                if hole.end_s < p.end_s:
                    next_pieces.append(Segment(hole.end_s, p.end_s))
            pieces = next_pieces
        out.extend(pieces)
    return out


def total(segments: list[Segment]) -> float:
    return sum(s.duration_s for s in segments)
