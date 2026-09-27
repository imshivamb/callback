from dataclasses import dataclass

from callback_voice.text.edit_distance import edit_distance

_MAX_EDITS = 2


@dataclass(frozen=True, slots=True)
class NearMiss:
    """A value that is almost the expected one.

    ``partial`` means characters are missing or extra rather than swapped ("X7Q2" for
    DX7Q2): typical of speech recognition dropping a sound, so the agent may have said
    it right. A same-length swap ("BX7Q2") means a different value was spoken.
    """

    value: str
    partial: bool


def near_miss(target: str, runs: list[str]) -> NearMiss | None:
    """The closest string in ``runs`` within two edits of ``target`` (exact matches excluded).

    Substrings of each run are considered, so surrounding characters do not hide a miss.
    Swaps are preferred over partial matches when both exist.
    """
    best: NearMiss | None = None
    for run in runs:
        for length in (len(target), len(target) - 1, len(target) - 2, len(target) + 1):
            if length < max(3, len(target) - _MAX_EDITS) or length > len(run):
                continue
            for start in range(len(run) - length + 1):
                candidate = run[start : start + length]
                edits = edit_distance(candidate, target)
                if 0 < edits <= _MAX_EDITS:
                    found = NearMiss(candidate, partial=length != len(target))
                    if not found.partial:
                        return found
                    best = best or found
    return best
