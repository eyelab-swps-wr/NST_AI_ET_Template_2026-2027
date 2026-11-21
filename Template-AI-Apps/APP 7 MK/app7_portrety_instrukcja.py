#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
APP 7 MK - Wplyw instrukcji na ogladanie 7 portretow (replikacja ze zmiana, v4.0 - PROTOTYP)
==========================================================================================
Tatler, Wade, Kwan, Findlay i Velichkovsky (2010), Yarbus, eye movements, and vision.

Przebieg (wg briefu zespolu):
  dane startowe (konsola) -> zgoda -> pozycja glowy + kalibracja 9 pkt (spectrum.calibrate)
  -> walidacja 5 pkt (blad w stopniach) -> podglad wzroku na zywo
  -> blok 1: swobodne ogladanie (7 zdjec) -> bloki status / wiarygodnosc (kolejnosc 50/50)
  -> natychmiastowe podsumowanie (udzial czasu fiksacji w 9 AOI x 3 warunki).

Tryby:
  Tobii Pro Spectrum   - prawdziwy pomiar (tobii-research 2.1.0 przez ../spectrum.py)
  SYMULACJA (mysz)     - JAWNA symulacja: spojrzenie = kursor myszy; dane oznaczone data_source=mouse_simulation
  Podglad AOI          - pokazuje 9 AOI na kazdym zdjeciu (do weryfikacji przez zespol)
  python app7_portrety_instrukcja.py --selftest   - automatyczny test calego przebiegu (symulacja skryptowa)

