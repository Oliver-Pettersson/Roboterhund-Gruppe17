"""Befehle, ihre Quellen und welche Quelle welchen Befehl geben darf."""

from enum import Enum, IntEnum


class Command(IntEnum):
    """Befehle an den Hund. Die Werte entsprechen pren_interfaces/DogCommand."""

    HIER = 1
    BRAV = 2
    SITZ = 3
    SUCH = 4
    PLATZ = 5
    AUF = 6


class CommandSource(str, Enum):
    """Woher ein Befehl kommt. Die Werte entsprechen DogCommand.SOURCE_*."""

    VOICE = 'voice'
    GESTURE = 'gesture'
    GUI = 'gui'


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
