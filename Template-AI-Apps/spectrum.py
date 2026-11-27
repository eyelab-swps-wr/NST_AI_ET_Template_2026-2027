# -*- coding: utf-8 -*-
"""
Wspolny modul Tobii Pro Spectrum dla wszystkich aplikacji w Template-AI-Apps.
Shared Tobii Pro Spectrum helper for every app in Template-AI-Apps.

Co daje / what it provides:
  find_all_eyetrackers()  - Spectrum na pierwszym miejscu + ustawiona czestotliwosc
  install_escape(win)     - ESC w KAZDYM momencie natychmiast przerywa eksperyment
                            (sprzata subskrypcje / tryb kalibracji i zamyka proces)
  collect_point(...)      - collect_data() w tle; okno odswieza sie, ESC dziala
  compute_and_apply(...)  - compute_and_apply() w tle; jw.
  GazeStream              - strumien gaze zgodny z SDK: bufor wszystkich probek,
                            znaczniki czasu z SDK (system_time_stamp), odrzucanie
                            probek niewaznych/NaN i przeterminowanych

Czestotliwosc / sampling rate:
    domyslnie 120 Hz; czestotliwosc mozna zmienic zmienna SPECTRUM_HZ.
    Zmiana: zmienna srodowiskowa SPECTRUM_HZ, np.  set SPECTRUM_HZ=600
"""
import math
import os
import sys
import threading
import time
from collections import deque

import tobii_research as tr

TARGET_HZ = float(os.environ.get("SPECTRUM_HZ", "120"))

# Probka starsza niz tyle sekund jest traktowana jako brak danych.
# A sample older than this is treated as "no gaze" (tracker lost the eyes).
MAX_SAMPLE_AGE_S = 0.1


# ============================================================================
# Wyszukiwanie i konfiguracja trackera
# ============================================================================
def _is_spectrum(tracker):
    return "spectrum" in (tracker.model or "").casefold()


def configure(tracker, target_hz=TARGET_HZ):
    """Ustaw czestotliwosc najblizsza target_hz (nie wieksza, jesli to mozliwe)."""
    try:
        freqs = sorted(tracker.get_all_gaze_output_frequencies())
        if not freqs:
            return
        not_above = [f for f in freqs if f <= target_hz + 0.5]
        chosen = not_above[-1] if not_above else freqs[0]
        if abs(tracker.get_gaze_output_frequency() - chosen) > 0.5:
            tracker.set_gaze_output_frequency(chosen)
        print(f"[SPECTRUM] Gaze output frequency: {tracker.get_gaze_output_frequency():.0f} Hz "
              f"(available: {', '.join(f'{f:.0f}' for f in freqs)})")
    except Exception as exc:  # nie blokuj eksperymentu / never block the session
        print(f"[SPECTRUM] Could not set gaze frequency: {exc}")


def find_all_eyetrackers():
    """Jak tr.find_all_eyetrackers(), ale Spectrum jest pierwszy i skonfigurowany."""
    trackers = list(tr.find_all_eyetrackers())
    trackers.sort(key=lambda t: not _is_spectrum(t))
    if trackers:
        et = trackers[0]
        if not _is_spectrum(et):
            print(f"[SPECTRUM] WARNING: Tobii Pro Spectrum not found, using {et.model}")
        configure(et)
    else:
        print("[SPECTRUM] No eye tracker found. Is the Spectrum on and visible "
              "in Tobii Pro Eye Tracker Manager?")
    return trackers


# ============================================================================
# ESC = natychmiastowe przerwanie / ESC = immediate abort
# ============================================================================
_cleanups = []
_aborting = False


def on_abort(fn):
    """Zarejestruj funkcje sprzatajaca wywolywana przy ESC (LIFO)."""
    _cleanups.append(fn)
    return fn


def remove_on_abort(fn):
    try:
        _cleanups.remove(fn)
    except ValueError:
        pass


