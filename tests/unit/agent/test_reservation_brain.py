import pytest

from callback_voice.reference_agents.restaurant.bookings.booking_store import BookingStore
from callback_voice.reference_agents.restaurant.dialog.reservation_brain import ReservationBrain
from callback_voice.reference_agents.restaurant.nlu.parse_party_size import parse_party_size
from callback_voice.reference_agents.restaurant.nlu.parse_time import parse_time
from callback_voice.text.spoken_code import find_code
from callback_voice.text.spoken_code_match import entity_spoken


def test_move_flow_reaches_verified_end_state() -> None:
    store = BookingStore()
    brain = ReservationBrain(store)
    brain.greet()
    for line in [
        "I need to move my booking to Saturday.",
        "It's D X 7 Q 2.",
        "Anytime between seven and nine.",
        "Seven thirty works.",
        "Actually make it 5 people.",
        "Yes please.",
    ]:
        brain.respond(line)
    booking = store.find("DX7Q2")
    assert booking is not None
    assert (booking.status, booking.day, booking.hour, booking.minute, booking.party_size) == (
        "moved",
        "saturday",
        19,
        30,
        5,
    )
    assert brain.respond("No, that's all, bye.").end_call


def test_full_slot_offers_alternatives() -> None:
    brain = ReservationBrain(BookingStore())
    brain.respond("Move booking DX7Q2 please")
    reply = brain.respond("Saturday at 8pm")
    assert "fully booked" in reply.text and "7:30 PM" in reply.text


def test_buggy_misread_garbles_the_code() -> None:
    brain = ReservationBrain(BookingStore(), misread={"D": "B"})
    reply = brain.respond("I want to move booking D X 7 Q 2")
    assert "B, X, 7, Q, 2" in reply.text
    assert not entity_spoken("DX7Q2", reply.text)


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("It's DX7 Q2.", "DX7Q2"),
        ("delta x-ray seven quebec two", "DX7Q2"),
        ("uh it is a D-X-7-Q-2", "DX7Q2"),
        ("a table for 4 at 8pm", None),
    ],
)
def test_find_code(text: str, code: str | None) -> None:
    assert find_code(text) == code


def test_time_and_party_parsing() -> None:
    assert parse_time("between seven and nine") is not None
    assert parse_time("7 to 9pm").earliest == 19  # type: ignore[union-attr]
    assert parse_time("half past 7").minute == 30  # type: ignore[union-attr]
    assert parse_party_size("table for 4 at 8pm") == 4
    assert parse_party_size("for 8pm") is None
