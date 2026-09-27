from collections.abc import Callable
from pathlib import Path
from typing import Final

import numpy as np

from callback_voice.audio.format import Audio
from callback_voice.audio.wav import read_mono
from callback_voice.chaos.noise_beds.cafe import cafe
from callback_voice.chaos.noise_beds.hum import hum
from callback_voice.chaos.noise_beds.office import office
from callback_voice.chaos.noise_beds.street import street
from callback_voice.chaos.noise_beds.wind import wind
from callback_voice.errors import ScenarioError

BEDS: Final[dict[str, Callable[[np.random.Generator, float], Audio]]] = {
    "street": street,
    "cafe": cafe,
    "office": office,
    "wind": wind,
    "hum": hum,
}
_LOOP_S = 30.0


def load_bed(name: str, rng: np.random.Generator, base_dir: Path) -> Audio:
    """A built-in bed by name, or an audio file (relative to the scenario), at unit RMS."""
    if name in BEDS:
        bed = BEDS[name](rng, _LOOP_S)
    else:
        path = Path(name) if Path(name).is_absolute() else base_dir / name
        if not path.is_file():
            raise ScenarioError(
                f"noise bed {name!r} is neither built in ({', '.join(BEDS)}) nor a file"
            )
        bed = read_mono(path)
    level = float(np.sqrt(np.mean(bed.astype(np.float64) ** 2)))
    return (bed / max(level, 1e-9)).astype(np.float32)
