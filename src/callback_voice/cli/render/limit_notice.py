from rich.text import Text

from callback_voice.core.models.limit_override import LimitOverride


def limit_notice(overrides: list[LimitOverride]) -> Text | None:
    """One warning line when this run uses loosened limits (a CI machine)."""
    if not overrides:
        return None
    applied = sorted({o.applied for o in overrides})
    targets = sorted({o.target for o in overrides})
    return Text(
        f"▲ CI limit: reply delay p95 up to {', '.join(f'{a:g}' for a in applied)} s on this "
        f"machine ({overrides[0].source}); the real target is "
        f"{', '.join(f'{t:g}' for t in targets)} s.\n",
        style="warn",
    )
