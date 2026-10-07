# ROS-2-Befehle

## Einzelnes Paket bauen

Im Verzeichnis `workspace`:

```powershell
colcon build --merge-install --packages-select pren_control
. .\install\local_setup.ps1
```

Nach jeder Änderung am Paket muss es neu gebaut und das lokale Setup erneut geladen werden.
