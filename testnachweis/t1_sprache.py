"""
T1 Spracherkennung (Anforderungen 4.1, 4.3-4.6, 4.12, 4.13).

Nutzt die Spracherkennung aus pren_perception (VoiceCommandDetector mit Vosk, Rauschfilter
und Wortliste) mit den Parametern aus perception.yaml, also genau den Stand des
voice_command-Nodes.

Ablauf: zwei Bloecke, zuerst ruhig, dann mit Hintergrundlaerm. Pro Block wird jeder
Befehl (HIER, BRAV, SITZ, SUCH) 5-mal und jedes von 5 aehnlichen Woertern einmal
abgefragt, in zufaelliger Reihenfolge. Enter druecken, Wort sagen, 4 s warten.

Start: scripts\\test_sprache.bat
"""

import argparse
from pathlib import Path
import random
import threading
import time

import sounddevice
from common import parameter, Protokoll, rate_tabelle, speichere_zusammenfassung, warte_enter
from pren_bringup.repo_paths import find_repo_root, find_vosk_model
from pren_perception.voice.keyword_spotter import RECOGNIZER_WORDS, RepeatFilter
from pren_perception.voice.microphone import Microphone
from pren_perception.voice.noise_gate import NoiseGate
from pren_perception.voice.voice_command_detector import VoiceCommandDetector
from pren_perception.voice.vosk_recognizer import VoskRecognizer

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1600   # 100 ms, wie im Node
BEFEHLE = ['HIER', 'BRAV', 'SITZ', 'SUCH']
NICHT_BEFEHLE = ['Sitzung', 'Brot', 'hier drin', 'bravo', 'suchen']   # Standardlauf
# Fuer Nachtests einzelner Befehle: aehnliche Woerter. "braun" und "brauchen" sind seit dem
# 20.11. keine Fuellwoerter mehr, ein Nachtest von BRAV soll pruefen, dass sie nichts ausloesen.
AEHNLICH = {'HIER': ['hier drin', 'hierher'], 'BRAV': ['brauchen', 'bravo', 'braun', 'Brot'],
            'SITZ': ['Sitzung', 'sitzen'], 'SUCH': ['suchen', 'Suppe']}


def nicht_befehle(befehle, anzahl):
    """Nicht-Befehle fuer einen Lauf: zuerst die aehnlichsten zu den gewaehlten Befehlen."""
    if set(befehle) == set(BEFEHLE):
        auswahl = NICHT_BEFEHLE
    else:
        auswahl = [w for b in befehle for w in AEHNLICH[b]] + NICHT_BEFEHLE
        auswahl = list(dict.fromkeys(auswahl))   # doppelte entfernen, Reihenfolge behalten
    return auswahl[:anzahl]


class Zuhoerer:
    """Verarbeitet das Mikrofon dauernd im Hintergrund, wie der Node."""

    def __init__(self, detector, mikrofon):
        self.detector, self.mikrofon = detector, mikrofon
        self.ereignisse = []      # (zeit, Befehl)
        self.verworfen = []       # (zeit, gehoerte Woerter), wenn kein Befehl daraus wurde
        self.letzter_laut = None  # Zeit des letzten Blocks ueber der Schwelle
        self.bloecke = 0          # gelesene Audiobloecke, 0 = Mikrofon liefert nichts
        self.max_pegel = 0.0      # hoechster Pegel seit pegel_zuruecksetzen()
        self._sperre = threading.Lock()
        self._laeuft = True
        self._thread = threading.Thread(target=self._schleife, daemon=True)

    def start(self):
        self.mikrofon.start()
        self._thread.start()

    def stop(self):
        self._laeuft = False
        self._thread.join(timeout=1.0)
        self.mikrofon.stop()

    def _schleife(self):
        schwelle = parameter('voice_command')['volume_threshold']
        zuletzt_verworfen = self.detector.last_rejected
        while self._laeuft:
            block = self.mikrofon.read(timeout_s=0.1)
            if block is None:
                continue
            jetzt = time.monotonic()
            befehl = self.detector.process(block, jetzt)
            with self._sperre:
                self.bloecke += 1
                self.max_pegel = max(self.max_pegel, self.detector.last_level)
                if self.detector.last_level >= schwelle:
                    self.letzter_laut = jetzt
                if befehl is not None:
                    self.ereignisse.append((jetzt, befehl, self.letzter_laut))
                if self.detector.last_rejected is not zuletzt_verworfen:
                    zuletzt_verworfen = self.detector.last_rejected
                    woerter = ' '.join(w.text for w in zuletzt_verworfen) or '(nichts verstanden)'
                    self.verworfen.append((jetzt, woerter))

    def pegel_zuruecksetzen(self):
        with self._sperre:
            self.max_pegel = 0.0

    def seit(self, t0):
        with self._sperre:
            return ([e for e in self.ereignisse if e[0] >= t0],
                    [v for v in self.verworfen if v[0] >= t0])


