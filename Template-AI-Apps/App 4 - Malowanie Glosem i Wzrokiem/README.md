# App 4 - Malowanie Glosem i Wzrokiem

Artsy app do tworzenia obrazow impressionistycznych:
- spojrzenie steruje polozeniem pedzla,
- glos (cechy dzwieku) steruje kolorem, pulsem i energia sladu,
- w trybie DEV dziala bez eye-trackera (mysz = spojrzenie).

## Uruchomienie

### Windows

```bat
run_app4.bat
```

### macOS/Linux

```bash
bash run_app4.sh
```

## Sterowanie

- `SPACE`: zakoncz i zapisz obraz
- `C`: wyczysc plotno
- `S`: zapisz obraz od razu
- `ESC`: wyjdz

## Uwagi

- Tryb `DEV` jest do budowania na laptopach studentow.
- Tryb `NAUCZYCIELA` wymaga Tobii Pro Spectrum (SDK w bundlowanym PsychoPy).
- Jezeli `sounddevice` nie jest dostepny, aplikacja przechodzi na proceduralna symulacje audio, aby sesja nadal byla estetyczna i plynna.

## Pedzel literowy SWPS (glos)

Powiedz po angielsku **S-W-P-S** (es, double-you, pee, es) albo **I love S-W-P-S** -
pedzel przestaje malowac plamy i zaczyna stawiac litery S W P S wzdluz sciezki wzroku
(glosnosc = wielkosc liter). Klawisz **L** wlacza/wylacza tryb literowy recznie.
Rozpoznawanie mowy jest offline (Vosk, model `models/vosk-model-small-en-us-0.15`,
pobierany przez `setup_bundle.bat`). Pasek statusu pokazuje `mowa: OK [ostatnio uslyszane litery]`.
