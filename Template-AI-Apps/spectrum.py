# -*- coding: utf-8 -*-
"""
Wspolny modul Tobii Pro Spectrum dla wszystkich aplikacji w Template-AI-Apps.
Shared Tobii Pro Spectrum helper for every app in Template-AI-Apps.

Uzycie / usage (w aplikacji / in an app):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import spectrum
    trackers = spectrum.find_all_eyetrackers()   # Spectrum first, Hz set

Czestotliwosc probkowania / sampling rate:
    domyslnie 120 Hz (tak jak X3-120, wiec progi w aplikacjach dzialaja bez zmian).
    Zmiana: zmienna srodowiskowa SPECTRUM_HZ, np.  set SPECTRUM_HZ=600
    Default 120 Hz (same as the old X3-120, so app thresholds stay valid).
    Override with the SPECTRUM_HZ environment variable.
"""
import os

import tobii_research as tr

TARGET_HZ = float(os.environ.get("SPECTRUM_HZ", "120"))


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
