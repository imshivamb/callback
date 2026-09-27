"""Maps each chaos event type name to its parameter model."""

from typing import Final, Literal

from callback_voice.chaos.params.ask_for_human import AskForHumanParams
from callback_voice.chaos.params.backchannel import BackchannelParams
from callback_voice.chaos.params.barge_in import BargeInParams
from callback_voice.chaos.params.base import ChaosParams
from callback_voice.chaos.params.change_mind import ChangeMindParams
from callback_voice.chaos.params.dtmf import DtmfParams
from callback_voice.chaos.params.jitter import JitterParams
from callback_voice.chaos.params.noise import NoiseParams
from callback_voice.chaos.params.packet_loss import PacketLossParams
from callback_voice.chaos.params.rate_change import RateChangeParams
from callback_voice.chaos.params.repeat_request import RepeatRequestParams
from callback_voice.chaos.params.silence import SilenceParams

type ChaosType = Literal[
    "barge_in",
    "backchannel",
    "silence",
    "noise",
    "rate_change",
    "dtmf",
    "packet_loss",
    "jitter",
    "ask_for_human",
    "repeat_request",
    "change_mind",
]

PARAMS_BY_TYPE: Final[dict[str, type[ChaosParams]]] = {
    "barge_in": BargeInParams,
    "backchannel": BackchannelParams,
    "silence": SilenceParams,
    "noise": NoiseParams,
    "rate_change": RateChangeParams,
    "dtmf": DtmfParams,
    "packet_loss": PacketLossParams,
    "jitter": JitterParams,
    "ask_for_human": AskForHumanParams,
    "repeat_request": RepeatRequestParams,
    "change_mind": ChangeMindParams,
}
