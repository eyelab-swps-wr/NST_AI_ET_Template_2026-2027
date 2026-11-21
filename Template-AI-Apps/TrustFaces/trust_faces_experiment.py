# -*- coding: utf-8 -*-
"""
Zaufanie do twarzy: prawdziwe vs wygenerowane przez AI - PsychoPy + Tobii (eye-tracking)
=========================================================================================
12 portretow (REAL_01-06, AI_01-06), kazdy widoczny 3 s, po nim ocena zaufania 1-7.
Tlo wszystkich portretow ujednolicone (RGB 230,230,230) - patrz prepare_stimuli.py.

STATUS: skrypt NIE zostal przetestowany z rzeczywistym eye-trackerem. Wersja testowa dziala w trybie
SYMULACJI (mysz / dane syntetyczne). Dane z symulacji sa oznaczone i nie nadaja sie do analizy badawczej.

Uruchomienie:
    run_experiment.bat                       (tryb Tobii; wybierany w oknie startowym)
    run_experiment.bat --sim                 (symulacja - mysz zastepuje wzrok)
    run_experiment.bat --sim --windowed      (okno zamiast pelnego ekranu)
    run_experiment.bat --autotest            (test automatyczny: bez interakcji, dane syntetyczne)
ESC w KAZDYM momencie natychmiast przerywa sesje (zapisane proby zostaja na dysku).
"""
import csv
import hashlib
import json
import math
import os
import random
import statistics
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))          # wspolny modul ../spectrum.py

from psychopy import core, event, gui, logging, visual
import psychopy

logging.console.setLevel(logging.ERROR)
import analysis

try:                                           # tobii_research jest opcjonalny w trybie symulacji
    import tobii_research as tr
    import spectrum
except Exception as _exc:                      # noqa: BLE001
    tr = spectrum = None
    _TOBII_IMPORT_ERROR = repr(_exc)
else:
    _TOBII_IMPORT_ERROR = None

# =============================================================================
# PARAMETRY (ustalone PRZED zbieraniem danych - nie zmieniaj w trakcie badania)
# =============================================================================
PRESENT_S = 3.0               # czas ekspozycji portretu (bylo 50 s w wersji wzorowanej na Tatlerze)
CROSS_S = 0.5                 # centralny krzyz
NEUTRAL_PAUSE_S = 1.0         # krotka neutralna przerwa po odpowiedzi
BREAK_EVERY = 5               # przerwa co N prob
BREAK_S = 30
RATING_MIN, RATING_MAX = 1, 7
IMAGE_W, IMAGE_H = 1536, 1024
BG_RGB = 230                  # tlo okna = tlo portretow
VALID_RATIO_MIN = 0.60        # ponizej tego proba jest wykluczana (prog ustalony z gory)
MAX_SAME_CATEGORY_RUN = 2

# Walidacja wlasna (po kalibracji): 5 punktow, mediana polozenia wzroku vs cel, w stopniach.
# DOBOR PROGU: Tatler i in. uzywali 0,5 / 1 deg dla EyeLink 500 Hz; dla Tobii (X120/Spectrum, ok. 120 Hz,
# badanie twarzy z AOI oczu rzedu 1-2 deg) przyjeto sredni blad <= 1,0 deg i maks. dla punktu <= 1,5 deg.
# Do potwierdzenia pilotazem na stanowisku.
VAL_POINTS = [(0.5, 0.5), (0.15, 0.15), (0.85, 0.15), (0.85, 0.85), (0.15, 0.85)]
VAL_MEAN_MAX_DEG = 1.0
VAL_POINT_MAX_DEG = 1.5
VAL_SHOW_S, VAL_SKIP_S, VAL_MIN_SAMPLES = 1.6, 0.6, 10
MAX_CALIBRATION_ATTEMPTS = 3

DEFAULT_SCREEN_WIDTH_CM = 52.0     # DO ZMIERZENIA na stanowisku (szerokosc obszaru obrazu)
DEFAULT_VIEW_DIST_CM = 65.0        # DO ZMIERZENIA na stanowisku

