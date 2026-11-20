"""Tests fuer die Anzeige von Haltung und Signalen in der Simulation."""

from pren_interfaces.msg import DogSignal, Posture
from pren_simulation.dog_appearance import BARK_LIGHT_DURATION_S, DogAppearance


def test_status_shows_posture_and_activity():
    appearance = DogAppearance()
    appearance.posture = Posture.SIT
    appearance.activity = 'Sitzt'

    assert appearance.status_text(0.0) == 'Hund sitzt\nSitzt'


def test_bark_plays_sound_and_lights_up_for_a_while():
    appearance = DogAppearance()

    sound = appearance.on_signal(DogSignal.BARK, now=10.0)

    assert sound == 'dog_bark.wav'
    assert appearance.light_intensity(10.5) > 0.0
    assert appearance.light_intensity(10.0 + BARK_LIGHT_DURATION_S) == 0.0


def test_praise_shows_text_without_sound():
    appearance = DogAppearance()

    sound = appearance.on_signal(DogSignal.PRAISE, now=0.0)

    assert sound is None
    assert 'BRAV' in appearance.status_text(1.0)
    assert 'BRAV' not in appearance.status_text(5.0)


def test_mission_complete_plays_chime():
    assert DogAppearance().on_signal(DogSignal.MISSION_COMPLETE, 0.0) == 'victory_chime.wav'


def test_reset_turns_effects_off():
    appearance = DogAppearance()
    appearance.posture = Posture.LIE
    appearance.on_signal(DogSignal.BARK, 0.0)

    appearance.reset()

    assert appearance.light_intensity(0.5) == 0.0
    assert appearance.status_text(0.5) == 'Hund steht'
