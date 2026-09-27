from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Base for user-authored config: unknown keys are errors, values are immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RecordModel(BaseModel):
    """Base for records Callback writes: tolerant of extra keys from newer versions."""

    model_config = ConfigDict(extra="ignore")
