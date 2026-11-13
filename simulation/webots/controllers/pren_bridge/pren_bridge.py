"""Webots-Controller fuer den Roboter: startet die ROS-Bridge aus dem Paket pren_simulation.

Webots startet diese Datei ueber webots-controller.exe. Die eigentliche Logik liegt im
ROS-Paket pren_simulation, damit sie mit colcon gebaut und getestet wird.
"""

from pathlib import Path

from pren_simulation.webots_bridge import main

SOUNDS_DIR = Path(__file__).resolve().parents[2] / 'sounds'

if __name__ == '__main__':
    main(SOUNDS_DIR)
