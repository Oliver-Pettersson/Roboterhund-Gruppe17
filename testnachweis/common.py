"""
Gemeinsame Hilfen fuer die Tests T1-T3 (Testnachweis, Bericht Kapitel 7).

Die Tests nutzen dieselben Klassen und Parameter wie die ROS-2-Nodes in
workspace/src/pren_perception (Parameter aus pren_bringup/config/perception.yaml).
Nur der Transport ueber ROS-Topics faellt weg, damit die Zeiten genau gemessen werden.
"""

import csv
from datetime import datetime
import platform
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ERGEBNISSE = REPO_ROOT / 'testnachweis' / 'ergebnisse'
PERCEPTION_YAML = REPO_ROOT / 'workspace' / 'src' / 'pren_bringup' / 'config' / 'perception.yaml'


def parameter(node: str) -> dict:
    """ros__parameters eines Nodes aus perception.yaml."""
    with open(PERCEPTION_YAML, encoding='utf-8') as f:
        return yaml.safe_load(f)[node]['ros__parameters']


def rechner() -> str:
    """Kurzbeschreibung des Rechners fuer das Protokoll."""
    return f'{platform.node()} ({platform.system()} {platform.release()}, {platform.processor()})'


class Protokoll:
    """Schreibt pro Versuch eine Zeile in eine CSV-Datei (Semikolon getrennt)."""

    def __init__(self, name: str, felder):
        ERGEBNISSE.mkdir(parents=True, exist_ok=True)
        self.start = datetime.now()
        self.pfad = ERGEBNISSE / f'{name}_{self.start:%Y-%m-%d_%H%M%S}.csv'
        self.felder = ['nr', 'zeit'] + list(felder)
        self.zeilen = []
        self._datei = open(self.pfad, 'w', newline='', encoding='utf-8-sig')
        self._csv = csv.DictWriter(self._datei, fieldnames=self.felder, delimiter=';')
        self._csv.writeheader()

    def schreibe(self, **werte) -> None:
        """Haengt einen Versuch an und speichert sofort."""
        zeile = {'nr': len(self.zeilen) + 1, 'zeit': f'{datetime.now():%H:%M:%S}'}
        for k, v in werte.items():
            if isinstance(v, bool):
                v = 'ja' if v else 'nein'
            elif isinstance(v, float):
                v = f'{v:.3f}'
            zeile[k] = v
        self.zeilen.append(zeile)
        self._csv.writerow(zeile)
        self._datei.flush()

    def schliessen(self) -> None:
        """Datei schliessen. Ohne gespeicherte Versuche wird die leere Datei geloescht."""
        self._datei.close()
        if not self.zeilen:
            self.pfad.unlink(missing_ok=True)


def rate_tabelle(zeilen, gruppe, latenz='latenz_s'):
    """Markdown-Tabelle: Versuche, korrekt, Rate und Latenz je Gruppe (z. B. je Befehl)."""
    gruppen = {}
    for z in zeilen:
        schluessel = tuple(z[g] for g in gruppe)
        gruppen.setdefault(schluessel, []).append(z)
    kopf = list(gruppe) + ['Versuche', 'korrekt', 'Rate', 'Latenz Mittel', 'Latenz max']
    out = ['| ' + ' | '.join(kopf) + ' |', '|' + ' --- |' * len(kopf)]
    alle = sorted(gruppen.items()) + [(('Gesamt',) + ('',) * (len(gruppe) - 1), zeilen)]
    for schluessel, gz in alle:
        ok = sum(z['korrekt'] == 'ja' for z in gz)
        lat = [float(z[latenz]) for z in gz if z.get(latenz) not in (None, '')]
        mittel = f'{sum(lat) / len(lat):.2f} s' if lat else '-'
        maximum = f'{max(lat):.2f} s' if lat else '-'
        out.append('| ' + ' | '.join(list(schluessel) + [
            str(len(gz)), str(ok), f'{ok / len(gz):.0%}' if gz else '-', mittel, maximum]) + ' |')
    return '\n'.join(out)


def speichere_zusammenfassung(protokoll: Protokoll, titel: str, text: str) -> Path:
    """Zusammenfassung als Markdown neben die CSV legen und ausgeben."""
    pfad = protokoll.pfad.with_suffix('.md')
    inhalt = (f'# {titel}\n\nDatum: {protokoll.start:%d.%m.%Y %H:%M}  \n'
              f'Rechner: {rechner()}  \nRohdaten: {protokoll.pfad.name}\n\n{text}\n')
    pfad.write_text(inhalt, encoding='utf-8')
    print('\n' + inhalt)
    print(f'Gespeichert: {protokoll.pfad}\n             {pfad}')
    return pfad


def lies_bild(cap, versuche: int = 10):
    """Naechstes Kamerabild oder None. Die ersten Bilder sind manchmal leer."""
    import cv2
    for _ in range(versuche):
        try:
            ok, frame = cap.read()
        except cv2.error:  # MSMF wirft bei manchen Kameras statt False zurueckzugeben
            ok, frame = False, None
        if ok and frame is not None:
            return frame
    return None


def oeffne_kamera(index: int, breite: int = None, hoehe: int = None):
    """Oeffnet eine Kamera und gibt (cap, erstes Bild, Backend) zurueck.

    Zuerst DirectShow: Unter Windows oeffnet es USB-Webcams in wenigen Sekunden, MSMF
    (OpenCV-Standard) braucht z. B. fuer eine Logitech C922 fast eine Minute. Liefert die
    gewuenschte Aufloesung kein Bild, wird die Standardaufloesung der Kamera genommen.
    """
    import cv2
    backends = [('DSHOW', cv2.CAP_DSHOW), ('MSMF', cv2.CAP_MSMF)]
    aufloesungen = [(breite, hoehe), (None, None)] if breite and hoehe else [(None, None)]
    for name, backend in backends:
        for b, h in aufloesungen:
            cap = cv2.VideoCapture(index, backend)
            if not cap.isOpened():
                cap.release()
                break  # dieses Backend kennt die Kamera nicht
            if b and h:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, b)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            frame = lies_bild(cap)
            if frame is not None:
                return cap, frame, name
            cap.release()
    raise SystemExit(f'Kamera {index} liefert kein Bild. Andere Programme mit Kamera schliessen, '
                     'in Windows den Kamerazugriff erlauben, anderen Index mit --kamera probieren.')


def warte_enter(text: str) -> str:
    """Eingabe im Terminal, gibt die Eingabe in Kleinbuchstaben zurueck.

    Ende der Eingabe (Fenster zu, Ctrl+Z, Ctrl+C unter Windows) zaehlt wie q.
    """
    try:
        return input(text).strip().lower()
    except EOFError:
        print()
        return 'q'
