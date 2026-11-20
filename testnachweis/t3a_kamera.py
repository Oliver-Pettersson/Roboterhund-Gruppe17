"""
T3a Sichtfeld und Aufloesung (Anforderungen 5.2, 5.3).

Prueft mit der Laptop-Kamera, ob der Knochen gross genug im Bild ist, damit YOLO ihn
erkennen kann. Die Kamera wird in der hoechsten Aufloesung geoeffnet. Gemessen wird die
sichtbare Knochenlaenge in Pixeln im Kamerabild und umgerechnet auf den Modell-Eingang
von YOLO (640 px).

Messungen: 3 m quer, 5 m quer und 5 m laengs (Spitze zur Kamera). Laengs ist der
schwierigste Fall, weil der Knochen von vorne stark verkuerzt erscheint.

Bedienung im Kamerafenster:
    S = Bild einfrieren, dann beide sichtbaren Enden des Knochens anklicken
    Q = Ende
Am Schluss wird gefragt, ob die beiden Raender des 30-Grad-Bereichs im Bild waren.

Start: scripts\\test_kamera.bat
"""

import argparse
import time

import cv2
from common import ERGEBNISSE, lies_bild, oeffne_kamera, parameter, Protokoll, speichere_zusammenfassung, warte_enter

FENSTER = 'T3a Kamera'
MODELL_EINGANG = 640
ERWARTUNG_5M = 22   # Schaetzung im Konzept: px im Modell-Eingang bei 5 m (1080p, ganzes Bild)
AUFLOESUNGEN = [(1920, 1080), (1280, 720), (640, 480)]
MESSUNGEN = [('3', 'quer'), ('5', 'quer'), ('5', 'laengs')]   # (Distanz in m, Ausrichtung)
LAGE_TEXT = {'quer': 'quer', 'laengs': 'laengs (Spitze zur Kamera)'}


def lies_taste(warten_ms):
    """Gedrueckte Taste als Kleinbuchstabe (S und s gleich, auch mit Feststelltaste)."""
    k = cv2.waitKey(warten_ms) & 0xFF
    return chr(k).lower() if k != 0xFF else ''


def oeffne_hoechste_aufloesung(index):
    """Oeffnet die Kamera in der hoechsten Aufloesung, die sie wirklich liefert."""
    for breite, hoehe in AUFLOESUNGEN:
        cap, frame, _ = oeffne_kamera(index, breite, hoehe)
        if frame.shape[1] == breite:
            return cap, frame
        cap.release()
    cap, frame, _ = oeffne_kamera(index)  # Notfall: Standardaufloesung der Kamera
    return cap, frame


def text(bild, inhalt, farbe):
    """Hinweis oben ins Bild, Schrift passend zur Bildbreite (langer Text wird kleiner)."""
    groesse = bild.shape[1] / 1300
    breite = cv2.getTextSize(inhalt, cv2.FONT_HERSHEY_SIMPLEX, groesse, max(1, int(2.5 * groesse)))[0][0]
    groesse *= min(1.0, (bild.shape[1] - 30) / breite)
    cv2.rectangle(bild, (0, 0), (bild.shape[1], int(50 * groesse) + 20), (0, 0, 0), -1)
    cv2.putText(bild, inhalt, (15, int(40 * groesse) + 10), cv2.FONT_HERSHEY_SIMPLEX, groesse,
                farbe, max(1, int(2.5 * groesse)))


