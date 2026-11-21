# Projekt 1 - Wplyw kontrowersyjnej wypowiedzi na sledzenie wzroku

To badanie wlasne. Brief: `projekt-1-brief.md`. Uruchomienie: `run_projekt1.bat`.

## Przebieg sesji

1. Uczestnik wpisuje kod pseudonimowy.
2. Uczestnik wyraza zgode (klawisz T).
3. Aplikacja przydziela grupe 1:1: kontrolna albo eksperymentalna.
4. Aplikacja wyswietla ekran dla badacza z nazwa grupy. Badacz mowi na glos instruktaz warunku.
   Tresci opinii nie ma w aplikacji, bo grupa musi je wczesniej zatwierdzic.
5. Kalibracja Tobii (9 punktow, ze wspolnego `../spectrum.py`).
6. 5 prezentacji kropki na bialym tle po torze nieskonczonosci: ruch PLYNNY albo SKOKOWY (przeskok co 0.8 s, 12 pozycji). Kolejnosc losowana z seedem.
   W kazdej probie przez 3 s kropka jest CZERWONA - to sygnal dla badacza, zeby przeszkadzal (eksperymentalna: kontrowersyjna opinia, kontrolna: neutralna wypowiedz - DO USTALENIA). Kolor zmienia sie w obu grupach, wiec bodziec jest identyczny.
7. Ekran zakonczenia z wynikiem dla badacza.

Przy utracie sygnalu (dluzej niz 1 s) prezentacja sie zatrzymuje. Aplikacja wtedy ponawia kalibracje i powtarza te prezentacje raz.
Prezentacja z utrata sygnalu jest oznaczona w danych powodem wykluczenia.

## Dane

Dane trafiaja do folderu `data/<kod>_<czas>/`:
- `samples.csv`: surowe probki, waznosc lewego i prawego oka, polozenie kropki, odleglosc wzroku od kropki, typ ruchu (`motion`) i faza (`phase`: przeszkadzanie / bez_przeszkadzania),
- `fixations.csv`: fiksacje z czasem, odlegloscia od kropki i AOI (kropka albo poza),
- `session.json`: grupa, seed, tracker, parametry, kalibracje, proby i podsumowanie.

## DO WERYFIKACJI przed badaniem

Brief nie ustala tych rzeczy, wiec sa do potwierdzenia przez grupe:
- **Tracker:** brief zaklada Tobii X120, a aplikacja uzywa SDK z szablonu (`tobii-research` 2.1.0). Trzeba sprawdzic, czy X120 jest widoczny w tym SDK.
- **Parametry:** czas prezentacji, predkosc i rozmiar kropki, promien AOI. Sa na gorze pliku `.py`.
- **Detekcja fiksacji:** to uproszczony I-DT. Parametry trzeba ustalic wedlug dokumentacji SDK.
- **Pomiar:** odleglosc jest liczona w pikselach. Nie ma przeliczenia na stopnie.
- **Kryteria wykluczenia:** progi waznych probek nie sa jeszcze ustalone.