INSTRUCTION = (
    "Za chwilę zobaczysz 12 portretów.\n\n"
    "Każdy obraz będzie widoczny przez 3 sekundy. Oglądaj go swobodnie, "
    "a po zniknięciu obrazu oceń osobę.\n\n"
    "Wybierz ocenę od 1 do 7, gdzie 1 oznacza osobę całkowicie niegodną zaufania, "
    "a 7 oznacza osobę całkowicie godną zaufania. "
    "Nie musisz porównywać osoby z poprzednimi portretami.\n\n"
    "Najpierw jedna próba treningowa.\n\nNaciśnij SPACJĘ, aby kontynuować."
)
RATING_PROMPT = "Jak bardzo godna zaufania jest ta osoba?"
DEBRIEF = (
    "Dziękujemy za udział.\n\n"
    "Połowa oglądanych portretów przedstawiała prawdziwe osoby, a połowa została wygenerowana przez AI. "
    "Badamy, czy oceny zaufania i sposób patrzenia na twarz zależą od tego, czy twarz jest prawdziwa. "
    "Nie podawaliśmy tego wcześniej, aby nie wpływać na Twoje spojrzenie.\n\n"
    "Twoje dane są zapisane pod kodem, bez imienia i nazwiska. Możesz poprosić o ich usunięcie.\n\n"
    "Naciśnij SPACJĘ, aby zakończyć."
)

SESSION = {}                  # wypelniane w main()
_state = {"dir": None, "t0": None, "recorder": None, "win": None}


# =============================================================================
# Pomocnicze: zegar, ESC, zapis
# =============================================================================
def now_ms():
    return (time.perf_counter() - _state["t0"]) * 1000.0


def log_event(name, **kw):
    d = _state["dir"]
    if d is None:
        return
    with open(d / "events.log", "a", encoding="utf-8") as f:
        f.write(json.dumps({"t_ms": round(now_ms(), 2), "event": name, **kw}, ensure_ascii=False) + "\n")


def _abort():
    try:
        log_event("ABORTED_BY_ESC")
        rec = _state["recorder"]
        if rec is not None:
            rec.stop()
    finally:
        if spectrum is not None:
            spectrum.abort()                       # sprzata subskrypcje/kalibracje i konczy proces
        os._exit(0)


def install_escape():
    try:
        event.globalKeys.remove(key="escape")
    except Exception:                              # noqa: BLE001
        pass
    event.globalKeys.add(key="escape", func=_abort, name="trust_faces_abort")


def append_csv(path, fields, rows):
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)
        f.flush()
        os.fsync(f.fileno())


TRIAL_FIELDS = [
    "participant_id", "session_id", "trial_id", "trial_order", "random_seed", "stimulus_id",
    "stimulus_category", "stimulus_path_hash", "presentation_start_ms", "presentation_end_ms",
    "trust_rating_1_7", "response_time_ms", "tracker_model", "sampling_frequency", "calibration_status",
    "validation_mean_error_deg", "valid_gaze_ratio", "invalid_reason", "recalibration_flag", "run_mode",
]
SAMPLE_FIELDS = [
    "sample_id", "participant_id", "session_id", "trial_id", "device_timestamp", "app_timestamp",
    "left_gaze_x", "left_gaze_y", "left_validity", "right_gaze_x", "right_gaze_y", "right_validity",
    "gaze_validity", "screen_width_px", "screen_height_px",
]


# =============================================================================
# Zrodla spojrzenia: Tobii / symulacja
# =============================================================================
class Recorder:
    """Wspolny interfejs: samples = (app_perf_s, device_us, lx, ly, lv, rx, ry, rv); wspolrzedne 0..1, (0,0)=lewy gorny."""
    mode = "?"
    model = "?"
    freq = 0.0

    def __init__(self):
        self._lock = threading.Lock()
        self.samples = []

    def _add(self, row):
        with self._lock:
            self.samples.append(row)

    def take_until(self, t_end_perf):
        with self._lock:
            out = [s for s in self.samples if s[0] <= t_end_perf]
            self.samples = [s for s in self.samples if s[0] > t_end_perf]
        return out

    def start(self): ...
    def stop(self): ...
    def poll(self): ...               # symulacja: wywolywane co klatke


if spectrum is not None:
    class _TobiiStream(spectrum.GazeStream):
        def __init__(self, et, rec):
            super().__init__(et)
            self._rec = rec

        def on_sample(self, d, g):             # watek SDK - tylko lekki zapis
            def eye(side):
                ok = bool(d[f"{side}_gaze_point_validity"])
                x, y = d[f"{side}_gaze_point_on_display_area"]
                ok = ok and math.isfinite(x) and math.isfinite(y)
                return (x, y, 1) if ok else (float("nan"), float("nan"), 0)
            lx, ly, lv = eye("left")
            rx, ry, rv = eye("right")
            self._rec._add((spectrum.sdk_time_to_perf(d["system_time_stamp"]), d["device_time_stamp"],
                            lx, ly, lv, rx, ry, rv))


