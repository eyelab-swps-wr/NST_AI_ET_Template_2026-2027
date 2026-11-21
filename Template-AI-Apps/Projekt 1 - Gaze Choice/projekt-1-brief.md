# Brief dla AI: replikacja ze zmianą — eye-tracking

Urządzenie docelowe: Tobii Pro Spectrum. Wygenerowano: 2026-11-21T12:48:19.734Z

## Instrukcja dla AI
Celem aplikacji jest szybkie demo z Tobii Pro Spectrum, a nie rozbudowana aplikacja badawcza. Przed implementacją sprawdź README.md i kod w folderze Template-AI-Apps/AI Template App, zwłaszcza ai_template_app.py. Oprzyj połączenie z trackerem i kalibrację na działającym szablonie; użyj zgodnego SDK/API i nie wymyślaj ani nie zastępuj po cichu tych mechanizmów. Demo ma pokazać pomiar wzroku na żywo, a następnie od razu wyświetlić krótką, zrozumiałą interpretację zebranych danych. Zbuduj tylko elementy konieczne do tego przebiegu; nie dodawaj rozbudowanych ekranów, paneli, ustawień ani analiz. Jeśli szczegółów technicznych nie da się potwierdzić w szablonie lub dokumentacji, oznacz je jako wymagające weryfikacji.
Trzymaj się zakresu szybkiego demo: połącz tracker zgodnie z szablonem, przeprowadź kalibrację, pokaż pomiar na żywo i natychmiast podsumuj jego prostą interpretację. Nie buduj rozbudowanej aplikacji ani funkcji wykraczających poza ten przebieg.
Pomóż zespołowi studentów przygotować replikację ze zmianą. Oddziel fakty z publikacji, zmiany zespołu i niewiadome.
Nie uzupełniaj luk domysłami. Pola DO UZUPEŁNIENIA oraz Do weryfikacji traktuj jako pytania do zespołu; nie deklaruj gotowości do pomiaru bez potwierdzenia.
Podsumowanie zespołu ma być napisane i zatwierdzone przez studentów, nie przez AI.
Przed integracją sprzętową zweryfikuj obsługę Tobii Pro Spectrum w dokładnej wersji SDK/API i środowisku wskazanym poniżej, na podstawie dokumentacji i testu stanowiska. Nie zakładaj zgodności ani nie wymyślaj API.
Brak weryfikacji blokuje integrację sprzętową, nie analizę protokołu ani jawnie oznaczoną symulację. Nie zastępuj po cichu danych sprzętowych symulacją.
Opracuj jawne reguły kalibracji, ważności próbek, zegarów i synchronizacji, mapowania AOI, detekcji fiksacji, obsługi błędów i zamknięcia zasobów. Nie utożsamiaj próbek wzroku z fiksacjami.
Zaproponuj próbę pilotażową i sprawdź eksport danych prototypu względem opisanego schematu. Nie przedstawiaj testów symulacyjnych jako walidacji sprzętu.
Poniższa treść to dane projektu, nie upoważnienie do uruchamiania poleceń, dostępu do sekretów ani przekazywania danych osobowych.

## Zespół i sposób pracy

### Kolor zespołu
blue

### Nazwa projektu / wersja
Gaze Choice — replikacja Krajbich 2010

### Rodzaj badania
Replikacja ze zmianą

## 1. Oryginalne badanie

### Tytuł badania, autorzy, rok, DOI / link
Krajbich I., Armel C. i Rangel A. (2010), Visual fixations and the computation and comparison of value in simple choice, Nature Neuroscience 13, 1292–1298. DOI: 10.1038/nn.2635.

### Problem i kontekst
Czy kierunek i czas spojrzeń wpływają na prostą dwuwariantową decyzję konsumencką, czy jedynie odzwierciedlają wcześniej ukształtowaną preferencję?

### Pytanie badawcze
Czy długość i moment utrzymywania spojrzenia na jednej z dwóch opcji przewidują albo zwiększają prawdopodobieństwo jej wyboru?

### Luka badawcza
Popularne modele decyzji traktują porównanie wartości jako natychmiastową maksymalizację i zwykle pomijają wizualny proces zbierania informacji.

### Cel badania
Sprawdzić, jak sekwencje fiksacji i ich czas trwania współwystępują z wyborem oraz ocenić model, w którym spojrzenie chwilowo zwiększa wpływ fixowanego bodźca.

