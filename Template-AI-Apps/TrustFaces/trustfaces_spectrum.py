#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TRUSTFACES - SZYBKI PROTOTYP (Tobii Pro Spectrum + PsychoPy)
============================================================
Wzorowany na "AI Template App". Jeden plik, wspolny modul ../spectrum.py.

Przebieg:
  1. polaczenie z Tobii Pro Spectrum
  2. kalibracja 9-punktowa (spectrum.calibrate: pozycja glowy -> punkty -> wykres, R = powtorz)
  3. instrukcja
  4. 12 prob: krzyz 500 ms -> portret 3 s -> ocena zaufania 1-7 (klawisze) -> pauza
  5. zapis + krotkie podsumowanie REAL vs AI w konsoli

Wyniki (data/<kod>_<czas>/):
  trials.csv        - jedna proba = jeden wiersz: ocena, RT, czas patrzenia na AOI (ms i %)
  gaze_samples.csv  - surowe probki z ekspozycji (czas od pokazania, x/y, AOI)
AOI pochodza ze stimuli.json (te same, co w pelnej wersji): eyes, lower, face_other, background.

To jest PROTOTYP: bez walidacji w stopniach i bez detekcji fiksacji (liczony jest czas
przebywania wzroku = liczba waznych probek / czestotliwosc). Pelna wersja: trust_faces_experiment.py.

Uruchomienie:
  run_spectrum_prototype.bat              - Tobii Pro Spectrum
  run_spectrum_prototype_symulacja.bat    - mysz zamiast wzroku (bez trackera)
Flagi: --sim (mysz)  --windowed  --show-gaze (kropka wzroku na portrecie, tylko podglad)
       --auto (z --sim: test bez interakcji)
