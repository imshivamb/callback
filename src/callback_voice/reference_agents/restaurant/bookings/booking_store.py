import copy
from typing import Final

from callback_voice.reference_agents.restaurant.bookings.booking import Booking

_SEED: Final = (
    Booking("DX7Q2", "Priya Sharma", "9810012345", "friday", 20, 0, 4),
    Booking("KT4M9", "Daniel Okafor", "4155550182", "saturday", 19, 30, 2),
    Booking("PL2V8", "Maria Lopez", "3105550199", "saturday", 20, 0, 6),
)
# Slots that are full regardless of party size, so agents must offer alternatives.
_FULL: Final = frozenset({("saturday", 20, 0), ("friday", 19, 0), ("saturday", 21, 0)})
_SLOTS: Final = tuple((h, m) for h in range(17, 22) for m in (0, 30))
MAX_PARTY: Final = 10


class BookingStore:
    """In-memory bookings for one call. Every call gets a fresh copy of the same seed,
    so trials are independent and verifiable afterwards.
    """

    def __init__(self) -> None:
        self._bookings = {b.ref: copy.copy(b) for b in _SEED}
        self.touched: str | None = None

    def find(self, ref: str) -> Booking | None:
        return self._bookings.get(ref.upper())

    def on_day(self, day: str) -> list[Booking]:
        return [b for b in self._bookings.values() if b.day == day and b.status != "cancelled"]

    def is_free(self, day: str, hour: int, minute: int) -> bool:
        return (day, hour, minute) not in _FULL and (hour, minute) in _SLOTS

    def free_slots(self, day: str, earliest: int, latest: int) -> list[tuple[int, int]]:
        """Open slots on ``day`` from ``earliest``:00 up to and including ``latest``:00."""
        return [
            (h, m)
            for h, m in _SLOTS
            if earliest <= h + m / 60 <= latest and self.is_free(day, h, m)
        ]

    def move(self, ref: str, day: str, hour: int, minute: int) -> Booking:
        booking = self._bookings[ref]
        booking.day, booking.hour, booking.minute = day, hour, minute
        booking.status = "moved"
        self.touched = ref
        return booking

    def update(
        self, ref: str, *, party_size: int | None = None, window_seat: bool | None = None
    ) -> None:
        booking = self._bookings[ref]
        if party_size is not None:
            booking.party_size = party_size
        if window_seat is not None:
            booking.window_seat = window_seat
        self.touched = ref

    def cancel(self, ref: str) -> None:
        self._bookings[ref].status = "cancelled"
        self.touched = ref

    def create(
        self, ref: str, name: str, day: str, hour: int, minute: int, party_size: int
    ) -> Booking:
        booking = Booking(ref, name, "", day, hour, minute, party_size, status="new")
        self._bookings[ref] = booking
        self.touched = ref
        return booking
