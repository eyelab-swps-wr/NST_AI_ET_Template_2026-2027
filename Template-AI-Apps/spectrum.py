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
    domyslnie 120 Hz (tak jak X3-120, wiec progi w aplikacjach dzialaja bez zmian).
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