def abort():
    """Sprzata (unsubscribe, wyjscie z trybu kalibracji, zamkniecie okien) i konczy proces."""
    global _aborting
    if _aborting:
        return
    _aborting = True
    print("\n[SPECTRUM] ESC - eksperyment przerwany.", flush=True)
    for fn in reversed(_cleanups):
        try:
            fn()
        except Exception as exc:
            print(f"[SPECTRUM] cleanup error: {exc}")
    try:
        from psychopy import logging, visual
        for ref in list(getattr(visual.window, "openWindows", [])):
            win = ref() if callable(ref) else ref
            if win is not None:
                try:
                    win.close()
                except Exception:
                    pass
        logging.flush()
    except Exception:
        pass
    sys.stdout.flush()
    sys.stderr.flush()
    # os._exit: zadne watki SDK / audio / bare "except:" w aplikacji nie zatrzymaja wyjscia.
    os._exit(0)


def install_escape(win=None):
    """ESC dziala globalnie: przy kazdym win.flip(), getKeys(), waitKeys(), core.wait()."""
    from psychopy import event
    try:
        event.globalKeys.remove(key="escape")
    except Exception:
        pass
    event.globalKeys.add(key="escape", func=abort, name="spectrum_abort")


def _run_in_background(win, fn, draw=None):
    """Uruchom blokujace wywolanie SDK w watku; okno dalej sie odswieza, ESC dziala."""
    box = {}

    def worker():
        try:
            box["result"] = fn()
        except Exception as exc:  # przekaz wyjatek do watku glownego
            box["error"] = exc

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    while th.is_alive():
        if draw is not None:
            draw()
        if win is not None:
            win.flip()  # flip przetwarza zdarzenia klawiatury -> globalny ESC
        else:
            time.sleep(0.01)
    if "error" in box:
        raise box["error"]
    return box.get("result")


# ============================================================================
# Kalibracja bez blokowania okna
# ============================================================================
CAL_OK_STATUSES = (
    tr.CALIBRATION_STATUS_SUCCESS,
    tr.CALIBRATION_STATUS_SUCCESS_LEFT_EYE,
    tr.CALIBRATION_STATUS_SUCCESS_RIGHT_EYE,
)


def guard_calibration(calibration):
    """Po ESC tracker zawsze wyjdzie z trybu kalibracji."""
    def _leave():
        calibration.leave_calibration_mode()
    on_abort(_leave)
    return _leave


def collect_point(calibration, nx, ny, win, draw=None, retries=3, retry_wait=0.3):
    """collect_data(nx, ny) z ponowieniami; True jesli SDK zwrocil sukces."""
    for i in range(retries):
        status = _run_in_background(win, lambda: calibration.collect_data(nx, ny), draw)
        if status in CAL_OK_STATUSES:
            return True
        if i < retries - 1:
            t_end = time.perf_counter() + retry_wait
            while time.perf_counter() < t_end:
                if draw is not None:
                    draw()
                win.flip()
    return False


def compute_and_apply(calibration, win, draw=None):
    return _run_in_background(win, calibration.compute_and_apply, draw)