ESC w kazdej chwili konczy sesje; ukonczone proby sa juz zapisane.
"""

# ============================================================================
# 1. IMPORTS
# ============================================================================
try:
    from psychopy import visual, core, event, gui, logging
    logging.console.setLevel(logging.ERROR)
except ImportError as exc:
    raise ImportError(
        "\n\nPsychoPy is not installed.\n"
        "Uruchom ..\\setup_bundle.bat i startuj przez run_spectrum_prototype.bat\n"
    ) from exc

import csv
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # wspolny ../spectrum.py (jak w AI Template App)

try:
    import tobii_research as tr
    import spectrum
except ImportError as exc:
    raise ImportError(
        "\n\nTobii Pro SDK 2.1.0 is not installed in this Python environment.\n"
        "Use 64-bit Python 3.10 (..\\setup_bundle.bat).\n"
    ) from exc

# ============================================================================
# 2. CONSTANTS
# ============================================================================
SIM = "--sim" in sys.argv
AUTO = SIM and "--auto" in sys.argv
FULLSCREEN = "--windowed" not in sys.argv and not AUTO
SHOW_GAZE = "--show-gaze" in sys.argv

CROSS_S = 0.5
PRESENT_S = 3.0
ITI_S = 1.0
MAX_SAME_CATEGORY_RUN = 2

BG_RGB = (230, 230, 230)        # = tlo portretow (prepare_stimuli.py)
IMAGE_W, IMAGE_H = 1536, 1024   # plotno portretow w px
TEXT_COLOR = "black"

INSTRUCTION = (
    "Za chwilę zobaczysz 12 portretów.\n\n"
    "Każdy będzie widoczny przez 3 sekundy - oglądaj go swobodnie.\n"
    "Po zniknięciu portretu oceń, jak bardzo ta osoba jest godna zaufania:\n\n"
    "1 = całkowicie niegodna zaufania   ...   7 = całkowicie godna zaufania\n"
    "(klawisze 1-7)\n\n"
    "Naciśnij SPACJĘ, aby rozpocząć."
)
RATING_PROMPT = "Jak bardzo godna zaufania jest ta osoba?\n\n1   2   3   4   5   6   7\n\n" \
                "1 = całkowicie niegodna      7 = całkowicie godna"
END_TEXT = "Dziękujemy!\n\nPołowa portretów przedstawiała prawdziwe osoby, połowa była wygenerowana przez AI.\n\n" \
           "Naciśnij SPACJĘ, aby zakończyć."

AOI_NAMES = ["eyes", "lower", "face_other", "background", "off_image"]


# ============================================================================
# 3. HELPERS
# ============================================================================
def norm_to_pix(win, nx, ny):
    """Display area Tobii (0..1, (0,0)=lewy gorny) -> PsychoPy pix ((0,0)=srodek)."""
    w, h = win.size
    return (nx - 0.5) * w, (0.5 - ny) * h


def connect_eyetracker():
    print("\n[TRUSTFACES] Szukam eye-trackera...")
    trackers = spectrum.find_all_eyetrackers()  # Spectrum pierwszy, czestotliwosc ustawiona
    spectrum_trackers = [t for t in trackers if "spectrum" in (t.model or "").casefold()]
    if not spectrum_trackers:
        models = ", ".join(t.model or "?" for t in trackers) or "brak"
        print(f"[TRUSTFACES] Nie znaleziono Tobii Pro Spectrum. Wykryto: {models}")
        return None
    et = spectrum_trackers[0]
    print(f"[TRUSTFACES] Polaczono : {et.model} | serial {et.serial_number} | {et.address}")
    return et


class SpectrumGaze(spectrum.GazeStream):
    """Strumien Spectrum z szablonu: drain() -> [(t_perf_s, nx, ny)] tylko wazne probki."""

    def __init__(self, et):
        super().__init__(et)
        self.freq = float(et.get_gaze_output_frequency())

    def poll(self):
        pass  # probki przychodza w watku SDK


class MouseGaze:
    """Tylko test: mysz = wzrok, jedna probka na klatke."""

    def __init__(self, win, freq):
        self.win, self.freq = win, freq
        self.mouse = event.Mouse(win=win, visible=False)
        self._buf = []

    def start(self): pass
    def stop(self): pass
    def wait_for_data(self, timeout=1.0): return True

    def poll(self):
        x, y = self.mouse.getPos()
        w, h = self.win.size
        self._buf.append((time.perf_counter(), x / w + 0.5, 0.5 - y / h))

    def drain(self):
        out, self._buf = self._buf, []
        return out

    def latest_norm(self):
        return self._buf[-1][1:] if self._buf else None


def make_order(stimuli, rng):
    """Losowa kolejnosc, najwyzej MAX_SAME_CATEGORY_RUN portrety tej samej kategorii pod rzad."""
    for _ in range(10000):
        order = stimuli[:]
        rng.shuffle(order)
        run = 1
        for a, b in zip(order, order[1:]):
            run = run + 1 if a["category"] == b["category"] else 1
            if run > MAX_SAME_CATEGORY_RUN:
                break
        else:
            return order
    return order


def classify_aoi(ix, iy, roi):
    """Punkt w px portretu -> nazwa AOI (prostokaty [x0, y0, x1, y1] ze stimuli.json)."""
    if not (0 <= ix < IMAGE_W and 0 <= iy < IMAGE_H):
        return "off_image"

    def inside(r):
        return r[0] <= ix <= r[2] and r[1] <= iy <= r[3]

    if inside(roi["eyes"]):
        return "eyes"
    if inside(roi["lower"]):
        return "lower"
    if inside(roi["face"]):
        return "face_other"
    return "background"


def text(win, msg, height=30, pos=(0, 0)):
    return visual.TextStim(win, text=msg, height=height, pos=pos, color=TEXT_COLOR,
                           wrapWidth=win.size[0] * 0.8, units="pix")


def wait_space(win, stim):
    event.clearEvents()
    t0 = time.perf_counter()
    while True:
        stim.draw()
        win.flip()
        if event.getKeys(["space"]) or (AUTO and time.perf_counter() - t0 > 0.3):
            return


def show_for(win, seconds, draw=None, gaze=None):
    t_end = time.perf_counter() + seconds
    while time.perf_counter() < t_end:
        if draw:
            draw()
        if gaze:
            gaze.poll()
        win.flip()


def present(win, img, gaze, frame_s, cursor):
    """Portret przez PRESENT_S. Zwraca (t_on, t_off) w skali perf_counter (znaczniki flipow)."""
    marks = []
    win.callOnFlip(lambda: marks.append(time.perf_counter()))
    img.draw()
    win.flip()
    while time.perf_counter() - marks[0] < PRESENT_S - 0.5 * frame_s:
        gaze.poll()
        img.draw()
        if cursor is not None:
            g = gaze.latest_norm()
            if g is not None:
                cursor.pos = norm_to_pix(win, *g)
                cursor.draw()
        win.flip()
    win.callOnFlip(lambda: marks.append(time.perf_counter()))
    win.flip()
    gaze.poll()
    return marks[0], marks[1]


def get_rating(win, prompt):
    event.clearEvents()
    t0 = time.perf_counter()
    keys = [str(k) for k in range(1, 8)]
    while True:
        prompt.draw()
        win.flip()
        if AUTO and time.perf_counter() - t0 > 0.2:
            return random.randint(1, 7), (time.perf_counter() - t0) * 1000
        k = event.getKeys(keys)
        if k:
            return int(k[0]), (time.perf_counter() - t0) * 1000


def append_csv(path, fields, rows):
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)


def summarize(rows):
    print("\n[TRUSTFACES] Podsumowanie (prototyp, bez wykluczen):")
    for cat in ("REAL", "AI"):
        r = [x for x in rows if x["category"] == cat]
        if not r:
            continue
        mean = lambda k: sum(float(x[k]) for x in r) / len(r)
        print(f"  {cat:4s}  n={len(r):2d}  ocena={mean('trust_rating'):.2f}  "
              f"oczy={mean('pct_eyes'):.1f}%  dol twarzy={mean('pct_lower'):.1f}%  "
              f"wazne probki={mean('valid_ratio') * 100:.0f}%")


# ============================================================================
# 4. ENTRY POINT
# ============================================================================
TRIAL_FIELDS = ["participant", "trial", "stimulus_id", "category", "trust_rating", "rt_ms",
                "exposure_ms", "n_valid", "valid_ratio"] + \
               [f"ms_{a}" for a in AOI_NAMES] + [f"pct_{a}" for a in ("eyes", "lower", "face_other", "background")] + \
               ["first_eyes_ms", "run_mode"]
SAMPLE_FIELDS = ["participant", "trial", "stimulus_id", "t_ms", "nx", "ny", "img_x", "img_y", "aoi"]


def main():
    stimuli = json.loads((HERE / "stimuli.json").read_text(encoding="utf-8"))["stimuli"]

    if AUTO:
        pid = "AUTOTEST"
    else:
        info = {"Kod uczestnika (bez nazwiska)": "P01"}
        dlg = gui.DlgFromDict(info, title="TrustFaces - prototyp Spectrum")
        if not dlg.OK:
            return
        pid = "".join(c for c in info["Kod uczestnika (bez nazwiska)"] if c.isalnum() or c in "_-") or "P00"

    eyetracker = None if SIM else connect_eyetracker()

    win = visual.Window(size=(1920, 1080), fullscr=FULLSCREEN, color="black", units="pix",
                        screen=0, allowGUI=not FULLSCREEN)
    spectrum.install_escape(win)  # ESC przerywa w kazdym momencie

    if not SIM and eyetracker is None:
        msg = visual.TextStim(win, text="Nie znaleziono Tobii Pro Spectrum.\n\n"
                                        "Sprawdz polaczenie i Tobii Pro Eye Tracker Manager.\n\n"
                                        "Dowolny klawisz = wyjscie.", height=30, color="orange", wrapWidth=900)
        msg.draw()
        win.flip()
        event.waitKeys()
        win.close()
        return

    frame_rate = float(win.getActualFrameRate(nIdentical=10, nMaxFrames=120, nWarmUpFrames=10) or 60.0)
    frame_s = 1.0 / frame_rate

    # --- kalibracja (czarne tlo, jak w szablonie) ----------------------------------------
    if SIM:
        gaze = MouseGaze(win, frame_rate)
        run_mode = "SIM_MOUSE"
    else:
        calibrated = spectrum.calibrate(win, eyetracker, points=spectrum.CAL_POINTS_9)
        if not calibrated:
            print("[TRUSTFACES] Uwaga: kalibracja zaakceptowana mimo statusu NIEUDANA.")
        gaze = SpectrumGaze(eyetracker)
        run_mode = "TOBII_SPECTRUM" if calibrated else "TOBII_SPECTRUM_CAL_FAILED"

    # --- przygotowanie --------------------------------------------------------------------
    win.setColor(BG_RGB, colorSpace="rgb255")
    W, H = (int(v) for v in win.size)
    scale = min(1.0, 0.97 * W / IMAGE_W, 0.97 * H / IMAGE_H)
    img_left = (W - IMAGE_W * scale) / 2.0   # lewa krawedz portretu w px ekranu (od lewej)
    img_top = (H - IMAGE_H * scale) / 2.0
    imgs = {s["stimulus_id"]: visual.ImageStim(win, image=str(HERE / s["filename"]),
                                               size=(IMAGE_W * scale, IMAGE_H * scale), units="pix")
            for s in stimuli}
    cross = text(win, "+", height=60)
    prompt = text(win, RATING_PROMPT, height=34)
    cursor = visual.Circle(win, radius=12, fillColor=[1, -0.6, -0.6], lineColor=None, opacity=0.7) \
        if SHOW_GAZE else None

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = HERE / "data" / f"{pid}_{stamp}{'_SIM' if SIM else ''}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random()
    order = make_order(stimuli, rng)
    (out_dir / "session.json").write_text(json.dumps({
        "participant": pid, "run_mode": run_mode, "started": stamp,
        "tracker": None if eyetracker is None else f"{eyetracker.model} {eyetracker.serial_number}",
        "gaze_hz": gaze.freq, "frame_rate_hz": round(frame_rate, 2), "screen_px": [W, H],
        "image_scale": scale, "order": [s["stimulus_id"] for s in order],
    }, indent=2), encoding="utf-8")

    gaze.start()
    gaze.wait_for_data(2.0)
    wait_space(win, text(win, INSTRUCTION))

    # --- proby ----------------------------------------------------------------------------
    rows = []
    for i, s in enumerate(order, 1):
        show_for(win, CROSS_S, draw=cross.draw, gaze=gaze)
        gaze.drain()                                   # wyrzuc probki sprzed portretu
        t_on, t_off = present(win, imgs[s["stimulus_id"]], gaze, frame_s, cursor)
        samples = [g for g in gaze.drain() if t_on <= g[0] <= t_off]
        rating, rt_ms = get_rating(win, prompt)

        roi = s["mask_or_roi_coordinates"]
        ms_per_sample = 1000.0 / gaze.freq
        ms = dict.fromkeys(AOI_NAMES, 0.0)
        first_eyes = ""
        sample_rows = []
        for t, nx, ny in samples:
            ix = (nx * W - img_left) / scale
            iy = (ny * H - img_top) / scale
            aoi = classify_aoi(ix, iy, roi)
            ms[aoi] += ms_per_sample
            t_ms = (t - t_on) * 1000
            if aoi == "eyes" and first_eyes == "":
                first_eyes = round(t_ms, 1)
            sample_rows.append({"participant": pid, "trial": i, "stimulus_id": s["stimulus_id"],
                                "t_ms": round(t_ms, 2), "nx": round(nx, 5), "ny": round(ny, 5),
                                "img_x": round(ix, 1), "img_y": round(iy, 1), "aoi": aoi})
        on_image = sum(ms[a] for a in AOI_NAMES if a != "off_image") or 1.0
        row = {"participant": pid, "trial": i, "stimulus_id": s["stimulus_id"], "category": s["category"],
               "trust_rating": rating, "rt_ms": round(rt_ms, 1), "exposure_ms": round((t_off - t_on) * 1000, 1),
               "n_valid": len(samples), "valid_ratio": round(min(1.0, len(samples) / (PRESENT_S * gaze.freq)), 3),
               "first_eyes_ms": first_eyes, "run_mode": run_mode}
        row.update({f"ms_{a}": round(ms[a], 1) for a in AOI_NAMES})
        row.update({f"pct_{a}": round(100 * ms[a] / on_image, 1) for a in ("eyes", "lower", "face_other", "background")})
        append_csv(out_dir / "trials.csv", TRIAL_FIELDS, [row])       # zapis po kazdej probie
        append_csv(out_dir / "gaze_samples.csv", SAMPLE_FIELDS, sample_rows)
        rows.append(row)
        print(f"[TRUSTFACES] {i:2d}/12 {s['stimulus_id']:8s} ocena={rating}  probek={len(samples)}  "
              f"oczy={row['pct_eyes']}%")
        show_for(win, ITI_S, gaze=gaze)

    gaze.stop()
    wait_space(win, text(win, END_TEXT))
    win.close()
    summarize(rows)
    print(f"[TRUSTFACES] Zapisano: {out_dir}")
    core.quit()


if __name__ == "__main__":
    main()