ESC w kazdej chwili przerywa sesje; dane zapisane do tej pory zostaja w folderze data/.
"""
import csv
import json
import math
import os
import platform
import random
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np

try:
    from psychopy import visual, core, event, logging
    logging.console.setLevel(logging.ERROR)
except ImportError as exc:
    raise ImportError("\nPsychoPy nie jest zainstalowane - uruchom przez run_app7.bat\n") from exc

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # ../spectrum.py
try:
    import tobii_research as tr
    import spectrum
except ImportError as exc:
    raise ImportError("\nBrak tobii-research 2.1.0 w tym srodowisku (64-bit Python 3.10).\n") from exc

APP_VERSION = "app7_mk v4.0-prototyp"
SELFTEST = "--selftest" in sys.argv

# ============================================================================
# KONFIGURACJA
# ============================================================================
CONDITIONS = {
    "free_view": ("Patrz na zdjecie swobodnie.", "instr_free"),
    "status": ("Ocen zamoznosc i pozycje spoleczna osoby przedstawionej na zdjeciu.", "instr_status"),
    "trust": ("Ocen wiarygodnosc osoby przedstawionej na zdjeciu.", "instr_trust"),
}
COND_LABEL = {"free_view": "Swobodne", "status": "Status", "trust": "Wiarygodnosc"}
COND_COLOR = {"free_view": "#9e9e9e", "status": "#f0a030", "trust": "#40a0f0"}

AOI_LABEL = {
    "oczy": "Oczy", "nos": "Nos", "usta": "Usta", "czolo_brwi": "Czolo i brwi",
    "reszta_twarzy": "Reszta twarzy", "wlosy_glowa": "Wlosy i glowa",
    "ubranie_tulow": "Ubranie i tulow", "detale_kontekstu": "Detale kontekstu", "tlo": "Tlo",
}
AOI_COLORS = {
    "oczy": (255, 0, 0), "nos": (255, 140, 0), "usta": (255, 0, 200), "czolo_brwi": (255, 255, 0),
    "reszta_twarzy": (0, 255, 0), "wlosy_glowa": (0, 200, 255), "ubranie_tulow": (80, 80, 255),
    "detale_kontekstu": (180, 0, 255), "tlo": (60, 60, 60),
}

# Detekcja fiksacji I-DT (Salvucci & Goldberg, 2000) na surowych probkach.
# PARAMETRY PILOTAZOWE - DO WERYFIKACJI na stanowisku (brief: nie wymyslac parametrow do analizy).
FIX_DISPERSION_DEG = 1.0
FIX_MIN_DUR_MS = 100
FIX_MAX_GAP_MS = 75

TRACK_LOSS_S = 2.0          # brak waznego spojrzenia dluzej niz tyle -> przerwanie proby
QUALITY_MIN_VALID = 0.80    # min. odsetek waznych probek (brief: 80-85%)
VAL_MEAN_MAX_DEG = 0.5      # brief: sredni blad walidacji < 0.5 deg
VAL_MAX_MAX_DEG = 1.0       # brief: maksymalny blad < 1.0 deg
VAL_POINTS = [(0.5, 0.5), (0.3, 0.3), (0.7, 0.3), (0.7, 0.7), (0.3, 0.7)]
MASK_W, MASK_H = 480, 358   # rozdzielczosc maski AOI (proporcje 2400x1792)


# ============================================================================
# USTAWIENIA SESJI (konsola - bez dodatkowych zaleznosci GUI)
# ============================================================================
def ask(prompt, default, cast=str, choices=None):
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        val = raw or str(default)
        try:
            val = cast(val)
        except ValueError:
            print("  Niepoprawna wartosc.")
            continue
        if choices and val not in choices:
            print(f"  Wybierz jedno z: {choices}")
            continue
        return val


def get_settings():
    if SELFTEST:
        return dict(participant_id="SELFTEST", mode="sim", distance_cm=63.0, screen_width_cm=53.0,
                    stim_s=2.0, instr_s=0.5, n_per_block=2, fullscreen=False, show_gaze=True,
                    seed=12345)
    print("=" * 70)
    print(" APP 7 MK - Wplyw instrukcji na ogladanie 7 portretow (PROTOTYP)")
    print("=" * 70)
    while True:
        pid = ask("Kod uczestnika (pseudonim, BEZ imienia/nazwiska)", "P001")
        if pid.replace("_", "").replace("-", "").isalnum():
            break
        print("  Tylko litery, cyfry, - i _")
    print("Tryb: 1 = Tobii Pro Spectrum   2 = SYMULACJA (mysz)   3 = Podglad AOI")
    mode = {"1": "spectrum", "2": "sim", "3": "aoi"}[ask("Tryb", "1", choices=["1", "2", "3"])]
    s = dict(participant_id=pid, mode=mode)
    s["distance_cm"] = ask("Odleglosc oczu od ekranu w cm (60-65)", 63.0, float)
    s["screen_width_cm"] = ask("Szerokosc obszaru obrazu monitora w cm (ZMIERZ!)", 53.0, float)
    s["stim_s"] = ask("Czas prezentacji zdjecia w s (MVP 20-30, pelne badanie 50)", 20.0, float)
    s["instr_s"] = ask("Czas instrukcji bloku w s", 10.0, float)
    s["n_per_block"] = ask("Liczba zdjec na blok (1-7; badanie = 7)", 7, int, choices=list(range(1, 8)))
    s["fullscreen"] = ask("Pelny ekran? (t/n)", "t", choices=["t", "n"]) == "t"
    s["show_gaze"] = ask("Pokazywac kursor wzroku podczas prob? (t/n - w badaniu: n)", "n",
                         choices=["t", "n"]) == "t"
    seed = ask("Ziarno losowania (puste = losowe)", "auto")
    s["seed"] = int(seed) if seed.isdigit() else random.SystemRandom().randint(1, 10 ** 9)
    return s


# ============================================================================
# AOI
# ============================================================================
class AOISet:
    def __init__(self, path):
        cfg = json.loads(Path(path).read_text(encoding="utf-8"))
        self.priority = cfg["priorytet"]
        self.photos = {}
        for pid, d in cfg["zdjecia"].items():
            mask = np.full((MASK_H, MASK_W), self.priority.index("tlo"), dtype=np.int16)
            # malujemy od najnizszego priorytetu do najwyzszego -> wyzszy nadpisuje
            for idx in range(len(self.priority) - 1, -1, -1):
                for x0, y0, x1, y1 in d.get(self.priority[idx], []):
                    mask[int(round(y0 * MASK_H)):int(round(y1 * MASK_H)),
                         int(round(x0 * MASK_W)):int(round(x1 * MASK_W))] = idx
            frac = {a: float((mask == i).mean()) for i, a in enumerate(self.priority)}
            self.photos[pid] = dict(file=HERE / d["plik"], mask=mask, area_frac=frac, rects=d)

    def label(self, photo_id, u, v):
        """u, v = wspolrzedne w obrazie 0..1 (0,0 = lewy gorny)."""
        if not (0.0 <= u < 1.0 and 0.0 <= v < 1.0):
            return "poza_zdjeciem"
        m = self.photos[photo_id]["mask"]
        return self.priority[int(m[int(v * MASK_H), int(u * MASK_W)])]

    def overlay_rgba(self, photo_id, alpha=0.45):
        from PIL import Image
        m = self.photos[photo_id]["mask"]
        img = np.zeros((MASK_H, MASK_W, 4), dtype=np.uint8)
        for i, a in enumerate(self.priority):
            sel = m == i
            img[sel, 0:3] = AOI_COLORS[a]
            img[sel, 3] = int(255 * (0.15 if a == "tlo" else alpha))
        return Image.fromarray(img, "RGBA")


# ============================================================================
# ZRODLA SPOJRZENIA
# ============================================================================
class SpectrumSource(spectrum.GazeStream):
    """Strumien Tobii (spectrum.GazeStream) + zapis kazdej surowej probki (oba oczy, waznosc)."""
    data_source = "tobii_pro_spectrum"

    def __init__(self, eyetracker):
        super().__init__(eyetracker)
        self._rec = None

    def now_us(self):
        return tr.get_system_time_stamp()

    def on_sample(self, d, g):
        rec = self._rec
        if rec is None:
            return
        lv, rv = bool(d["left_gaze_point_validity"]), bool(d["right_gaze_point_validity"])
        lx, ly = d["left_gaze_point_on_display_area"]
        rx, ry = d["right_gaze_point_on_display_area"]
        rec.append((d["system_time_stamp"], d["device_time_stamp"], lx, ly, lv, rx, ry, rv, g))

    def begin(self):
        self._rec = []

    def end(self):
        r, self._rec = self._rec, None
        return r or []

    def poll(self, win):
        pass


class SimSource:
    """JAWNA SYMULACJA: spojrzenie = mysz (lub skrypt w --selftest). Probki co klatke ekranu."""
    data_source = "mouse_simulation"

    def __init__(self, win, scripted=False):
        self.win = win
        self.mouse = event.Mouse(win=win, visible=not scripted)
        self.scripted = scripted
        self._rec = None
        self._latest = None
        self.targets = [(0.5, 0.5)]
        self._t0 = time.perf_counter()
        self.active = False

    def now_us(self):
        return int(time.perf_counter() * 1e6)

    def start(self):
        self.active = True

    def stop(self):
        self.active = False

    def wait_for_data(self, timeout=1.0):
        return True

    def poll(self, win):
        if self.scripted:  # 400 ms na cel + szum ~3 px
            k = int((time.perf_counter() - self._t0) / 0.4) % len(self.targets)
            nx, ny = self.targets[k]
            nx += random.gauss(0, 0.0015)
            ny += random.gauss(0, 0.0015)
        else:
            x, y = self.mouse.getPos()
            w, h = win.size
            nx, ny = x / w + 0.5, 0.5 - y / h
        self._latest = (nx, ny)
        if self._rec is not None:
            t = self.now_us()
            self._rec.append((t, t, nx, ny, True, nx, ny, True, (nx, ny)))

    def latest_norm(self):
        return self._latest

    def begin(self):
        self._rec = []

    def end(self):
        r, self._rec = self._rec, None
        return r or []


# ============================================================================
# GEOMETRIA
# ============================================================================
class Geometry:
    def __init__(self, win, distance_cm, screen_width_cm):
        self.W, self.H = win.size
        self.distance_cm = distance_cm
        self.px_per_cm = self.W / screen_width_cm
        ih = self.H * 0.92
        iw = ih * 2400 / 1792
        if iw > self.W * 0.96:
            iw = self.W * 0.96
            ih = iw * 1792 / 2400
        self.img_w, self.img_h = iw, ih

    def norm_to_pix(self, nx, ny):
        return (nx - 0.5) * self.W, (0.5 - ny) * self.H

    def norm_to_img(self, nx, ny):
        px, py = self.norm_to_pix(nx, ny)
        return (px + self.img_w / 2) / self.img_w, (self.img_h / 2 - py) / self.img_h

    def px_to_deg(self, px):
        return math.degrees(math.atan((px / self.px_per_cm) / self.distance_cm))

    def deg_to_px(self, deg):
        return math.tan(math.radians(deg)) * self.distance_cm * self.px_per_cm

    def stim_size_deg(self):
        f = lambda s: math.degrees(2 * math.atan((s / self.px_per_cm / 2) / self.distance_cm))
        return f(self.img_w), f(self.img_h)


# ============================================================================
# FIKSACJE (I-DT) - surowe probki != fiksacje
# ============================================================================
def detect_fixations(samples, disp_px, min_dur_us, max_gap_us):
    """samples: lista (t_us, x_px, y_px) tylko waznych probek, posortowana po czasie."""
    fix, i, n = [], 0, len(samples)
    while i < n:
        t0 = samples[i][0]
        j = i
        while j + 1 < n and samples[j + 1][0] - samples[j][0] <= max_gap_us and samples[j][0] - t0 < min_dur_us:
            j += 1
        if samples[j][0] - t0 < min_dur_us:
            i += 1
            continue
        xs = [s[1] for s in samples[i:j + 1]]
        ys = [s[2] for s in samples[i:j + 1]]
        mnx, mxx, mny, mxy = min(xs), max(xs), min(ys), max(ys)
        if (mxx - mnx) + (mxy - mny) > disp_px:
            i += 1
            continue
        sx, sy = sum(xs), sum(ys)
        while j + 1 < n and samples[j + 1][0] - samples[j][0] <= max_gap_us:
            _, x, y = samples[j + 1]
            a, b, c, d = min(mnx, x), max(mxx, x), min(mny, y), max(mxy, y)
            if (b - a) + (d - c) > disp_px:
                break
            mnx, mxx, mny, mxy = a, b, c, d
            sx += x
            sy += y
            j += 1
        k = j - i + 1
        fix.append((t0, samples[j][0], sx / k, sy / k))
        i = j + 1
    return fix


# ============================================================================
# ZAPIS DANYCH
# ============================================================================
SAMPLE_FIELDS = ["participant_id", "data_source", "trial_id", "block_id", "condition_id", "photo_id",
                 "timestamp_us", "device_time_stamp_us", "t_from_stimulus_ms",
                 "left_x", "left_y", "left_valid", "right_x", "right_y", "right_valid",
                 "gaze_x", "gaze_y", "img_u", "img_v", "sample_validity", "eye_mode", "sample_aoi_id"]
FIX_FIELDS = ["participant_id", "data_source", "trial_id", "block_id", "condition_id", "photo_id",
              "fixation_id", "fixation_start_us", "fixation_end_us", "fixation_duration_ms",
              "fix_x_px", "fix_y_px", "img_u", "img_v", "AOI_id", "AOI_area_px2"]
TRIAL_FIELDS = ["participant_id", "data_source", "trial_id", "repeat_of", "block_id", "block_index",
                "condition_id", "instruction_text_id", "photo_id", "photo_order_within_block", "block_order",
                "participant_distance_cm", "display_resolution", "stimulus_angular_size_deg",
                "trial_start_time_us", "stimulus_start_time_us", "stimulus_end_time_us",
                "tracking_status", "n_samples", "valid_sample_ratio", "quality_ok",
                "calibration_status", "validation_error_deg", "n_fixations"]
AOI_FIELDS = ["participant_id", "data_source", "trial_id", "block_id", "condition_id", "photo_id", "quality_ok",
              "AOI_id", "AOI_area_px2", "AOI_area_fraction", "fixation_count", "fixation_count_per_1000s_valid",
              "total_fixation_duration_ms", "proportion_fixation_time", "density_ms_per_1000px2",
              "normalized_aoi_duration"]


class DataWriter:
    def __init__(self, settings):
        out = HERE / "data"
        out.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.base = out / f"{settings['participant_id']}_{stamp}"
        self.files = {}
        for name, fields in (("samples", SAMPLE_FIELDS), ("fixations", FIX_FIELDS),
                             ("trials", TRIAL_FIELDS), ("aoi_summary", AOI_FIELDS)):
            p = Path(f"{self.base}_{name}.csv")
            with open(p, "w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fields).writeheader()
            self.files[name] = (p, fields)

    def append(self, name, rows):
        p, fields = self.files[name]
        with open(p, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fields, extrasaction="ignore")
            for r in rows:
                w.writerow(r)

    def write_config(self, cfg):
        Path(f"{self.base}_config.json").write_text(json.dumps(cfg, indent=1, ensure_ascii=False), encoding="utf-8")


# ============================================================================
# EKRANY POMOCNICZE
# ============================================================================
def text_screen(win, text, keys=("space",), timeout=None, color="white", height=30):
    stim = visual.TextStim(win, text=text, height=height, color=color, wrapWidth=win.size[0] * 0.8, units="pix")
    event.clearEvents(eventType="keyboard")
    clock = core.Clock()
    if SELFTEST and timeout is None:
        timeout = 0.3
    while True:
        stim.draw()
        win.flip()
        k = event.getKeys(list(keys)) if keys else []
        if k:
            return k[-1]
        if timeout is not None and clock.getTime() >= timeout:
            return None


def run_validation(win, src, geo):
    """5 punktow, po 1.5 s; blad = odleglosc sredniego spojrzenia (ostatnie 1 s) od celu, w stopniach."""
    dot = visual.Circle(win, radius=14, fillColor="white", lineColor=None, units="pix")
    inner = visual.Circle(win, radius=3, fillColor="black", lineColor=None, units="pix")
    text_screen(win, "WALIDACJA\n\nPatrz na srodek kazdego punktu.\n\nSPACJA = start")
    errs = []
    if isinstance(src, SimSource) and src.scripted:
        src.targets = [(0.5, 0.5)]
    for nx, ny in VAL_POINTS:
        if isinstance(src, SimSource) and src.scripted:
            src.targets = [(nx, ny)]
        dot.pos = inner.pos = geo.norm_to_pix(nx, ny)
        clock = core.Clock()
        pts = []
        while clock.getTime() < 1.5:
            src.poll(win)
            g = src.latest_norm()
            if clock.getTime() > 0.5 and g is not None:
                pts.append(geo.norm_to_pix(*g))
            dot.draw(); inner.draw(); win.flip()
        if pts:
            mx = sum(p[0] for p in pts) / len(pts)
            my = sum(p[1] for p in pts) / len(pts)
            tx, ty = geo.norm_to_pix(nx, ny)
            errs.append(geo.px_to_deg(math.hypot(mx - tx, my - ty)))
        else:
            errs.append(None)
    valid = [e for e in errs if e is not None]
    mean_e = sum(valid) / len(valid) if valid else None
    max_e = max(valid) if valid else None
    ok = mean_e is not None and len(valid) == len(errs) and mean_e < VAL_MEAN_MAX_DEG and max_e < VAL_MAX_MAX_DEG
    pts_txt = "   ".join("brak" if e is None else f"{e:.2f}" for e in errs)
    msg = (f"WALIDACJA {'OK' if ok else 'PONIZEJ KRYTERIUM'}\n\n"
           f"Bledy punktow [deg]: {pts_txt}\n"
           f"Sredni: {'-' if mean_e is None else f'{mean_e:.2f}'} deg (kryterium < {VAL_MEAN_MAX_DEG})   "
           f"Max: {'-' if max_e is None else f'{max_e:.2f}'} deg (kryterium < {VAL_MAX_MAX_DEG})\n\n"
           f"Stopnie zaleza od wpisanej odleglosci i szerokosci ekranu.\n\n"
           f"SPACJA = dalej     R = powtorz kalibracje")
    key = text_screen(win, msg, keys=("space", "r"), color="lime" if ok else "orange", height=26)
    return dict(ok=ok, mean_deg=mean_e, max_deg=max_e, points_deg=errs, redo=(key == "r"))


def live_preview(win, src, geo):
    """Pomiar na zywo: kursor wzroku + status sledzenia, az do SPACJI."""
    cursor = visual.Circle(win, radius=15, fillColor=[1, 0.2, 0.2], lineColor=None, opacity=0.8, units="pix")
    grid = [visual.Circle(win, radius=6, pos=geo.norm_to_pix(x, y), fillColor="gray", lineColor=None, units="pix")
            for x in (0.1, 0.5, 0.9) for y in (0.1, 0.5, 0.9)]
    info = visual.TextStim(win, text="POMIAR NA ZYWO - patrz na szare punkty. Czerwony punkt = Twoje spojrzenie.\n"
                                     "SPACJA = rozpocznij badanie", height=24, color="white",
                           pos=(0, -geo.H / 2 + 60), wrapWidth=geo.W * 0.9, units="pix")
    status = visual.TextStim(win, text="", height=22, pos=(0, geo.H / 2 - 30), units="pix")
    tag = visual.TextStim(win, text=f"ZRODLO: {src.data_source}", height=18, color="yellow",
                          pos=(-geo.W / 2 + 10, -geo.H / 2 + 15), anchorHoriz="left", units="pix")
    event.clearEvents(eventType="keyboard")
    clock = core.Clock()
    while True:
        src.poll(win)
        g = src.latest_norm()
        for d in grid:
            d.draw()
        if g is not None:
            cursor.pos = geo.norm_to_pix(*g)
            cursor.draw()
            status.text, status.color = "Sledzenie: OK", "lime"
        else:
            status.text, status.color = "Sledzenie: BRAK SPOJRZENIA", "orange"
        status.draw(); info.draw(); tag.draw()
        win.flip()
        if event.getKeys(["space"]) or (SELFTEST and clock.getTime() > 0.8):
            return


# ============================================================================
# PROBA
# ============================================================================
def run_trial(win, src, geo, aois, images, photo_id, show_gaze, stim_s):
    """Zwraca (status, start_us, stim_start_us, stim_end_us, surowe probki)."""
    cross = visual.TextStim(win, text="+", height=50, color="white", units="pix")
    cursor = visual.Circle(win, radius=12, fillColor=[1, 0.2, 0.2], lineColor=None, opacity=0.7, units="pix")
    trial_start = src.now_us()
    fix_dur = random.uniform(0.5, 1.0)  # brief: punkt centralny 500-1000 ms
    clock = core.Clock()
    while clock.getTime() < fix_dur:
        src.poll(win)
        cross.draw()
        win.flip()

    if isinstance(src, SimSource) and src.scripted:  # selftest: skrypt "patrzy" po AOI zdjecia
        r = aois.photos[photo_id]["rects"]
        src.targets = []
        for a in ("oczy", "usta", "ubranie_tulow", "detale_kontekstu", "oczy", "tlo"):
            if a in r:
                x0, y0, x1, y1 = r[a][0]
                u, v = (x0 + x1) / 2, (y0 + y1) / 2
                px, py = u * geo.img_w - geo.img_w / 2, geo.img_h / 2 - v * geo.img_h
                src.targets.append((px / geo.W + 0.5, 0.5 - py / geo.H))
            elif a == "tlo":
                src.targets.append((0.5 - geo.img_w / geo.W * 0.45, 0.5 + geo.img_h / geo.H * 0.45))
        src._t0 = time.perf_counter()

    img = images[photo_id]
    src.begin()
    img.draw()
    win.flip()
    stim_start = src.now_us()
    clock.reset()
    last_valid = time.perf_counter()
    status = "ok"
    while clock.getTime() < stim_s:
        src.poll(win)
        g = src.latest_norm()
        now = time.perf_counter()
        if g is not None:
            last_valid = now
        elif now - last_valid > TRACK_LOSS_S:
            status = "aborted_tracking_loss"
            break
        img.draw()
        if show_gaze and g is not None:
            cursor.pos = geo.norm_to_pix(*g)
            cursor.draw()
        win.flip()
    win.flip()  # sygnal konca: pusty ekran
    stim_end = src.now_us()
    samples = src.end()
    return status, trial_start, stim_start, stim_end, samples


def analyse_trial(trial, samples, geo, aois, pid):
    """Probki -> wiersze CSV; I-DT -> fiksacje -> AOI; metryki AOI dla proby."""
    photo = trial["photo_id"]
    area_img = geo.img_w * geo.img_h
    t_stim = trial["stimulus_start_time_us"]
    base = {k: trial[k] for k in ("participant_id", "data_source", "trial_id", "block_id", "condition_id", "photo_id")}
    srows, valid_px = [], []
    for ts, dts, lx, ly, lv, rx, ry, rv, g in samples:
        row = dict(base, timestamp_us=ts, device_time_stamp_us=dts, t_from_stimulus_ms=round((ts - t_stim) / 1000, 2),
                   left_x=lx if lv else "", left_y=ly if lv else "", left_valid=int(lv),
                   right_x=rx if rv else "", right_y=ry if rv else "", right_valid=int(rv),
                   sample_validity=int(g is not None),
                   eye_mode="both" if lv and rv else ("left" if lv else ("right" if rv else "none")))
        if g is not None:
            u, v = geo.norm_to_img(*g)
            row.update(gaze_x=round(g[0], 5), gaze_y=round(g[1], 5), img_u=round(u, 4), img_v=round(v, 4),
                       sample_aoi_id=aois.label(photo, u, v))
            valid_px.append((ts,) + geo.norm_to_pix(*g))
        srows.append(row)
    n = len(samples)
    valid_ratio = len(valid_px) / n if n else 0.0
    valid_px.sort()

    fixes = detect_fixations(valid_px, geo.deg_to_px(FIX_DISPERSION_DEG), FIX_MIN_DUR_MS * 1000, FIX_MAX_GAP_MS * 1000)
    frows = []
    per_aoi = {a: [0, 0.0] for a in aois.priority + ["poza_zdjeciem"]}
    for k, (t0, t1, x, y) in enumerate(fixes, 1):
        u = (x + geo.img_w / 2) / geo.img_w
        v = (geo.img_h / 2 - y) / geo.img_h
        a = aois.label(photo, u, v)
        dur = (t1 - t0) / 1000
        per_aoi[a][0] += 1
        per_aoi[a][1] += dur
        area = aois.photos[photo]["area_frac"].get(a, 0) * area_img
        frows.append(dict(base, fixation_id=f"{trial['trial_id']}_F{k:03d}", fixation_start_us=t0, fixation_end_us=t1,
                          fixation_duration_ms=round(dur, 1), fix_x_px=round(x, 1), fix_y_px=round(y, 1),
                          img_u=round(u, 4), img_v=round(v, 4), AOI_id=a, AOI_area_px2=round(area)))

    total_on_img = sum(per_aoi[a][1] for a in aois.priority)
    valid_s = valid_ratio * (trial["stimulus_end_time_us"] - t_stim) / 1e6
    quality_ok = valid_ratio >= QUALITY_MIN_VALID and trial["tracking_status"] == "ok"
    arows = []
    for a in aois.priority:
        frac = aois.photos[photo]["area_frac"][a]
        cnt, dur = per_aoi[a]
        prop = dur / total_on_img if total_on_img else 0.0
        arows.append(dict(base, quality_ok=int(quality_ok), AOI_id=a, AOI_area_px2=round(frac * area_img),
                          AOI_area_fraction=round(frac, 4), fixation_count=cnt,
                          fixation_count_per_1000s_valid=round(cnt / valid_s * 1000, 1) if valid_s > 0 else "",
                          total_fixation_duration_ms=round(dur, 1), proportion_fixation_time=round(prop, 4),
                          density_ms_per_1000px2=round(dur / (frac * area_img) * 1000, 4) if frac > 0 else "",
                          normalized_aoi_duration=round(prop / frac, 3) if frac > 0 else ""))
    return srows, frows, arows, valid_ratio, quality_ok, len(fixes)


# ============================================================================
# PODSUMOWANIE
# ============================================================================
def summarise(aoi_rows, aois):
    good = [r for r in aoi_rows if r["quality_ok"]]
    used_all = not good
    rows = good or aoi_rows
    dur = {c: {a: 0.0 for a in aois.priority} for c in CONDITIONS}
    for r in rows:
        dur[r["condition_id"]][r["AOI_id"]] += r["total_fixation_duration_ms"]
    prop = {}
    for c in CONDITIONS:
        tot = sum(dur[c].values())
        prop[c] = {a: (dur[c][a] / tot if tot else 0.0) for a in aois.priority}
    return prop, used_all, len({r["trial_id"] for r in rows})


def interpretation(prop):
    face = {c: prop[c]["oczy"] + prop[c]["usta"] for c in prop}
    ctx = {c: prop[c]["ubranie_tulow"] + prop[c]["detale_kontekstu"] for c in prop}
    pct = lambda x: f"{100 * x:.0f}%"
    def verdict(target, others):  # roznica < 2 pkt proc. = brak wyraznej roznicy
        d = target - max(others)
        return "ZGODNY" if d >= 0.02 else ("BRAK WYRAZNEJ ROZNICY" if d > -0.02 else "NIEZGODNY")
    h2 = verdict(face["trust"], (face["free_view"], face["status"]))
    h1 = verdict(ctx["status"], (ctx["free_view"], ctx["trust"]))
    return (
        f"H2 (wiarygodnosc -> oczy + usta): udzial czasu fiksacji {pct(face['trust'])} vs swobodne "
        f"{pct(face['free_view'])}, status {pct(face['status'])}  ->  kierunek: {h2}.\n"
        f"H1 (status -> ubranie + detale kontekstu): {pct(ctx['status'])} vs swobodne {pct(ctx['free_view'])}, "
        f"wiarygodnosc {pct(ctx['trust'])}  ->  kierunek: {h1}."
    )


def summary_screen(win, prop, interp, quality_txt, src):
    W, H = win.size
    els = [visual.TextStim(win, text="PODSUMOWANIE - udzial czasu fiksacji w AOI wg instrukcji", height=30,
                           pos=(0, H / 2 - 40), color="white", units="pix", wrapWidth=W * 0.9)]
    aoi_list = list(AOI_LABEL)
    top, row_h = H / 2 - 100, (H * 0.55) / len(aoi_list)
    x0, bar_max = -W * 0.18, W * 0.42
    maxp = max([max(p.values()) for p in prop.values()] + [0.01])
    for i, a in enumerate(aoi_list):
        y = top - i * row_h - row_h / 2
        els.append(visual.TextStim(win, text=AOI_LABEL[a], height=min(22, row_h * 0.5), pos=(x0 - 15, y),
                                   anchorHoriz="right", color="white", units="pix"))
        bh = row_h * 0.8 / 3
        for k, c in enumerate(CONDITIONS):
            p = prop[c][a]
            w = max(1.0, bar_max * p / maxp)
            yy = y + row_h * 0.4 - bh / 2 - k * bh
            els.append(visual.Rect(win, width=w, height=bh * 0.9, pos=(x0 + w / 2, yy), fillColor=COND_COLOR[c],
                                   lineColor=None, units="pix"))
            els.append(visual.TextStim(win, text=f"{100 * p:.0f}%", height=max(10, bh * 0.8), pos=(x0 + w + 8, yy),
                                       anchorHoriz="left", color=COND_COLOR[c], units="pix"))
    for k, c in enumerate(CONDITIONS):
        els.append(visual.TextStim(win, text=f"■ {COND_LABEL[c]}", height=22, color=COND_COLOR[c], units="pix",
                                   pos=(W * 0.32, top - 20 - k * 32), anchorHoriz="left"))
    els.append(visual.TextStim(win, text=interp + "\n\n" + quality_txt +
                               "\nWynik opisowy jednej sesji - NIE jest testem statystycznym ani walidacja sprzetu."
                               "   SPACJA = koniec", height=20, color="white", units="pix",
                               pos=(0, -H / 2 + H * 0.17), wrapWidth=W * 0.92))
    if src.data_source != "tobii_pro_spectrum":
        els.append(visual.TextStim(win, text="SYMULACJA - dane nie pochodza z eye-trackera", height=26, color="orange",
                                   pos=(0, H / 2 - 75), units="pix"))
    event.clearEvents(eventType="keyboard")
    clock = core.Clock()
    while not event.getKeys(["space"]):
        for e in els:
            e.draw()
        win.flip()
        if SELFTEST and clock.getTime() > 1.0:
            break


# ============================================================================
# TRYB: PODGLAD AOI
# ============================================================================
def aoi_preview(win, aois, geo, images):
    legend = "   ".join(AOI_LABEL[a] for a in aois.priority)
    for pid in sorted(aois.photos):
        ov = visual.ImageStim(win, image=aois.overlay_rgba(pid), size=(geo.img_w, geo.img_h), units="pix")
        info = visual.TextStim(win, text=f"{pid}  |  SPACJA = nastepne zdjecie  |  {legend}", height=16,
                               pos=(0, -geo.H / 2 + 14), color="white", units="pix", wrapWidth=geo.W)
        keys = []
        for a in aois.priority:
            c = AOI_COLORS[a]
            keys.append((AOI_LABEL[a], [v / 127.5 - 1 for v in c]))
        lg = [visual.TextStim(win, text=f"■ {name}", color=col, height=20, units="pix", anchorHoriz="left",
                              pos=(-geo.W / 2 + 10, geo.H / 2 - 20 - i * 24)) for i, (name, col) in enumerate(keys)]
        event.clearEvents(eventType="keyboard")
        clock = core.Clock()
        while not event.getKeys(["space"]):
            images[pid].draw(); ov.draw(); info.draw()
            for t in lg:
                t.draw()
            win.flip()
            if SELFTEST and clock.getTime() > 0.3:
                break


# ============================================================================
# GLOWNY PRZEBIEG
# ============================================================================
def connect_spectrum():
    """Wg szablonu AI Template App: tylko Tobii Pro Spectrum."""
    print("\n[APP7] Szukam eye-trackera...")
    trackers = spectrum.find_all_eyetrackers()
    sp = [t for t in trackers if "spectrum" in (t.model or "").casefold()]
    if not sp:
        print("[APP7] Nie znaleziono Tobii Pro Spectrum. Wykryto: "
              + (", ".join(t.model or "?" for t in trackers) or "nic"))
        return None
    et = sp[0]
    print(f"[APP7] Polaczono: {et.model}  SN {et.serial_number}  {et.address}")
    return et


def calibrate_and_validate(win, src, geo, et):
    """Spectrum: spectrum.calibrate (pozycja glowy, 9 pkt, wykres) + walidacja. Symulacja: tylko 'walidacja'."""
    while True:
        cal_status = "not_applicable_simulation"
        if et is not None:
            src.stop()
            ok = spectrum.calibrate(win, et, points=spectrum.CAL_POINTS_9)
            cal_status = "success" if ok else "accepted_despite_failure"
            src.start()
            if not src.wait_for_data(2.0):
                text_screen(win, "Brak danych ze strumienia wzroku po kalibracji.\nSPACJA = ponow kalibracje",
                            color="orange")
                continue
        val = run_validation(win, src, geo)
        if not val["redo"]:
            return cal_status, val


def main():
    settings = get_settings()
    rng = random.Random(settings["seed"])
    random.seed(settings["seed"] + 1)
    aois = AOISet(HERE / "aoi_definitions.json")

    et = None
    if settings["mode"] == "spectrum":
        et = connect_spectrum()

    win = visual.Window(size=(1920, 1080) if not SELFTEST else (1024, 640), fullscr=settings["fullscreen"],
                        color="black", units="pix", screen=0, allowGUI=not settings["fullscreen"])
    spectrum.install_escape(win)
    win.mouseVisible = settings["mode"] != "spectrum" and not SELFTEST
    geo = Geometry(win, settings["distance_cm"], settings["screen_width_cm"])

    loading = visual.TextStim(win, text="Wczytywanie zdjec...", height=30, units="pix")
    loading.draw(); win.flip()
    images = {pid: visual.ImageStim(win, image=str(p["file"]), size=(geo.img_w, geo.img_h), units="pix")
              for pid, p in aois.photos.items()}

    if settings["mode"] == "aoi":
        aoi_preview(win, aois, geo, images)
        win.close()
        return

    if settings["mode"] == "spectrum" and et is None:
        text_screen(win, "Nie znaleziono Tobii Pro Spectrum.\n\nSprawdz polaczenie i Tobii Pro Eye Tracker Manager.\n"
                         "(Do testu bez trackera uruchom ponownie i wybierz tryb 2 = SYMULACJA.)\n\nSPACJA = wyjscie",
                    color="orange")
        win.close()
        return

    src = SpectrumSource(et) if et is not None else SimSource(win, scripted=SELFTEST)
    writer = DataWriter(settings)

    # --- plan: free_view zawsze pierwszy; status/trust 50/50; zdjecia losowane osobno w kazdym bloku
    block_order = rng.choice(["status_first", "trust_first"])
    blocks = ["free_view"] + (["status", "trust"] if block_order == "status_first" else ["trust", "status"])
    all_photos = sorted(aois.photos)
    photo_set = rng.sample(all_photos, settings["n_per_block"]) if settings["n_per_block"] < 7 else all_photos
    plan = {b: rng.sample(photo_set, len(photo_set)) for b in blocks}

    w_deg, h_deg = geo.stim_size_deg()
    config = dict(
        app_version=APP_VERSION, session_status="running", data_source=src.data_source,
        participant_id=settings["participant_id"], started=datetime.now().isoformat(timespec="seconds"),
        settings=settings, random_seed=settings["seed"], block_order=block_order, blocks=blocks, photo_order=plan,
        display_resolution=f"{geo.W}x{geo.H}", image_size_px=[round(geo.img_w), round(geo.img_h)],
        stimulus_angular_size_deg=[round(w_deg, 2), round(h_deg, 2)],
        tracker=None if et is None else dict(model=et.model, serial=et.serial_number, address=et.address,
                                             gaze_output_frequency_hz=et.get_gaze_output_frequency()),
        sdk="tobii-research " + getattr(tr, "__version__", "?"), python=platform.python_version(),
        fixation_algorithm=dict(name="I-DT (dyspersja) na srednim spojrzeniu obu oczu",
                                dispersion_deg=FIX_DISPERSION_DEG, min_duration_ms=FIX_MIN_DUR_MS,
                                max_gap_ms=FIX_MAX_GAP_MS, status="PARAMETRY PILOTAZOWE - DO WERYFIKACJI"),
        quality_criteria=dict(min_valid_sample_ratio=QUALITY_MIN_VALID, validation_mean_deg=VAL_MEAN_MAX_DEG,
                              validation_max_deg=VAL_MAX_MAX_DEG, tracking_loss_abort_s=TRACK_LOSS_S),
        aoi_definitions=json.loads((HERE / "aoi_definitions.json").read_text(encoding="utf-8")),
        aoi_area_fraction={p: aois.photos[p]["area_frac"] for p in all_photos},
        clocks="timestamp_us: Spectrum = system_time_stamp SDK (us); symulacja = time.perf_counter (us)",
        calibrations=[],
    )
    writer.write_config(config)

    def on_abort_save():
        config["session_status"] = "aborted_by_esc"
        config["ended"] = datetime.now().isoformat(timespec="seconds")
        writer.write_config(config)
        print(f"[APP7] Sesja przerwana. Dane czesciowe: {writer.base}_*")
    spectrum.on_abort(on_abort_save)

    # --- zgoda i instrukcja
    text_screen(win, "BADANIE: ogladanie portretow\n\nZobaczysz 3 serie zdjec. Przed kazda seria pojawi sie polecenie.\n"
                     "Patrz na zdjecia zgodnie z poleceniem - niczego nie trzeba klikac ani mowic.\n\n"
                     "Eksperymentator: SPACJA = uczestnik wyrazil zgode, rozpocznij.\nESC = przerwij w dowolnej chwili.")
    src.start()
    cal_status, val = calibrate_and_validate(win, src, geo, et)
    config["calibrations"].append(dict(time=datetime.now().isoformat(timespec="seconds"), status=cal_status,
                                       validation=val))
    writer.write_config(config)
    live_preview(win, src, geo)

    all_aoi_rows, trial_no, n_bad = [], 0, 0
    for bi, block in enumerate(blocks, 1):
        if bi > 1:
            text_screen(win, f"Krotka przerwa.\n\nSeria {bi} z 3.\n\nSPACJA = dalej")
        text, instr_id = CONDITIONS[block]
        text_screen(win, f"Seria {bi} z 3\n\n{text}", keys=(), timeout=settings["instr_s"], height=40)
        queue = [(p, None) for p in plan[block]]
        order = {p: i for i, p in enumerate(plan[block], 1)}
        while queue:
            photo, repeat_of = queue.pop(0)
            trial_no += 1
            tid = f"T{trial_no:03d}"
            status, t_start, s_start, s_end, samples = run_trial(win, src, geo, aois, images, photo,
                                                                 settings["show_gaze"], settings["stim_s"])
            trial = dict(participant_id=settings["participant_id"], data_source=src.data_source, trial_id=tid,
                         repeat_of=repeat_of or "", block_id=block, block_index=bi, condition_id=block,
                         instruction_text_id=instr_id, photo_id=photo, photo_order_within_block=order[photo],
                         block_order=block_order, participant_distance_cm=settings["distance_cm"],
                         display_resolution=f"{geo.W}x{geo.H}",
                         stimulus_angular_size_deg=f"{w_deg:.2f}x{h_deg:.2f}", trial_start_time_us=t_start,
                         stimulus_start_time_us=s_start, stimulus_end_time_us=s_end, tracking_status=status,
                         calibration_status=config["calibrations"][-1]["status"],
                         validation_error_deg="" if val["mean_deg"] is None else round(val["mean_deg"], 3))
            srows, frows, arows, vr, q_ok, nfix = analyse_trial(trial, samples, geo, aois, settings["participant_id"])
            trial.update(n_samples=len(samples), valid_sample_ratio=round(vr, 4), quality_ok=int(q_ok), n_fixations=nfix)
            writer.append("samples", srows)
            writer.append("fixations", frows)
            writer.append("trials", [trial])
            if status == "ok":
                writer.append("aoi_summary", arows)
                all_aoi_rows.extend(arows)
                if not q_ok:
                    n_bad += 1
                print(f"[APP7] {tid} {block:9s} {photo}  waznych probek {vr:.0%}  fiksacji {nfix}")
                continue
            # utrata sledzenia: przerwana proba -> rekalibracja (R) lub powtorzenie (SPACJA), nowy trial_id
            print(f"[APP7] {tid} przerwana - utrata sledzenia")
            key = text_screen(win, "UTRACONO SLEDZENIE WZROKU - proba przerwana.\n\n"
                                   "R = rekalibracja i powtorzenie proby\nSPACJA = powtorz probe bez rekalibracji\n"
                                   "ESC = zakoncz sesje", keys=("r", "space"), color="orange")
            if key == "r":
                cal_status, val = calibrate_and_validate(win, src, geo, et)
                config["calibrations"].append(dict(time=datetime.now().isoformat(timespec="seconds"),
                                                   status=cal_status, validation=val, after_trial=tid))
                writer.write_config(config)
            queue.insert(0, (photo, tid))

    src.stop()
    config["session_status"] = "completed"
    config["ended"] = datetime.now().isoformat(timespec="seconds")
    writer.write_config(config)
    spectrum.remove_on_abort(on_abort_save)

    prop, used_all, n_used = summarise(all_aoi_rows, aois)
    interp = interpretation(prop)
    v_txt = "-" if val["mean_deg"] is None else f"{val['mean_deg']:.2f} deg"
    quality_txt = (f"Jakosc: walidacja sredni blad {v_txt} ({'OK' if val['ok'] else 'ponizej kryterium'}); "
                   f"prob ponizej {QUALITY_MIN_VALID:.0%} waznych probek: {n_bad}. "
                   + ("UWAGA: zadna proba nie spelnila kryterium - pokazano wszystkie." if used_all
                      else f"Analiza z {n_used} prob spelniajacych kryterium."))
    print("\n[APP7] " + interp.replace("\n", "\n[APP7] "))
    print(f"[APP7] {quality_txt}")
    print(f"[APP7] Dane zapisane: {writer.base}_*.csv / _config.json")
    summary_screen(win, prop, interp, quality_txt, src)
    win.close()
    if SELFTEST:
        print(f"SELFTEST_BASE={writer.base}")


if __name__ == "__main__":
    main()
    core.quit()
