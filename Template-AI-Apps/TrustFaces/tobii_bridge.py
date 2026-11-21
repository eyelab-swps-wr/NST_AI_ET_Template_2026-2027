# -*- coding: utf-8 -*-
"""
Lokalny most Tobii <-> przegladarka dla web/index.html
======================================================
Przegladarka nie ma dostepu do eye-trackera. Ten program (tylko biblioteka standardowa + opcjonalnie
tobii_research) laczy sie z trackerem przez Tobii Pro SDK, wystawia maly API HTTP wylacznie na
127.0.0.1 i zapisuje dane w TYM SAMYM formacie co wersja PsychoPy (trials/gaze_samples/fixations/aoi_metrics).

Uruchomienie:   python tobii_bridge.py            (prawdziwy tracker)
                python tobii_bridge.py --sim      (dane syntetyczne, bez urzadzenia - TYLKO test)
                python tobii_bridge.py --no-browser --port 8765

STATUS: NIE przetestowano z rzeczywistym eye-trackerem. Nie zakladaj, ze Tobii Pro SDK (tobii_research)
obsluguje Tobii X120 - sprawdz na stanowisku (patrz README). Brak trackera => most konczy sie bledem,
a NIE przelacza sie po cichu na symulacje (symulacja tylko jawnie: --sim).
"""
import atexit
import csv
import hashlib
import json
import math
import os
import random
import re
import statistics
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analysis  # noqa: E402

try:
    import tobii_research as tr
except Exception as exc:  # noqa: BLE001
    tr = None
    TOBII_IMPORT_ERROR = repr(exc)
else:
    TOBII_IMPORT_ERROR = None

# ---- parametry zgodne z trust_faces_experiment.py (zmieniaj w obu miejscach naraz) ---------------------
PRESENT_S = 3.0
VALID_RATIO_MIN = 0.60
MAX_SAME_CATEGORY_RUN = 2
VAL_MEAN_MAX_DEG = 1.0
VAL_POINT_MAX_DEG = 1.5
VAL_MIN_SAMPLES = 10
VAL_SKIP_S = 0.6
PORT = 8765

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
STIMULI = json.loads((HERE / "stimuli.json").read_text(encoding="utf-8"))["stimuli"]
STIM_IDS = {s["stimulus_id"] for s in STIMULI}
STIM_BY_ID = {s["stimulus_id"]: s for s in STIMULI}
HASHES = {s["stimulus_id"]: hashlib.sha256((HERE / s["filename"]).read_bytes()).hexdigest() for s in STIMULI}

SIM = "--sim" in sys.argv
LOCK = threading.RLock()


# =============================================================================
# Losowanie (identyczne jak w wersji PsychoPy)
# =============================================================================
def derive_seed(pid, sid):
    return int(hashlib.sha256(f"{pid}|{sid}".encode()).hexdigest()[:8], 16)


def make_order(seed):
    rng = random.Random(seed)
    real = [s for s in STIMULI if s["category"] == "REAL"]
    ai = [s for s in STIMULI if s["category"] == "AI"]
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
        real = [s for s in STIMULI if s["category"] == "REAL"]
        ai = [s for s in STIMULI if s["category"] == "AI"]
    raise RuntimeError("losowanie nie spelnilo ograniczen")


