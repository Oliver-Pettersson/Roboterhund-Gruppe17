# Aktueller Zustand des Hundes, fuer Anzeige und Diagnose.

std_msgs/Header header
string state                 # Verhaltenszustand: STANDING, SITTING, LYING, COMING, SEARCHING
string activity              # Lesbare Beschreibung, z. B. "Suchbereich absuchen"
bool busy                    # true, solange SUCH laeuft und andere Befehle gesperrt sind
uint8 posture                # Posture-Konstante (STAND, SIT, LIE)
uint8 last_command           # DogCommand-Konstante, 0 = noch kein Befehl
string last_command_source
