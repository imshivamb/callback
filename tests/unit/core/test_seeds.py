from callback_voice.core.seeds.derive_seed import derive_seed
from callback_voice.core.seeds.make_rng import make_rng


def test_seed_is_stable_and_distinct() -> None:
    assert derive_seed(1, "a", 0) == derive_seed(1, "a", 0)
    assert derive_seed(1, "a", 0) != derive_seed(1, "a", 1)
    assert 0 <= derive_seed("x") < 2**63


def test_streams_are_independent() -> None:
    a = make_rng(7, "chaos", "x").random(3)
    b = make_rng(7, "chaos", "y").random(3)
    assert list(a) != list(b)
    assert list(make_rng(7, "chaos", "x").random(3)) == list(a)
