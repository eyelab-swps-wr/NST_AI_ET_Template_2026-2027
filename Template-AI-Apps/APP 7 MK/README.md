# APP 7 MK – Wpływ instrukcji na oglądanie 7 portretów (prototyp v4.0)

Replikacja ze zmianą: Tatler i in. (2010), *Yarbus, eye movements, and vision*.

## Uruchomienie
`run_app7.bat`. Ustawienia wpisuje się w oknie konsoli (Enter = wartość domyślna):

| Tryb | Do czego służy |
|---|---|
| 1 – Tobii Pro Spectrum | prawdziwy pomiar (tobii-research 2.1.0 przez `../spectrum.py`, jak w AI Template App) |
| 2 – SYMULACJA (mysz) | test bez trackera; spojrzenie = kursor; dane oznaczone `data_source=mouse_simulation` |
| 3 – Podgląd AOI | 9 AOI nałożonych na każde zdjęcie, żeby zespół mógł je sprawdzić |

Automatyczny test całego przebiegu (bez klawiatury, okno 1024×640): `..\PsychoPy\python.exe app7_portrety_instrukcja.py --selftest`.
ESC w każdej chwili przerywa sesję; to, co zebrano do tego momentu, zostaje w `data/`.

## Przebieg
Zgoda → pozycja głowy + kalibracja 9-punktowa (`spectrum.calibrate`) → walidacja 5-punktowa (błąd w °) → podgląd wzroku na żywo →
blok **swobodne** (zawsze pierwszy) → bloki **status** / **wiarygodność** (kolejność losowana 50/50) → podsumowanie.
Każdy blok zaczyna się 10-sekundową instrukcją. Każda próba: krzyżyk fiksacyjny 500–1000 ms → zdjęcie (domyślnie 20 s).
Kolejność zdjęć jest losowana osobnie w każdym bloku, a ziarno losowania jest zapisywane.
Jeśli przez ponad 2 s nie ma ważnego spojrzenia, próba jest przerywana (R = rekalibracja, SPACJA = powtórzenie z nowym `trial_id`, `repeat_of` = id przerwanej próby).

## Dane (`data/<kod>_<data>_*`)
- `samples.csv`: surowe próbki (oba oczy, ważność, timestamp SDK w µs, AOI próbki)
- `fixations.csv`: fiksacje I-DT z przypisanym AOI
- `trials.csv`: log prób (warunek, zdjęcie, kolejność, czasy start/stop, odsetek ważnych próbek, kalibracja/walidacja)
- `aoi_summary.csv`: próba × 9 AOI (liczba fiksacji, czas, udział, gęstość na px², czas znormalizowany = udział czasu / udział powierzchni)
- `config.json`: ustawienia, ziarno, plan losowania, geometria, wersje, definicje AOI, status sesji

## DO WERYFIKACJI przez zespół (prototyp tego nie rozstrzyga)
- **AOI** w `aoi_definitions.json` to prostokąty wyznaczone na oko z miniatur. Sprawdźcie je w trybie 3 i poprawcie, a wielokąty dodajcie później, jeśli będą potrzebne.
- **Detekcja fiksacji**: tobii-research podaje tylko surowe próbki, więc aplikacja sama liczy fiksacje algorytmem I-DT z parametrami **pilotażowymi** (dyspersja 1,0°, min. 100 ms, max przerwa 75 ms). Trzeba je zatwierdzić.
- **Geometria**: stopnie (walidacja, dyspersja, rozmiar kątowy) zależą od wpisanej odległości i szerokości ekranu w cm. Zmierzcie je.
- **Częstotliwość**: 120 Hz z `spectrum.py` (`SPECTRUM_HZ`). Potwierdźcie ją na stanowisku.
- Działanie z prawdziwym Spectrum **nie było testowane sprzętowo**. Testy przeszedł tylko tryb symulacji.
- Licencje zdjęć, kolor zespołu, liczba uczestników, procedura zgody i ochrony danych.

Podsumowanie na końcu to opis jednej sesji, a nie test statystyczny.