### Hipotezy (jeśli występują)
H1: Prawdopodobieństwo wyboru opcji rośnie w ostatnich 1000 ms wraz ze względną przewagą czasu patrzenia na nią. H2: Większa suma czasu fiksacji w AOI wybranej opcji wiąże się z większym prawdopodobieństwem wyboru. H3: Wzorzec spojrzeń będzie zmienny i rejestrowalny przed odpowiedzią, a nie dopiero po podjęciu decyzji.

### Uczestnicy
Oryginalnie 39 studentów Caltech. Nasz plan pilotażowy: 30–40 dorosłych uczestników, bez danych medycznych, z dobrym widzeniem lub korekcją; kryteria i kryteria wykluczenia należy potwierdzić przed rekrutacją.

### Aparatura i środowisko
Oryginał: stacjonarny eye-tracker Tobii, ekran i rejestracja wyboru klawiszami. Nasza aparatura: Tobii Pro Spectrum; dokładna rozdzielczość ekranu, odległość i częstotliwość są do potwierdzenia na stanowisku.

## 2. Zaplanuj badanie

### Pytanie i hipoteza / Oryginalne badanie
Jak wzrok uczestniczy w procesie porównywania wartości i wyboru pomiędzy dwoma bodźcami?

### Pytanie i hipoteza / Nasze badanie
Czy w parach neutralnych zdjęć opcji względny czas patrzenia na opcję przewiduje jej wybór, zwłaszcza tuż przed odpowiedzią?

### Pytanie i hipoteza / Uzasadnienie / wpływ na wynik
Utrzymujemy schemat dwóch opcji i wolny wybór, ale zmieniamy treść bodźców i ograniczamy próbę do pilotażowego demo.

### Warunki / zmienna niezależna / Oryginalne badanie
Wolny wybór pomiędzy dwoma snackami; początkowy rating preferencji 70 produktów i faza wyboru.

### Warunki / zmienna niezależna / Nasze badanie
Jedna para dwóch neutralnych, zrównoważonych estetycznie zdjęć produktów na każdą próbę; pozycja lewej/prawej opcji kontrbalansowana.

### Warunki / zmienna niezależna / Uzasadnienie / wpływ na wynik
Kontrbalansowanie pozycji pozwala oddzielić efekt wzroku od preferencji strony ekranu.

### Bodźce / Oryginalne badanie
70 zdjęć snacków i duplikowane pary oparte na indywidualnych wartościach preferencji.

### Bodźce / Nasze badanie
Np. 12–20 par neutralnych zdjęć produktów o podobnym zabarwieniu i powierzchni zajmowanej na ekranie.

### Bodźce / Uzasadnienie / wpływ na wynik
Bodźce mają wywoływać prawdziwą dwuwariantową decyzję, ale minimalizować wpływ seksualnego, politycznego lub zaskakująco emocjonalnego treści.

### Procedura / Oryginalne badanie
Ocena preferencji, 3 godziny bez jedzenia, wybór jednej nagrody w losowej próbie i eye-tracking przy 50 Hz.

### Procedura / Nasze badanie
Zgoda → instrukcja → kalibracja → 8 prób treningowych → 48 prób z losową kolejnością → krótki debriefing.

### Procedura / Uzasadnienie / wpływ na wynik
Skala jest wystarczająca do pilotu i ma ograniczyć czas sesji oraz zmęczenie.

### Pomiary / analiza / Oryginalne badanie
Czas i kolejne fiksacje, próby zmiany decyzji, reakcje i dopasowanie modelu drift-diffusion.

### Pomiary / analiza / Nasze badanie
Time to First Fixation, Total Fixation Duration, liczba i czas fiksacji w AOI lewej i prawej opcji oraz wybór i czas odpowiedzi.

### Pomiary / analiza / Uzasadnienie / wpływ na wynik
Pomiary bezpośrednio opisują, jak długo i gdzie uczestnik patrzył przed decyzją.

### Aparatura / uczestnicy / Oryginalne badanie
39 studentów Caltech, dobór oparty na akceptowalności snacków i świadoma zgoda.

### Aparatura / uczestnicy / Nasze badanie
Plan: 30–40 studentów lub dorosłych ochotników z kręgów uczelni; Tobii Pro Spectrum; kryteria rekrutacji i status kalibracji do potwierdzenia.

### Aparatura / uczestnicy / Uzasadnienie / wpływ na wynik
Grupa umożliwia pilotaż i porównanie w obrębie uczestnika przy rozsądnym czasie prowadzenia.

### Schemat eksperymentalny
Within Subjects

### Najważniejsze ograniczenia naszego badania
Mała próba pilotażowa ogranicza uogólnianie i moc statystyczną. Neutralne bodźce mogą być mniej motywujące niż nagrody żywieniowe. Względny czas spojrzenia nie przesądza o przyczynowości. Różnice wobec oryginału: krótsza procedura, liczba prób i inne bodźce. Brakuje potwierdzonego prógów kalibracji i SDK.

