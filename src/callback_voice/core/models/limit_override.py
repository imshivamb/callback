from callback_voice.core.models.strict_model import RecordModel


class LimitOverride(RecordModel):
    """A limit this run used instead of the scenario's own, and why.

    Written to results.json and shown in the report, so a loosened CI limit is never
    mistaken for the real target.
    """

    scenario_id: str
    metric: str
    target: float
    applied: float
    source: str
