#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PROJEKT 1 - WPLYW KONTROWERSYJNEJ WYPOWIEDZI NA SLEDZENIE WZROKU (badanie wlasne)

Sesja (wg projekt-1-brief.md):
  kod uczestnika -> zgoda -> losowy przydzial 1:1 (kontrolna / eksperymentalna)
  -> instruktaz warunku (badacz mowi na glos) -> kalibracja Tobii
  -> 5 prob: kropka na bialym tle po torze nieskonczonosci, ruch PLYNNY albo SKOKOWY
     (kolejnosc losowana z seedem) -> zapis danych -> wynik.
W kazdej probie jest okno PRZESZKADZANIA: kropka zmienia kolor na czerwony (sygnal dla badacza).
Zmiana koloru wystepuje w OBU grupach (identyczny bodziec); grupy roznia sie tym, co mowi badacz.

Polaczenie i kalibracja: wspolny ../spectrum.py z AI Template App (tobii-research 2.1.0).
Brief celuje w Tobii X120 - zgodnosc X120 z tym SDK jest DO WERYFIKACJI na stanowisku.
Brak trackera = koniec z komunikatem (brak symulacji, zgodnie z briefem).
ESC = przerwanie w kazdej chwili (dane czesciowe sa zapisywane).
"""
import csv
import json
import math
import random
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from psychopy import core, event, logging, visual
logging.console.setLevel(logging.ERROR)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # wspolny ../spectrum.py z szablonu
import tobii_research as tr
import spectrum

# --- parametry: wszystkie DO WERYFIKACJI w pilotazu (brief ich nie ustala) -----
N_TRIALS = 5             # liczba prezentacji kropki
DURATION_S = 10.0        # czas jednej prezentacji
SPEED_PX_S = 300.0       # stala predkosc kropki
DOT_RADIUS_PX = 12       # rozmiar kropki
AOI_RADIUS_PX = 80       # promien dynamicznego AOI kropki
TRACK_LOSS_S = 1.0       # brak waznego wzroku dluzej = utrata trackingu
FIX_DISPERSION_PX = 60   # I-DT: maks. rozrzut (x+y) w fiksacji
FIX_MIN_MS = 100         # I-DT: minimalny czas fiksacji
JUMP_INTERVAL_S = 0.8    # ruch skokowy: co ile sekund kropka przeskakuje
JUMP_STEPS = 12          # ruch skokowy: liczba pozycji na torze (rowne odstepy)
DISTURB_LEN_S = 3.0      # dlugosc okna przeszkadzania w kazdej probie
DISTURB_MIN_START_S = 2.0  # najwczesniejszy start okna (start losowany z seedem)
DOT_COLOR = "black"
DISTURB_COLOR = "red"    # kolor kropki w oknie przeszkadzania
MOTIONS = ("plynny", "skokowy")
FONT = "Arial"
GROUPS = ("kontrolna", "eksperymentalna")


class Gaze(spectrum.GazeStream):
    """Strumien z szablonu + surowe probki: (ts_us, valid_left, valid_right, x, y) w px."""
    def __init__(self, et, win):
        super().__init__(et)
        self.w, self.h = win.size
        self.samples = []

    def on_sample(self, d, g):
        x, y = ((g[0] - 0.5) * self.w, (0.5 - g[1]) * self.h) if g else (None, None)
        self.samples.append((d["system_time_stamp"], int(d["left_gaze_point_validity"]),
                             int(d["right_gaze_point_validity"]), x, y))


def text(win, msg, color="black", height=30, pos=(0, 0)):
    return visual.TextStim(win, text=msg, color=color, height=height, pos=pos, font=FONT,
                           wrapWidth=win.size[0] * 0.8)


def show(win, msg, keys=("space",)):
    text(win, msg, height=24 if msg.count("\n") > 12 else 30).draw()
    win.flip()
    return event.waitKeys(keyList=list(keys))[0]


def ask_id(win):
    pid = ""
    while True:
        text(win, "Kod pseudonimowy uczestnika (bez imienia), ENTER = dalej\n\n" + (pid or "_")).draw()
        win.flip()
        for k in event.waitKeys():
            if k == "return" and pid:
                return pid
            if k == "backspace":
                pid = pid[:-1]
            elif len(k) == 1 and k.isalnum() and len(pid) < 12:
                pid += k.upper()


def assign_group(data_dir, rng):
    """1:1 - grupa z mniejsza liczba zakonczonych sesji; remis = losowanie."""
    counts = {g: 0 for g in GROUPS}
    for f in data_dir.glob("*/session.json"):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            if s.get("status") == "completed":
                counts[s["group_condition"]] += 1
        except Exception:
            pass
    low = min(counts.values())
    return rng.choice([g for g in GROUPS if counts[g] == low]), counts


def infinity_path(win):
    """Lemniskata Bernoulliego, parametryzowana dlugoscia luku -> stala predkosc."""
    a = min(win.size[0] * 0.40, win.size[1] * 0.70)
    t = np.linspace(0, 2 * np.pi, 4000)
    den = 1 + np.sin(t) ** 2
    xs, ys = a * np.cos(t) / den, a * np.sin(t) * np.cos(t) / den
    s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(xs), np.diff(ys)))])
    return xs, ys, s


def dot_position(path, elapsed_s, motion):
    """plynny: stala predkosc po torze; skokowy: przeskok o 1/JUMP_STEPS toru co JUMP_INTERVAL_S."""
    xs, ys, s = path
    if motion == "skokowy":
        d = (int(elapsed_s / JUMP_INTERVAL_S) % JUMP_STEPS) * s[-1] / JUMP_STEPS
    else:
        d = (SPEED_PX_S * elapsed_s) % s[-1]
    return float(np.interp(d, s, xs)), float(np.interp(d, s, ys))


def present_dot(win, gaze, path, motion, disturb):
    """Jedna prezentacja kropki. disturb = (od_s, do_s) okna przeszkadzania.
    Zwraca (status, start_us, end_us, lista (ts_us, tx, ty, w_oknie 0/1))."""
    dot = visual.Circle(win, radius=DOT_RADIUS_PX, fillColor=DOT_COLOR, lineColor=None)
    targets = []
    clock = core.Clock()
    start_us = tr.get_system_time_stamp()
    lost_since = None
    status = "ok"
    while clock.getTime() < DURATION_S:
        el = clock.getTime()
        tx, ty = dot_position(path, el, motion)
        dis = int(disturb[0] <= el < disturb[1])
        dot.fillColor = DISTURB_COLOR if dis else DOT_COLOR
        dot.pos = (tx, ty)
        dot.draw()
        win.flip()
        targets.append((tr.get_system_time_stamp(), tx, ty, dis))
        if gaze.latest_norm() is None:
            lost_since = lost_since if lost_since is not None else clock.getTime()
            if clock.getTime() - lost_since > TRACK_LOSS_S:
                status = "tracking_lost"
                break
        else:
            lost_since = None
    return status, start_us, tr.get_system_time_stamp(), targets


def detect_fixations(samples):
    """I-DT na waznych probkach (probki != fiksacje). Zwraca liste (start_us, end_us, x, y)."""
    pts = [s for s in samples if s[3] is not None]
    fixes, i = [], 0
    while i < len(pts):
        j = i
        while j + 1 < len(pts):
            win = pts[i:j + 2]
            xs, ys = [p[3] for p in win], [p[4] for p in win]
            if (max(xs) - min(xs)) + (max(ys) - min(ys)) > FIX_DISPERSION_PX or pts[j + 1][0] - pts[j][0] > 100_000:
                break
            j += 1
        if (pts[j][0] - pts[i][0]) / 1000 >= FIX_MIN_MS:
            seg = pts[i:j + 1]
            fixes.append((seg[0][0], seg[-1][0], sum(p[3] for p in seg) / len(seg), sum(p[4] for p in seg) / len(seg)))
            i = j + 1
        else:
            i += 1
    return fixes


def target_at(targets, ts):
    """Klatka ekranu najblizsza w czasie: (tx, ty, w_oknie_przeszkadzania)."""
    k = int(np.searchsorted([t[0] for t in targets], ts).clip(0, len(targets) - 1))
    return targets[k][1], targets[k][2], targets[k][3]


def analyse(samples, targets, start_us, end_us):
    samples = [s for s in samples if start_us <= s[0] <= end_us]
    fixes = detect_fixations(samples)
    rows = []
    for n, (fs, fe, fx, fy) in enumerate(fixes, 1):
        tx, ty, dis = target_at(targets, (fs + fe) // 2)
        dist = math.hypot(fx - tx, fy - ty)
        rows.append({"fixation_id": n, "fixation_start_us": fs, "fixation_end_us": fe,
                     "fixation_duration_ms": round((fe - fs) / 1000, 1), "fix_x": round(fx, 1),
                     "fix_y": round(fy, 1), "target_x": round(tx, 1), "target_y": round(ty, 1),
                     "distance_to_dot_px": round(dist, 1), "aoi": "kropka" if dist <= AOI_RADIUS_PX else "poza",
                     "phase": "przeszkadzanie" if dis else "bez_przeszkadzania"})
    valid = [s for s in samples if s[3] is not None]
    summ = {**stats(rows), "n_samples": len(samples),
            "valid_sample_pct": round(100 * len(valid) / len(samples), 1) if samples else 0}
    return rows, summ


def stats(rows):
    """Miary fiksacji dla dowolnego podzbioru wierszy fixations."""
    return {
        "fixation_count": len(rows),
        "fixation_count_dot": sum(r["aoi"] == "kropka" for r in rows),
        "fixation_count_outside": sum(r["aoi"] == "poza" for r in rows),
        "pct_fixations_outside": round(100 * sum(r["aoi"] == "poza" for r in rows) / len(rows), 1) if rows else None,
        "mean_fixation_duration_ms": round(sum(r["fixation_duration_ms"] for r in rows) / len(rows), 1) if rows else None,
        "mean_fixation_distance_px": round(sum(r["distance_to_dot_px"] for r in rows) / len(rows), 1) if rows else None,
    }


def _jsonable(o):
    """numpy -> zwykle typy Pythona (wczesniej win.size wywalal zapis session.json)."""
    return o.tolist() if hasattr(o, "tolist") else str(o)


def save(folder, meta, samples, targets, fix_rows):
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "samples.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["participant_id", "group_condition", "trial_id", "gaze_timestamp_us", "validity_left",
                     "validity_right", "gaze_x", "gaze_y", "target_x", "target_y", "distance_to_dot_px",
                     "motion", "phase"])
        for trial_id, (smp, tg, motion) in samples.items():
            for ts, vl, vr, x, y in smp:
                tx, ty, dis = target_at(tg, ts) if tg else (None, None, None)
                d = round(math.hypot(x - tx, y - ty), 1) if x is not None and tx is not None else ""
                wr.writerow([meta["participant_id"], meta["group_condition"], trial_id, ts, vl, vr,
                             "" if x is None else round(x, 1), "" if y is None else round(y, 1),
                             "" if tx is None else round(tx, 1), "" if ty is None else round(ty, 1), d, motion,
                             "" if dis is None else ("przeszkadzanie" if dis else "bez_przeszkadzania")])
    if fix_rows:
        with open(folder / "fixations.csv", "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=list(fix_rows[0]))
            wr.writeheader()
            wr.writerows(fix_rows)
    (folder / "session.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=_jsonable), encoding="utf-8")
    print(f"[PROJEKT 1] Zapisano: {folder}")


def main():
    found = spectrum.find_all_eyetrackers()
    if not found:
        print("[PROJEKT 1] Nie znaleziono eye-trackera Tobii - koniec (brak trybu symulacji).")
        return
    et = found[0]
    print(f"[PROJEKT 1] Tracker: {et.model} {et.serial_number}")

    win = visual.Window(fullscr=True, color="white", units="pix")
    win.mouseVisible = False
    spectrum.install_escape(win)

    data_dir = HERE / "data"
    pid = ask_id(win)
    seed = random.randrange(10 ** 6)
    group, counts = assign_group(data_dir, random.Random(seed))
    folder = data_dir / f"{pid}_{datetime.now():%Y%m%d_%H%M%S}"
    meta = {"participant_id": pid, "group_condition": group, "randomization_seed": seed,
            "groups_before": counts, "tracker": f"{et.model} {et.serial_number}",
            "screen_px": [int(v) for v in win.size], "started": datetime.now().isoformat(timespec="seconds"),
            "parameters": {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float, str))},
            "fixation_algorithm": "I-DT (uproszczony) - DO WERYFIKACJI wg dokumentacji SDK",
            "calibrations": [], "trials": [], "status": "running"}
    samples, all_fix = {}, []
    # plan prob: ruch plynny/skokowy na zmiane, kolejnosc i start okna przeszkadzania losowane z seedem
    rng = random.Random(seed)
    motions = [MOTIONS[i % 2] for i in range(N_TRIALS)]
    rng.shuffle(motions)
    plan = []
    for n, m in enumerate(motions, 1):
        d0 = round(rng.uniform(DISTURB_MIN_START_S, DURATION_S - DISTURB_LEN_S - 1.0), 2)
        plan.append({"trial_id": f"t{n:02d}", "motion": m, "disturb_start_s": d0,
                     "disturb_end_s": round(d0 + DISTURB_LEN_S, 2)})
    meta["trial_plan"] = plan

    def on_esc():  # ESC: zapisz to, co jest
        meta["status"] = "aborted"
        save(folder, meta, samples, {}, all_fix)
    spectrum.on_abort(on_esc)

    show(win, "INFORMACJA I ZGODA\n\nPodczas zadania rejestrowany jest ruch Twoich oczu.\n"
              "Dane sa zapisywane pod kodem, bez imienia i nazwiska.\n"
              "Mozesz przerwac w kazdej chwili bez konsekwencji.\n\nT = zgadzam sie", keys=("t",))

    # Ekran dla badacza: instruktaz warunku (tresc opinii NIE jest w aplikacji - zatwierdzony zestaw zespolu)
    if group == "eksperymentalna":
        msg = ("[BADACZ] Grupa: EKSPERYMENTALNA\n\nWypowiedz spokojnie zatwierdzony zestaw opinii,\n"
               "potem instrukcje: \"Sledz kropke wzrokiem przez caly czas prezentacji.\"\n\n"
               "Gdy kropka zrobi sie CZERWONA - przeszkadzaj: wypowiadaj kontrowersyjna opinie,\n"
               "az kropka znow bedzie czarna.")
    else:
        msg = ("[BADACZ] Grupa: KONTROLNA\n\nPowiedz instrukcje:\n"
               "\"Sledz kropke wzrokiem przez caly czas prezentacji.\"\n\n"
               "Gdy kropka zrobi sie CZERWONA - wypowiadaj neutralna wypowiedz kontrolna\n"
               "(DO USTALENIA przez zespol), az kropka znow bedzie czarna.")
    show(win, msg + "\n\nSPACJA = dalej (kalibracja)")

    def calibrate():
        ok = spectrum.calibrate(win, et, points=spectrum.CAL_POINTS_9)
        while not ok:
            meta["calibrations"].append("failed")
            show(win, "Kalibracja nieudana.\n\nSPACJA = powtorz")
            ok = spectrum.calibrate(win, et, points=spectrum.CAL_POINTS_9)
        meta["calibrations"].append("ok")

    calibrate()
    path = infinity_path(win)
    gaze = Gaze(et, win)
    show(win, f"Sledz kropke wzrokiem przez caly czas prezentacji.\n"
              f"Kropka bedzie poruszac sie plynnie albo przeskakiwac.\n\n"
              f"Bedzie {N_TRIALS} krotkich prezentacji.\n\nSPACJA = start")

    def run_one(trial_id, p):
        gaze.samples = []
        gaze.start()
        gaze.wait_for_data()
        status, t0, t1, targets = present_dot(win, gaze, path, p["motion"],
                                              (p["disturb_start_s"], p["disturb_end_s"]))
        gaze.stop()
        samples[trial_id] = (list(gaze.samples), targets, p["motion"])
        fix_rows, summ = analyse(gaze.samples, targets, t0, t1)
        for r in fix_rows:
            r.update(participant_id=pid, group_condition=group, trial_id=trial_id, motion=p["motion"],
                     included=int(status == "ok"))
        all_fix.extend(fix_rows)
        meta["trials"].append({**p, "trial_id": trial_id, "trial_start_us": t0, "trial_end_us": t1,
                               "tracking_status": status, "calibration_status": meta["calibrations"][-1],
                               "exclusion_reason": "" if status == "ok" else status, **summ})
        return status

    for n, p in enumerate(plan, 1):
        if run_one(p["trial_id"], p) != "ok":  # utrata trackingu: kalibracja i jedno powtorzenie
            show(win, "Utracono sygnal wzroku.\n\nPonowna kalibracja i powtorzenie prezentacji.\n\nSPACJA = dalej")
            calibrate()
            run_one(p["trial_id"] + "_r", p)
        if n < N_TRIALS:
            core.wait(1.0)  # krotka pauza na bialym ekranie miedzy prezentacjami

    spectrum.remove_on_abort(on_esc)
    ok_fix = [r for r in all_fix if r["included"]]
    ok_trials = [t for t in meta["trials"] if t["tracking_status"] == "ok"]
    result = None
    if ok_fix:
        result = {
            "trials_ok": len(ok_trials),
            "valid_sample_pct": round(sum(t["valid_sample_pct"] for t in ok_trials) / len(ok_trials), 1),
            "fixation_count": len(ok_fix),
            "fixation_count_dot": sum(r["aoi"] == "kropka" for r in ok_fix),
            "fixation_count_outside": sum(r["aoi"] == "poza" for r in ok_fix),
            "pct_fixations_outside": round(100 * sum(r["aoi"] == "poza" for r in ok_fix) / len(ok_fix), 1),
            "mean_fixation_duration_ms": round(sum(r["fixation_duration_ms"] for r in ok_fix) / len(ok_fix), 1),
            "mean_fixation_distance_px": round(sum(r["distance_to_dot_px"] for r in ok_fix) / len(ok_fix), 1),
        }
    if result:
        result["by_motion_phase"] = {
            f"{m}/{ph}": stats([r for r in ok_fix if r["motion"] == m and r["phase"] == ph])
            for m in MOTIONS for ph in ("bez_przeszkadzania", "przeszkadzanie")}
    meta["summary"] = result
    meta["status"] = "completed" if result else "excluded_tracking_lost"
    meta["ended"] = datetime.now().isoformat(timespec="seconds")
    save(folder, meta, samples, {}, all_fix)

    if result:
        res = (f"Udane prezentacje: {result['trials_ok']}/{N_TRIALS}\n"
               f"Liczba fiksacji: {result['fixation_count']}  (na kropce {result['fixation_count_dot']}, "
               f"poza {result['fixation_count_outside']})\n"
               f"Fiksacje poza kropka: {result['pct_fixations_outside']}%\n"
               f"Sredni czas fiksacji: {result['mean_fixation_duration_ms']} ms\n"
               f"Srednia odleglosc fiksacji od kropki: {result['mean_fixation_distance_px']} px\n"
               f"Wazne probki: {result['valid_sample_pct']}%\n\n"
               "Odleglosc fiksacji od kropki [px] / % fiksacji poza kropka:\n" +
               "\n".join(f"{k}: {v['mean_fixation_distance_px']} / {v['pct_fixations_outside']}%"
                         for k, v in result["by_motion_phase"].items()))
    else:
        res = "Brak udanych prezentacji (utrata sygnalu) - sesja wykluczona."
    show(win, f"Dziekujemy - to koniec badania.\n\n[BADACZ] Grupa: {group}\n\n{res}\n\n"
              "Pojedyncza sesja nie pozwala porownac grup.\n\nSPACJA = koniec")
    win.close()
    core.quit()


if __name__ == "__main__":
    main()