class TobiiRecorder(Recorder):
    mode = "TOBII"

    def __init__(self, et):
        super().__init__()
        self.et = et
        self.model = f"{et.model} (serial {et.serial_number})"
        try:
            self.freq = float(et.get_gaze_output_frequency())
        except Exception:                          # noqa: BLE001
            self.freq = float("nan")
        self._stream = _TobiiStream(et, self)

    def start(self):
        self._stream.start()
        self._stream.wait_for_data(2.0)

    def stop(self):
        self._stream.stop()


class SimRecorder(Recorder):
    """Mysz (lub dane syntetyczne w --autotest) zastepuja wzrok. Probkowanie = czestotliwosc klatek."""

    def __init__(self, win, auto=False, rng=None):
        super().__init__()
        self.mode = "SIMULATION_AUTOTEST" if auto else "SIMULATION_MOUSE"
        self.model = "SIMULATION (synthetic, no eye tracker)" if auto else "SIMULATION (mouse, no eye tracker)"
        self.win, self.auto = win, auto
        self.rng = rng or random.Random(0)
        self.mouse = event.Mouse(win=win, visible=not auto)
        self.freq = 60.0
        self.target = (0.5, 0.5)               # w autotescie: punkt, wokol ktorego "patrzy" syntetyczny wzrok
        self._tgt_t = 0.0

    def poll(self):
        t = time.perf_counter()
        if self.auto:
            if t > self._tgt_t:                # co ~0.35 s nowy cel (sakada), miedzy nimi dryf
                self.target = (self.rng.choice([0.44, 0.5, 0.56]), self.rng.choice([0.40, 0.46, 0.64, 0.5]))
                self._tgt_t = t + 0.35
            x = self.target[0] + self.rng.gauss(0, 0.002)
            y = self.target[1] + self.rng.gauss(0, 0.002)
            ok = self.rng.random() > 0.02      # 2% losowych utrat
        else:
            mx, my = self.mouse.getPos()       # pix (0,0)=srodek
            w, h = self.win.size
            x, y = mx / w + 0.5, 0.5 - my / h
            ok = True
        if ok:
            self._add((t, int(t * 1e6), x, y, 1, x, y, 1))
        else:
            nan = float("nan")
            self._add((t, int(t * 1e6), nan, nan, 0, nan, nan, 0))


# =============================================================================
# Losowanie (odtwarzalne) z ograniczeniami
# =============================================================================
def derive_seed(participant_id, session_id):
    return int(hashlib.sha256(f"{participant_id}|{session_id}".encode()).hexdigest()[:8], 16)


def make_order(stimuli, seed):
    """12 prob w 3 blokach po 4: w kazdym bloku po 2 REAL i 2 AI (rowna obecnosc kategorii na poczatku/srodku/koncu);
    kolejnosc wewnatrz bloku i same bodzce losowe; odrzucamy uklady z > MAX_SAME_CATEGORY_RUN tej samej kategorii pod rzad."""
    rng = random.Random(seed)
    real = [s for s in stimuli if s["category"] == "REAL"]
    ai = [s for s in stimuli if s["category"] == "AI"]
    for _ in range(10000):
        r, a = real[:], ai[:]
        rng.shuffle(r)
        rng.shuffle(a)
        order = []
        for _b in range(3):
            block = [r.pop(), r.pop(), a.pop(), a.pop()]
            rng.shuffle(block)
            order += block
        run, ok = 1, True
        for p, q in zip(order, order[1:]):
            run = run + 1 if p["category"] == q["category"] else 1
            if run > MAX_SAME_CATEGORY_RUN:
                ok = False
                break
        if ok:
            return order
        real, ai = [s for s in stimuli if s["category"] == "REAL"], [s for s in stimuli if s["category"] == "AI"]
    raise RuntimeError("Nie udalo sie wylosowac kolejnosci spelniajacej ograniczenia")


