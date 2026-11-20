"""
T2 Gestenerkennung (Anforderungen 4.2, 4.7-4.9, 4.13).

Nutzt die Gestenerkennung aus pren_perception (MediaPipe-Handpunkte, Klassifikation und
Glaettung 4 von 5 Bildern) mit den Parametern aus perception.yaml, also genau den Stand
des gesture_command-Nodes. Kamera wie im camera-Node (Index, Aufloesung aus perception.yaml).

Ablauf: drei Bloecke, 0,5 m, 1 m und 2 m. Pro Block jede Geste (SITZ, PLATZ, AUF) 5-mal und
3-mal eine neutrale Bewegung, in zufaelliger Reihenfolge. Bedienung im Kamerafenster:
Leertaste = los / weiter, W = Versuch wiederholen, Q = Ende.

Start: scripts\\test_gesten.bat
"""

import argparse
from pathlib import Path
import random
import time

import cv2
from common import (lies_bild, oeffne_kamera, parameter, Protokoll, rate_tabelle,
                    speichere_zusammenfassung)
from pren_bringup.repo_paths import find_hand_model, find_repo_root
from pren_perception.gesture.gesture_command_detector import GestureCommandDetector
from pren_perception.gesture.gesture_debouncer import GestureDebouncer
from pren_perception.gesture.hand_landmark_detector import HandLandmarkDetector

GESTEN = {
    'SITZ': 'offene Hand, Handflaeche zur Kamera',
    'PLATZ': 'Zeigefinger nach unten',
    'AUF': 'Zeigefinger nach oben',
}
NEUTRAL = ('NEUTRAL', 'Handy halten, Arme verschraenken oder Kopf kratzen')
FENSTER = 'T2 Gesten'


class Kamera:
    """Kamera wie im camera-Node (Index und Aufloesung aus perception.yaml)."""

    def __init__(self, p):
        self.cap, _, self.backend = oeffne_kamera(p['device'], p['width'], p['height'])

    def bild(self):
        return lies_bild(self.cap, versuche=1)


def zeige(frame, zeilen, farbe=(255, 255, 255)):
    bild = frame.copy()
    groesse = bild.shape[1] / 1000          # Schrift passend zur Bildbreite
    zeile = int(40 * groesse) + 8
    cv2.rectangle(bild, (0, 0), (bild.shape[1], zeile * len(zeilen) + 12), (0, 0, 0), -1)
    for i, text in enumerate(zeilen):
        cv2.putText(bild, text, (10, zeile * (i + 1)), cv2.FONT_HERSHEY_SIMPLEX, groesse,
                    farbe, max(1, int(2 * groesse)))
    cv2.imshow(FENSTER, bild)
    taste = cv2.waitKey(1) & 0xFF
    return ord(chr(taste).lower()) if taste != 0xFF else taste  # Q und q gleich (Feststelltaste)


def warte_taste(kamera, zeilen, tasten=(ord(' '),), farbe=(255, 255, 255)):
    """Live-Bild mit Text, bis eine der Tasten gedrueckt wird."""
    while True:
        frame = kamera.bild()
        if frame is None:
            continue
        taste = zeige(frame, zeilen, farbe)
        if taste == ord('q'):
            raise KeyboardInterrupt
        if taste in tasten:
            return taste


def versuch(kamera, detector, debouncer, haende, ziel, fenster_s):
    """Ein Versuch: fenster_s Sekunden Bilder auswerten."""
    debouncer.reset()
    for _ in range(3):
        kamera.cap.grab()  # gepufferte alte Bilder verwerfen
    t0 = time.monotonic()
    erste_hand, ereignisse, rechenzeiten = None, [], []
    while time.monotonic() - t0 < fenster_s:
        frame = kamera.bild()
        if frame is None:
            continue
        t_bild = time.monotonic()
        befehl = detector.process(frame, t_bild)
        rechenzeiten.append((time.monotonic() - t_bild) * 1000)
        if haende['zuletzt'] and erste_hand is None:
            erste_hand = t_bild
        if befehl is not None:
            ereignisse.append((time.monotonic(), befehl.name))
        rest = fenster_s - (time.monotonic() - t0)
        zeige(frame, [f'{ziel}: jetzt zeigen ... {rest:.1f} s',
                      f'erkannt: {", ".join(e[1] for e in ereignisse) or "-"}'], (0, 255, 255))
    erkannt = [e[1] for e in ereignisse]
    korrekt = (erkannt[:1] == [ziel] and set(erkannt) == {ziel}) if ziel in GESTEN else not erkannt
    latenz = ''
    if ereignisse and erste_hand is not None:
        latenz = max(0.0, ereignisse[0][0] - erste_hand)
    return {'erkannt': ' '.join(erkannt) or '-', 'korrekt': korrekt, 'latenz_s': latenz,
            'rechenzeit_ms': sum(rechenzeiten) / len(rechenzeiten) if rechenzeiten else ''}


