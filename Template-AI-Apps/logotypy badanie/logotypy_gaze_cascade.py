#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LOGOTYPY HITACHI - GAZE CASCADE (szybki prototyp, replikacja Shimojo i in., 2003)

Przebieg (skrocony - brak czasu):
  1. instrukcja + kod uczestnika (z linii polecen, domyslnie "P01"),
  2. kalibracja Tobii Pro Spectrum (spectrum.calibrate z szablonu: pozycja glowy,
     9 punktow, wykres bledu, SPACJA = akceptuj, R = powtorz),
  3. blok PREFERENCJA: 6 prob = wszystkie pary 4 logo, strony losowane,
  4. blok KONTROLA: 4 proby, "ktore logo ma wiecej ciemnych elementow",
  5. zapis danych (CSV prob + CSV surowych probek + JSON konfiguracji),
  6. ekran wynikow: krzywa gaze likelihood przed odpowiedzia + czas patrzenia.

Proba: krzyzyk 500 ms -> para logo bez limitu czasu -> strzalka lewo/prawo -> przerwa 400 ms.
ESC = natychmiastowe przerwanie w kazdym momencie.

Uruchomienie:  run_logotypy.bat              (Tobii Pro Spectrum)
               run_logotypy_symulacja.bat    (JAWNA SYMULACJA: mysz = wzrok, bez kalibracji)
