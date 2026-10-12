from rich.text import Text

from callback_voice.core.config.target_config import TwilioTarget


def phone_notice(targets: dict[str, TwilioTarget]) -> Text | None:
    """The warning printed before any real phone call is placed."""
    if not targets:
        return None
    lines = [
        f"  {name}: {t.from_number} → {t.to_number} (about ${t.usd_per_minute:g}/min, check your Twilio rates)"
        for name, t in targets.items()
    ]
    return Text.assemble(
        ("▲ Real phone calls. ", "warn"),
        "Only call numbers you own or have permission to call. Callback records both "
        "sides of each call; recording and consent rules depend on where you and the "
        "person called are, so check them (this is not legal advice). Twilio bills your "
        "account per started minute.\n",
        ("\n".join(lines), "muted"),
        "\n",
    )
