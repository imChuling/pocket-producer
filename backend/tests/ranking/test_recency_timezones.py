"""recency() must accept naive and aware timestamps in any combination.

Regression for 2026-11-10: Mongo hands back naive UTC datetimes while new
fragments are written with datetime.now(UTC); mixing them raised TypeError in
the memory agent's neighbor signals.
"""

import pytest

from ranking.features import recency


@pytest.mark.parametrize(
    "created, newest",
    [
        ("2026-11-10T22:00:00", "2026-11-10T22:36:19+00:00"),
        ("2026-11-10T22:00:00+00:00", "2026-11-10T22:36:19"),
        ("2026-11-10T22:00:00", "2026-11-10T22:36:19"),
        ("2026-11-10T22:00:00+00:00", "2026-11-10T22:36:19+00:00"),
    ],
)
def test_naive_and_aware_mix(created, newest):
    value = recency(created, newest)
    assert 0.0 < value <= 1.0


def test_same_instant_in_two_forms_is_identical():
    assert recency("2026-11-01T00:00:00", "2026-11-10T00:00:00") == pytest.approx(
        recency("2026-11-01T00:00:00+00:00", "2026-11-10T00:00:00+00:00")
    )