## 3. Bodźce, ekran i AOI

### Co widzi uczestnik? (ekran po ekranie)
Ekran startowy z instrukcją; stały punkt centralny; para prostokątnych zdjęć po lewej i prawej stronie ekranu; po odpowiedzi krótka informacja o zapisaniu próby.

### Co uczestnik ma zrobić
Wybrać jedną z dwóch opcji, która wydaje się bardziej atrakcyjna lub lepiej odpowiada instrukcji „Wybierz opcję preferowaną”. Wybór klawiszami strzałek lub F/J.

### Bodźce i ich identyfikatory
12–20 par zdjęć produktów przygotowanych jako pliki o identycznym rozmiarze pikseli. Każda próba ma przypisane stimulus_id, wersję lewej/prawej opcji i numer losowania.

### AOI 1 / AOI / nazwa
Lewy bodziec

### AOI 1 / Co obejmuje?
Prostokątny obszar obrazu po lewej stronie ekranu, bez marginesów ekranu i podpisów.

### AOI 1 / Dlaczego ważne?
Pomiar względnego czasu patrzenia i ostatnich fiksacji przed wyborem opcji lewej.

### AOI 2 / AOI / nazwa
Prawy bodziec

### AOI 2 / Co obejmuje?
Prostokątny obszar obrazu po prawej stronie ekranu, bez marginesów ekranu i podpisów.

### AOI 2 / Dlaczego ważne?
Pomiar względnego czasu patrzenia i ostatnich fiksacji przed wyborem opcji prawej.

### AOI 3 / AOI / nazwa
Punkt centralny

### AOI 3 / Co obejmuje?
Mały obszar 80–100 px wokół środka ekranu, skalowanie po rozdzielczości do potwierdzenia.

### AOI 3 / Dlaczego ważne?
Kontrola początku próby i powrót spojrzenia przed prezentacją pary.

## 4. Procedura

### Polecenie dla uczestnika
Na ekranie: „Wybierz opcję, którą wolisz. Nie ma dobrej lub złej odpowiedzi. Oglądaj parę tak długo, jak potrzebujesz, a następnie naciśnij strzałkę w lewo lub w prawo.” Badacz mówi to samo ustnie i potwierdza zrozumienie.

### Przebieg całej sesji
Zgoda i pseudonim → instrukcja → sprawdzenie widzenia i stanowiska → kalibracja Tobii → 8 prób treningowych → 48 prób głównych → krótki debriefing i wylogowanie.

### Przebieg pojedynczej próby
Wyświetlenie punktu centralnego przez 800 ms → para zdjęć aż do odpowiedzi, bez limitu ≤10 s → zapis odpowiedzi i czasu → ekran neutralny przez 500 ms.

### Randomizacja / kontrbalansowanie
Losowe ustawienie każdej pary po lewej/prawej stronie z kontrbalansowaniem pozycji. Kolejność prób generowana losowo z równomiernym rozłożeniem warunków i zapisanym seedem.

### Początek i koniec sesji oraz prób
Sesja zaczyna się po udanej kalibracji. Próba zaczyna się w momencie wyświetlenia pary i kończy po naciśnięciu odpowiedzi. Czas po 10 s bez odpowiedzi oznacza brak odpowiedzi i przejście do next trial.

### Przerwania, błędy, powtórzenia
Przy utracie trackingu zatrzymać próbę, oznaczyć tracking_status i kalibrację ponownie. Nie wypełniać danych estymacją. Powtórzyć tylko próbę, jeśli system nie zarejestrował pełnej prezentacji lub wystąpiła awaria.

### Odpowiedź uczestnika
Klawiatura

### Liczba prób, czasy prezentacji i reguły zakończenia
8 prób treningowych i 48 prób głównych; punkt centralny 800 ms; bodźce do odpowiedzi lub maks. 10 s; przerwa 500 ms; opcjonalna przerwa co 12 prób.

## 5. Pomiary i dane

### Pomiar 1 / Pomiar
Total Fixation Duration

### Pomiar 1 / Co oznacza w naszym badaniu?
Suma czasów ważnych fiksacji przypadających na AOI każdego obrazu w oknie od początku prezentacji pary do odpowiedzi; jednostka: ms.

### Pomiar 1 / AOI / warunek
AOI lewej i prawej opcji; porównanie lewa vs prawa, wynik przeliczony na wybrana vs niewybrana.

