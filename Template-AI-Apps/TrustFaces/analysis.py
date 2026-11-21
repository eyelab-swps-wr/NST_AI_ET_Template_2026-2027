# -*- coding: utf-8 -*-
"""
Detekcja fiksacji (I-VT), przypisanie do AOI i metryki - bez zaleznosci poza biblioteka standardowa.
Fixation detection (I-VT), AOI assignment and per-trial metrics. Standard library only.

Uzycie samodzielne / standalone:   python analysis.py <folder_sesji>
Aplikacja wywoluje run_session_analysis() automatycznie na koncu sesji.

WAZNE: surowe probki NIE sa fiksacjami. Fiksacje powstaja tu z probek algorytmem I-VT
(prog predkosci wg domyslnych ustawien Tobii I-VT; NIE sa to progi EyeLink z artykulu Tatlera).
Parametry sa zapisywane w fixations.csv (detection_parameters) i musza byc potwierdzone pilotazem
na rzeczywistym urzadzeniu.
"""
import csv
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# --- parametry I-VT (wartosci startowe, do potwierdzenia pilotazem) -------------------------
IVT = {
    "velocity_threshold_deg_s": 30.0,   # domyslny prog Tobii I-VT
    "velocity_window_ms": 20.0,         # okno liczenia predkosci
    "gap_fill_max_ms": 75.0,            # interpolacja krotkich luk (utrata sladzenia)
    "merge_max_gap_ms": 75.0,           # laczenie sasiednich fiksacji ...
    "merge_max_angle_deg": 0.5,         # ... o ile leza blisko siebie
    "min_fixation_ms": 60.0,            # krotsze odrzucane
}

AOI_PRIORITY = ("eyes", "lower", "face_other", "background")


# ---------------------------------------------------------------------------------------------
def _angle_deg(dx_px, dy_px, cm_per_px, dist_cm):
    d_cm = math.hypot(dx_px, dy_px) * cm_per_px
    return math.degrees(math.atan2(d_cm, dist_cm))


def binocular(sample):
    """sample: dict z kluczami left/right_gaze_x/y/validity (0..1, (0,0)=lewy gorny). -> (x, y) lub None"""
    pts = []
    for side in ("left", "right"):
        if int(sample[f"{side}_validity"]) == 1:
            x, y = sample[f"{side}_gaze_x"], sample[f"{side}_gaze_y"]
            if x is not None and y is not None and math.isfinite(x) and math.isfinite(y):
                pts.append((x, y))
    if not pts:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def detect_fixations(samples, screen_w, screen_h, cm_per_px, dist_cm, params=IVT):
    """samples: lista dict {t_ms, ...} jednego triala, posortowana. Zwraca liste fiksacji (px ekranu)."""
    if len(samples) < 3:
        return []
    t = [s["t_ms"] for s in samples]
    g = []
    for s in samples:
        b = binocular(s)
        g.append(None if b is None else (b[0] * screen_w, b[1] * screen_h))
    n = len(g)
    # 1) wypelnianie krotkich luk (interpolacja liniowa)
    i = 0
    while i < n:
        if g[i] is None:
            j = i
            while j < n and g[j] is None:
                j += 1
            if i > 0 and j < n and (t[j] - t[i - 1]) <= params["gap_fill_max_ms"]:
                for k in range(i, j):
                    a = (t[k] - t[i - 1]) / (t[j] - t[i - 1])
                    g[k] = (g[i - 1][0] + a * (g[j][0] - g[i - 1][0]),
                            g[i - 1][1] + a * (g[j][1] - g[i - 1][1]))
            i = j
        else:
            i += 1
    # 2) predkosc kolowa (okno ~velocity_window_ms) i klasyfikacja
    dt_med = statistics.median(b - a for a, b in zip(t, t[1:])) or 1.0
    k = max(1, int(round(params["velocity_window_ms"] / dt_med / 2)))
    is_fix = [False] * n
    for i in range(n):
        a, b = max(0, i - k), min(n - 1, i + k)
        if g[a] is None or g[b] is None or g[i] is None or t[b] == t[a]:
            continue
        ang = _angle_deg(g[b][0] - g[a][0], g[b][1] - g[a][1], cm_per_px, dist_cm)
        v = ang / ((t[b] - t[a]) / 1000.0)
        is_fix[i] = v < params["velocity_threshold_deg_s"]
    # 3) grupowanie kolejnych probek fiksacyjnych
    groups, i = [], 0
    while i < n:
        if is_fix[i]:
            j = i
            while j + 1 < n and is_fix[j + 1]:
                j += 1
            groups.append((i, j))
            i = j + 1
        else:
            i += 1

    def centroid(a, b):
        xs = [g[m][0] for m in range(a, b + 1)]
        ys = [g[m][1] for m in range(a, b + 1)]
        return sum(xs) / len(xs), sum(ys) / len(ys)

    # 4) laczenie bliskich fiksacji
    merged = []
    for a, b in groups:
        if merged:
            pa, pb = merged[-1]
            gap = t[a] - t[pb]
            c1, c2 = centroid(pa, pb), centroid(a, b)
            if gap <= params["merge_max_gap_ms"] and \
                    _angle_deg(c2[0] - c1[0], c2[1] - c1[1], cm_per_px, dist_cm) <= params["merge_max_angle_deg"]:
                merged[-1] = (pa, b)
                continue
        merged.append((a, b))
    # 5) odrzucenie zbyt krotkich; czas = od pierwszej do ostatniej probki + 1 okres probkowania
    out = []
    for a, b in merged:
        start, end = t[a], t[b] + dt_med
        if end - start < params["min_fixation_ms"]:
            continue
        cx, cy = centroid(a, b)
        out.append({"start_ms": start, "end_ms": end, "duration_ms": end - start, "x_px": cx, "y_px": cy})
    return out


