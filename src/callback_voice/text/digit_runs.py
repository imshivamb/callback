from callback_voice.text.number_words import UNITS
from callback_voice.text.tokens import tokens

_DIGIT_WORDS = {w: str(v) for w, v in UNITS.items() if v < 10}


def digit_runs(text: str, min_length: int = 5) -> list[str]:
    """Runs of digits as spoken or written: "9 8 1 0 0, 1 2 3 4 5" -> ["9810012345"].

    Digits and digit words join across spaces and commas; any other word breaks the
    run ("double seven" is expanded).
    """
    runs: list[str] = []
    current = ""
    words = tokens(text.replace("-", " "))
    i = 0
    while i < len(words):
        word = words[i]
        if word in {"double", "triple"} and i + 1 < len(words) and words[i + 1] in _DIGIT_WORDS:
            current += _DIGIT_WORDS[words[i + 1]] * (2 if word == "double" else 3)
            i += 2
            continue
        if word.isdigit():
            current += word
        elif word in _DIGIT_WORDS:
            current += _DIGIT_WORDS[word]
        else:
            if len(current) >= min_length:
                runs.append(current)
            current = ""
        i += 1
    if len(current) >= min_length:
        runs.append(current)
    return runs
