# AI Template App — Tobii X3-120 (X120)

> **Wersja dla Tobii X3-120.** Dla Tobii Pro Spectrum użyj [`../AI Template App`](../AI%20Template%20App/).

To ten sam szablon co wersja Spectrum (kalibracja 5-punktowa, kursor spojrzenia na żywo, ESC = wyjście
w każdej chwili). Różnice:

- szuka trackera **X3-120** po nazwie modelu (jeśli go nie rozpozna, bierze pierwszy znaleziony i wypisuje ostrzeżenie),
- ustawia częstotliwość **120 Hz**,
- etykieta na ekranie: `LIVE - Tobii X3-120`.

## Uruchomienie (Windows)

1. Podłącz X3-120 i sprawdź w **Tobii Pro Eye Tracker Manager**, czy jest widoczny.
2. Uruchom `run_app_x120.bat`. Skrypt używa bundlowanego Pythona `..\PsychoPy\python.exe`
   (64-bit Python 3.10 z PsychoPy i `tobii-research` 2.1.0). Jeśli go nie ma, najpierw uruchom `..\setup_bundle.bat`.

Szablon korzysta ze wspólnego modułu `../spectrum.py` (ESC, kalibracja w tle, strumień gaze zgodny z SDK).
Mimo nazwy ten moduł działa z każdym trackerem Tobii Pro SDK, także z X3-120.
