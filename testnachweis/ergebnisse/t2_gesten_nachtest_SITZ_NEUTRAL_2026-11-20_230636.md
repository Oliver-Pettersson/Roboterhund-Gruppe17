# T2 Gestenerkennung - Nachtest SITZ, NEUTRAL

Datum: 20.11.2026 23:06  
Rechner: Lianos_HP (Windows 11, Intel64 Family 6 Model 189 Stepping 1, GenuineIntel)  
Rohdaten: t2_gesten_nachtest_SITZ_NEUTRAL_2026-11-20_230636.csv

Kamera: Index 1, 640x480
Glaettung: 4 von 5 Bildern, SITZ 7 von 8

| distanz_m | erwartet | Versuche | korrekt | Rate | Latenz Mittel | Latenz max |
| --- | --- | --- | --- | --- | --- | --- |
| 0.5 | NEUTRAL | 5 | 5 | 100% | - | - |
| 0.5 | SITZ | 5 | 5 | 100% | 0.44 s | 0.44 s |
| 1 | NEUTRAL | 5 | 5 | 100% | - | - |
| 1 | SITZ | 5 | 5 | 100% | 0.62 s | 1.17 s |
| 2 | NEUTRAL | 5 | 5 | 100% | - | - |
| 2 | SITZ | 5 | 5 | 100% | 0.45 s | 0.50 s |
| Gesamt |  | 30 | 30 | 100% | 0.50 s | 1.17 s |

Rechenzeit pro Bild (MediaPipe + Klassifikation): 30 ms im Mittel

Kriterium: jede Geste >= 90 % in allen Distanzen, NEUTRAL loest nichts aus, unter 1 s.
