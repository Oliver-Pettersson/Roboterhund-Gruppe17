"""Tests fuer die Pfadsuche der Launch-Dateien."""

from pathlib import Path

from pren_bringup.repo_paths import (
    find_file,
    find_hand_model,
    find_repo_root,
    find_vosk_model,
    find_webots_home,
    HAND_MODEL_NAME,
    VOSK_MODEL_NAME,
    webots_environment,
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


def test_vosk_model_found_in_models_folder(tmp_path):
    model = tmp_path / 'models' / 'voice' / VOSK_MODEL_NAME
    model.mkdir(parents=True)

    assert find_vosk_model(tmp_path) == model


def test_missing_vosk_model_names_the_expected_folder(tmp_path):
    with pytest.raises(RuntimeError, match='voice'):
        find_vosk_model(tmp_path)


def test_hand_model_found_in_models_folder(tmp_path):
    model = tmp_path / 'models' / 'gesture' / HAND_MODEL_NAME
    model.parent.mkdir(parents=True)
    model.write_text('')

    assert find_hand_model(tmp_path) == model


def test_missing_model_names_searched_places(tmp_path):
    with pytest.raises(RuntimeError, match='hand_landmarker.task'):
        find_hand_model(tmp_path)


PIXI = r'C:\repo\.pixi\envs\default'
PIXI_ENVIRONMENT = {
    'CONDA_PREFIX': PIXI,
    'PATH': ';'.join([PIXI, PIXI + r'\Library\bin', r'C:\Windows\system32', r'C:\Tools']),
    'QT_PLUGIN_PATH': PIXI + r'\Library\plugins',
    'XML_CATALOG_FILES': 'file:///C:/repo/.pixi/envs/default/etc/xml/catalog',
    'SystemRoot': r'C:\Windows',
    'LOCALAPPDATA': r'C:\Users\dog\AppData\Local',
}


def test_webots_environment_removes_pixi_qt_plugins():
    environment = webots_environment(PIXI_ENVIRONMENT, Path('C:/Webots'))

    assert 'QT_PLUGIN_PATH' not in environment
    assert 'XML_CATALOG_FILES' not in environment
    assert 'CONDA_PREFIX' not in environment


def test_webots_environment_keeps_system_path_and_variables():
    environment = webots_environment(PIXI_ENVIRONMENT, Path('C:/Webots'))

    assert environment['PATH'] == r'C:\Windows\system32;C:\Tools'
    assert environment['SystemRoot'] == r'C:\Windows'
    assert environment['LOCALAPPDATA'] == r'C:\Users\dog\AppData\Local'
    assert environment['WEBOTS_HOME'] == str(Path('C:/Webots'))


def test_webots_environment_without_pixi_changes_nothing_but_webots_home():
    plain = {'PATH': r'C:\Windows', 'SystemRoot': r'C:\Windows'}

    environment = webots_environment(plain, Path('C:/Webots'))

    assert environment == {**plain, 'WEBOTS_HOME': str(Path('C:/Webots'))}