def waehle_mikrofon(device):
    """Index aus perception.yaml oder --device (Zahl oder Teil des Namens), None = Standard."""
    if device is None:
        return None
    if isinstance(device, int) or device.lstrip('-').isdigit():
        return None if int(device) < 0 else int(device)
    for i, d in enumerate(sounddevice.query_devices()):   # erster Treffer = Standard-Audio-API
        if d['max_input_channels'] > 0 and device.lower() in d['name'].lower():
            return i
    raise SystemExit(f'Kein Mikrofon mit "{device}" im Namen. Liste: pixi run python -m sounddevice')


def baue_detector(repo_root):
    p = parameter('voice_command')
    return VoiceCommandDetector(
        recognizer=VoskRecognizer(find_vosk_model(repo_root), SAMPLE_RATE, RECOGNIZER_WORDS),
        gate=NoiseGate(threshold=p['volume_threshold'], hangover_chunks=p['hangover_chunks'],
                       pre_roll_chunks=p['pre_roll_chunks']),
        repeat_filter=RepeatFilter(p['repeat_cooldown_s']),
        min_confidence=p['min_confidence'],
        max_utterance_s=p['max_utterance_s'],
    )


def pegeltest(zuhoerer, dauer_s=3.0):
    """Prueft, ob das Mikrofon Ton liefert und Sprache die Schwelle erreicht."""
    schwelle = parameter('voice_command')['volume_threshold']
    vorher = zuhoerer.bloecke
    zuhoerer.pegel_zuruecksetzen()
    time.sleep(dauer_s)
    if zuhoerer.bloecke == vorher:
        raise SystemExit('Das Mikrofon liefert keinen Ton. Andere Programme mit Mikrofon '
                         'schliessen, in Windows den Mikrofonzugriff erlauben, neu starten.')
    pegel = zuhoerer.max_pegel
    if pegel >= schwelle:
        print(f'  Pegel {pegel:.0f}, Schwelle {schwelle:.0f}: ok')
    else:
        print(f'  Pegel {pegel:.0f}, Schwelle {schwelle:.0f}: zu leise, lauter oder naeher sprechen.')
    return pegel


def versuch(zuhoerer, ziel, fenster_s):
    """Ein Versuch: Fenster abwarten und auswerten."""
    t0 = time.monotonic()
    time.sleep(fenster_s)
    ereignisse, verworfen = zuhoerer.seit(t0)
    erkannt = [e[1].name for e in ereignisse]
    if ziel in BEFEHLE:
        korrekt = erkannt == [ziel]
    else:
        korrekt = not erkannt
    latenz = ''
    if ereignisse and ereignisse[0][2] is not None:
        latenz = max(0.0, ereignisse[0][0] - ereignisse[0][2])
    gehoert = '; '.join(v[1] for v in verworfen)
    return {'erkannt': ' '.join(erkannt) or '-', 'korrekt': korrekt, 'latenz_s': latenz,
            'gehoert_verworfen': gehoert}


