# Tworzenie aplikacji w `Template-AI-Apps`

Ten katalog jest wspólnym miejscem dla aplikacji warsztatowych przygotowanych
dla Tobii Pro Spectrum. Każda aplikacja ma własny podkatalog i skrypt startowy.
Wspólne środowisko PsychoPy oraz integrację z Tobii Pro SDK udostępnia
`spectrum.py`.

## Struktura

```text
Template-AI-Apps/
├── PsychoPy/                         # opcjonalne środowisko PsychoPy dla Windows
│   └── python.exe
├── spectrum.py                       # wspólne wyszukiwanie, kalibracja i strumień gaze
├── setup_bundle.bat                  # przygotowanie Pythona, PsychoPy i Tobii Pro SDK
├── requirements-students.txt         # wspólne zależności aplikacji warsztatowych
├── install_deps.bat                  # instalacja zależności na Windows
├── install_deps.sh                   # instalacja zależności na Linux/macOS
├── AI Template App/
│   ├── ai_template_app.py            # główny skrypt aplikacji
│   ├── requirements.txt              # zależności specyficzne dla aplikacji
│   ├── run_app.bat                   # uruchomienie na Windows
│   ├── run_app.sh                    # uruchomienie na Linux/macOS
│   └── README.md                     # instrukcje dla tej aplikacji
└── App N - Nazwa/
    ├── appN_nazwa.py
    ├── run_appN.bat
    ├── run_appN.sh
    └── README.md                     # zalecane
```

Nową aplikację dodaj jako **podkatalog bezpośrednio w `Template-AI-Apps`**,
obok `AI Template App` i pozostałych `App N - ...`. Nie umieszczaj jej wewnątrz
folderu `PsychoPy`.

## Pliki nowej aplikacji

1. **Skrypt `.py`** — punkt wejścia o jednoznacznej nazwie, np.
   `app7_nazwa.py`. Trzymaj ścieżki do własnych zasobów względem lokalizacji
   skryptu, a nie bieżącego katalogu terminala.
2. **Launcher Windows `.bat`** — zmienia katalog roboczy na folder aplikacji,
   znajduje interpreter według zasad poniżej i uruchamia skrypt. Wzoruj się na
   `AI Template App/run_app.bat`.
3. **Launcher Linux/macOS `.sh`** — ustawia katalog roboczy na folder aplikacji
   i uruchamia `python3` (z czytelnym błędem, jeśli go nie ma). Wzoruj się na
   `App 6 - Kaskada Spojrzenia i Wybor/run_app6.sh`.
4. **Zależności** — dodawaj pakiety używane przez wiele aplikacji do
   `requirements-students.txt`. Pakiety tylko dla jednej aplikacji wpisz do jej
   `requirements.txt` i opisz osobny sposób instalacji w jej `README.md`.
5. **README** — opisz cel, uruchomienie, wymagany sprzęt, tryb symulacji oraz
   miejsce zapisu wyników.

Przykładowa zawartość folderu:

```text
App 7 - Nazwa/
├── app7_nazwa.py
├── run_app7.bat
├── run_app7.sh
├── requirements.txt    # tylko jeśli są zależności specyficzne dla aplikacji
└── README.md
```

## Python i PsychoPy na Windows

Uruchomienie i instalator szukają interpretera w tej samej kolejności:

1. Ścieżka wskazana zmienną środowiskową `PSYCHOPY_PYTHON` (musi wskazywać
   istniejący plik `python.exe`).
2. `Template-AI-Apps/PsychoPy/python.exe`.
3. `Template-AI-Apps/.venv/Scripts/python.exe`.
4. Standardowe lokalizacje instalacji PsychoPy w `Program Files` lub
   `%LOCALAPPDATA%\Programs`.
5. Launcher `py -3`, a następnie `python` z `PATH`. Alias Microsoft Store
   `WindowsApps` nie jest traktowany jako właściwy interpreter.

Preferowane dla zajęć jest dostarczenie/instalacja PsychoPy w katalogu
`Template-AI-Apps/PsychoPy`. Folder `PsychoPy` jest lokalnym środowiskiem
uruchomieniowym i nie jest śledzony w Git (`.gitignore`).

Jeśli PsychoPy znajduje się w innym miejscu, ustaw zmienną przed uruchomieniem
launchera **i instalatora**, np. w wierszu polecenia:

```bat
set PSYCHOPY_PYTHON=C:\sciezka\do\PsychoPy\python.exe
```

Z tego samego okna uruchom `run_appN.bat` albo `install_deps.bat`. Oba skrypty
muszą używać tego samego interpretera, aby biblioteki instalowały się tam, skąd
aplikacja je importuje.

Na Windows:

1. Umieść folder PsychoPy w `Template-AI-Apps/PsychoPy` albo ustaw
   `PSYCHOPY_PYTHON`.
2. Uruchom `install_deps.bat`, jeśli wymagane biblioteki nie są już dostępne
   w tym interpreterze.
3. Uruchom launcher aplikacji, np. `run_app7.bat`.

## Sprzęt i SDK Tobii Pro Spectrum

Wszystkie aplikacje sprzętowe korzystają z Tobii Pro Spectrum i oficjalnego
pakietu Tobii Pro SDK `tobii-research==2.1.0`, instalowanego w 64-bitowym
środowisku PsychoPy przez `setup_bundle.bat`. Nie kopiuj starego SDK do katalogu
aplikacji — aktualny szablon korzysta z pakietu Tobii Pro SDK w tym środowisku.

W nowych aplikacjach wzoruj się na `AI Template App/ai_template_app.py`:
używaj `import tobii_research as tr` oraz wspólnego modułu `spectrum.py`
do wykrywania trackera, kalibracji, strumienia próbek i bezpiecznego kończenia
eksperymentu. Nie implementuj ponownie obsługi sprzętu ani nie zakładaj
zgodności z innym SDK. Test sprzętowy wykonuj na stanowisku z Tobii Pro
Spectrum i Tobii Pro Eye Tracker Manager.

`DEV_MODE` aplikacji może symulować wzrok myszą, ale nie potwierdza to
poprawności połączenia z eye-trackerem ani integracji SDK.

## Wyniki i pliki lokalne

Zapisuj wygenerowane obrazy, CSV i logi w podkatalogu wynikowym danej
aplikacji. Nie commituj danych uczestników ani wyników sesji do repozytorium;
używaj wyłącznie bezpiecznych, pseudonimowych identyfikatorów i zgodnie z
procedurą laboratorium. Lokalne środowisko Python/PsychoPy, cache i logi są
wyłączone z Git przez `.gitignore`.
