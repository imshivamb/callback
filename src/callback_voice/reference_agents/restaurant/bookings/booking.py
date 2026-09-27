from dataclasses import asdict, dataclass
from typing import Any, Literal

type BookingStatus = Literal["confirmed", "moved", "cancelled", "new"]


@dataclass(slots=True)
class Booking:
    ref: str
    name: str
    phone: str
    day: str
    hour: int
    minute: int
    party_size: int
    status: BookingStatus = "confirmed"
    window_seat: bool = False

    def to_json(self) -> dict[str, Any]:
        return asdict(self)
