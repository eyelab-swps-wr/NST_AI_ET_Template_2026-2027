# Projekt 1 - Gaze Choice

Szybkie demo na Tobii Pro Spectrum, oparte na badaniu Krajbich, Armel i Rangel (2010).
Brief: `projekt-1-brief.md`.

**Przed startem:** skalibruj uczestnika w Tobii Pro Eye Tracker Manager.
Aplikacja nie ma wlasnej kalibracji. Uzywa kalibracji zapisanej w trackerze.

Ustalenia grupy z briefu:
- instrukcja: "Wybierz opcje, ktora wolisz...",
- pary neutralnych produktow; strona lewa/prawa jest losowana, polowa par jest zamieniona stronami,
- przebieg kazdej pary: krzyzyk 800 ms, para az do odpowiedzi (maks. 10 s), "Zapisano" przez 500 ms,
- odpowiedz: strzalka w lewo lub w prawo albo F / J,
- wzrok jest mierzony w tle, bez kropki na ekranie.

Na koncu wyswietla sie ekran z wynikiem: czas patrzenia na opcje wybrana i niewybrana,
ostatnia sekunda przed wyborem oraz czas decyzji. Wynik zapisuje sie w `data/wynik_<czas>.csv`.

Pary produktow sa w liscie `PAIRS` na gorze pliku `projekt1_gaze_choice.py`. Mozesz je podmienic.
Brief podaje tylko "12-20 par", bez konkretnych produktow.

Uruchomienie:
- `run_projekt1.bat`: z trackerem.
- `run_projekt1_symulacja.bat`: test, mysz udaje wzrok.
