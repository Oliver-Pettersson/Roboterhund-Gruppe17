"""
Selbsttest: prueft ohne Bedienung, ob die Tests T1, T2 und T3a auf diesem Rechner laufen.

Laedt die Modelle, oeffnet Mikrofon und Kamera, wertet echte Daten mit dem Code aus
pren_perception aus und oeffnet kurz ein Fenster. Gibt pro Punkt OK oder FEHLER aus.

Start: pixi run cmd /c "cd workspace && call .\\install\\local_setup.bat && cd ..\\testnachweis && python selbsttest.py"
"""

from pathlib import Path
import time
import traceback

ERGEBNIS = []


def pruefe(name):
    def deko(fn):
        try:
            info = fn()
            ERGEBNIS.append((name, True, info or ''))
        except Exception as e:  # noqa: BLE001
            ERGEBNIS.append((name, False, f'{type(e).__name__}: {e}'))
            traceback.print_exc()
        return fn
    return deko


ROOT = {}


@pruefe('Importe und Parameter')
def _():
    import common
    from pren_bringup.repo_paths import find_repo_root
    ROOT['repo'] = find_repo_root(Path(__file__).resolve())
    common.parameter('voice_command'), common.parameter('gesture_command'), common.parameter('camera')
    return str(ROOT['repo'])


@pruefe('T1: Vosk-Modell laden')
def _():
    import t1_sprache
    ROOT['detector'] = t1_sprache.baue_detector(ROOT['repo'])


@pruefe('T1: Mikrofon 2 s lesen und auswerten')
def _():
    import t1_sprache
    from common import parameter
    from pren_perception.voice.microphone import Microphone
    device = parameter('voice_command')['device']
    mic = Microphone(t1_sprache.SAMPLE_RATE, t1_sprache.CHUNK_SAMPLES,
                     device=None if device < 0 else device)
    z = t1_sprache.Zuhoerer(ROOT['detector'], mic)
    z.start()
    t0 = time.monotonic()
    r = t1_sprache.versuch(z, 'SITZ', 2.0)
    bloecke, pegel = z.bloecke, z.max_pegel
    z.stop()
    if time.monotonic() - t0 < 1.9:
        raise RuntimeError('Fenster zu kurz')
    if bloecke < 10:
        raise RuntimeError(f'Mikrofon liefert kaum Ton: {bloecke} Bloecke in 2 s (erwartet ca. 20)')
    schwelle = parameter('voice_command')['volume_threshold']
    return (f'{mic.device_name}, {bloecke} Bloecke in 2 s, max. Pegel {pegel:.1f} '
            f'(Schwelle {schwelle:.0f}), Versuch: {r}')


@pruefe('T2: Kamera wie camera-Node oeffnen')
def _():
    import t2_gesten
    from common import parameter
    k = t2_gesten.Kamera(parameter('camera'))
    for _ in range(10):
        frame = k.bild()
        if frame is not None:
            break
    ROOT['kamera'], ROOT['frame'] = k, frame
    if frame is None:
        raise RuntimeError('kein Bild')
    return f'{frame.shape[1]}x{frame.shape[0]}'


@pruefe('T2: MediaPipe und Gesten-Pipeline auf 2 s Kamerabildern')
def _():
    import t2_gesten
    from common import parameter
    from pren_bringup.repo_paths import find_hand_model
    from pren_perception.gesture.gesture_command_detector import GestureCommandDetector
    from pren_perception.gesture.gesture_debouncer import GestureDebouncer
    from pren_perception.gesture.hand_landmark_detector import HandLandmarkDetector
    import cv2
    hd = HandLandmarkDetector(find_hand_model(ROOT['repo']))
    haende = {'zuletzt': False}

    def finde(b):
        g = hd.detect(b)
        haende['zuletzt'] = bool(g)
        return g
    p = parameter('gesture_command')
    db = GestureDebouncer(**p)   # alle Glaettungs-Parameter wie im Node
    det = GestureCommandDetector(find_hands=finde, debouncer=db)
    cv2.namedWindow(t2_gesten.FENSTER, cv2.WINDOW_NORMAL)
    r = t2_gesten.versuch(ROOT['kamera'], det, db, haende, 'NEUTRAL', 2.0)
    t2_gesten.zeige(ROOT['frame'], ['Selbsttest', 'Zeile 2 mit etwas laengerem Text zum Pruefen'])
    cv2.waitKey(500)
    cv2.destroyAllWindows()
    ROOT['kamera'].cap.release()
    hd.close()
    return f'Versuch: {r}'


@pruefe('T3a: Kamera in hoechster Aufloesung')
def _():
    import cv2
    import t3a_kamera
    from common import parameter
    cap, frame = t3a_kamera.oeffne_hoechste_aufloesung(parameter('camera')['device'])
    t3a_kamera.text(frame, 'Selbsttest', (0, 255, 255))
    cv2.namedWindow(t3a_kamera.FENSTER, cv2.WINDOW_NORMAL)
    cv2.imshow(t3a_kamera.FENSTER, frame)
    cv2.waitKey(500)
    cv2.destroyAllWindows()
    cap.release()
    return f'{frame.shape[1]}x{frame.shape[0]}'


@pruefe('Protokoll: CSV und Zusammenfassung schreiben')
def _():
    import common
    p = common.Protokoll('selbsttest', ['erwartet', 'korrekt', 'latenz_s'])
    p.schreibe(erwartet='SITZ', korrekt=True, latenz_s=0.4)
    p.schliessen()
    md = common.speichere_zusammenfassung(p, 'Selbsttest', common.rate_tabelle(p.zeilen, ['erwartet']))
    p.pfad.unlink()
    md.unlink()
    return 'ok'


print('\n=== Selbsttest ===')
for name, ok, info in ERGEBNIS:
    print(f'{"OK    " if ok else "FEHLER"} {name}  {info}')
print('\nAlles OK' if all(ok for _, ok, _ in ERGEBNIS) else '\nEs gibt Fehler (siehe oben).')
