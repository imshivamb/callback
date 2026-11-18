import time
from collections import OrderedDict

from callback_voice.reference_agents.restaurant.bookings.booking_store import BookingStore

_KEEP = 500
_CLOCK_SLACK_S = 2.0


class CallRegistry:
    """Booking stores by call id, so ``/verify`` can report a finished call's end state."""

    def __init__(self) -> None:
        self._stores: OrderedDict[str, BookingStore] = OrderedDict()
        self._opened_at: dict[str, float] = {}

    def open(self, call_id: str) -> BookingStore:
        store = BookingStore()
        self._stores[call_id] = store
        self._opened_at[call_id] = time.time()
        while len(self._stores) > _KEEP:
            old, _ = self._stores.popitem(last=False)
            self._opened_at.pop(old, None)
        return store

    def get(self, call_id: str) -> BookingStore | None:
        return self._stores.get(call_id)

    def opened_between(self, start: float, end: float) -> list[str]:
        """Calls that began between ``start`` and ``end`` (Unix seconds), give or take
        a little clock slack. Used to find a phone call, whose agent never sees
        Callback's call id, from the time Callback placed it."""
        return [
            call_id
            for call_id, at in self._opened_at.items()
            if start - _CLOCK_SLACK_S <= at <= end + _CLOCK_SLACK_S
        ]