def main():
    ap = argparse.ArgumentParser(description='T1 Spracherkennung')
    ap.add_argument('--wiederholungen', type=int, default=5, help='Versuche pro Befehl und Block')
    ap.add_argument('--befehle', default=','.join(BEFEHLE),
                    help='nur diese Befehle testen, z. B. BRAV oder BRAV,SUCH (Standard: alle)')
    ap.add_argument('--nicht-befehle', type=int, default=None,
                    help='Anzahl aehnlicher Woerter pro Block (Standard: 5, mit --befehle 2)')
    ap.add_argument('--fenster', type=float, default=4.0, help='Zuhoerzeit pro Versuch in s')
    ap.add_argument('--device', default=None,
                    help='Mikrofon-Index oder Teil des Namens, z. B. C922 (Standard: perception.yaml)')
    args = ap.parse_args()
    befehle = [b.strip().upper() for b in args.befehle.split(',') if b.strip()]
    unbekannt = [b for b in befehle if b not in BEFEHLE]
    if unbekannt or not befehle:
        ap.error(f'unbekannter Befehl {unbekannt}, erlaubt: {",".join(BEFEHLE)}')
    alle = set(befehle) == set(BEFEHLE)
    anzahl = args.nicht_befehle if args.nicht_befehle is not None else (5 if alle else 2)
    woerter = nicht_befehle(befehle, anzahl)

    print('=== T1 Spracherkennung ===\n')
    if not alle:
        print(f'Nachtest: {", ".join(befehle)} je {args.wiederholungen}-mal pro Block, '
              f'aehnliche Woerter: {", ".join(woerter) or "-"}\n')
    repo_root = find_repo_root(Path(__file__).resolve())
    device = args.device if args.device is not None else parameter('voice_command')['device']
    print('Lade Vosk-Modell ...')
    detector = baue_detector(repo_root)
    device = waehle_mikrofon(device)
    mikrofon = Microphone(SAMPLE_RATE, CHUNK_SAMPLES, device=device)
    print(f'Mikrofon: {mikrofon.device_name}')
    distanz = warte_enter('Abstand der sprechenden Person zum Laptop in m (Enter = 1): ') or '1'

    zuhoerer = Zuhoerer(detector, mikrofon)
    zuhoerer.start()
    while True:
        if warte_enter('Pegeltest: Enter druecken, dann im Testabstand "Hallo" sagen (q = Ende): ') == 'q':
            zuhoerer.stop()
            return
        try:
            pegel = pegeltest(zuhoerer)
        except SystemExit:
            zuhoerer.stop()
            raise
        if pegel >= parameter('voice_command')['volume_threshold']:
            break
        if warte_enter('  Nochmals testen? Enter = ja, w = trotzdem weiter: ') == 'w':
            break
    name = 't1_sprache' if alle else 't1_sprache_nachtest_' + '_'.join(befehle)
    protokoll = Protokoll(name, ['block', 'distanz_m', 'gesagt', 'erwartet', 'erkannt', 'korrekt',
                                 'latenz_s', 'gehoert_verworfen'])
    try:
        for block, hinweis in [('ruhig', 'Raum ruhig, kein Laerm abspielen.'),
                               ('laerm', 'Jetzt Hintergrundlaerm einschalten (z. B. Video mit '
                                         'Stimmengewirr, etwa 1 m neben dem Laptop).')]:
            print(f'\n--- Block "{block}" ---\n{hinweis}')
            if warte_enter('Bereit? Enter = Start, q = Ende: ') == 'q':
                break
            liste = [b for b in befehle for _ in range(args.wiederholungen)] + woerter
            random.shuffle(liste)
            i = 0
            while i < len(liste):
                ziel = liste[i]
                if warte_enter(f'[{i + 1}/{len(liste)}] Sag: {ziel}   (Enter, dann sprechen) ') == 'q':
                    raise KeyboardInterrupt
                r = versuch(zuhoerer, ziel, args.fenster)
                info = f'  -> erkannt: {r["erkannt"]}   {"OK" if r["korrekt"] else "FALSCH"}'
                if r['latenz_s'] != '':
                    info += f'   ({r["latenz_s"]:.2f} s nach Sprechende)'
                if r['gehoert_verworfen'] and not r['korrekt']:
                    info += f'   [gehoert: {r["gehoert_verworfen"]}]'
                print(info)
                if warte_enter('     Enter = speichern, w = wiederholen (nur wenn der Ablauf '
                               'schiefging): ') == 'w':
                    continue
                erwartet = ziel if ziel in BEFEHLE else 'nicht-befehl'
                protokoll.schreibe(block=block, distanz_m=distanz, gesagt=ziel, erwartet=erwartet,
                                   **r)
                i += 1
    except KeyboardInterrupt:
        print('\nAbgebrochen, bisherige Versuche sind gespeichert.')
    finally:
        zuhoerer.stop()
        protokoll.schliessen()

    if protokoll.zeilen:
        fehl = [z for z in protokoll.zeilen if z['erwartet'] == 'nicht-befehl' and z['korrekt'] == 'nein']
        n_nicht = sum(z['erwartet'] == 'nicht-befehl' for z in protokoll.zeilen)
        fehl_text = ', '.join(f'"{z["gesagt"]}" -> {z["erkannt"]}' for z in fehl)
        text = (f'Mikrofon: {mikrofon.device_name}, Abstand {distanz} m\n\n'
                + ('' if alle else f'Nachtest nur {", ".join(befehle)}, aehnliche Woerter: '
                                   f'{", ".join(woerter) or "-"}\n\n')
                + rate_tabelle(protokoll.zeilen, ['block', 'erwartet'])
                + f'\n\nFehlausloesungen durch Nicht-Befehle: {len(fehl)} von {n_nicht}'
                + (f' ({fehl_text})' if fehl else '') + '\n'
                + '\nKriterium: jeder Befehl >= 90 %, hoechstens 1 Fehlausloesung, unter 1 s.')
        titel = 'T1 Spracherkennung' + ('' if alle else f' - Nachtest {", ".join(befehle)}')
        speichere_zusammenfassung(protokoll, titel, text)


if __name__ == '__main__':
    main()
