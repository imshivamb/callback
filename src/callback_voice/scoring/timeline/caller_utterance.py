from dataclasses import dataclass

from callback_voice.caller.engine.utterance import FLOOR_TAKING
from callback_voice.scoring.timeline.segment import Segment


@dataclass(frozen=True, slots=True)
class CallerUtterance:
    """One thing the caller said, with speech edges measured on the recording.

    ``speech`` comes from VAD on the clean caller stem; ``planned`` is where the
    engine placed the clip. Measured edges are what metrics use.
    """

    speech: Segment
    planned: Segment
    text: str
    tag: str
    chaos_id: str | None = None
    chaos_type: str | None = None

    @property
    def takes_floor(self) -> bool:
        return self.tag in FLOOR_TAKING
