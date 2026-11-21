# Zaufanie do twarzy: prawdziwe vs wygenerowane przez AI

Uproszczone badanie dydaktyczne (PsychoPy + Tobii). Uczestnik ogląda 12 portretów (6 prawdziwych,
6 wygenerowanych przez AI), każdy **3 s**, po czym ocenia zaufanie w skali 1–7.

**Status:** NIE przetestowano z rzeczywistym eye-trackerem. Zweryfikowano tylko tryb symulacji
(`--autotest`: pełna sesja 12 prób, zapis plików, I-VT, AOI). Dane z symulacji nie nadają się do analizy.

## Uruchomienie
- `run_experiment.bat --sim --windowed` – test z myszą zamiast wzroku (okno startowe: kod, zgody, odległość).
- `run_experiment.bat --autotest` – automatyczna sesja bez interakcji (dane syntetyczne).
- `run_experiment.bat` – tryb Tobii (wymaga trackera i `..\setup_bundle.bat`; awaryjnie użyje `uv`).
- ESC przerywa w każdej chwili; zapisane próby zostają.

## Przebieg
okno startowe (zgoda, pełnoletność, wzrok) → kalibracja 9-punktowa (`spectrum.calibrate`) → walidacja
własna (5 punktów, błąd w stopniach) → instrukcja → próba treningowa (schematyczny owal, nie twarz) →
12 prób: krzyż 500 ms → portret 3 s → ocena 1–7 (klawisze lub mysz, bez limitu) → pauza 1 s;
przerwa 30 s po 5. i 10. próbie → pytanie o komfort → debriefing → automatyczna analiza.

Kolejność: losowana osobno dla uczestnika z ziarnem wyprowadzonym z kodu (odtwarzalna); 3 bloki po 4
próby, w każdym 2 REAL + 2 AI; nie więcej niż 2 obrazy tej samej kategorii z rzędu.

## Bodźce
`stimuli/REAL_01–06.png`, `AI_01–06.png` powstały z `badania/natural face` i `badania/ai face`
(`prepare_stimuli.py`, oryginały nietknięte): tło zastąpione jednym poziomem RGB(230,230,230) (maska
osoby z modelu tła), wspólne płótno 1536×1024. Podgląd: `stimuli_preview.png` (z AOI). Metadane: `stimuli.json`.
Źródło/licencja: zgoda zadeklarowana przez badacza 2026-11-21, brak dokumentu; generator AI: nieznany.

## AOI (te same reguły dla wszystkich bodźców, względem ramki twarzy z detektora Haara)
`eyes` (15–50% wysokości), `lower` (usta i dolna część, 55–100%), `face` (ramka), `background` (poza ramką: włosy,
ubranie, tło). Brak wartości sztywnych dla pojedynczych zdjęć.

## Pomiary (`aoi_metrics.csv`)
total fixation duration, fixation count, time to first fixation, czas na 100 000 px² AOI, udział w czasie
ważnych próbek, valid_gaze_ratio. Fiksacje: I-VT (30°/s, okno 20 ms, min. 60 ms, scalanie 75 ms/0,5°) –
**wartości startowe do potwierdzenia pilotażem**, nie progi EyeLink z artykułu Tatlera.

## Do ustalenia na stanowisku
- Zmierz i wpisz szerokość obszaru obrazu [cm] i odległość [cm] (domyślnie 52 / 65 – tylko przykład).
- Progi walidacji (średni błąd ≤ 1,0°, maks. punktu ≤ 1,5°) i `VALID_RATIO_MIN = 0,60` to moje wartości
  startowe, ustalone przed zbieraniem danych; potwierdź pilotażem na 2–3 osobach.
- Czy używany SDK obsługuje X120 (repozytorium zawiera szablony pod Spectrum i `tobii-research` 2.1.0).
- Mapowanie wzroku na piksele zakłada pełny ekran pokrywający obszar obrazu trackera.

