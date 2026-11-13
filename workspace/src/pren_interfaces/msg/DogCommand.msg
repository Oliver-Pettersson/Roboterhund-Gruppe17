# Ein erkannter Befehl an den Hund (aus Sprache, Geste oder GUI).

uint8 HIER=1
uint8 BRAV=2
uint8 SITZ=3
uint8 SUCH=4
uint8 PLATZ=5
uint8 AUF=6

string SOURCE_VOICE=voice
string SOURCE_GESTURE=gesture
string SOURCE_GUI=gui

std_msgs/Header header
uint8 command          # eine der Konstanten oben
string source          # SOURCE_VOICE, SOURCE_GESTURE oder SOURCE_GUI
float32 confidence     # 0.0 bis 1.0, 1.0 wenn die Quelle keine Konfidenz liefert