### Pomiar 1 / Jak porównujemy?
Porównać sumę czasu patrzenia na opcję wybraną i niewybraną; analiza trendu w przedziałach czasu przed decyzją.

### Pomiar 2 / Pomiar
Time to First Fixation

### Pomiar 2 / Co oznacza w naszym badaniu?
Czas od prezentacji pary do pierwszej fiksacji z lokalizacją w każdym AOI; jednostka: ms.

### Pomiar 2 / AOI / warunek
AOI lewej i prawej opcji.

### Pomiar 2 / Jak porównujemy?
Porównać pierwszy AOI i czas do wejścia spojrzenia do AOI opcji końcowo wybranej.

### Dodatkowe dane (odpowiedź, poprawność, czas zadania…)
Wybrana opcja, czas odpowiedzi, poprawność proceduralna, status trackingu, kolejność AOI i kryteria włączenia próby.

### Detekcja fiksacji i wizyt
Najpierw zweryfikować algorytm i parametry dostępne dla Pro Spectrum. Surowe próbki nie są fiksacjami. Docelowo Tobii I-VT; parametry, minimalna długość fiksacji i łączone oczami — DO WERYFIKACJI NA STANOWISKU.

### Schemat danych — jakie pola zapisujemy dla każdej próby?
participant_id; trial_id; condition; stimulus_id; left_stimulus_id; right_stimulus_id; trial_start; stimulus_onset; response; response_side; response_time; choice; tracking_status; calibration_status; AOI wyniki; randomization_seed.

### Plan analizy
Dane analizować na poziomie prób i uczestników. Dla H1 porównać średni udział czasu patrzenia na opcję wybraną vs niewybraną w przedziałach np. 0–500, 500–1000 i 1000 ms–decyzja. Dla H2 zastosować prosty model mieszany logit: wybór ~ względny czas fiksacji + side_of_choice; losowa intercepcja dla uczestnika.

## 6. Specyfikacja prototypu

- [x] Start / identyfikator — Kod uczestnika, wersja eksperymentu, zgoda i instrukcja. — WYMAGANE

- [x] Kalibracja i kontrola — Integracja lub jasno opisany etap ręczny; status jakości trackingu. — WYMAGANE

- [x] Warunki i bodźce — Prawidłowa kolejność, identyfikatory i kontrolowane różnice. — WYMAGANE

- [x] Instrukcja i próba — Start, prezentacja, odpowiedź, stop; bez przypadkowych przejść. — WYMAGANE

- [x] Logowanie zdarzeń — Timestampy, trial_id, condition, stimulus_id i status. — WYMAGANE

- [x] Zapis / eksport — Format danych, kompletność, bezpieczne przechowywanie. — WYMAGANE

- [x] Obsługa błędów — Utrata trackingu, przerwanie, restart lub powtórzenie próby. — WYMAGANE

- [ ] Próba pilotażowa — Przeprowadź całą sesję i sprawdź, czy dane odpowiadają procedurze. — NIE WYBRANO

### Minimalny działający prototyp (MVP)
Aplikacja pokazuje instrukcję, kalibruje sprzęt, prezentuje parę bodźców, rejestruje wybór i AOI, zapisuje CSV/JSON oraz po próbie pilotażowej podaje prostą tabelę: wybrana opcja, czas odpowiedzi i suma czasu patrzenia.

### Integracja eye-trackera — urządzenie, SDK/API, ograniczenia
Urządzenie, SDK/API i sposób odczytu próbek muszą zostać potwierdzone na konkretnym Windows/Linux stanowisku. Należy użyć działającego szablonu z repozytorium, a nie zakładać nazw funkcji.

### System stanowiska pomiarowego
DO UZUPEŁNIENIA

### Język implementacji
DO UZUPEŁNIENIA

### Dokładne wersje systemu
Do weryfikacji: system operacyjny, sterowniki Tobii, wersja SDK/API, Python/.NET i wersja 32/64-bit.

### SDK/API: nazwa, wersja, dokumentacja i dostępny przykład
Do weryfikacji. Nazwa SDK, dokładna wersja, dokumentacja i działający przykład muszą zostać potwierdzone przed implementacją.

### Stan weryfikacji zgodności SDK/API z Tobii Pro Spectrum
DO UZUPEŁNIENIA

### Tryb prototypu
Sprzęt i osobny, jawnie wybierany tryb symulacji

### Ekran, geometria i częstotliwość próbkowania
Rozdzielczość, rozmiar i częstotliwość odświeżania ekranu; odległość; skalowanie; częstotliwość próbkowania i układ współrzędnych do potwierdzenia na stanowisku.

