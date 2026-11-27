#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI TEMPLATE APP
===============
Eye Tracking starter template using Tobii Pro Spectrum + PsychoPy.

Structure for students:
  1. SDK setup & device connection
  2. 5-point screen-based calibration
  3. Gaze data streaming with live cursor
  4. Clean shutdown

Press ESC at any time to quit.
"""

# ============================================================================
# 1. IMPORTS
# ============================================================================
try:
    from psychopy import visual, core, event, logging
    logging.console.setLevel(logging.ERROR)
except ImportError as exc:
    raise ImportError(
        "\n\nPsychoPy is not installed.\n"
        "Install it with: pip install psychopy\n"
        "Or download standalone from https://www.psychopy.org/download.html\n"
    ) from exc

import sys
from pathlib import Path

# Wspolny modul ../spectrum.py (ESC, kalibracja bez blokowania, strumien gaze zgodny z SDK)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import tobii_research as tr
    import spectrum
except ImportError as exc:
    raise ImportError(
        "\n\nTobii Pro SDK 2.1.0 is not installed in this Python environment.\n"
        "Use 64-bit Python 3.10 and install requirements.txt in the same environment.\n"
    ) from exc

# ============================================================================
# 2. CONSTANTS
# ============================================================================
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FULLSCREEN = True

CAL_ACTIVE_COLOR = "white"
CAL_DOT_RADIUS = 20
GAZE_CURSOR_RADIUS = 15
GAZE_CURSOR_COLOR = [1.0, 0.2, 0.2]

CALIBRATION_POINTS = [
    (0.5, 0.5),
    (0.1, 0.1),
    (0.9, 0.1),
    (0.9, 0.9),
    (0.1, 0.9),
]


# ============================================================================
# 3. HELPERS
# ============================================================================
def norm_to_pix(nx, ny):
    px = (nx - 0.5) * SCREEN_WIDTH
    py = (0.5 - ny) * SCREEN_HEIGHT
    return px, py


def connect_eyetracker():
    print("\n[AI TEMPLATE] Searching for eye tracker...")
    trackers = spectrum.find_all_eyetrackers()  # Spectrum first, frequency set
    if not trackers:
        print("[AI TEMPLATE] No eye tracker found.")
        return None

    spectrum_trackers = [
        tracker for tracker in trackers
        if "spectrum" in (tracker.model or "").casefold()
    ]
    if not spectrum_trackers:
        models = ", ".join(tracker.model or "Unknown model" for tracker in trackers)
        print(f"[AI TEMPLATE] Tobii Pro Spectrum not found. Detected: {models}")
        return None

    et = spectrum_trackers[0]
    print(f"[AI TEMPLATE] Connected  : {et.model}")
    print(f"[AI TEMPLATE] Serial     : {et.serial_number}")
    print(f"[AI TEMPLATE] Address    : {et.address}")
    return et


class GazeCollector(spectrum.GazeStream):
    """Tobii Pro Spectrum gaze stream - see spectrum.GazeStream for the SDK details
    (thread-safe buffer, SDK timestamps, invalid/NaN/stale samples rejected)."""

    def start(self):
        super().start()
        print("[AI TEMPLATE] Gaze stream started.")

    def stop(self):
        super().stop()
        print("[AI TEMPLATE] Gaze stream stopped.")

    def get_gaze_pix(self):
        g = self.latest_norm()  # None if no valid eye or sample older than 100 ms
        if g is None:
            return None
        return norm_to_pix(g[0], g[1])


def run_calibration(win, eyetracker):
    calibration = tr.ScreenBasedCalibration(eyetracker)
    calibration.enter_calibration_mode()
    spectrum.guard_calibration(calibration)  # ESC -> leave calibration mode
    print("[AI TEMPLATE] Calibration mode entered.")

    dot = visual.Circle(win, radius=CAL_DOT_RADIUS, fillColor=CAL_ACTIVE_COLOR, lineColor=None)
    inner = visual.Circle(win, radius=4, fillColor="black", lineColor=None)
    instruction = visual.TextStim(
        win,
        text="Look at each dot as it appears.\n\nPress SPACE to begin.",
        height=28,
        color="white",
        pos=(0, 0),
    )

    instruction.draw()
    win.flip()
    keys = event.waitKeys(keyList=["space", "escape"])
    if "escape" in keys:
        calibration.leave_calibration_mode()
        return False

    ok_statuses = (
        tr.CALIBRATION_STATUS_SUCCESS,
        tr.CALIBRATION_STATUS_SUCCESS_LEFT_EYE,
        tr.CALIBRATION_STATUS_SUCCESS_RIGHT_EYE,
    )
    success = False
    for attempt in range(3):
        failed = []
        for nx, ny in CALIBRATION_POINTS:
            px, py = norm_to_pix(nx, ny)
            # Let the eye land on the dot before sampling (~1 s).
            for frame in range(60):
                dot.radius = max(8, CAL_DOT_RADIUS - frame * 0.2)
                dot.pos = (px, py)
                inner.pos = (px, py)
                dot.draw()
                inner.draw()
                win.flip()
                if "escape" in event.getKeys(["escape"]):
                    calibration.leave_calibration_mode()
                    return False

            # collect_data() blocks ~1-3 s; run it in the background so ESC still works
            collected = spectrum.collect_point(
                calibration, nx, ny, win, draw=lambda: (dot.draw(), inner.draw()))
            if not collected:
                failed.append((nx, ny))
            core.wait(0.3)

        result = spectrum.compute_and_apply(calibration, win)
        if not failed and result.status in ok_statuses:
            success = True
            break
        print(f"[AI TEMPLATE] Calibration attempt {attempt + 1} failed (missing: {failed}, status: {result.status}).")
        for nx, ny in CALIBRATION_POINTS:
            calibration.discard_data(nx, ny)

    calibration.leave_calibration_mode()

    status_text = "Calibration OK!" if success else "Calibration FAILED - try again."
    print(f"[AI TEMPLATE] {status_text}")

    msg = visual.TextStim(win, text=status_text, height=32, color="white")
    msg.draw()
    win.flip()
    core.wait(1.5)

    return success


def run_gaze_demo(win, gaze_collector):
    cursor = visual.Circle(
        win,
        radius=GAZE_CURSOR_RADIUS,
        fillColor=GAZE_CURSOR_COLOR,
        lineColor=None,
        opacity=0.8,
    )
    mode_label = visual.TextStim(
        win,
        text="LIVE - Tobii Pro Spectrum",
        height=20,
        color="lime",
        pos=(-SCREEN_WIDTH // 2 + 10, SCREEN_HEIGHT // 2 - 20),
        anchorHoriz="left",
        anchorVert="top",
    )
    instructions = visual.TextStim(
        win,
        text="Gaze tracking active | ESC to quit",
        height=22,
        color="white",
        pos=(0, -SCREEN_HEIGHT // 2 + 30),
    )
    no_signal = visual.TextStim(win, text="No gaze signal", height=22, color="orange")

    gaze_collector.start()

    while True:
        if "escape" in event.getKeys():
            break

        gaze_pix = gaze_collector.get_gaze_pix()

        win.clearBuffer()
        instructions.draw()
        mode_label.draw()

        if gaze_pix is not None:
            cursor.pos = gaze_pix
            cursor.draw()
        else:
            no_signal.draw()

        win.flip()

    gaze_collector.stop()


# ============================================================================
# 4. ENTRY POINT
# ============================================================================
def main():
    eyetracker = connect_eyetracker()

    win = visual.Window(
        size=(SCREEN_WIDTH, SCREEN_HEIGHT),
        fullscr=FULLSCREEN,
        color="black",
        units="pix",
        screen=0,
    )
    spectrum.install_escape(win)  # ESC aborts the experiment at any moment

    if eyetracker is None:
        msg = visual.TextStim(
            win,
            text="Tobii Pro Spectrum not found.\n\n"
                 "Check that the tracker is connected and Tobii Pro Eye Tracker Manager is running.\n\n"
                 "Press any key to quit.",
            height=30,
            color="orange",
            wrapWidth=900,
        )
        msg.draw()
        win.flip()
        event.waitKeys()
        win.close()
        return

    calibrated = run_calibration(win, eyetracker)
    if not calibrated:
        win.close()
        return

    gaze_collector = GazeCollector(eyetracker)
    run_gaze_demo(win, gaze_collector)

    win.close()
    print("[AI TEMPLATE] Done.")


if __name__ == "__main__":
    main()
