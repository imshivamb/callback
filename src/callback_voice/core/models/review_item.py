from callback_voice.core.models.strict_model import RecordModel


class ReviewItem(RecordModel):
    """A check Callback could not settle on its own: a person should listen.

    Used when the scoring transcription is unsure (low word confidence, or two
    transcriptions disagree). Review items never fail a run.
    """

    check: str
    heard: str | None
    reason: str
    t_s: float
    end_s: float | None = None