## Pliki sesji (`data/<kod>_S<sesja>_<czas>/`, ignorowane przez git)
`trials.csv`, `gaze_samples.csv` (współrzędne 0–1, (0,0)=lewy górny; czas w ms od startu aplikacji),
`fixations.csv`, `aoi_metrics.csv`, `session_config.json`, `events.log`, `quality_report.txt`, `trial_order.json`.
Przechowuj lokalnie, usuń po zajęciach zgodnie z instrukcją prowadzącego; nie wysyłaj surowych danych do usług zewnętrznych.

## Wersja HTML (`web/index.html` + `tobii_bridge.py`)
Strona z badaniem w przeglądarce + lokalny most Pythona. **Przeglądarka sama nie ma dostępu do eye-trackera**, dlatego
`tobii_bridge.py` łączy się z urządzeniem przez Tobii Pro SDK (`tobii_research`), nasłuchuje tylko na `127.0.0.1:8765`,
odbiera od strony znaczniki czasu prób i zapisuje dane w tym samym formacie co wersja PsychoPy
(`trials.csv`, `gaze_samples.csv`, `fixations.csv`, `aoi_metrics.csv`, …; `data/<kod>_S<sesja>_<czas>_HTML[_SIM]/`).

- `run_html_experiment.bat` – tryb Tobii (wymaga trackera; brak trackera = błąd, bez cichej symulacji).
- `run_html_experiment.bat --sim` – dane syntetyczne, tylko test aplikacji (adres `http://127.0.0.1:8765/`).
- Wymagany **pełny ekran** na ekranie z trackerem (strona sprawdza rozmiar okna), zoom przeglądarki 100%.
- ESC albo wyjście z pełnego ekranu przerywa sesję; zapisane próby zostają.
- Synchronizacja czasu: strona mierzy przesunięcie zegara względem mostu (12 pingów, wybór najmniejszego RTT) przed każdą próbą;
  początek/koniec ekspozycji to znaczniki klatek `requestAnimationFrame`. Niepewność: ok. ±1 klatka ekranu + opóźnienie wyświetlacza
  (nie mierzone). Dla badań wymagających ms-dokładności użyj wersji PsychoPy.
- Przetestowano: pełną sesję 12 prób w trybie `--sim` (Edge/Playwright): ekspozycja 3004–3005 ms, ~360 próbek/próbę, zapis i analiza OK.
  **Nie przetestowano:** prawdziwego trackera, kalibracji/walidacji, pełnego ekranu z fizycznym ekranem, ESC z klawiatury.
- X120: nie zakładaj, że `tobii_research` (Tobii Pro SDK) go obsługuje – sprawdź na stanowisku.

## Szybki prototyp Tobii Pro Spectrum (`trustfaces_spectrum.py`)
Jednoplikowa wersja wzorowana na `AI Template App`, korzysta ze wspólnego `../spectrum.py`.
Przebieg: kod uczestnika → połączenie ze Spectrum → kalibracja 9-punktowa (`spectrum.calibrate`, R = powtórz) →
instrukcja → 12 prób (krzyż 500 ms → portret 3 s → ocena 1–7 klawiszami) → podsumowanie REAL vs AI w konsoli.

- `run_spectrum_prototype.bat` – Tobii Pro Spectrum (`--show-gaze` dodaje kropkę wzroku na portrecie, tylko do podglądu).
- `run_spectrum_prototype_symulacja.bat` – mysz zamiast wzroku, w oknie.
- Wyniki: `data/<kod>_<czas>/trials.csv` (ocena, RT, czas patrzenia na AOI w ms i %, czas do pierwszego spojrzenia na oczy),
  `gaze_samples.csv` (surowe próbki z AOI), `session.json`.
- Uproszczenia względem pełnej wersji: brak walidacji w stopniach, brak I-VT (czas patrzenia = liczba ważnych próbek / Hz),
  brak próby treningowej i okna zgód. AOI te same (`stimuli.json`).
- Przetestowano tylko symulację (`--sim --auto`). **Nie przetestowano z prawdziwym Spectrum.**