# =============================================================================
# Zrodlo spojrzenia: Tobii albo symulacja
# =============================================================================
class Gaze:
    """samples: (perf_s, device_us, lx, ly, lv, rx, ry, rv); 0..1, (0,0)=lewy gorny rog obszaru obrazu."""

    def __init__(self):
        self.samples = []
        self.lock = threading.Lock()
        self.et = None
        self.model = "SIMULATION (synthetic, no eye tracker)" if SIM else "?"
        self.freq = 120.0
        self.cal = None
        self.active = False
        self._sim_thread = None
        self._sim_stop = threading.Event()

    # --- polaczenie -----------------------------------------------------------------------------
    def connect(self):
        if SIM:
            return
        if tr is None:
            sys.exit(f"Brak biblioteki tobii_research ({TOBII_IMPORT_ERROR}).\n"
                     "Zainstaluj ja w srodowisku z ..\\setup_bundle.bat albo uruchom z --sim (tylko test).")
        try:
            import spectrum  # wspolny modul: Spectrum pierwszy + czestotliwosc
            trackers = spectrum.find_all_eyetrackers()
        except Exception:  # noqa: BLE001
            trackers = list(tr.find_all_eyetrackers())
        if not trackers:
            sys.exit("Nie znaleziono eye-trackera (Tobii Pro Eye Tracker Manager uruchomiony? Kabel?). "
                     "Most NIE przechodzi na symulacje; uzyj --sim, aby jawnie przetestowac bez urzadzenia.")
        self.et = trackers[0]
        self.model = f"{self.et.model} (serial {self.et.serial_number})"
        try:
            self.freq = float(self.et.get_gaze_output_frequency())
        except Exception:  # noqa: BLE001
            self.freq = float("nan")
        print(f"[BRIDGE] Tracker: {self.model} | {self.freq} Hz | {self.et.address}")

    # --- strumien ---------------------------------------------------------------------------------
    def _on_gaze(self, d):  # watek SDK - tylko lekki zapis
        def eye(side):
            x, y = d[f"{side}_gaze_point_on_display_area"]
            ok = bool(d[f"{side}_gaze_point_validity"]) and math.isfinite(x) and math.isfinite(y)
            return (x, y, 1) if ok else (float("nan"), float("nan"), 0)
        lx, ly, lv = eye("left")
        rx, ry, rv = eye("right")
        perf = time.perf_counter() - (tr.get_system_time_stamp() - d["system_time_stamp"]) / 1e6
        with self.lock:
            self.samples.append((perf, d["device_time_stamp"], lx, ly, lv, rx, ry, rv))

    def start(self):
        if self.active:
            return
        self.active = True
        if SIM:
            self._sim_stop.clear()
            self._sim_thread = threading.Thread(target=self._sim_loop, daemon=True)
            self._sim_thread.start()
        else:
            self.et.subscribe_to(tr.EYETRACKER_GAZE_DATA, self._on_gaze, as_dictionary=True)

    def stop(self):
        if not self.active:
            return
        self.active = False
        if SIM:
            self._sim_stop.set()
        else:
            try:
                self.et.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self._on_gaze)
            except Exception:  # noqa: BLE001
                pass

    def _sim_loop(self):  # syntetyczny "wzrok": sakady miedzy oczami / ustami, 120 Hz
        rng = random.Random(1)
        tgt, next_t = (0.5, 0.5), 0.0
        period = 1 / 120
        due = time.perf_counter()
        while not self._sim_stop.is_set():
            t = time.perf_counter()
            if t < due:                      # sleep() na Windows ma ~15 ms ziarnistosci - czekamy krotkimi krokami
                time.sleep(0.0005)
                continue
            due += period
            if t > next_t:
                tgt = (rng.choice([0.44, 0.5, 0.56]), rng.choice([0.40, 0.46, 0.64, 0.5]))
                next_t = t + 0.35
            x, y = tgt[0] + rng.gauss(0, 0.002), tgt[1] + rng.gauss(0, 0.002)
            row = (t, int(t * 1e6), x, y, 1, x, y, 1) if rng.random() > 0.02 else \
                (t, int(t * 1e6), float("nan"), float("nan"), 0, float("nan"), float("nan"), 0)
            with self.lock:
                self.samples.append(row)

    def take_window(self, t0, t1):
        with self.lock:
            win = [s for s in self.samples if t0 <= s[0] <= t1]
            self.samples = [s for s in self.samples if s[0] > t1 - 0.0]  # starsze niz koniec okna nie beda potrzebne
        return win

    def peek_window(self, t0, t1):
        with self.lock:
            return [s for s in self.samples if t0 <= s[0] <= t1]

    # --- kalibracja ---------------------------------------------------------------------------------
    def cal_enter(self):
        if SIM:
            return
        self.stop()
        self.cal = tr.ScreenBasedCalibration(self.et)
        self.cal.enter_calibration_mode()

    def cal_collect(self, x, y):
        if SIM:
            time.sleep(0.3)
            return True
        status = self.cal.collect_data(x, y)
        return status in (tr.CALIBRATION_STATUS_SUCCESS, tr.CALIBRATION_STATUS_SUCCESS_LEFT_EYE,
                          tr.CALIBRATION_STATUS_SUCCESS_RIGHT_EYE)

    def cal_compute(self):
        if SIM:
            return {"ok": True, "status": "SIMULATED", "points": []}
        result = self.cal.compute_and_apply()
        ok = result.status in (tr.CALIBRATION_STATUS_SUCCESS, tr.CALIBRATION_STATUS_SUCCESS_LEFT_EYE,
                               tr.CALIBRATION_STATUS_SUCCESS_RIGHT_EYE)
        pts = []
        for cp in result.calibration_points:
            tx, ty = cp.position_on_display_area
            samples = []
            for smp in cp.calibration_samples:
                for eye in (smp.left_eye, smp.right_eye):
                    if eye.validity == tr.VALIDITY_VALID_AND_USED:
                        samples.append(list(eye.position_on_display_area))
            pts.append({"x": tx, "y": ty, "samples": samples})
        return {"ok": ok, "status": str(result.status), "points": pts}

    def cal_leave(self):
        if SIM or self.cal is None:
            return
        try:
            self.cal.leave_calibration_mode()
        finally:
            self.cal = None

    def shutdown(self):
        self.stop()
        try:
            self.cal_leave()
        except Exception:  # noqa: BLE001
            pass