# =============================================================================
# Ekrany
# =============================================================================
def text_stim(win, text, y=0, height=30, color="black", wrap=None, **kw):
    return visual.TextStim(win, text=text, pos=(0, y), height=height, color=color, units="pix",
                           wrapWidth=wrap or win.size[0] * 0.75, languageStyle="LTR", **kw)


def wait_keys(win, stim_list, keys):
    event.clearEvents()
    while True:
        for s in stim_list:
            s.draw()
        win.flip()
        k = event.getKeys(keys)
        if k:
            return k[0]
        if SESSION.get("auto"):
            return keys[0]


def show_text(win, text, keys=("space",), **kw):
    return wait_keys(win, [text_stim(win, text, **kw)], list(keys))


def run_calibration_and_validation(win, rec):
    """Kalibracja (spectrum.calibrate, 9 punktow) + walidacja wlasna. Zwraca (status, mean_deg, recal_flag)."""
    if rec.mode != "TOBII":
        return "SIMULATION_NOT_APPLICABLE", None, 0
    cm_per_px = SESSION["screen_width_cm"] / win.size[0]
    recal = 0
    status, mean_deg = "NOT_RUN", None
    for attempt in range(1, MAX_CALIBRATION_ATTEMPTS + 1):
        win.setColor((0, 0, 0), colorSpace="rgb255")   # kalibracja na czarnym tle (biale punkty z modulu spectrum)
        win.flip()
        ok = spectrum.calibrate(win, rec.et, points=spectrum.CAL_POINTS_9)
        win.setColor((BG_RGB, BG_RGB, BG_RGB), colorSpace="rgb255")
        win.flip()
        log_event("calibration", attempt=attempt, accepted=bool(ok))
        rec.start()
        errs = run_validation(win, rec, cm_per_px)
        rec.stop()
        valid = [e for e in errs if e is not None]
        mean_deg = (sum(valid) / len(valid)) if valid else None
        passed = bool(ok) and len(valid) == len(VAL_POINTS) and mean_deg <= VAL_MEAN_MAX_DEG \
            and max(valid) <= VAL_POINT_MAX_DEG
        log_event("validation", attempt=attempt, errors_deg=[None if e is None else round(e, 3) for e in errs],
                  mean_deg=None if mean_deg is None else round(mean_deg, 3), passed=passed)
        if passed:
            return "CALIBRATED_VALIDATED", mean_deg, recal
        status = "CALIBRATION_FAILED" if not ok else "VALIDATION_FAILED"
        recal = 1
        txt = ("Walidacja: błąd średni %.2f° (prog %.1f°), maks. %.2f° (prog %.1f°)." %
               (mean_deg or float("nan"), VAL_MEAN_MAX_DEG, max(valid) if valid else float("nan"), VAL_POINT_MAX_DEG)
               if valid else "Walidacja: brak danych.")
        if attempt < MAX_CALIBRATION_ATTEMPTS:
            k = show_text(win, txt + "\n\nR = powtórz kalibrację   C = kontynuuj mimo to (próby zostaną oznaczone)",
                          keys=("r", "c"))
            if k == "c":
                return status, mean_deg, recal
        else:
            show_text(win, txt + "\n\nOsiągnięto limit prób kalibracji. Dane zostaną oznaczone jako niewiarygodne.\n"
                      "SPACJA = kontynuuj")
    return status, mean_deg, recal


def run_validation(win, rec, cm_per_px):
    w, h = win.size
    order = VAL_POINTS[:]
    random.shuffle(order)
    dot = visual.Circle(win, radius=14, fillColor="black", lineColor=None, units="pix")
    inner = visual.Circle(win, radius=3, fillColor="white", lineColor=None, units="pix")
    results = {}
    show_text(win, "WALIDACJA\n\nPatrz na czarną kropkę, aż zniknie.\n\nSPACJA = start")
    for nx, ny in order:
        dot.pos = inner.pos = ((nx - 0.5) * w, (0.5 - ny) * h)
        t_on = None
        rec.take_until(float("inf"))
        t_start = time.perf_counter()
        while time.perf_counter() - t_start < VAL_SHOW_S:
            dot.draw(); inner.draw(); win.flip()
            if t_on is None:
                t_on = time.perf_counter()
        pts = []
        for s in rec.take_until(float("inf")):
            if s[0] - t_on < VAL_SKIP_S:
                continue
            for ok, x, y in ((s[4], s[2], s[3]), (s[7], s[5], s[6])):
                if ok:
                    pts.append((x, y))
        if len(pts) < VAL_MIN_SAMPLES:
            results[(nx, ny)] = None
            continue
        mx = statistics.median(p[0] for p in pts)
        my = statistics.median(p[1] for p in pts)
        d_px = math.hypot((mx - nx) * w, (my - ny) * h)
        results[(nx, ny)] = analysis._angle_deg(d_px, 0, cm_per_px, SESSION["viewing_distance_cm"])
    return [results[p] for p in VAL_POINTS]