"""
import csv
import itertools
import json
import math
import random
import sys
from datetime import datetime
from pathlib import Path

from psychopy import core, event, logging, visual
logging.console.setLevel(logging.ERROR)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # wspolny ../spectrum.py z szablonu
import tobii_research as tr
import spectrum

VERSION = "logotypy-proto-0.1"
SIM = "--sim" in sys.argv
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
PARTICIPANT = ARGS[0] if ARGS else "P01"

STIMULI = {
    "H1910_1918": HERE / "Logo" / "Hitachi 1.png",
    "H1918_1968": HERE / "Logo" / "hitachi 2.png",
    "H1968_1992": HERE / "Logo" / "hitachi 3.png",
    "H1992_NOW": HERE / "Logo" / "hitachi 4.png",
}
N_CONTROL = 4                     # liczba prob kontrolnych (skrocone)
FIX_S, ITI_S = 0.5, 0.4           # krzyzyk 500 ms, przerwa 400 ms
AOI_MARGIN = 25                   # px wokol logo
WINDOW_MS, BIN_MS = 2000, 100     # analiza: 2 s przed odpowiedzia, przedzialy 100 ms
BG = "#ffffff"                    # logo maja biale tlo -> biale tlo ekranu
FG = "#202020"
FONT = "Arial"
KEYS = {"left": "left", "right": "right"}

INSTR = {
    "preference": "Zobaczysz dwa logo Hitachi.\nPrzyjrzyj sie obu i wybierz logo, ktore wyglada\n"
                  "BARDZIEJ ATRAKCYJNIE. Nie ma poprawnej odpowiedzi.\n\n"
                  "Strzalka W LEWO = lewe logo,  strzalka W PRAWO = prawe logo.\n"
                  "Przed kazda para patrz na krzyzyk na srodku.\n\nSPACJA = start",
    "control": "Teraz zadanie kontrolne.\nWybierz logo, ktore ma WIECEJ CIEMNYCH ELEMENTOW\n"
               "(wieksza powierzchnie ciemnego koloru). Nie oceniaj atrakcyjnosci.\n\n"
               "Strzalka W LEWO = lewe logo,  strzalka W PRAWO = prawe logo.\n\nSPACJA = start",
}


# ----------------------------------------------------------------------------
# Zrodla wzroku: Tobii (sprzet) albo mysz (JAWNA symulacja)
# ----------------------------------------------------------------------------
class Gaze(spectrum.GazeStream):
    """Strumien z szablonu + lista wszystkich probek (SDK system_time_stamp us, x, y, valid)."""
    def __init__(self, et):
        super().__init__(et)
        self.samples = []

    def on_sample(self, d, g):
        self.samples.append((d["system_time_stamp"], g,
                             d["left_gaze_point_validity"], d["right_gaze_point_validity"]))

    def poll(self):
        pass


class MouseGaze:
    """SYMULACJA: pozycja myszy = wzrok (probka co klatke). Nie jest to walidacja sprzetu."""
    def __init__(self, win):
        self.win, self.mouse, self.samples = win, event.Mouse(win=win, visible=True), []
        self.n_samples = self.n_valid = 0

    def start(self): pass
    def stop(self): pass

    def poll(self):
        x, y = self.mouse.getPos()
        w, h = self.win.size
        self.samples.append((tr.get_system_time_stamp(), (x / w + 0.5, 0.5 - y / h), 1, 1))


def text(win, msg, pos=(0, 0), height=30, color=FG, **kw):
    return visual.TextStim(win, text=msg, pos=pos, height=height, color=color, font=FONT,
                           wrapWidth=win.size[0] * 0.9, **kw)


def wait_space(win, stims):
    event.clearEvents()
    while not event.getKeys(["space"]):
        for s in stims:
            s.draw()
        win.flip()


# ----------------------------------------------------------------------------
# Bodzce i AOI
# ----------------------------------------------------------------------------
def make_images(win):
    """Kazde logo przeskalowane proporcjonalnie do tej samej wysokosci, miesci sie w polowie ekranu."""
    from PIL import Image
    W, H = win.size
    box_w, box_h = W * 0.38, H * 0.40
    aspects = {k: (lambda im: im.size[0] / im.size[1])(Image.open(p)) for k, p in STIMULI.items()}
    img_h = min(box_h, box_w / max(aspects.values()))   # wspolna wysokosc dla wszystkich
    imgs = {k: visual.ImageStim(win, image=str(p), size=(img_h * aspects[k], img_h), units="pix")
            for k, p in STIMULI.items()}
    return imgs, img_h, W * 0.25


def aoi_rect(img, cx):
    w, h = img.size
    return (cx - w / 2 - AOI_MARGIN, cx + w / 2 + AOI_MARGIN, -h / 2 - AOI_MARGIN, h / 2 + AOI_MARGIN)


def which_aoi(win, g, aois):
    """g = (nx, ny) display area -> 'left' / 'right' / None."""
    if g is None:
        return None
    w, h = win.size
    px, py = (g[0] - 0.5) * w, (0.5 - g[1]) * h
    for side, (x0, x1, y0, y1) in aois.items():
        if x0 <= px <= x1 and y0 <= py <= y1:
            return side
    return None


# ----------------------------------------------------------------------------
# Jedna proba
# ----------------------------------------------------------------------------
def run_trial(win, gaze, imgs, x0, trial_id, block, condition, left_id, right_id):
    L, R = imgs[left_id], imgs[right_id]
    L.pos, R.pos = (-x0, 0), (x0, 0)
    aois = {"left": aoi_rect(L, -x0), "right": aoi_rect(R, x0)}
    hint = text(win, "<-  lewe                                     prawe  ->",
                pos=(0, -win.size[1] * 0.36), height=22, color="#888888")
    cue = text(win, "Ktore bardziej atrakcyjne?" if condition == "preference" else "Ktore ma wiecej ciemnych elementow?",
               pos=(0, win.size[1] * 0.36), height=26, color="#555555")
    cross = text(win, "+", height=60)

    t0 = core.getTime()
    while core.getTime() - t0 < FIX_S:
        cross.draw()
        win.flip()
        gaze.poll()

    event.clearEvents()
    n_before = len(gaze.samples)
    box = {}
    win.callOnFlip(lambda: box.__setitem__("onset", tr.get_system_time_stamp()))  # onset = 1. flip pary
    key = None
    while key is None:
        L.draw(); R.draw(); hint.draw(); cue.draw()
        win.flip()
        gaze.poll()
        keys = event.getKeys(keyList=list(KEYS))
        key = keys[0] if keys else None
    t_resp = tr.get_system_time_stamp()
    t_on = box["onset"]

    t0 = core.getTime()
    while core.getTime() - t0 < ITI_S:
        win.flip()
        gaze.poll()

    side = KEYS[key]
    other = "right" if side == "left" else "left"
    # probki z czasu prezentacji (+ zapas, bo callback SDK moze dojsc chwile pozniej)
    trial_samples = [s for s in gaze.samples[max(0, n_before - 200):] if t_on <= s[0] <= t_resp]
    raw = []
    dwell = {"left": 0.0, "right": 0.0}
    for i, (ts, g, lv, rv) in enumerate(trial_samples):
        a = which_aoi(win, g, aois)
        raw.append({"trial_id": trial_id, "t_us": ts, "t_rel_resp_ms": round((ts - t_resp) / 1000, 2),
                    "gaze_x_norm": "" if g is None else round(g[0], 5),
                    "gaze_y_norm": "" if g is None else round(g[1], 5),
                    "left_valid": lv, "right_valid": rv, "valid": int(g is not None),
                    "aoi": a or "", "on_chosen": "" if a is None else int(a == side)})
        if a and i + 1 < len(trial_samples):
            dt = trial_samples[i + 1][0] - ts
            if dt <= 100_000:            # luka > 100 ms nie jest liczona jako patrzenie
                dwell[a] += dt / 1000
    n = len(trial_samples)
    n_valid = sum(1 for s in trial_samples if s[1] is not None)
    chosen_id = left_id if side == "left" else right_id

    row = {"participant_id": PARTICIPANT, "trial_id": trial_id, "block": block, "condition": condition,
           "pair_id": "-".join(sorted((left_id, right_id))),
           "left_stimulus_id": left_id, "right_stimulus_id": right_id,
           "chosen_stimulus_id": chosen_id, "chosen_side": side, "response_key": key,
           "stimulus_onset_us": t_on, "response_timestamp_us": t_resp,
           "reaction_time_ms": round((t_resp - t_on) / 1000),
           "sample_count": n, "valid_gaze_ratio": round(n_valid / n, 3) if n else 0,
           "left_aoi_dwell_ms": round(dwell["left"]), "right_aoi_dwell_ms": round(dwell["right"]),
           "chosen_dwell_ms": round(dwell[side]), "unchosen_dwell_ms": round(dwell[other]),
           "repeat_of": ""}
    return row, raw


# ----------------------------------------------------------------------------
# Analiza: gaze likelihood wyrownane do odpowiedzi
# ----------------------------------------------------------------------------
def likelihood_curve(raw, trial_ids):
    """Dla kazdego przedzialu: srednia (po probach) udzialu probek na logo wybranym.
    Probki poza AOI / niewazne = NaN (pomijane)."""
    nbins = WINDOW_MS // BIN_MS
    per_trial = {t: [[] for _ in range(nbins)] for t in trial_ids}
    for r in raw:
        if r["trial_id"] not in per_trial or r["on_chosen"] == "":
            continue
        rel = -r["t_rel_resp_ms"]
        if 0 <= rel < WINDOW_MS:
            b = nbins - 1 - int(rel // BIN_MS)
            per_trial[r["trial_id"]][b].append(r["on_chosen"])
    curve = []
    for b in range(nbins):
        vals = [sum(v[b]) / len(v[b]) for v in per_trial.values() if v[b]]
        curve.append(sum(vals) / len(vals) if vals else math.nan)
    return curve


def summarize(rows, raw):
    out = {}
    for cond in ("preference", "control"):
        rs = [r for r in rows if r["condition"] == cond]
        if not rs:
            continue
        curve = likelihood_curve(raw, {r["trial_id"] for r in rs})
        last = [v for v in curve[-5:] if not math.isnan(v)]   # ostatnie 500 ms
        out[cond] = {"n": len(rs), "curve": curve,
                     "last500": sum(last) / len(last) if last else math.nan,
                     "chosen_ms": sum(r["chosen_dwell_ms"] for r in rs) / len(rs),
                     "unchosen_ms": sum(r["unchosen_dwell_ms"] for r in rs) / len(rs),
                     "rt_s": sum(r["reaction_time_ms"] for r in rs) / len(rs) / 1000,
                     "valid": sum(r["valid_gaze_ratio"] for r in rs) / len(rs)}
    return out


def show_results(win, summ, rows, mode_label):
    W, H = win.size
    COL = {"preference": "#d6336c", "control": "#555555"}
    NAME = {"preference": "preferencja", "control": "kontrola"}
    stims = [text(win, "WYNIKI  -  gaze likelihood (Shimojo i in., 2003)  " + mode_label,
                  pos=(0, H * 0.44), height=30)]

    # --- wykres krzywej ---
    gw, gh = W * 0.50, H * 0.45
    gx0, gy0 = -W * 0.42, -H * 0.18          # lewy dolny rog wykresu
    stims.append(visual.Rect(win, gw, gh, pos=(gx0 + gw / 2, gy0 + gh / 2), lineColor="#999999", fillColor=None))
    y50 = gy0 + gh * 0.5
    stims.append(visual.Line(win, start=(gx0, y50), end=(gx0 + gw, y50), lineColor="#bbbbbb"))
    for v in (0, 0.5, 1):
        stims.append(text(win, f"{v:.1f}", pos=(gx0 - 30, gy0 + gh * v), height=18))
    nb = WINDOW_MS // BIN_MS
    for k in range(0, nb + 1, 5):
        stims.append(text(win, f"{-(WINDOW_MS - k * BIN_MS) / 1000:.1f}", pos=(gx0 + gw * k / nb, gy0 - 20), height=18))
    stims.append(text(win, "czas do odpowiedzi [s]", pos=(gx0 + gw / 2, gy0 - 50), height=20))
    stims.append(text(win, "P(wzrok na logo wybranym)", pos=(gx0 - 70, gy0 + gh / 2), height=20, ori=-90))
    ly = gy0 + gh + 25
    for cond, s in summ.items():
        pts = [(gx0 + gw * (b + 0.5) / nb, gy0 + gh * v) for b, v in enumerate(s["curve"]) if not math.isnan(v)]
        if len(pts) >= 2:
            stims.append(visual.ShapeStim(win, vertices=pts, closeShape=False, lineColor=COL[cond], lineWidth=4))
        for p in pts:
            stims.append(visual.Circle(win, radius=4, pos=p, fillColor=COL[cond], lineColor=None))
        stims.append(text(win, f"— {NAME[cond]} (n={s['n']})", pos=(gx0 + gw * (0.2 if cond == "preference" else 0.7), ly),
                          height=22, color=COL[cond]))

    # --- tabela po prawej ---
    lines = []
    for cond, s in summ.items():
        l5 = "brak danych" if math.isnan(s["last500"]) else f"{s['last500'] * 100:.0f}%"
        lines.append(f"{NAME[cond].upper()}  (n={s['n']})\n"
                     f"  ostatnie 0,5 s: {l5} na wybranym\n"
                     f"  patrzenie: wybrane {s['chosen_ms'] / 1000:.2f} s / niewybrane {s['unchosen_ms'] / 1000:.2f} s\n"
                     f"  sredni RT: {s['rt_s']:.2f} s   wazne probki: {s['valid'] * 100:.0f}%")
    pref = [r["chosen_stimulus_id"] for r in rows if r["condition"] == "preference"]
    counts = sorted(((pref.count(k), k) for k in STIMULI), reverse=True)
    lines.append("WYBORY (preferencja):\n" + "\n".join(f"  {k}: {c}x" for c, k in counts))
    stims.append(visual.TextStim(win, text="\n\n".join(lines), pos=(W * 0.13, H * 0.05), height=21, color=FG,
                                 font=FONT, wrapWidth=W * 0.34, alignText="left", anchorHoriz="left"))

    p, c = summ.get("preference"), summ.get("control")
    if p and not math.isnan(p["last500"]):
        if p["last500"] > 0.6:
            verdict = "Przed odpowiedzia wzrok przesuwal sie na logo, ktore potem wybrano - wzorzec gaze cascade."
        else:
            verdict = "Nie widac wyraznego przesuniecia wzroku na wybrane logo przed odpowiedzia."
        if c and not math.isnan(c["last500"]):
            verdict += f"  (Preferencja {p['last500'] * 100:.0f}% vs kontrola {c['last500'] * 100:.0f}%.)"
    else:
        verdict = "Za malo waznych probek w AOI, zeby policzyc krzywa."
    stims.append(text(win, verdict + "\nTo pojedyncza sesja demo - nie wynik badania.   SPACJA = koniec",
                      pos=(0, -H * 0.40), height=22))
    wait_space(win, stims)


# ----------------------------------------------------------------------------
def main():
    seed = random.randrange(1_000_000)
    rng = random.Random(seed)
    et = None
    if not SIM:
        found = [t for t in spectrum.find_all_eyetrackers() if "spectrum" in (t.model or "").lower()]
        if not found:
            print("Nie znaleziono Tobii Pro Spectrum. (Jawna symulacja bez trackera: run_logotypy_symulacja.bat)")
            input("Enter = koniec")
            return
        et = found[0]

    win = visual.Window(fullscr=True, color=BG, units="pix")
    win.mouseVisible = SIM
    spectrum.install_escape(win)
    mode_label = "[SYMULACJA - mysz]" if SIM else "[Tobii Pro Spectrum]"

    wait_space(win, [text(win, "Badanie: logotypy Hitachi\n\nNajpierw kalibracja eye-trackera,\n"
                               "potem kilka krotkich wyborow miedzy dwoma logo.\n\n"
                               f"Uczestnik: {PARTICIPANT}   {mode_label}\n\nSPACJA = dalej")])

    # --- kalibracja (mechanizm z szablonu) ---
    if SIM:
        cal_status = "skipped_simulation"
    else:
        ok = spectrum.calibrate(win, et)
        cal_status = "success" if ok else "accepted_but_failed"

    imgs, img_h, x0 = make_images(win)
    pairs = list(itertools.combinations(STIMULI, 2))            # 6 par
    # preferencja: kazda para raz, polowa par zamieniona stronami
    pref = pairs[:]
    rng.shuffle(pref)
    flips = [i % 2 == 1 for i in range(len(pref))]
    rng.shuffle(flips)
    pref = [(b, a) if f else (a, b) for (a, b), f in zip(pref, flips)]
    # kontrola: N_CONTROL losowych par, losowa strona
    ctrl = rng.sample(pairs, N_CONTROL)
    ctrl = [(b, a) if rng.random() < 0.5 else (a, b) for a, b in ctrl]

    gaze = MouseGaze(win) if SIM else Gaze(et)
    gaze.start()
    if not SIM and not gaze.wait_for_data(timeout=2.0):
        print("[UWAGA] Brak probek z trackera po 2 s.")

    rows, raw, tid = [], [], 0
    for block, (cond, trials) in enumerate((("preference", pref), ("control", ctrl)), start=1):
        wait_space(win, [text(win, INSTR[cond])])
        for left_id, right_id in trials:
            tid += 1
            row, r = run_trial(win, gaze, imgs, x0, tid, block, cond, left_id, right_id)
            row["calibration_status"] = cal_status
            rows.append(row)
            raw += r
    gaze.stop()

    # --- zapis ---
    out = HERE / "data"
    out.mkdir(exist_ok=True)
    stamp = f"{PARTICIPANT}_{datetime.now():%Y%m%d_%H%M%S}"
    mode = "simulation" if SIM else "hardware"
    with open(out / f"trials_{stamp}.csv", "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=["mode"] + list(rows[0]))
        wr.writeheader()
        wr.writerows({"mode": mode, **r} for r in rows)
    with open(out / f"samples_{stamp}.csv", "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=list(raw[0]) if raw else ["trial_id"])
        wr.writeheader()
        wr.writerows(raw)
    summ = summarize(rows, raw)
    cfg = {"participant_id": PARTICIPANT, "software_version": VERSION, "mode": mode, "random_seed": seed,
           "tracker_model": et.model if et else "none (mouse simulation)",
           "tracker_serial": et.serial_number if et else "",
           "tracker_sample_rate": et.get_gaze_output_frequency() if et else "per-frame",
           "sdk": f"tobii_research {getattr(tr, '__version__', '?')}",
           "calibration_status": cal_status, "screen_px": list(win.size), "logo_height_px": round(img_h),
           "aoi_margin_px": AOI_MARGIN, "fixation_cross_ms": FIX_S * 1000, "iti_ms": ITI_S * 1000,
           "binocular_rule": "srednia z waznych oczu (spectrum.binocular_norm)",
           "fixation_detection": "BRAK - liczymy dwell time z probek; algorytm fiksacji DO WERYFIKACJI",
           "stimulus_distance_cm": "DO UZUPELNIENIA",
           "stimuli": {k: str(v.name) for k, v in STIMULI.items()},
           "summary": {c: {k: v for k, v in s.items()} for c, s in summ.items()}}
    with open(out / f"config_{stamp}.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2, default=str)
    print(f"Zapisano: {out / ('trials_' + stamp + '.csv')} (+ samples_, config_)")

    show_results(win, summ, rows, mode_label)
    win.close()
    core.quit()


if __name__ == "__main__":
    main()