GAZE = Gaze()
S = {}   # biezaca sesja


def append_csv(path, fields, rows):
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)
        f.flush()
        os.fsync(f.fileno())


def save_cfg():
    (S["dir"] / "session_config.json").write_text(json.dumps(S["cfg"], indent=2, ensure_ascii=False), encoding="utf-8")


def log_event(name, **kw):
    if "dir" in S:
        with open(S["dir"] / "events.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({"t_ms": round((time.perf_counter() - S["t0"]) * 1000, 2), "event": name, **kw},
                               ensure_ascii=False) + "\n")


# =============================================================================
# Endpointy
# =============================================================================
def clean_id(v, default=""):
    v = "".join(c for c in str(v) if c.isalnum() or c in "_-")[:32]
    return v or default


def api_status(_):
    return {"mode": "SIMULATION_SYNTHETIC" if SIM else "TOBII", "tracker_model": GAZE.model,
            "frequency_hz": None if GAZE.freq != GAZE.freq else GAZE.freq,
            "validation": {"mean_max_deg": VAL_MEAN_MAX_DEG, "point_max_deg": VAL_POINT_MAX_DEG,
                           "min_samples": VAL_MIN_SAMPLES, "skip_s": VAL_SKIP_S},
            "present_s": PRESENT_S, "stimuli": sorted(STIM_IDS)}


def api_sync(b):  # estymacja przesuniecia zegara przegladarki wzgledem zegara mostu
    return {"bridge_ms": time.perf_counter() * 1000.0}