def fixation_cross(win):
    t_end = time.perf_counter() + CROSS_S
    cross = text_stim(win, "+", height=60)
    while time.perf_counter() < t_end:
        cross.draw(); win.flip()


def present(win, rec, stim_img, frame_s):
    """Pokazuje obraz przez PRESENT_S s. Zwraca (start_perf, end_perf)."""
    marks = []
    win.callOnFlip(lambda: marks.append(time.perf_counter()))
    stim_img.draw(); win.flip()
    t_on = marks[0]
    while time.perf_counter() - t_on < PRESENT_S - 0.5 * frame_s:
        rec.poll()
        stim_img.draw(); win.flip()
    win.callOnFlip(lambda: marks.append(time.perf_counter()))
    win.flip()                                      # pusty ekran (tlo)
    return t_on, marks[1]


def get_rating(win):
    """Skala 1-7: klawisze 1-7 lub klikniecie myszy. Bez limitu czasu. Zwraca (ocena, czas_ms)."""
    w, h = win.size
    n = RATING_MAX - RATING_MIN + 1
    xs = [(-0.3 + 0.6 * i / (n - 1)) * w for i in range(n)]
    boxes = [visual.Rect(win, width=70, height=70, pos=(x, -40), lineColor="black", fillColor=None,
                         lineWidth=3, units="pix") for x in xs]
    nums = [text_stim(win, str(RATING_MIN + i), y=-40, height=34) for i in range(n)]
    for i, x in enumerate(xs):
        nums[i].pos = (x, -40)
    q = text_stim(win, RATING_PROMPT, y=120, height=38)
    lo = text_stim(win, "1 = całkowicie niegodna zaufania", y=-130, height=22, wrap=w * 0.4)
    hi = text_stim(win, "7 = całkowicie godna zaufania", y=-130, height=22, wrap=w * 0.4)
    lo.pos, hi.pos = (-0.3 * w, -130), (0.3 * w, -130)
    mouse = event.Mouse(win=win, visible=True)
    event.clearEvents()
    t_start = time.perf_counter()
    mouse.clickReset()
    mouse_prev = mouse.getPressed()[0]
    while True:
        q.draw(); lo.draw(); hi.draw()
        for b, nn in zip(boxes, nums):
            b.draw(); nn.draw()
        win.flip()
        if SESSION.get("auto"):
            time.sleep(0.15)
            return random.randint(1, 7), (time.perf_counter() - t_start) * 1000
        keys = event.getKeys([str(i) for i in range(RATING_MIN, RATING_MAX + 1)])
        if keys:
            return int(keys[0]), (time.perf_counter() - t_start) * 1000
        pressed = mouse.getPressed()[0]
        if pressed and not mouse_prev:
            mx, my = mouse.getPos()
            for i, b in enumerate(boxes):
                if b.contains((mx, my)):
                    mouse.setVisible(False)
                    return RATING_MIN + i, (time.perf_counter() - t_start) * 1000
        mouse_prev = pressed


def neutral_pause(win, seconds):
    t_end = time.perf_counter() + seconds
    while time.perf_counter() < t_end:
        win.flip()


def break_screen(win):
    t_end = time.perf_counter() + (1.0 if SESSION.get("auto") else BREAK_S)
    while time.perf_counter() < t_end:
        left = max(0, int(math.ceil(t_end - time.perf_counter())))
        text_stim(win, f"Krótka przerwa.\n\nZa {left} s zaczniemy kolejną część.").draw()
        win.flip()
    show_text(win, "Naciśnij SPACJĘ, gdy będziesz gotowy/a.")


