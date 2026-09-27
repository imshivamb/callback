from pathlib import Path

from callback_voice.chaos.params.noise import NoiseParams
from callback_voice.chaos.processors.backchannel_chaos import BackchannelChaos
from callback_voice.chaos.processors.barge_in_chaos import BargeInChaos
from callback_voice.chaos.processors.chaos_processor import ChaosProcessor
from callback_voice.chaos.processors.dtmf_chaos import DtmfChaos
from callback_voice.chaos.processors.jitter_chaos import JitterChaos
from callback_voice.chaos.processors.noise_chaos import NoiseChaos
from callback_voice.chaos.processors.packet_loss_chaos import PacketLossChaos
from callback_voice.chaos.processors.rate_change_chaos import RateChangeChaos
from callback_voice.chaos.processors.replace_line_chaos import ReplaceLineChaos
from callback_voice.chaos.processors.silence_chaos import SilenceChaos
from callback_voice.core.models.chaos_config import ChaosConfig
from callback_voice.core.models.chaos_event import ChaosEvent
from callback_voice.core.seeds.make_rng import make_rng


def build_processors(chaos: ChaosConfig, seed: int, base_dir: Path) -> list[ChaosProcessor]:
    """One processor per chaos event, each with its own seeded random stream.

    Order matters for outbound shaping: noise is mixed first, then the line impairs
    the mixed signal (loss, jitter), as on a real phone line.
    """
    events = list(chaos.events)
    if chaos.noise is not None:
        events.insert(0, ChaosEvent(id="noise", type="noise", trigger=None, params=chaos.noise))
    processors: list[ChaosProcessor] = []
    for event in sorted(events, key=lambda e: e.type in {"packet_loss", "jitter"}):
        rng = make_rng(seed, "chaos", event.id)
        match event.type:
            case "barge_in":
                processors.append(BargeInChaos(event))
            case "backchannel":
                processors.append(BackchannelChaos(event, rng))
            case "silence":
                processors.append(SilenceChaos(event))
            case "ask_for_human" | "repeat_request" | "change_mind":
                processors.append(ReplaceLineChaos(event))
            case "rate_change":
                processors.append(RateChangeChaos(event))
            case "dtmf":
                processors.append(DtmfChaos(event))
            case "noise":
                assert isinstance(event.params, NoiseParams)
                processors.append(NoiseChaos(event, event.params, rng, base_dir))
            case "packet_loss":
                processors.append(PacketLossChaos(event, rng))
            case "jitter":
                processors.append(JitterChaos(event, rng))
    return processors