def api_session_start(b):
    with LOCK:
        pid = clean_id(b.get("participant_id"))
        if not pid:
            raise ValueError("pusty kod uczestnika")
        c = b.get("consent", {})
        if not (c.get("written") and c.get("adult") and c.get("vision")):
            raise ValueError("brak zgody / pelnoletnosci / widzenia")
        sid = clean_id(b.get("session_id"), "1")
        seed = int(b["seed"]) if str(b.get("seed", "")).strip() else derive_seed(pid, sid)
        mode = "SIMULATION_SYNTHETIC" if SIM else "TOBII"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        d = HERE / "data" / f"{pid}_S{sid}_{stamp}_HTML{'_SIM' if SIM else ''}"
        d.mkdir(parents=True, exist_ok=True)
        S.clear()
        S.update(dir=d, t0=time.perf_counter(), pid=pid, sid=sid, seed=seed, mode=mode, offset_ms=0.0,
                 cal_status="NOT_RUN", val_mean=None, recal=0, finished=False)
        S["cfg"] = {
            "participant_id": pid, "session_id": sid, "random_seed": seed, "run_mode": mode, "frontend": "html+bridge",
            "tracker_model": GAZE.model, "sampling_frequency": GAZE.freq, "calibration_status": "NOT_RUN",
            "validation_mean_error_deg": None, "validation_mean_max_deg": VAL_MEAN_MAX_DEG,
            "validation_point_max_deg": VAL_POINT_MAX_DEG,
            "screen_width_px": int(b["screen_width_px"]), "screen_height_px": int(b["screen_height_px"]),
            "screen_width_cm": float(b["screen_width_cm"]), "viewing_distance_cm": float(b["viewing_distance_cm"]),
            "image_scale": float(b["image_scale"]), "device_pixel_ratio": b.get("device_pixel_ratio"),
            "present_s": PRESENT_S, "valid_ratio_min": VALID_RATIO_MIN, "autotest": bool(b.get("autotest")),
            "fullscreen": bool(b.get("fullscreen")), "user_agent": str(b.get("user_agent", ""))[:200],
            "started": stamp, "analysis_ivt_parameters": analysis.IVT,
            "note": "Gaze x/y = znormalizowane wspolrzedne obszaru obrazu (0..1, (0,0)=lewy gorny). "
                    "Piksele = CSS px okna przegladarki w pelnym ekranie; zakladamy, ze okno pokrywa obszar obrazu trackera.",
        }
        save_cfg()
        order = make_order(seed)
        (d / "trial_order.json").write_text(json.dumps({"stimuli": [{"stimulus_id": s["stimulus_id"], "category": s["category"]}
                                                                    for s in order]}, indent=1), encoding="utf-8")
        log_event("session_start", mode=mode, seed=seed)
        return {"seed": seed, "dir": d.name, "order": [{"stimulus_id": s["stimulus_id"], "category": s["category"]} for s in order]}


def api_cal_enter(b):
    with LOCK:
        GAZE.cal_enter()
    return {"ok": True}


def api_cal_collect(b):
    return {"ok": GAZE.cal_collect(float(b["x"]), float(b["y"]))}


def api_cal_compute(b):
    with LOCK:
        res = GAZE.cal_compute()
    log_event("calibration_computed", ok=res["ok"], status=res["status"])
    return res


def api_cal_leave(b):
    with LOCK:
        GAZE.cal_leave()
    return {"ok": True}


def api_gaze_start(b):
    with LOCK:
        GAZE.start()
    return {"ok": True}


def api_gaze_stop(b):
    with LOCK:
        GAZE.stop()
    return {"ok": True}


def _to_bridge_perf(client_ms):
    return (client_ms + S["offset_ms"]) / 1000.0


def api_set_offset(b):
    S["offset_ms"] = float(b["offset_ms"])
    return {"ok": True}


def api_val_window(b):
    """Walidacja punktu: mediana wazne probki w oknie [t_on+skip, t_off] vs cel; zwraca blad w stopniach."""
    nx, ny = float(b["x"]), float(b["y"])
    t_on, t_off = _to_bridge_perf(float(b["t_on_ms"])), _to_bridge_perf(float(b["t_off_ms"]))
    samples = GAZE.peek_window(t_on + VAL_SKIP_S, t_off)
    pts = []
    for s in samples:
        for ok, x, y in ((s[4], s[2], s[3]), (s[7], s[5], s[6])):
            if ok:
                pts.append((x, y))
    if len(pts) < VAL_MIN_SAMPLES:
        return {"error_deg": None, "n": len(pts)}
    mx, my = statistics.median(p[0] for p in pts), statistics.median(p[1] for p in pts)
    W, H = S["cfg"]["screen_width_px"], S["cfg"]["screen_height_px"]
    cm_per_px = S["cfg"]["screen_width_cm"] / W
    deg = analysis._angle_deg((mx - nx) * W, (my - ny) * H, cm_per_px, S["cfg"]["viewing_distance_cm"])
    return {"error_deg": deg, "n": len(pts)}