# ============================================================================
# Pelna kalibracja z ekranem pozycji glowy i podgladem jakosci
# Full calibration: head-position screen -> calibration -> result plot (R = redo)
# ============================================================================
CAL_POINTS_5 = [(0.5, 0.5), (0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
CAL_POINTS_9 = [(0.5, 0.5), (0.1, 0.1), (0.5, 0.1), (0.9, 0.1), (0.9, 0.5),
                (0.9, 0.9), (0.5, 0.9), (0.1, 0.9), (0.1, 0.5)]


def _n2p(win, nx, ny):
    """Display area (0..1, (0,0)=top-left) -> PsychoPy pix (0,0)=center."""
    w, h = win.size
    return (nx - 0.5) * w, (0.5 - ny) * h


def _wait_space_or_r(win, draw_fn):
    from psychopy import event
    event.clearEvents(eventType="keyboard")
    while True:
        draw_fn()
        win.flip()
        keys = event.getKeys(["space", "r"])
        if keys:
            return keys[-1]


def show_user_position(win, eyetracker, text="Usiadz tak, aby oba punkty byly zielone i blisko srodka.\nSPACJA = dalej"):
    """Ekran pozycji glowy (EYETRACKER_USER_POSITION_GUIDE): oczy w track boxie."""
    from psychopy import event, visual
    state = {}

    def cb(d):
        state["d"] = d

    try:
        eyetracker.subscribe_to(tr.EYETRACKER_USER_POSITION_GUIDE, cb, as_dictionary=True)
    except Exception as exc:
        print(f"[SPECTRUM] User position guide unavailable: {exc}")
        return
    unsub = lambda: eyetracker.unsubscribe_from(tr.EYETRACKER_USER_POSITION_GUIDE, cb)
    on_abort(unsub)
    w, h = win.size
    box = visual.Rect(win, width=w * 0.4, height=h * 0.4, units="pix", lineColor="white", fillColor=None, lineWidth=3)
    eyes = {s: visual.Circle(win, radius=22, units="pix", lineColor=None) for s in ("left", "right")}
    info = visual.TextStim(win, text=text, units="pix", pos=(0, -h * 0.32), height=28, color="white", wrapWidth=w * 0.8)
    dist = visual.TextStim(win, text="", units="pix", pos=(0, h * 0.28), height=26, color="white")
    event.clearEvents(eventType="keyboard")
    try:
        while not event.getKeys(["space"]):
            box.draw()
            d = state.get("d")
            zs = []
            if d is not None:
                for side in ("left", "right"):
                    if d[f"{side}_user_position_validity"]:
                        x, y, z = d[f"{side}_user_position"]
                        # x mirrored so the dot moves like a mirror image of the head
                        eyes[side].pos = ((0.5 - x) * w * 0.4, (0.5 - y) * h * 0.4)
                        eyes[side].radius = 14 + 24 * (1.0 - min(1.0, max(0.0, z)))
                        ok = 0.2 < x < 0.8 and 0.2 < y < 0.8 and 0.2 < z < 0.8
                        eyes[side].fillColor = "lime" if ok else "orange"
                        eyes[side].draw()
                        zs.append(z)
            if zs:
                z = sum(zs) / len(zs)
                dist.text = "Za blisko - odsun sie" if z < 0.25 else ("Za daleko - przysun sie" if z > 0.75 else "Odleglosc OK")
            else:
                dist.text = "Nie widze oczu"
            dist.draw()
            info.draw()
            win.flip()
    finally:
        try:
            unsub()
        except Exception:
            pass
        remove_on_abort(unsub)


def _draw_cal_result(win, result, points):
    """Tobii-style result plot: lines from each target to left (green) / right (red) eye samples.
    Returns mean error in px per point (None if no valid samples)."""
    from psychopy import visual
    errs = {}
    for cp in (result.calibration_points if result is not None else []):
        tx, ty = cp.position_on_display_area
        tpx = _n2p(win, tx, ty)
        d = []
        for smp in cp.calibration_samples:
            for eye, col in ((smp.left_eye, "lime"), (smp.right_eye, "red")):
                if eye.validity == tr.VALIDITY_VALID_AND_USED:
                    ex, ey = eye.position_on_display_area
                    epx = _n2p(win, ex, ey)
                    visual.Line(win, start=tpx, end=epx, units="pix", lineColor=col, lineWidth=1).draw()
                    d.append(math.hypot(epx[0] - tpx[0], epx[1] - tpx[1]))
        errs[(round(tx, 2), round(ty, 2))] = (sum(d) / len(d)) if d else None
    for nx, ny in points:
        px, py = _n2p(win, nx, ny)
        e = errs.get((round(nx, 2), round(ny, 2)))
        visual.Circle(win, radius=12, pos=(px, py), units="pix", lineColor="white", fillColor=None, lineWidth=2).draw()
        label = "brak danych" if e is None else f"{e:.0f} px"
        visual.TextStim(win, text=label, pos=(px, py - 30), units="pix", height=18,
                        color="white" if e is not None and e < 60 else "orange").draw()
    return errs


def calibrate(win, eyetracker, points=CAL_POINTS_9, position_screen=True):
    """
    Pelna kalibracja Tobii Pro Spectrum:
      1) ekran pozycji glowy, 2) kalibracja (punkty kurcza sie, collect_data w tle),
      3) wykres wynikow z bledem w px dla kazdego punktu: SPACJA = akceptuj, R = powtorz.
    ESC dziala przez caly czas (install_escape). Zwraca True gdy kalibracja zaakceptowana.
    """
    from psychopy import event, visual
    if position_screen:
        show_user_position(win, eyetracker)

    dot = visual.Circle(win, radius=20, units="pix", fillColor="white", lineColor=None)
    center = visual.Circle(win, radius=4, units="pix", fillColor="black", lineColor=None)
    msg = visual.TextStim(win, text="", units="pix", height=28, color="white", wrapWidth=win.size[0] * 0.8)
    w, h = win.size

    while True:
        msg.text = "KALIBRACJA\n\nPatrz na srodek kazdego punktu, az zniknie.\n\nSPACJA = start"
        msg.pos = (0, 0)
        if _wait_space_or_r(win, msg.draw) == "r":
            continue

        calibration = tr.ScreenBasedCalibration(eyetracker)
        calibration.enter_calibration_mode()
        leave = guard_calibration(calibration)
        result = None
        try:
            for nx, ny in points:
                px, py = _n2p(win, nx, ny)
                dot.pos = center.pos = (px, py)
                for frame in range(45):  # ~0.75 s: let the eye land on the dot
                    dot.radius = max(8, 26 - frame * 0.4)
                    dot.draw(); center.draw(); win.flip()
                ok = collect_point(calibration, nx, ny, win, draw=lambda: (dot.draw(), center.draw()))
                if not ok:
                    print(f"[SPECTRUM] Calibration point {nx:.1f},{ny:.1f}: no data")
            msg.text = "Obliczam kalibracje..."
            result = compute_and_apply(calibration, win, draw=msg.draw)
        finally:
            try:
                leave()
            except Exception:
                pass
            remove_on_abort(leave)

        status_ok = result is not None and result.status in CAL_OK_STATUSES
        title = visual.TextStim(win, units="pix", pos=(0, h * 0.40), height=22, wrapWidth=w * 0.95,
                                color="lime" if status_ok else "orange",
                                text=("Kalibracja OK" if status_ok else "Kalibracja NIEUDANA") +
                                     "   |   SPACJA = akceptuj   R = powtorz   (zielony = lewe oko, czerwony = prawe)")

        def draw_result():
            title.draw()
            _draw_cal_result(win, result, points)

        key = _wait_space_or_r(win, draw_result)
        if key == "space":
            print(f"[SPECTRUM] Calibration accepted (status ok: {status_ok})")
            event.clearEvents(eventType="keyboard")
            return status_ok


# ============================================================================
# Strumien gaze zgodny z SDK / SDK-correct gaze stream
# ============================================================================
def sdk_time_to_perf(system_time_stamp_us):
    """Przelicz system_time_stamp (us, zegar SDK) na skale time.perf_counter() (s)."""
    return time.perf_counter() - (tr.get_system_time_stamp() - system_time_stamp_us) / 1e6


def _eye(d, side):
    if d[f"{side}_gaze_point_validity"]:
        x, y = d[f"{side}_gaze_point_on_display_area"]
        if math.isfinite(x) and math.isfinite(y):
            return x, y
    return None


def binocular_norm(d):
    """Srednia z waznych oczu w ukladzie display area (0..1, (0,0)=lewy gorny) lub None."""
    pts = [p for p in (_eye(d, "left"), _eye(d, "right")) if p is not None]
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


class GazeStream:
    """
    Subskrypcja EYETRACKER_GAZE_DATA (as_dictionary=True) wg zalecen Tobii Pro SDK:
      * callback jest lekki i dziala w watku SDK -> tylko zapis pod lockiem,
      * kazda probka trafia do bufora (nic nie ginie przy 120-1200 Hz),
      * czas = system_time_stamp z SDK (us), nie czas przyjscia callbacku,
      * probki niewazne / NaN / przeterminowane nie sa zwracane jako spojrzenie,
      * bledy strumienia (EYETRACKER_STREAM_ERRORS) sa logowane,
      * stop() jest idempotentny i wywolywany automatycznie przy ESC.
    """

    def __init__(self, eyetracker, max_age_s=MAX_SAMPLE_AGE_S, buffer_seconds=300):
        self._et = eyetracker
        self._lock = threading.Lock()
        self._latest = None
        self._buffer = deque(maxlen=int(max(TARGET_HZ, 120) * buffer_seconds))
        self.max_age_s = max_age_s
        self.active = False
        self.n_samples = 0
        self.n_valid = 0

    # --- subskrypcja -------------------------------------------------------
    def start(self):
        if self.active:
            return
        self._et.subscribe_to(tr.EYETRACKER_GAZE_DATA, self._callback, as_dictionary=True)
        try:
            self._et.subscribe_to(tr.EYETRACKER_STREAM_ERRORS, self._on_stream_error, as_dictionary=True)
        except Exception:
            pass
        self.active = True
        on_abort(self.stop)

    def stop(self):
        if not self.active:
            return
        self.active = False
        remove_on_abort(self.stop)
        for stream, cb in ((tr.EYETRACKER_GAZE_DATA, self._callback),
                           (tr.EYETRACKER_STREAM_ERRORS, self._on_stream_error)):
            try:
                self._et.unsubscribe_from(stream, cb)
            except Exception:
                pass

    def wait_for_data(self, timeout=1.0):
        """Strumien SDK startuje ~0.3-0.5 s po subscribe_to; poczekaj na pierwsza probke."""
        t_end = time.perf_counter() + timeout
        while self.n_samples == 0 and time.perf_counter() < t_end:
            time.sleep(0.005)
        return self.n_samples > 0

    # --- watek SDK ----------------------------------------------------------
    def _callback(self, d):
        g = binocular_norm(d)
        sample = (d["system_time_stamp"], d["device_time_stamp"], g)
        with self._lock:
            self._latest = sample
            self._buffer.append(sample)
            self.n_samples += 1
            if g is not None:
                self.n_valid += 1
        self.on_sample(d, g)

    def on_sample(self, d, gaze_norm):
        """Hook dla podklas (wywolywany w watku SDK - trzymaj go lekkim)."""

    def _on_stream_error(self, err):
        print(f"[SPECTRUM] Stream error: {err}")

    # --- odczyt w watku glownym -------------------------------------------
    def latest_norm(self):
        """Najnowsze wazne spojrzenie (nx, ny) w display area lub None (brak/stare)."""
        with self._lock:
            s = self._latest
        if s is None or s[2] is None:
            return None
        age_s = (tr.get_system_time_stamp() - s[0]) / 1e6
        if age_s > self.max_age_s:
            return None
        return s[2]

    def drain(self):
        """Wszystkie probki od ostatniego wywolania: lista (t_perf_s, nx, ny) (tylko wazne)."""
        with self._lock:
            items = list(self._buffer)
            self._buffer.clear()
        now_perf = time.perf_counter()
        now_sys = tr.get_system_time_stamp()
        return [(now_perf - (now_sys - ts) / 1e6, g[0], g[1])
                for ts, _dev, g in items if g is not None]
