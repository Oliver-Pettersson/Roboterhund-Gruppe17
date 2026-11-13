"""Tests fuer die Pfadsuche der Launch-Dateien."""

from pren_bringup.repo_paths import (
    find_file,
    find_hand_model,
    find_repo_root,
    find_vosk_model,
    find_webots_home,
    HAND_MODEL_NAME,
    VOSK_MODEL_NAME,
)
import pytest


def test_find_repo_root_walks_up(tmp_path):
    (tmp_path / 'pixi.toml').write_text('')
    (tmp_path / 'simulation' / 'webots').mkdir(parents=True)
    nested = tmp_path / 'workspace' / 'src'
    nested.mkdir(parents=True)

    assert find_repo_root(nested) == tmp_path


def test_find_repo_root_fails_outside_repo(tmp_path):
    with pytest.raises(RuntimeError):
        find_repo_root(tmp_path)


def test_webots_home_prefers_environment_variable(tmp_path):
    assert find_webots_home({'WEBOTS_HOME': str(tmp_path)}) == tmp_path


def test_webots_home_falls_back_to_local_app_data(tmp_path):
    webots = tmp_path / 'Programs' / 'Webots'
    webots.mkdir(parents=True)

    assert find_webots_home({'LOCALAPPDATA': str(tmp_path),
                             'ProgramFiles': str(tmp_path / 'none')}) == webots


def test_webots_home_missing_raises(tmp_path):
    with pytest.raises(RuntimeError):
        find_webots_home({'ProgramFiles': str(tmp_path / 'none')})


def test_find_file_searches_recursively(tmp_path):
    target = tmp_path / 'msys64' / 'bin' / 'webots.exe'
    target.parent.mkdir(parents=True)
    target.write_text('')

    assert find_file(tmp_path, 'webots.exe') == target


def test_vosk_model_prefers_models_folder(tmp_path):
    new = tmp_path / 'models' / 'voice' / VOSK_MODEL_NAME
    old = tmp_path / 'prototypes' / 'voice_detection' / 'models' / VOSK_MODEL_NAME
    new.mkdir(parents=True)
    old.mkdir(parents=True)

    assert find_vosk_model(tmp_path) == new


def test_vosk_model_falls_back_to_prototype(tmp_path):
    old = tmp_path / 'prototypes' / 'voice_detection' / 'models' / VOSK_MODEL_NAME
    old.mkdir(parents=True)

    assert find_vosk_model(tmp_path) == old


def test_hand_model_found_in_prototype(tmp_path):
    model = tmp_path / 'prototypes' / 'gesture_recognition' / HAND_MODEL_NAME
    model.parent.mkdir(parents=True)
    model.write_text('')

    assert find_hand_model(tmp_path) == model


def test_missing_model_names_searched_places(tmp_path):
    with pytest.raises(RuntimeError, match='hand_landmarker.task'):
        find_hand_model(tmp_path)