def make_practice_image(win, scale):
    """Trening: schematyczny owal, NIE twarz z zestawu badawczego (wszystkie 12 portretow jest w badaniu)."""
    w = 380 * scale
    oval = visual.ShapeStim(win, vertices=[(math.cos(a / 40 * 2 * math.pi) * 0.5 * w,
                                            math.sin(a / 40 * 2 * math.pi) * 0.65 * w) for a in range(40)],
                            fillColor=(0.45, 0.45, 0.45), lineColor=None, units="pix")
    label = text_stim(win, "TRENING — to nie jest portret z badania", y=-0.65 * w - 50, height=26)
    return oval, label


# =============================================================================
# Glowna procedura
# =============================================================================
def startup_dialog(args):
    info = {
        "Kod uczestnika (bez imienia i nazwiska)": "P01",
        "Sesja": "1",
        "Tryb": "SIMULATION" if args["sim"] else "TOBII",
        "Szerokość obszaru obrazu [cm]": DEFAULT_SCREEN_WIDTH_CM,
        "Odległość od ekranu [cm]": DEFAULT_VIEW_DIST_CM,
        "Seed (puste = z kodu uczestnika)": "",
        "Pisemna zgoda uzyskana": False,
        "Pełnoletność potwierdzona": False,
        "Widzenie prawidłowe lub skorygowane": False,
    }
    dlg = gui.DlgFromDict(info, title="Zaufanie do twarzy — start sesji", sortKeys=False,
                          order=list(info.keys()), tip={"Tryb": "TOBII albo SIMULATION"})
    if not dlg.OK:
        sys.exit(0)
    return info


