def say_time(hour: int, minute: int) -> str:
    """20, 30 -> "8:30 PM"; 19, 0 -> "7 PM"."""
    twelve = hour - 12 if hour > 12 else hour
    return f"{twelve}:{minute:02d} PM" if minute else f"{twelve} PM"


def say_code(code: str, *, misread: dict[str, str] | None = None) -> str:
    """Spell a code with pauses so TTS reads it character by character.

    ``misread`` substitutes characters, which is how the buggy agent garbles
    booking references ("D" read out as "B").
    """
    swaps = misread or {}
    return ", ".join(swaps.get(c, c) for c in code)


def say_phone(phone: str) -> str:
    """Read a phone number digit by digit in two groups: "9 8 1 0 0, 1 2 3 4 5"."""
    digits = [d for d in phone if d.isdigit()]
    half = len(digits) // 2
    return f"{' '.join(digits[:half])}, {' '.join(digits[half:])}"


def say_day(day: str) -> str:
    return day.capitalize()