def main():
    ap = argparse.ArgumentParser(description='T3a Sichtfeld und Aufloesung')
    ap.add_argument('--kamera', type=int, default=None, help='Kameraindex (Standard: perception.yaml)')
    args = ap.parse_args()

    index = args.kamera if args.kamera is not None else parameter('camera')['device']
    cap, frame = oeffne_hoechste_aufloesung(index)
    hoehe_px, breite_px = frame.shape[:2]
    print(f'=== T3a Kamera ===\nKamera {index}: {breite_px}x{hoehe_px}')
    kamerahoehe = warte_enter('Hoehe der Kamera ueber Boden in cm (Enter = ueberspringen): ')

    fotos = ERGEBNISSE / 'fotos_t3a'
    fotos.mkdir(parents=True, exist_ok=True)
    protokoll = Protokoll('t3a_kamera', ['distanz_m', 'ausrichtung', 'px_kamera', 'px_modell_640',
                                         'aufloesung', 'kamerahoehe_cm', 'foto'])
    klicks = []

    def maus(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN and len(klicks) < 2:
            klicks.append((x, y))

    cv2.namedWindow(FENSTER, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(FENSTER, min(breite_px, 1280), int(min(breite_px, 1280) * hoehe_px / breite_px))
    cv2.setMouseCallback(FENSTER, maus)
    try:
        for distanz, lage in MESSUNGEN:
            while True:  # Live-Bild bis S
                neu = lies_bild(cap, versuche=1)
                if neu is None:
                    cv2.waitKey(10)
                    continue
                frame = neu
                bild = frame.copy()
                text(bild, f'Knochen {LAGE_TEXT[lage]} auf {distanz} m legen, dann S druecken '
                     '(Q = Ende)', (0, 255, 255))
                cv2.imshow(FENSTER, bild)
                taste = lies_taste(1)
                if taste == 'q':
                    raise KeyboardInterrupt
                if taste == 's':
                    break
            klicks.clear()
            while len(klicks) < 2:  # eingefroren, Enden anklicken
                bild = frame.copy()
                text(bild, f'{distanz} m {lage}: beide sichtbaren Enden des Knochens anklicken',
                     (0, 0, 255))
                for pt in klicks:
                    cv2.circle(bild, pt, 6, (0, 0, 255), -1)
                cv2.imshow(FENSTER, bild)
                if lies_taste(20) == 'q':
                    raise KeyboardInterrupt
            (x1, y1), (x2, y2) = klicks
            px = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            px_modell = px * MODELL_EINGANG / max(breite_px, hoehe_px)
            cv2.line(frame, klicks[0], klicks[1], (0, 0, 255), 2)
            datei = fotos / f't3a_{distanz}m_{lage}_{time.strftime("%Y%m%d_%H%M%S")}.jpg'
            cv2.imwrite(str(datei), frame)
            print(f'{distanz} m {lage}: Knochen {px:.0f} px im Kamerabild, {px_modell:.0f} px im '
                  f'Modell-Eingang ({MODELL_EINGANG} px)')
            protokoll.schreibe(distanz_m=distanz, ausrichtung=lage, px_kamera=round(px),
                               px_modell_640=round(px_modell), aufloesung=f'{breite_px}x{hoehe_px}', kamerahoehe_cm=kamerahoehe,
                               foto=datei.name)
    except KeyboardInterrupt:
        print('Abgebrochen.')
    finally:
        cap.release()
        cv2.destroyAllWindows()
        protokoll.schliessen()

    if protokoll.zeilen:
        sichtbar = warte_enter('Bei 5 m: Waren die Objekte 1,3 m links und rechts der Mitte beide im Bild? (j/n): ')
        tabelle = ['| Distanz | ausrichtung | px Kamerabild | px Modell-Eingang 640 |',
                   '| --- | --- | --- | --- |']
        tabelle += [f'| {z["distanz_m"]} m | {z["ausrichtung"]} | {z["px_kamera"]} | '
                    f'{z["px_modell_640"]} |'
                    for z in protokoll.zeilen]
        inhalt = (f'Kamera: Index {index}, {breite_px}x{hoehe_px}, Hoehe {kamerahoehe or "-"} cm\n\n'
                + '\n'.join(tabelle)
                + f'\n\n30-Grad-Bereich ganz im Bild: {"ja" if sichtbar.startswith("j") else "nein"}'
                + f'\n\nVergleich: Schaetzung im Konzept fuer 5 m quer ca. {ERWARTUNG_5M} px '
                  '(ganzes 1080p-Bild auf 640 px). YOLO braucht erfahrungsgemaess mind. ca. 15-20 px.')
        speichere_zusammenfassung(protokoll, 'T3a Sichtfeld und Aufloesung', inhalt)


if __name__ == '__main__':
    main()