def main():
    args = {"sim": "--sim" in sys.argv or "--autotest" in sys.argv,
            "windowed": "--windowed" in sys.argv or "--autotest" in sys.argv,
            "auto": "--autotest" in sys.argv}
    SESSION["auto"] = args["auto"]
    stimuli_json = json.loads((HERE / "stimuli.json").read_text(encoding="utf-8"))
    stimuli = stimuli_json["stimuli"]
    assert len(stimuli) == 12, "Oczekiwano 12 bodzcow - uruchom prepare_stimuli.py"

    if args["auto"]:
        info = {"Kod uczestnika (bez imienia i nazwiska)": "AUTOTEST", "Sesja": datetime.now().strftime("%H%M%S"),
                "Tryb": "SIMULATION", "Szerokość obszaru obrazu [cm]": DEFAULT_SCREEN_WIDTH_CM,
                "Odległość od ekranu [cm]": DEFAULT_VIEW_DIST_CM, "Seed (puste = z kodu uczestnika)": "",
                "Pisemna zgoda uzyskana": True, "Pełnoletność potwierdzona": True,
                "Widzenie prawidłowe lub skorygowane": True}
    else:
        info = startup_dialog(args)
    pid = "".join(c for c in str(info["Kod uczestnika (bez imienia i nazwiska)"]) if c.isalnum() or c in "_-")
    sid_ = "".join(c for c in str(info["Sesja"]) if c.isalnum() or c in "_-") or "1"
    if not pid:
        sys.exit("Pusty kod uczestnika.")
    if not (info["Pisemna zgoda uzyskana"] and info["Pełnoletność potwierdzona"]
            and info["Widzenie prawidłowe lub skorygowane"]):
        sys.exit("Brak zgody / pelnoletnosci / widzenia - sesja nie moze sie rozpoczac.")
    sim = str(info["Tryb"]).upper().startswith("SIM")
    seed_txt = str(info["Seed (puste = z kodu uczestnika)"]).strip()
    seed = int(seed_txt) if seed_txt else derive_seed(pid, sid_)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = HERE / "data" / f"{pid}_S{sid_}_{stamp}{'_SIM' if sim else ''}"
    session_dir.mkdir(parents=True, exist_ok=True)
    _state["dir"] = session_dir
    _state["t0"] = time.perf_counter()

    # --- eye tracker ---------------------------------------------------------------------------
    et = None
    if not sim:
        if spectrum is None:
            sys.exit(f"Brak biblioteki tobii_research / spectrum.py: {_TOBII_IMPORT_ERROR}")
        trackers = spectrum.find_all_eyetrackers()
        if not trackers:
            sys.exit("Nie znaleziono eye-trackera. Uruchom z --sim, aby przetestowac bez urzadzenia.")
        et = trackers[0]
        print(f"[TRUST] Tracker: {et.model} | serial {et.serial_number} | {et.address}")

    # --- okno ----------------------------------------------------------------------------------
    win = visual.Window(size=(1920, 1080), fullscr=not args["windowed"], color=(BG_RGB, BG_RGB, BG_RGB),
                        colorSpace="rgb255", units="pix", screen=0, allowGUI=False, waitBlanking=True)
    _state["win"] = win
    install_escape()                               # nasz ESC: zapis zdarzenia + sprzatanie (wola spectrum.abort, jesli jest)
    W, H = (int(v) for v in win.size)
    frame_rate = win.getActualFrameRate(nIdentical=10, nMaxFrames=120, nWarmUpFrames=10, threshold=1) or 60.0
    frame_rate = float(frame_rate)
    frame_s = 1.0 / frame_rate
    scale = min(1.0, 0.97 * H / IMAGE_H, 0.97 * W / IMAGE_W)

    rec = SimRecorder(win, auto=args["auto"], rng=random.Random(seed)) if sim else TobiiRecorder(et)
    _state["recorder"] = rec
    if sim:
        rec.start()
    SESSION.update(screen_width_cm=float(info["Szerokość obszaru obrazu [cm]"]),
                   viewing_distance_cm=float(info["Odległość od ekranu [cm]"]))
    sampling_hz = round(rec.freq if sim is False else frame_rate, 1)
    if sim:
        rec.freq = frame_rate

    # --- kalibracja + walidacja --------------------------------------------------------------------
    cal_status, val_mean, recal_flag = run_calibration_and_validation(win, rec)
    if not sim:
        rec.start()

    cfg = {
        "participant_id": pid, "session_id": sid_, "random_seed": seed, "run_mode": rec.mode,
        "tracker_model": rec.model, "sampling_frequency": sampling_hz, "calibration_status": cal_status,
        "validation_mean_error_deg": None if val_mean is None else round(val_mean, 3),
        "validation_mean_max_deg": VAL_MEAN_MAX_DEG, "validation_point_max_deg": VAL_POINT_MAX_DEG,
        "screen_width_px": W, "screen_height_px": H, "screen_width_cm": SESSION["screen_width_cm"],
        "viewing_distance_cm": SESSION["viewing_distance_cm"], "image_scale": scale,
        "measured_frame_rate_hz": round(frame_rate, 2), "present_s": PRESENT_S, "cross_s": CROSS_S,
        "valid_ratio_min": VALID_RATIO_MIN, "fullscreen": not args["windowed"], "autotest": args["auto"],
        "psychopy_version": psychopy.__version__, "python": sys.version.split()[0],
        "tobii_research_version": getattr(tr, "__version__", None), "started": stamp,
        "analysis_ivt_parameters": analysis.IVT,
        "note": "Gaze x/y w samples = znormalizowane wspolrzedne obszaru obrazu (0..1, (0,0)=lewy gorny); px = x*screen_width_px.",
    }
    (session_dir / "session_config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    log_event("session_start", mode=rec.mode, seed=seed, calibration=cal_status)

    # --- zasoby ----------------------------------------------------------------------------------
    order = make_order(stimuli, seed)
    imgs = {s["stimulus_id"]: visual.ImageStim(win, image=str(HERE / s["filename"]),
                                               size=(IMAGE_W * scale, IMAGE_H * scale), units="pix")
            for s in stimuli}
    hashes = {s["stimulus_id"]: hashlib.sha256((HERE / s["filename"]).read_bytes()).hexdigest() for s in stimuli}

    # --- instrukcja + trening ----------------------------------------------------------------------
    show_text(win, INSTRUCTION)
    oval, label = make_practice_image(win, scale)
    fixation_cross(win)
    marks = []
    win.callOnFlip(lambda: marks.append(time.perf_counter()))
    oval.draw(); label.draw(); win.flip()
    while time.perf_counter() - marks[0] < PRESENT_S - 0.5 * frame_s:
        rec.poll(); oval.draw(); label.draw(); win.flip()
    win.flip()
    get_rating(win)
    rec.take_until(float("inf"))
    show_text(win, "To była próba treningowa — jej wyniki nie są zapisywane.\n\nNaciśnij SPACJĘ, aby rozpocząć badanie.")

    # --- proby glowne -------------------------------------------------------------------------------
    for i, s in enumerate(order, 1):
        trial_id = f"T{i:02d}"
        fixation_cross(win)
        rec.take_until(float("inf"))                 # wyrzuc probki sprzed obrazu
        t_on, t_off = present(win, rec, imgs[s["stimulus_id"]], frame_s)
        samples = [x for x in rec.take_until(t_off) if x[0] >= t_on]
        rating, rt_ms = get_rating(win)
        neutral_pause(win, NEUTRAL_PAUSE_S)

        n_valid = sum(1 for x in samples if x[4] or x[7])
        expected = PRESENT_S * (rec.freq if rec.freq == rec.freq and rec.freq else frame_rate)
        valid_ratio = round(n_valid / len(samples), 4) if samples else 0.0
        reasons = []
        if cal_status not in ("CALIBRATED_VALIDATED", "SIMULATION_NOT_APPLICABLE"):
            reasons.append(cal_status.lower())
        if valid_ratio < VALID_RATIO_MIN:
            reasons.append(f"valid_gaze_ratio<{VALID_RATIO_MIN}")
        if len(samples) < 0.5 * expected:
            reasons.append("too_few_samples")
        if abs((t_off - t_on) - PRESENT_S) > 3 * frame_s:
            reasons.append("presentation_duration_off")

        append_csv(session_dir / "trials.csv", TRIAL_FIELDS, [{
            "participant_id": pid, "session_id": sid_, "trial_id": trial_id, "trial_order": i, "random_seed": seed,
            "stimulus_id": s["stimulus_id"], "stimulus_category": s["category"],
            "stimulus_path_hash": hashes[s["stimulus_id"]],
            "presentation_start_ms": round((t_on - _state["t0"]) * 1000, 2),
            "presentation_end_ms": round((t_off - _state["t0"]) * 1000, 2),
            "trust_rating_1_7": rating, "response_time_ms": round(rt_ms, 1), "tracker_model": rec.model,
            "sampling_frequency": sampling_hz, "calibration_status": cal_status,
            "validation_mean_error_deg": cfg["validation_mean_error_deg"], "valid_gaze_ratio": valid_ratio,
            "invalid_reason": ";".join(reasons), "recalibration_flag": recal_flag, "run_mode": rec.mode,
        }])
        rows = []
        for k, x in enumerate(samples, 1):
            ok = bool(x[4] or x[7])
            rows.append({
                "sample_id": f"{trial_id}_{k:05d}", "participant_id": pid, "session_id": sid_, "trial_id": trial_id,
                "device_timestamp": x[1], "app_timestamp": round((x[0] - _state["t0"]) * 1000, 3),
                "left_gaze_x": "" if not x[4] else round(x[2], 5), "left_gaze_y": "" if not x[4] else round(x[3], 5),
                "left_validity": int(x[4]),
                "right_gaze_x": "" if not x[7] else round(x[5], 5), "right_gaze_y": "" if not x[7] else round(x[6], 5),
                "right_validity": int(x[7]), "gaze_validity": int(ok),
                "screen_width_px": W, "screen_height_px": H,
            })
        append_csv(session_dir / "gaze_samples.csv", SAMPLE_FIELDS, rows)
        log_event("trial_done", trial_id=trial_id, stimulus=s["stimulus_id"], rating=rating,
                  samples=len(samples), valid_ratio=valid_ratio)
        if i % BREAK_EVERY == 0 and i < len(order):
            break_screen(win)

    # --- koniec: komfort, debriefing, analiza --------------------------------------------------------
    comfort = show_text(win, "Jak się czujesz po badaniu?\n\n1 = bardzo niekomfortowo ... 5 = zupełnie komfortowo\n\n"
                        "(naciśnij 1-5)", keys=("1", "2", "3", "4", "5"))
    log_event("comfort_1_5", value=int(comfort))
    show_text(win, DEBRIEF)
    rec.stop()
    log_event("session_end")
    win.close()
    json.dump({"stimuli": [{"stimulus_id": s["stimulus_id"], "category": s["category"]} for s in order]},
              open(session_dir / "trial_order.json", "w", encoding="utf-8"), indent=1)
    n_fix, n_aoi = analysis.run_session_analysis(session_dir)
    print(f"[TRUST] Zapisano: {session_dir}\n[TRUST] fiksacje: {n_fix}, wiersze AOI: {n_aoi}")
    print((session_dir / "quality_report.txt").read_text(encoding="utf-8"))
    core.quit()


if __name__ == "__main__":
    main()