### Połączenie, kalibracja, walidacja i utrata trackingu
Wykryć tracker → potwierdzić status połączenia → przeprowadzić kalibrację zgodną z wybraną wersją SDK → obsłużyć nieudany wynik → zatrzymać i powiadomić przy utracie trackingu → zamknąć strumień i zasoby po sesji.

### Zegary, synchronizacja i surowe próbki
Zachować timestamp urządzenia i czas aplikacji oraz metodę synchronizacji dostępną w SDK. Zapisać próby obu oczu i status ważności, jeśli SDK udostępnia. Nie deklarować dokładności ponad potwierdzoną dokumentacją.

- [x] Surowe próbki wzroku z timestampami, ważnością i trybem źródła — WYMAGANE

- [x] Zdarzenia sesji i prób z identyfikatorami warunku i bodźca — WYMAGANE

- [x] Wyniki pomiarów obliczone według opisanych reguł — WYMAGANE

- [x] Konfiguracja, wersje i numer pozwalający odtworzyć losowanie — WYMAGANE

### Format danych prototypu
CSV + JSON konfiguracji

## 7. Testy, jakość i etyka

- [ ] Instrukcja jest zrozumiała dla osoby spoza zespołu. — NIE POTWIERDZONO

- [ ] Każdy warunek został przetestowany, a różnice są zgodne z planem. — NIE POTWIERDZONO

- [ ] Kalibracja / tracking ma sprawdzony status; błędy są obsłużone. — NIE POTWIERDZONO

- [ ] Start i koniec próby zapisują poprawne zdarzenia i czasy. — NIE POTWIERDZONO

- [ ] Eksport zawiera komplet wymaganych pól i można go otworzyć. — NIE POTWIERDZONO

- [ ] Testowa sesja pozwala odpowiedzieć na pytanie badawcze. — NIE POTWIERDZONO

- [ ] Informacja, zgoda, minimalizacja danych i pseudonimizacja są uwzględnione. — NIE POTWIERDZONO

- [ ] Określono kryteria wykluczenia próby / danych i sposób ich dokumentowania. — NIE POTWIERDZONO

### Kryteria jakości danych
Początkowo: minimum 70% ważnych próbek w czasie prezentacji, udana kalibracja i kompletny zapis odpowiedzi. Kryteria można doprecyzować po pilotazie i dokumentacji SDK.

### Ryzyka techniczne i plan działania
Ryzyka: utrata trackingu, błąd kalibracji, zmęczenie, przesunięcie ekranu, awaria urządzenia i słaba trafność AOI. Reakcja: zatrzymać, oznaczyć status, ponownie kalibrować, powtórzyć wadliwą próbę według z góry ustalonej reguły.

### Ochrona danych
Uczestników informuje się o rejestracji wzroku i możliwości zrezygnowania. Używać kodu pseudonimowego, oddzielić klucz identyfikacyjny, ograniczyć dostęp i ustalić termin usunięcia surowych danych zgodnie z wytycznymi uczelni.

## 8. Podsumowanie zespołu

### Co dokładnie badamy?
Badamy, czy czas i miejsce patrzenia na jedną z dwóch opcji wiążą się z wyborem tej opcji. Porównujemy czas fiksacji i moment pierwszego spojrzenia dla lewej i prawej opcji.

### Co zmieniamy i dlaczego?
Zamiast jedzenia i realnych nagród używamy neutralnych par zdjęć produktów. Skracamy sesję do 48 prób i 8 treningowych. Pozycji lewej/prawej ustawiamy losowo i kontrbalansowo.

### Jakie wyniki przewidujemy i jakie pomiary je sprawdzą?
Przewidujemy większą sumę czasu patrzenia i późniejsze przesunięcie spojrzenia ku opcję wybraną, szczególnie w ostatnim przedziale przed odpowiedzią.

### Czy prototyp pozwala odpowiedzieć na pytanie badawcze? Co jeszcze trzeba sprawdzić?
MVP może odpowiedzieć na pytanie pilotażowe, jeżeli można potwierdzić zgodność SDK i jakości danych. Wciąż trzeba zweryfikować udział próbek, stabilność AOI i moc próby.

### Co AI ma przygotować jako następny krok?
Lista braków i pytań przed implementacją

### Otwarte pytania / czego AI nie powinno zakładać
AI nie powinno zakładać: wersji SDK, systemu, częstotliwości/prędkości ekranowej, rozdzielczości, odległości, parametrów detekcji fiksacji, sposobu losowania i kryteriów kalibracji. Te wartości wymagają potwierdzenia na stanowisku.
