# Logotypy Hitachi – gaze cascade (szybki prototyp)

Replikacja ze zmianą: Shimojo i in. (2003), twarze → 4 historyczne logo Hitachi (`Logo/`).
Brief: `brief-replikacja-tobii-pro-spectrum (1).md`.

## Uruchomienie
- `run_logotypy.bat P07` – Tobii Pro Spectrum (P07 = kod uczestnika, domyślnie P01)
- `run_logotypy_symulacja.bat` – **jawna symulacja**: mysz = wzrok, bez kalibracji (tylko test aplikacji)
- ESC = natychmiastowe przerwanie w każdym momencie

## Przebieg (skrócony, ~3 min)
1. Ekran startowy → **kalibracja** (`spectrum.calibrate` z szablonu: pozycja głowy, 9 punktów,
   wykres błędu w px; SPACJA = akceptuj, R = powtórz).
2. **Preferencja**: 6 prób = wszystkie pary 4 logo, kolejność i strona losowane (połowa par zamieniona).
3. **Kontrola**: 4 próby – „które logo ma więcej ciemnych elementów”.
4. Próba: krzyżyk 500 ms → para logo bez limitu czasu → strzałka ←/→ → przerwa 400 ms.
5. **Ekran wyników**: krzywa gaze likelihood (P(wzrok na logo wybranym)) w ostatnich 2 s przed odpowiedzią,
   preferencja vs kontrola, czas patrzenia na wybrane/niewybrane, RT, odsetek ważnych próbek.

Liczby prób: `N_CONTROL` i lista par w `logotypy_gaze_cascade.py`.

## Dane (`data/`)
- `trials_<kod>_<czas>.csv` – jedna linia na próbę (bodźce, wybór, RT, ważne próbki, dwell w AOI)
- `samples_<kod>_<czas>.csv` – surowe próbki (czas SDK w µs, czas względem odpowiedzi, x/y, ważność oczu, AOI)
- `config_<kod>_<czas>.json` – seed, tracker, częstotliwość, status kalibracji, ekran, podsumowanie

## Do weryfikacji (nie zakładamy)
- **Fiksacje**: SDK nie liczy fiksacji – prototyp liczy *dwell time z próbek*, nie Fixation Count.
  Algorytm fiksacji (np. Tobii Pro Lab I-VT) do ustalenia.
- Częstotliwość: domyślnie 120 Hz (`set SPECTRUM_HZ=600` przed uruchomieniem, aby zmienić).
- Odległość od ekranu, rozmiar fizyczny monitora, próg ważnych próbek i kryteria wykluczenia – po pilotażu.
- Brak prób treningowych i przerwy między blokami (skrócone celowo).