def api_set_calibration(b):
    S["cal_status"] = str(b["status"])
    S["val_mean"] = b.get("mean_error_deg")
    S["recal"] = int(b.get("recalibration_flag", 0))
    S["cfg"]["calibration_status"] = S["cal_status"]
    S["cfg"]["validation_mean_error_deg"] = None if S["val_mean"] is None else round(float(S["val_mean"]), 3)
    save_cfg()
    log_event("calibration_status", **{k: b.get(k) for k in ("status", "mean_error_deg", "recalibration_flag", "errors_deg")})
    return {"ok": True}


def api_trial_finish(b):
    sid_ = str(b["stimulus_id"])
    if sid_ not in STIM_IDS:
        raise ValueError("nieznany bodziec")
    rating = int(b["rating"])
    if not 1 <= rating <= 7:
        raise ValueError("ocena poza zakresem")
    trial_id = f"T{int(b['trial_order']):02d}"
    t_on, t_off = _to_bridge_perf(float(b["onset_ms"])), _to_bridge_perf(float(b["offset_ms"]))
    samples = GAZE.take_window(t_on, t_off)
    t0 = S["t0"]
    cfg = S["cfg"]
    freq = GAZE.freq if GAZE.freq == GAZE.freq and GAZE.freq else 120.0
    n_valid = sum(1 for x in samples if x[4] or x[7])
    valid_ratio = round(n_valid / len(samples), 4) if samples else 0.0
    frame_ms = float(b.get("frame_ms", 16.7))
    dur = float(b["offset_ms"]) - float(b["onset_ms"])
    reasons = []
    if S["cal_status"] not in ("CALIBRATED_VALIDATED", "SIMULATION_NOT_APPLICABLE"):
        reasons.append(S["cal_status"].lower())
    if valid_ratio < VALID_RATIO_MIN:
        reasons.append(f"valid_gaze_ratio<{VALID_RATIO_MIN}")
    if len(samples) < 0.5 * PRESENT_S * freq:
        reasons.append("too_few_samples")
    if abs(dur - PRESENT_S * 1000) > 3 * frame_ms:
        reasons.append("presentation_duration_off")
    append_csv(S["dir"] / "trials.csv", TRIAL_FIELDS, [{
        "participant_id": S["pid"], "session_id": S["sid"], "trial_id": trial_id, "trial_order": int(b["trial_order"]),
        "random_seed": S["seed"], "stimulus_id": sid_, "stimulus_category": STIM_BY_ID[sid_]["category"],
        "stimulus_path_hash": HASHES[sid_],
        "presentation_start_ms": round((t_on - t0) * 1000, 2), "presentation_end_ms": round((t_off - t0) * 1000, 2),
        "trust_rating_1_7": rating, "response_time_ms": round(float(b["rt_ms"]), 1), "tracker_model": GAZE.model,
        "sampling_frequency": freq, "calibration_status": S["cal_status"],
        "validation_mean_error_deg": cfg["validation_mean_error_deg"], "valid_gaze_ratio": valid_ratio,
        "invalid_reason": ";".join(reasons), "recalibration_flag": S["recal"], "run_mode": S["mode"],
    }])
    rows = []
    W, H = cfg["screen_width_px"], cfg["screen_height_px"]
    for k, x in enumerate(samples, 1):
        ok = bool(x[4] or x[7])
        rows.append({
            "sample_id": f"{trial_id}_{k:05d}", "participant_id": S["pid"], "session_id": S["sid"], "trial_id": trial_id,
            "device_timestamp": x[1], "app_timestamp": round((x[0] - t0) * 1000, 3),
            "left_gaze_x": "" if not x[4] else round(x[2], 5), "left_gaze_y": "" if not x[4] else round(x[3], 5),
            "left_validity": int(x[4]),
            "right_gaze_x": "" if not x[7] else round(x[5], 5), "right_gaze_y": "" if not x[7] else round(x[6], 5),
            "right_validity": int(x[7]), "gaze_validity": int(ok), "screen_width_px": W, "screen_height_px": H,
        })
    append_csv(S["dir"] / "gaze_samples.csv", SAMPLE_FIELDS, rows)
    log_event("trial_done", trial_id=trial_id, stimulus=sid_, rating=rating, samples=len(samples), valid_ratio=valid_ratio,
              page_duration_ms=round(dur, 1))
    return {"trial_id": trial_id, "samples": len(samples), "valid_ratio": valid_ratio, "invalid_reason": ";".join(reasons)}


