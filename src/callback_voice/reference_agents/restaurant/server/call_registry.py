from collections import OrderedDict

from callback_voice.reference_agents.restaurant.bookings.booking_store import BookingStore

_KEEP = 500


class CallRegistry:
    """Booking stores by call id, so ``/verify`` can report a finished call's end state."""

    def __init__(self) -> None:
        self._stores: OrderedDict[str, BookingStore] = OrderedDict()

    def open(self, call_id: str) -> BookingStore:
        store = BookingStore()
        self._stores[call_id] = store
        while len(self._stores) > _KEEP:
            self._stores.popitem(last=False)
        return store

    def get(self, call_id: str) -> BookingStore | None:
        return self._stores.get(call_id)
