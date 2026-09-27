from typing import Any

_BETWEEN = "_between"


def match_state(observed: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    """Differences between the agent's reported end state and the scenario's ``match``.

    Returns one plain sentence per mismatch; an empty list means the state matches.
    Strings compare case-insensitively; ``<field>_between: [lo, hi]`` is inclusive.
    """
    problems: list[str] = []
    for key, want in expected.items():
        if key.endswith(_BETWEEN):
            field = key.removesuffix(_BETWEEN)
            got = observed.get(field)
            lo, hi = want
            if not isinstance(got, int | float) or not lo <= got <= hi:
                problems.append(f"{field} is {got!r}, expected between {lo} and {hi}")
            continue
        got = observed.get(key)
        same = (str(got).lower() == str(want).lower()) if isinstance(want, str) else got == want
        if not same:
            problems.append(f"{key} is {got!r}, expected {want!r}")
    return problems
