"""Tests fuer den Messwert mit Ablaufzeit."""

from pren_behavior.latest_reading import LatestReading


def test_fresh_value_is_returned():
    reading = LatestReading(max_age_s=0.5)
    reading.update('pose', now=10.0)

    assert reading.get(now=10.4) == 'pose'


def test_old_value_is_replaced_by_default():
    reading = LatestReading(max_age_s=0.5)
    reading.update('pose', now=10.0)

    assert reading.get(now=10.6) is None
    assert reading.get(now=10.6, default='nichts') == 'nichts'


def test_without_value_default_is_returned():
    reading = LatestReading(max_age_s=0.5)

    assert reading.get(now=0.0, default='nichts') == 'nichts'
    assert not reading.ever_received


def test_clear_forgets_value():
    reading = LatestReading(max_age_s=0.5)
    reading.update('pose', now=1.0)

    reading.clear()

    assert reading.get(now=1.0) is None