def api_session_finish(b):
    with LOCK:
        GAZE.stop()
        log_event("comfort_1_5", value=b.get("comfort"))
        log_event("session_end")
        S["finished"] = True
        n_fix, n_aoi = analysis.run_session_analysis(S["dir"])
        report = (S["dir"] / "quality_report.txt").read_text(encoding="utf-8")
    return {"fixations": n_fix, "aoi_rows": n_aoi, "report": report, "dir": S["dir"].name}


def api_session_abort(b):
    with LOCK:
        GAZE.shutdown()
        if "dir" in S:
            log_event("ABORTED", reason=str(b.get("reason", ""))[:100])
    return {"ok": True}


POST = {
    "/api/sync": api_sync, "/api/session/start": api_session_start, "/api/cal/enter": api_cal_enter,
    "/api/cal/collect": api_cal_collect, "/api/cal/compute": api_cal_compute, "/api/cal/leave": api_cal_leave,
    "/api/gaze/start": api_gaze_start, "/api/gaze/stop": api_gaze_stop, "/api/offset": api_set_offset,
    "/api/val/window": api_val_window, "/api/calibration": api_set_calibration, "/api/trial/finish": api_trial_finish,
    "/api/session/finish": api_session_finish, "/api/session/abort": api_session_abort,
}


class Handler(BaseHTTPRequestHandler):
    server_version = "TrustFacesBridge/1.0"

    def log_message(self, fmt, *a):  # ciszej
        pass

    def _host_ok(self):
        host = self.headers.get("Host", "")
        return host in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host"})
        path = self.path.split("?")[0]
        if path == "/api/status":
            return self._send(200, api_status(None))
        if path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")
        if path in ("/", "/index.html"):
            return self._send(200, (HERE / "web" / "index.html").read_bytes(), "text/html; charset=utf-8")
        m = re.fullmatch(r"/stimuli/([A-Z]+_\d\d)\.png", path)
        if m and m.group(1) in STIM_IDS:
            return self._send(200, (HERE / "stimuli" / f"{m.group(1)}.png").read_bytes(), "image/png")
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host"})
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"):
            return self._send(403, {"error": "bad origin"})
        fn = POST.get(self.path.split("?")[0])
        if fn is None:
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            if fn not in (api_sync, api_cal_collect, api_val_window, api_set_offset) and "dir" not in S and fn not in (
                    api_session_start, api_session_abort, api_cal_enter, api_cal_compute, api_cal_leave):
                raise ValueError("brak aktywnej sesji")
            self._send(200, fn(body))
        except Exception as exc:  # noqa: BLE001
            print(f"[BRIDGE] blad {self.path}: {exc!r}")
            self._send(400, {"error": str(exc)})


def main():
    port = PORT
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    GAZE.connect()
    atexit.register(GAZE.shutdown)
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)   # TYLKO localhost
    url = f"http://127.0.0.1:{port}/"
    print(f"[BRIDGE] {'SYMULACJA (dane syntetyczne)' if SIM else 'TOBII'} | {url} | Ctrl+C konczy")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        GAZE.shutdown()


if __name__ == "__main__":
    main()
