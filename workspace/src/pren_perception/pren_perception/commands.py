"""Befehle, die die Wahrnehmung erkennen kann. Einzige Quelle der Werte: DogCommand.msg."""

from enum import IntEnum

from pren_interfaces.msg import DogCommand


class Command(IntEnum):
    """Befehle an den Hund."""

    HIER = DogCommand.HIER
    BRAV = DogCommand.BRAV
    SITZ = DogCommand.SITZ
    SUCH = DogCommand.SUCH
    PLATZ = DogCommand.PLATZ
    AUF = DogCommand.AUF