# ---------------------------------------------------------------------------------------------
def aoi_rects_screen(stim, screen_w, screen_h, scale):
    """AOI z stimuli.json (px obrazu 1536x1024, lewy gorny) -> px ekranu (obraz wysrodkowany, skala `scale`)."""
    cw, ch = 1536, 1024
    ox, oy = screen_w / 2 - cw * scale / 2, screen_h / 2 - ch * scale / 2
    rects = {}
    for name in ("face", "eyes", "lower"):
        l, tp, r, b = stim["mask_or_roi_coordinates"][name]
        rects[name] = (ox + l * scale, oy + tp * scale, ox + r * scale, oy + b * scale)
    return rects


def aoi_of_point(x, y, rects):
    def inside(r):
        return r[0] <= x <= r[2] and r[1] <= y <= r[3]
    if inside(rects["eyes"]):
        return "eyes"
    if inside(rects["lower"]):
        return "lower"
    if inside(rects["face"]):
        return "face_other"
    return "background"


def aoi_areas(rects, screen_w, screen_h):
    def area(r):
        return max(0.0, r[2] - r[0]) * max(0.0, r[3] - r[1])
    face = area(rects["face"])
    eyes, lower = area(rects["eyes"]), area(rects["lower"])
    return {
        "eyes": eyes, "lower": lower, "face": face,
        "face_other": face - eyes - lower,
        "background": screen_w * screen_h - face,
    }


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def run_session_analysis(session_dir, stimuli_json=HERE / "stimuli.json"):
    session_dir = Path(session_dir)
    cfg = json.loads((session_dir / "session_config.json").read_text(encoding="utf-8"))
    stim = {s["stimulus_id"]: s for s in json.loads(Path(stimuli_json).read_text(encoding="utf-8"))["stimuli"]}
    W, H = cfg["screen_width_px"], cfg["screen_height_px"]
    cm_per_px = cfg["screen_width_cm"] / W
    dist = cfg["viewing_distance_cm"]
    scale = cfg["image_scale"]
    trials = _read_csv(session_dir / "trials.csv")

    by_trial = {}
    with open(session_dir / "gaze_samples.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d = {"t_ms": float(r["app_timestamp"])}
            for k in ("left_gaze_x", "left_gaze_y", "right_gaze_x", "right_gaze_y"):
                d[k] = _num(r[k])
            for k in ("left_validity", "right_validity"):
                d[k] = int(r[k])
            by_trial.setdefault(r["trial_id"], []).append(d)

    fix_rows, aoi_rows, fid = [], [], 0
    params_txt = json.dumps(IVT, sort_keys=True)
    for tr in trials:
        tid, sid = tr["trial_id"], tr["stimulus_id"]
        samples = sorted(by_trial.get(tid, []), key=lambda s: s["t_ms"])
        onset = float(tr["presentation_start_ms"])
        rects = aoi_rects_screen(stim[sid], W, H, scale)
        areas = aoi_areas(rects, W, H)
        fixes = detect_fixations(samples, W, H, cm_per_px, dist)
        dt_med = statistics.median(b["t_ms"] - a["t_ms"] for a, b in zip(samples, samples[1:])) if len(samples) > 2 else 0
        valid_time_ms = sum(1 for s in samples if binocular(s) is not None) * dt_med
        acc = {a: {"dur": 0.0, "n": 0, "ttff": None} for a in AOI_PRIORITY}
        for fx in fixes:
            fid += 1
            name = aoi_of_point(fx["x_px"], fx["y_px"], rects)
            fix_rows.append({
                "fixation_id": fid, "participant_id": tr["participant_id"], "trial_id": tid,
                "start_timestamp": round(fx["start_ms"], 2), "end_timestamp": round(fx["end_ms"], 2),
                "duration_ms": round(fx["duration_ms"], 2),
                "fixation_x": round(fx["x_px"], 1), "fixation_y": round(fx["y_px"], 1),
                "aoi_name": name, "eye": "binocular_mean",
                "detection_algorithm": "I-VT", "detection_parameters": params_txt,
            })
            a = acc[name]
            a["dur"] += fx["duration_ms"]
            a["n"] += 1
            ttff = fx["start_ms"] - onset
            if a["ttff"] is None or ttff < a["ttff"]:
                a["ttff"] = ttff
        # AOI zbiorcze: 'face' = eyes + lower + face_other
        acc["face"] = {
            "dur": sum(acc[k]["dur"] for k in ("eyes", "lower", "face_other")),
            "n": sum(acc[k]["n"] for k in ("eyes", "lower", "face_other")),
            "ttff": min([acc[k]["ttff"] for k in ("eyes", "lower", "face_other") if acc[k]["ttff"] is not None], default=None),
        }
        for name in ("eyes", "lower", "face", "face_other", "background"):
            a = acc[name]
            aoi_rows.append({
                "participant_id": tr["participant_id"], "trial_id": tid, "stimulus_id": sid,
                "stimulus_category": tr["stimulus_category"], "aoi_name": name,
                "total_fixation_duration_ms": round(a["dur"], 1),
                "fixation_count": a["n"],
                "time_to_first_fixation_ms": "" if a["ttff"] is None else round(a["ttff"], 1),
                "aoi_area_px2": round(areas[name]),
                "duration_ms_per_100k_px2": round(a["dur"] / areas[name] * 1e5, 3) if areas[name] > 0 else "",
                "share_of_valid_time": round(a["dur"] / valid_time_ms, 4) if valid_time_ms > 0 else "",
                "valid_gaze_ratio": tr["valid_gaze_ratio"], "invalid_reason": tr["invalid_reason"],
                "excluded": 1 if tr["invalid_reason"] else 0,
            })

    def write(name, rows, fields):
        with open(session_dir / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    fix_fields = ["fixation_id", "participant_id", "trial_id", "start_timestamp", "end_timestamp", "duration_ms",
                  "fixation_x", "fixation_y", "aoi_name", "eye", "detection_algorithm", "detection_parameters"]
    aoi_fields = ["participant_id", "trial_id", "stimulus_id", "stimulus_category", "aoi_name",
                  "total_fixation_duration_ms", "fixation_count", "time_to_first_fixation_ms", "aoi_area_px2",
                  "duration_ms_per_100k_px2", "share_of_valid_time", "valid_gaze_ratio", "invalid_reason", "excluded"]
    write("fixations.csv", fix_rows, fix_fields)
    write("aoi_metrics.csv", aoi_rows, aoi_fields)

    # raport jakosci
    ratios = [_num(t["valid_gaze_ratio"]) for t in trials if _num(t["valid_gaze_ratio"]) is not None]
    excl = [t for t in trials if t["invalid_reason"]]
    lines = [
        f"Raport jakosci danych - uczestnik {cfg['participant_id']}, sesja {cfg['session_id']}",
        f"Tryb: {cfg['run_mode']} | tracker: {cfg['tracker_model']} | czestotliwosc: {cfg['sampling_frequency']} Hz",
        f"Kalibracja: {cfg['calibration_status']} | walidacja: sredni blad {cfg.get('validation_mean_error_deg')} deg "
        f"(prog {cfg['validation_mean_max_deg']} deg)",
        f"Proby: {len(trials)}; wykluczone: {len(excl)}",
        f"valid_gaze_ratio: min {min(ratios):.2f}, mediana {statistics.median(ratios):.2f}, max {max(ratios):.2f}" if ratios else "brak prob",
        f"Fiksacje: {len(fix_rows)} (I-VT, parametry w fixations.csv)",
    ]
    for t in excl:
        lines.append(f"  wykluczona {t['trial_id']} ({t['stimulus_id']}): {t['invalid_reason']}")
    if cfg["run_mode"] != "TOBII":
        lines.append("UWAGA: dane NIE pochodza z eye-trackera (symulacja) - nie nadaja sie do analizy badawczej.")
    (session_dir / "quality_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(fix_rows), len(aoi_rows)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uzycie: python analysis.py <folder_sesji>")
    print("fiksacje: %d, wiersze AOI: %d" % run_session_analysis(sys.argv[1]))
