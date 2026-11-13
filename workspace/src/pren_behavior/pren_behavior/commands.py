"""Befehle, ihre Quellen und welche Quelle welchen Befehl geben darf."""

from enum import Enum, IntEnum

from pren_interfaces.msg import DogCommand


class Command(IntEnum):
    """Befehle an den Hund. Die Werte kommen aus pren_interfaces/DogCommand."""

    HIER = DogCommand.HIER
    BRAV = DogCommand.BRAV
    SITZ = DogCommand.SITZ
    SUCH = DogCommand.SUCH
    PLATZ = DogCommand.PLATZ
    AUF = DogCommand.AUF


class CommandSource(str, Enum):
    """Woher ein Befehl kommt. Die Werte kommen aus DogCommand.SOURCE_*."""

    VOICE = DogCommand.SOURCE_VOICE
    GESTURE = DogCommand.SOURCE_GESTURE
    GUI = DogCommand.SOURCE_GUI


# Laut Aufgabenstellung: Sprache HIER, BRAV, SITZ, SUCH; Gesten SITZ, PLATZ, AUF.
# Die GUI darf zum Testen alle Befehle senden.
ALLOWED_COMMANDS_BY_SOURCE = {
    CommandSource.VOICE: frozenset({Command.HIER, Command.BRAV, Command.SITZ, Command.SUCH}),
    CommandSource.GESTURE: frozenset({Command.SITZ, Command.PLATZ, Command.AUF}),
    CommandSource.GUI: frozenset(Command),
}


def is_allowed(command: Command, source: CommandSource) -> bool:
    """Gibt zurueck, ob die Quelle diesen Befehl laut Aufgabenstellung geben darf."""
    return command in ALLOWED_COMMANDS_BY_SOURCE[source]