def main():
    ap = argparse.ArgumentParser(description='T2 Gestenerkennung')
    ap.add_argument('--wiederholungen', type=int, default=5, help='Versuche pro Geste und Distanz')
    ap.add_argument('--neutral', type=int, default=3, help='neutrale Versuche pro Distanz')
    ap.add_argument('--gesten', default=None,
                    help='Nachtest nur dieser Gesten, z. B. SITZ,NEUTRAL: jede --wiederholungen-mal '
                         'pro Distanz (Standard: alle Gesten plus --neutral neutrale)')
    ap.add_argument('--distanzen', default='0.5,1,2', help='Distanzen in m, kommagetrennt')
    ap.add_argument('--fenster', type=float, default=5.0, help='Zeit pro Versuch in s')
    ap.add_argument('--kamera', type=int, default=None,
                    help='Kameraindex, z. B. 1 fuer externe Webcam (Standard: perception.yaml)')
    args = ap.parse_args()
    erlaubt = list(GESTEN) + [NEUTRAL[0]]
    gesten = None
    if args.gesten:
        gesten = [g.strip().upper() for g in args.gesten.split(',') if g.strip()]
        if not gesten or any(g not in erlaubt for g in gesten):
            ap.error(f'--gesten: erlaubt sind {",".join(erlaubt)}')

    print('=== T2 Gestenerkennung ===')
    if gesten:
        print(f'Nachtest: {", ".join(gesten)} je {args.wiederholungen}-mal pro Distanz')
    repo_root = find_repo_root(Path(__file__).resolve())
    p_geste, p_kamera = parameter('gesture_command'), parameter('camera')
    if args.kamera is not None:
        p_kamera['device'] = args.kamera
    hand_detector = HandLandmarkDetector(find_hand_model(repo_root))
    haende = {'zuletzt': False}

    def finde_haende(bild):
        gefunden = hand_detector.detect(bild)
        haende['zuletzt'] = bool(gefunden)
        return gefunden

    debouncer = GestureDebouncer(**p_geste)   # alle Glaettungs-Parameter wie im Node
    detector = GestureCommandDetector(find_hands=finde_haende, debouncer=debouncer)
    kamera = Kamera(p_kamera)
    breite = int(kamera.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    hoehe = int(kamera.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f'Kamera {p_kamera["device"]} ({kamera.backend}): {breite}x{hoehe}. '
          'Bedienung im Kamerafenster.')
    cv2.namedWindow(FENSTER, cv2.WINDOW_NORMAL)

    name = 't2_gesten_nachtest_' + '_'.join(gesten) if gesten else 't2_gesten'
    protokoll = Protokoll(name, ['distanz_m', 'erwartet', 'erkannt', 'korrekt',
                                        'latenz_s', 'rechenzeit_ms'])
    try:
        for distanz in [d.strip() for d in args.distanzen.split(',') if d.strip()]:
            warte_taste(kamera, [f'Neuer Block: Testperson steht {distanz} m vor der Kamera.',
                                 'Leertaste = Start, Q = Ende'])
            if gesten:
                liste = [g for g in gesten for _ in range(args.wiederholungen)]
            else:
                liste = [g for g in GESTEN for _ in range(args.wiederholungen)]
                liste += [NEUTRAL[0]] * args.neutral
            random.shuffle(liste)
            i = 0
            while i < len(liste):
                ziel = liste[i]
                hinweis = GESTEN.get(ziel, NEUTRAL[1])
                warte_taste(kamera, [f'[{i + 1}/{len(liste)}] {distanz} m   Naechste: {ziel}',
                                     hinweis, 'Hand aus dem Bild nehmen, dann Leertaste'])
                r = versuch(kamera, detector, debouncer, haende, ziel, args.fenster)
                ergebnis = f'erkannt: {r["erkannt"]}  ->  {"OK" if r["korrekt"] else "FALSCH"}'
                if r['latenz_s'] != '':
                    ergebnis += f'  ({r["latenz_s"]:.2f} s)'
                print(f'[{distanz} m] {ziel}: {ergebnis}')
                taste = warte_taste(kamera, [ergebnis, 'Leertaste = speichern und weiter',
                                             'W = wiederholen (nur bei Ablauffehler)'],
                                    tasten=(ord(' '), ord('w')),
                                    farbe=(0, 255, 0) if r['korrekt'] else (0, 0, 255))
                if taste == ord('w'):
                    continue
                protokoll.schreibe(distanz_m=distanz, erwartet=ziel, **r)
                i += 1
    except KeyboardInterrupt:
        print('Abgebrochen, bisherige Versuche sind gespeichert.')
    finally:
        kamera.cap.release()
        cv2.destroyAllWindows()
        hand_detector.close()
        protokoll.schliessen()

    if protokoll.zeilen:
        rz = [float(z['rechenzeit_ms']) for z in protokoll.zeilen if z['rechenzeit_ms']]
        glaettung = (f'{p_geste["min_agreeing"]} von {p_geste["window_size"]} Bildern, SITZ '
                     f'{p_geste.get("open_palm_min_agreeing") or p_geste["min_agreeing"]} von '
                     f'{p_geste.get("open_palm_window_size") or p_geste["window_size"]}')
        text = (f'Kamera: Index {p_kamera["device"]}, {breite}x{hoehe}\n'
                f'Glaettung: {glaettung}\n\n'
                + rate_tabelle(protokoll.zeilen, ['distanz_m', 'erwartet'])
                + (f'\n\nRechenzeit pro Bild (MediaPipe + Klassifikation): '
                   f'{sum(rz) / len(rz):.0f} ms im Mittel' if rz else '')
                + '\n\nKriterium: jede Geste >= 90 % in allen Distanzen, NEUTRAL loest nichts aus, '
                  'unter 1 s.')
        titel = 'T2 Gestenerkennung' + (f' - Nachtest {", ".join(gesten)}' if gesten else '')
        speichere_zusammenfassung(protokoll, titel, text)


if __name__ == '__main__':
    main()
