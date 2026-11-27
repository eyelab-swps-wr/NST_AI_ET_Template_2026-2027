#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
APP 4 - MALOWANIE GLOSEM I WZROKIEM

Artsy prototype:
- Gaze paints on a living canvas (Tobii)
- Voice timbre and loudness shape brush color, size and pulse
- Strong jitter compensation keeps movement fluid but stable

Controls:
- Say in English "S-W-P-S" letter by letter ("es, double-you, pee, es")
  or "I love S-W-P-S": the brush switches from ink blots to the letters
  S W P S (offline speech recognition: Vosk, models/ folder)
- L: toggle letter brush manually
- SPACE: finish artwork
- C: clear canvas
- S: save snapshot now
- ESC: quit
"""

import colorsys
import json
import math
import queue
import random
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np

# ============================================================================
# 0. TOBII CONFIGURATION
# ============================================================================
# Tobii Pro Spectrum: tobii_research (SDK 2.1.0) is installed in the bundled
# ..\PsychoPy python; shared helper spectrum.py lives in the parent folder.
HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

# ============================================================================
# 1. IMPORTS
# ============================================================================
try:
    from psychopy import core, event, logging, visual
except ImportError as exc:
    raise ImportError("Brak PsychoPy. Zainstaluj: pip install psychopy") from exc

import tobii_research as tr

import spectrum

try:
    import sounddevice as sd

    SOUNDDEVICE_OK = True
except Exception:
    SOUNDDEVICE_OK = False
    sd = None

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_OK = True
except Exception:
    PIL_OK = False
    Image = ImageDraw = ImageFont = None

try:
    import vosk

    vosk.SetLogLevel(-1)
    VOSK_OK = True
except Exception:
    vosk = None
    VOSK_OK = False

VOSK_MODEL_DIR = HERE / "models" / "vosk-model-small-en-us-0.15"

logging.console.setLevel(logging.ERROR)

# ============================================================================
# 2. PARAMETERS
# ============================================================================
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FULLSCREEN = True

ACTIVE_SCREEN_WIDTH = float(SCREEN_WIDTH)
ACTIVE_SCREEN_HEIGHT = float(SCREEN_HEIGHT)

CANVAS_W = 1280
CANVAS_H = 720

SESSION_SECONDS = 35.0

# ============================================================================
# 3. GAZE TOOLS + CURSOR VISIBILITY
# ============================================================================
def norm_to_pix(nx, ny):
    px = (nx - 0.5) * ACTIVE_SCREEN_WIDTH
    py = (0.5 - ny) * ACTIVE_SCREEN_HEIGHT
    return px, py


def update_active_screen_size(win):
    global ACTIVE_SCREEN_WIDTH, ACTIVE_SCREEN_HEIGHT
    try:
        w, h = win.size
        ACTIVE_SCREEN_WIDTH = max(1.0, float(w))
        ACTIVE_SCREEN_HEIGHT = max(1.0, float(h))
    except Exception:
        ACTIVE_SCREEN_WIDTH = float(SCREEN_WIDTH)
        ACTIVE_SCREEN_HEIGHT = float(SCREEN_HEIGHT)


CURSOR_WATCHER = None
CURSOR_REVEALED = False


def init_hidden_cursor(win):
    global CURSOR_WATCHER, CURSOR_REVEALED
    CURSOR_WATCHER = event.Mouse(win=win)
    CURSOR_WATCHER.getRel()
    CURSOR_REVEALED = False
    win.mouseVisible = False


def reveal_cursor_if_moved(win, threshold=0.0):
    global CURSOR_REVEALED
    if CURSOR_WATCHER is None or CURSOR_REVEALED:
        return
    dx, dy = CURSOR_WATCHER.getRel()
    if abs(dx) > threshold or abs(dy) > threshold:
        win.mouseVisible = True
        CURSOR_REVEALED = True


class GazeCollector(spectrum.GazeStream):
    """Strumien gaze Tobii Pro Spectrum (logika SDK we wspolnym ../spectrum.py)."""

    def __init__(self, eyetracker, win=None):
        super().__init__(eyetracker)
        self._win = win

    def get_gaze_pix(self):
        g = self.latest_norm()  # None gdy brak waznych oczu lub probka starsza niz 100 ms
        if g is None:
            return None
        nx = max(-0.3, min(1.3, g[0]))
        ny = max(-0.3, min(1.3, g[1]))
        g = (nx, ny)
        return norm_to_pix(g[0], g[1])


def connect_eyetracker():
    trackery = spectrum.find_all_eyetrackers()
    if not trackery:
        return None

    et = trackery[0]
    print(f"Polaczono: {et.model} | SN: {et.serial_number}")
    return et


def run_calibration(win, eyetracker):
    calibration = tr.ScreenBasedCalibration(eyetracker)
    calibration.enter_calibration_mode()
    spectrum.guard_calibration(calibration)  # ESC -> wyjscie z trybu kalibracji

    points = [(0.5, 0.5), (0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
    dot = visual.Circle(win, radius=20, fillColor="white", lineColor=None)
    center = visual.Circle(win, radius=4, fillColor="black", lineColor=None)

    instrukcja = visual.TextStim(
        win,
        text="Patrz na punkty kalibracyjne. Nacisnij SPACJE, aby zaczac.",
        color="white",
        height=30,
        wrapWidth=1300,
    )
    instrukcja.draw()
    win.flip()
    keys = event.waitKeys(keyList=["space", "escape"])
    if "escape" in keys:
        calibration.leave_calibration_mode()
        return None

    ok_statuses = (
        tr.CALIBRATION_STATUS_SUCCESS,
        tr.CALIBRATION_STATUS_SUCCESS_LEFT_EYE,
        tr.CALIBRATION_STATUS_SUCCESS_RIGHT_EYE,
    )
    success = False
    for attempt in range(3):
        failed = []
        for nx, ny in points:
            px, py = norm_to_pix(nx, ny)
            # Let the eye land on the dot before sampling (~1 s).
            for frame in range(60):
                reveal_cursor_if_moved(win)
                dot.radius = max(8, 24 - frame * 0.27)
                dot.pos = (px, py)
                center.pos = (px, py)
                dot.draw()
                center.draw()
                win.flip()
                if "escape" in event.getKeys(["escape"]):
                    calibration.leave_calibration_mode()
                    return None

            collected = spectrum.collect_point(
                calibration, nx, ny, win, draw=lambda: (dot.draw(), center.draw()))
            if not collected:
                failed.append((nx, ny))

            dot.fillColor = "green" if collected else "red"
            dot.radius = 20
            dot.draw()
            center.draw()
            win.flip()
            core.wait(0.2)
            dot.fillColor = "white"

        result = spectrum.compute_and_apply(calibration, win)
        if not failed and result.status in ok_statuses:
            success = True
            break
        print(f"[APP4] Calibration attempt {attempt + 1} failed (missing: {failed}, status: {result.status}).")
        for nx, ny in points:
            calibration.discard_data(nx, ny)

    calibration.leave_calibration_mode()
    if not success:
        print("[APP4] Warning: calibration did not succeed. Continuing anyway.")
    return True


# ============================================================================
# 4. AUDIO ANALYSIS
# ============================================================================
class SpellingListener:
    """Offline English speech recognition (Vosk) limited to a tiny grammar.

    Triggers (-> `triggered = True`):
      * the letters S W P S spelled one by one ("es, double-you, pee, es"), or
      * "I love ..." followed by at least 2 of the letters within a few seconds
        ("I love S-W-P-S" - "I love" is easy to recognise, so the letters may be
        partially misheard).
    A tiny grammar makes recognition robust and fast; other speech becomes [unk].
    """

    TARGET = "SWPS"
    GRAMMAR = ["s", "es", "w", "double you", "p", "pee", "i love", "[unk]"]
    TOKEN_TO_LETTER = {"s": "S", "es": "S", "w": "W", "p": "P", "pee": "P"}
    LOVE_WINDOW_S = 6.0

    def __init__(self, samplerate=16000):
        self.sr = samplerate
        self.available = VOSK_OK and VOSK_MODEL_DIR.exists()
        self.status = "OK" if self.available else ("brak vosk" if not VOSK_OK else "brak modelu")
        self.heard = ""          # last recognised tokens, e.g. "SWP" or "<3SW"
        self.triggered = False
        self._love_t = None
        self._love_letters = 0
        self._q = queue.Queue(maxsize=200)
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self.available and self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()

    def feed(self, x_float32):
        """Called from the audio callback: keep it cheap, just queue int16 bytes."""
        if not self.available:
            return
        pcm = (np.clip(x_float32, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
        try:
            self._q.put_nowait(pcm)
        except queue.Full:
            pass

    def _run(self):
        try:
            model = vosk.Model(str(VOSK_MODEL_DIR))
            rec = vosk.KaldiRecognizer(model, self.sr, json.dumps(self.GRAMMAR))
        except Exception as exc:
            print(f"[APP4] Vosk init failed: {exc}")
            self.available = False
            self.status = "blad modelu"
            return
        print("[APP4] Vosk listening for S-W-P-S / I love S-W-P-S")
        while not self._stop.is_set():
            try:
                pcm = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            if rec.AcceptWaveform(pcm):
                self.handle_text(json.loads(rec.Result()).get("text", ""))

    def handle_text(self, text, now=None):
        now = time.perf_counter() if now is None else now
        # Multi-word grammar phrases -> single tokens before splitting.
        text = " " + text.strip() + " "
        text = text.replace(" double you ", " w ").replace(" i love ", " <3 ")
        tokens = text.split()
        if not any(t in self.TOKEN_TO_LETTER or t == "<3" for t in tokens):
            return
        for t in tokens:
            if t == "<3":
                self._love_t, self._love_letters = now, 0
                self.heard = (self.heard + "<3")[-10:]
            elif t in self.TOKEN_TO_LETTER:
                self.heard = (self.heard + self.TOKEN_TO_LETTER[t])[-10:]
                if self._love_t is not None and now - self._love_t <= self.LOVE_WINDOW_S:
                    self._love_letters += 1
        print(f"[APP4] Heard: {text.strip()!r}  (history: {self.heard})")
        if self.TARGET in self.heard.replace("<3", "") or self._love_letters >= 2:
            if not self.triggered:
                print("[APP4] S-W-P-S recognised -> letter brush ON")
            self.triggered = True
            self._love_t, self._love_letters = None, 0


class VoiceAnalyzer:
    """Continuously estimates RMS + spectral centroid + ZCR from microphone input."""

    def __init__(self, samplerate=16000, blocksize=1024):
        self.sr = samplerate
        self.blocksize = blocksize
        self.lock = threading.Lock()

        self.rms = 0.0
        self.centroid = 0.25  # normalized 0..1
        self.zcr = 0.1  # normalized 0..1

        self._stream = None
        self.available = False
        self.mode = "SIM"

        self._sim_t = 0.0
        self.listener = None  # optional SpellingListener fed with the same audio

    def _callback(self, indata, frames, callback_time, status):
        x = np.asarray(indata[:, 0], dtype=np.float32)
        if x.size == 0:
            return
        if self.listener is not None:
            self.listener.feed(x)

        x = np.nan_to_num(x, copy=False)
        rms = float(np.sqrt(np.mean(x * x) + 1e-12))

        xw = x * np.hanning(len(x))
        spec = np.abs(np.fft.rfft(xw))
        freqs = np.fft.rfftfreq(len(xw), d=1.0 / self.sr)

        ssum = float(np.sum(spec)) + 1e-12
        centroid_hz = float(np.sum(spec * freqs) / ssum)
        centroid_n = max(0.0, min(1.0, centroid_hz / (self.sr * 0.5)))

        z = np.sign(x)
        z[z == 0] = 1
        zcr = float(np.mean(np.abs(np.diff(z))) * 0.5)
        zcr = max(0.0, min(1.0, zcr))

        with self.lock:
            self.rms = 0.82 * self.rms + 0.18 * rms
            self.centroid = 0.75 * self.centroid + 0.25 * centroid_n
            self.zcr = 0.75 * self.zcr + 0.25 * zcr

    def start(self):
        if SOUNDDEVICE_OK:
            try:
                self._stream = sd.InputStream(
                    channels=1,
                    samplerate=self.sr,
                    blocksize=self.blocksize,
                    callback=self._callback,
                )
                self._stream.start()
                self.available = True
                self.mode = "MIC"
                return
            except Exception:
                self._stream = None

        self.available = False
        self.mode = "SIM"

    def stop(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def get_features(self, dt):
        if self.available:
            with self.lock:
                return self.rms, self.centroid, self.zcr

        # Soft procedural fallback when no microphone backend is available.
        self._sim_t += dt
        rms = 0.10 + 0.08 * (0.5 + 0.5 * math.sin(2.0 * math.pi * 0.42 * self._sim_t))
        centroid = 0.35 + 0.25 * (0.5 + 0.5 * math.sin(2.0 * math.pi * 0.17 * self._sim_t + 1.2))
        zcr = 0.18 + 0.10 * (0.5 + 0.5 * math.sin(2.0 * math.pi * 0.31 * self._sim_t + 0.4))
        return rms, centroid, zcr


# ============================================================================
# 5. PAINTING ENGINE
# ============================================================================
class GazeSmoother:
    """Adaptive smoothing + deadzone to remove fixation jitter while preserving flow."""

    def __init__(self):
        self.has_point = False
        self.x = 0.0
        self.y = 0.0
        self.last_t = None

    def update(self, px, py, now_t):
        if not self.has_point:
            self.x, self.y = px, py
            self.has_point = True
            self.last_t = now_t
            return self.x, self.y, 0.0

        dt = max(1e-4, now_t - (self.last_t or now_t))
        self.last_t = now_t

        dx = px - self.x
        dy = py - self.y
        dist = math.hypot(dx, dy)
        speed = dist / dt

        deadzone = 4.0
        if dist < deadzone:
            return self.x, self.y, speed

        alpha = 0.30 + min(0.50, speed / 1200.0)
        self.x += alpha * dx
        self.y += alpha * dy
        return self.x, self.y, speed


def build_base_canvas(w, h):
    yy = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    xx = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]

    r = 0.02 + 0.08 * (1.0 - yy) + 0.02 * np.sin(2 * math.pi * (xx * 0.7 + yy * 0.2))
    g = 0.03 + 0.07 * (1.0 - yy) + 0.02 * np.sin(2 * math.pi * (xx * 0.3 + yy * 0.5 + 0.2))
    b = 0.05 + 0.11 * (1.0 - yy)
    b = np.broadcast_to(b, (h, w))

    canvas = np.stack([r, g, b], axis=2)
    return np.clip(canvas, 0.0, 1.0).astype(np.float32)


def add_soft_stamp(canvas, cx, cy, radius, color_rgb, alpha, shape_kind="circle", texture=0.0):
    h, w, _ = canvas.shape
    if not np.isfinite(cx) or not np.isfinite(cy):
        return
    if not np.isfinite(radius) or radius <= 0:
        return
    if not np.isfinite(alpha):
        return

    rr = max(2.0, float(radius))
    cx = max(0.0, min(float(w - 1), float(cx)))
    cy = max(0.0, min(float(h - 1), float(cy)))

    x0 = max(0, int(cx - rr * 1.8))
    x1 = min(w, int(cx + rr * 1.8) + 1)
    y0 = max(0, int(cy - rr * 1.8))
    y1 = min(h, int(cy + rr * 1.8) + 1)
    if x1 <= x0 or y1 <= y0:
        return

    ys = np.arange(y0, y1, dtype=np.float32)[:, None]
    xs = np.arange(x0, x1, dtype=np.float32)[None, :]

    dx = xs - cx
    dy = ys - cy
    dist2 = dx ** 2 + dy ** 2
    sigma2 = (rr * 0.62) ** 2

    if shape_kind == "square":
        edge = np.maximum(np.abs(dx), np.abs(dy))
        mask = np.exp(-(edge ** 2) / (2.0 * sigma2))
    elif shape_kind == "diamond":
        manhattan = np.abs(dx) + np.abs(dy)
        mask = np.exp(-(manhattan ** 2) / (2.0 * sigma2))
    elif shape_kind == "ring":
        dist = np.sqrt(np.maximum(0.0, dist2))
        r0 = rr * (0.55 + 0.25 * texture)
        band = rr * (0.12 + 0.16 * texture)
        mask = np.exp(-((dist - r0) ** 2) / (2.0 * max(1e-6, band ** 2)))
    elif shape_kind == "star":
        ang = np.arctan2(dy, dx)
        dist = np.sqrt(np.maximum(0.0, dist2))
        petals = 5.0
        radial = 0.70 + 0.30 * np.cos(petals * ang)
        dist_mod = dist / np.maximum(1e-4, radial)
        mask = np.exp(-(dist_mod ** 2) / (2.0 * sigma2))
    else:
        mask = np.exp(-dist2 / (2.0 * sigma2))

    # Voice-driven grain texture on top of the base brush shape.
    if texture > 0.0:
        noise = np.random.uniform(1.0 - texture, 1.0, size=mask.shape).astype(np.float32)
        mask *= noise

    mask *= max(0.0, min(1.0, alpha))

    region = canvas[y0:y1, x0:x1, :]
    blend = mask[..., None]
    target = np.array(color_rgb, dtype=np.float32)[None, None, :]
    region[:] = region * (1.0 - blend) + target * blend


_LETTER_CACHE = {}
_LETTER_FONT_FILES = ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf")


def _letter_mask(letter, size_px):
    """Float32 alpha mask (0..1) with `letter` rendered at roughly size_px height."""
    size_px = int(max(16, min(400, round(size_px / 8.0) * 8)))  # quantize -> cache hits
    key = (letter, size_px)
    if key in _LETTER_CACHE:
        return _LETTER_CACHE[key]
    font = None
    for name in _LETTER_FONT_FILES:
        try:
            font = ImageFont.truetype(name, size_px)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    pad = size_px // 4
    img = Image.new("L", (size_px + 2 * pad, size_px + 2 * pad), 0)
    draw = ImageDraw.Draw(img)
    l, t, r, b = draw.textbbox((0, 0), letter, font=font)
    draw.text(((img.width - (r - l)) / 2 - l, (img.height - (b - t)) / 2 - t), letter, fill=255, font=font)
    mask = np.asarray(img, dtype=np.float32) / 255.0
    _LETTER_CACHE[key] = mask
    return mask


def add_letter_stamp(canvas, cx, cy, letter, size_px, color_rgb, alpha):
    """Blend a letter (centered at cx, cy; canvas row 0 = top) into the canvas."""
    if not PIL_OK or not (np.isfinite(cx) and np.isfinite(cy) and np.isfinite(size_px)):
        return
    mask = _letter_mask(letter, size_px) * max(0.0, min(1.0, alpha))
    h, w, _ = canvas.shape
    mh, mw = mask.shape
    x0, y0 = int(cx - mw / 2), int(cy - mh / 2)
    cx0, cy0 = max(0, x0), max(0, y0)
    cx1, cy1 = min(w, x0 + mw), min(h, y0 + mh)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    m = mask[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0][..., None]
    region = canvas[cy0:cy1, cx0:cx1, :]
    target = np.array(color_rgb, dtype=np.float32)[None, None, :]
    region[:] = region * (1.0 - m) + target * m


_HEART_CACHE = {}


def _heart_letter_masks(letter, size_px):
    """Cached masks on one padded grid (size_px = heart height), pre-combined so that a stamp is
         out = layer * A + Halo*c_halo + Spark*c_spark + Heart*c_heart + Letter*white
    Heart: implicit curve (x^2 + y^2 - 1)^3 - x^2 y^3 <= 0 (supersampled, smooth edges).
    Halo ("aureola"): blurred, enlarged heart glow + star sparkles on a ring."""
    from PIL import ImageFilter

    size_px = int(max(24, min(480, round(size_px / 8.0) * 8)))
    key = (letter, size_px)
    if key in _HEART_CACHE:
        return _HEART_CACHE[key]
    pad = int(size_px * 0.55)
    n = size_px + 2 * pad
    ss = 2  # supersampling
    g = np.linspace(-1.0, 1.0, n * ss, dtype=np.float32) * (n / size_px) * 1.25
    xx, yy = np.meshgrid(g, -g)  # y up
    yy = yy + 0.15               # optical centering of the heart
    f = (xx ** 2 + yy ** 2 - 1.0) ** 3 - (xx ** 2) * (yy ** 3)
    heart_img = Image.fromarray(((f <= 0) * 255).astype(np.uint8), "L").resize((n, n), Image.LANCZOS)
    heart = np.asarray(heart_img, dtype=np.float32) / 255.0

    halo_img = heart_img.filter(ImageFilter.MaxFilter(size=max(3, (size_px // 10) | 1)))
    halo_img = halo_img.filter(ImageFilter.GaussianBlur(radius=size_px * 0.16))
    halo = np.asarray(halo_img, dtype=np.float32) / 255.0
    halo = np.clip(halo * 1.4, 0.0, 1.0) * (1.0 - heart * 0.85) * 0.55  # glow mostly outside

    spark_canvas = np.zeros((n, n, 3), dtype=np.float32)
    rng = random.Random(hash(key))
    for _ in range(8):
        a = rng.uniform(0, 2 * math.pi)
        r = size_px * rng.uniform(0.62, 0.86)
        add_soft_stamp(spark_canvas, n / 2 + math.cos(a) * r, n / 2 + math.sin(a) * r,
                       rng.uniform(2.5, 2.5 + size_px * 0.035), (1.0, 1.0, 1.0), 0.85, shape_kind="star")
    spark = spark_canvas[..., 0]

    letter_mask = _letter_mask(letter, size_px * 0.52)
    lm = np.zeros((n, n), dtype=np.float32)
    lh, lw = letter_mask.shape
    oy = (n - lh) // 2 + int(size_px * 0.02)
    ox = (n - lw) // 2
    lm[max(0, oy):oy + lh, max(0, ox):ox + lw] = letter_mask[:min(lh, n - oy), :min(lw, n - ox)]

    ht = heart * 0.92
    lt = lm * 0.97
    keep_l = 1.0 - lt
    masks = {
        "A": ((1.0 - ht) * keep_l)[..., None],                 # how much of the layer survives
        "halo": (halo * (1.0 - ht) * keep_l)[..., None],
        "spark": (spark * (1.0 - ht) * keep_l)[..., None],
        "heart": (ht * keep_l)[..., None],
        "letter": lt[..., None],
    }
    _HEART_CACHE[key] = masks
    return masks


def add_heart_letter_stamp(layers, cx, cy, letter, size_px, color_rgb, hue=0.0):
    """Letter inside a heart with a glowing halo + sparkles, stamped into every layer in `layers`."""
    if not PIL_OK or not (np.isfinite(cx) and np.isfinite(cy) and np.isfinite(size_px)):
        return
    m = _heart_letter_masks(letter, size_px)
    halo_rgb = np.array(colorsys.hsv_to_rgb((hue + 0.12) % 1.0, 0.55, 1.0), dtype=np.float32)
    spark_rgb = np.array(colorsys.hsv_to_rgb((hue + 0.30) % 1.0, 0.30, 1.0), dtype=np.float32)
    heart_rgb = np.array(color_rgb, dtype=np.float32)
    add = m["halo"] * halo_rgb + m["spark"] * spark_rgb + m["heart"] * heart_rgb + m["letter"]
    A = m["A"]
    for canvas in layers:
        h, w, _ = canvas.shape
        mh, mw = A.shape[:2]
        x0, y0 = int(cx - mw / 2), int(cy - mh / 2)
        cx0, cy0 = max(0, x0), max(0, y0)
        cx1, cy1 = min(w, x0 + mw), min(h, y0 + mh)
        if cx1 <= cx0 or cy1 <= cy0:
            continue
        sy, sx = slice(cy0 - y0, cy1 - y0), slice(cx0 - x0, cx1 - x0)
        region = canvas[cy0:cy1, cx0:cx1, :]
        np.clip(region * A[sy, sx] + add[sy, sx], 0.0, 1.0, out=region)


def add_impressionistic_splatter(canvas, cx, cy, color_rgb, strength, shape_kind="circle", texture=0.0):
    if not np.isfinite(cx) or not np.isfinite(cy):
        return
    if not np.isfinite(strength):
        return

    strength = max(0.0, min(1.0, float(strength)))
    n = int(2 + strength * 8)
    for _ in range(n):
        angle = random.uniform(0.0, 2.0 * math.pi)
        dist = random.uniform(4.0, 95.0 + 250.0 * strength)
        rx = cx + math.cos(angle) * dist
        ry = cy + math.sin(angle) * dist
        radius = random.uniform(6.0, 14.0 + 30.0 * strength)
        alpha = random.uniform(0.10, 0.22 + 0.22 * strength)
        add_soft_stamp(canvas, rx, ry, radius, color_rgb, alpha, shape_kind=shape_kind, texture=texture)


def choose_brush_shape(rms, centroid, zcr):
    """Pick brush shape from audio features so voice changes texture and geometry."""
    if zcr > 0.22:
        candidates = ["star", "ring", "diamond", "circle"]
    elif centroid > 0.45:
        candidates = ["diamond", "square", "ring", "circle"]
    elif rms > 0.16:
        candidates = ["square", "circle", "diamond", "ring"]
    else:
        candidates = ["circle", "diamond", "square", "ring"]
    return random.choice(candidates)


def pix_to_canvas(px, py):
    if not np.isfinite(px) or not np.isfinite(py):
        return None

    nx = (px / ACTIVE_SCREEN_WIDTH) + 0.5
    ny = 0.5 - (py / ACTIVE_SCREEN_HEIGHT)
    nx = max(0.0, min(1.0, nx))
    ny = max(0.0, min(1.0, ny))

    x = nx * (CANVAS_W - 1)
    y = ny * (CANVAS_H - 1)
    return x, y


def save_canvas(canvas, out_path):
    arr = np.clip(canvas * 255.0, 0, 255).astype(np.uint8)
    if PIL_OK:
        Image.fromarray(arr, mode="RGB").save(str(out_path))
        return str(out_path)

    npy_path = out_path.with_suffix(".npy")
    np.save(npy_path, canvas)
    return str(npy_path)


# ============================================================================
# 6. VISUAL FLOW
# ============================================================================
def show_intro(win):
    text = visual.TextStim(
        win,
        text=(
            "APP 4: MALOWANIE GLOSEM I WZROKIEM\n\n"
            "Patrz tam, gdzie chcesz malowac.\n"
            "Mow do mikrofonu, a barwa i puls pedzla beda sie zmieniac\n"
            "na podstawie cech dzwieku (glosnosc + widmo), nie znaczenia slow.\n"
            "Powiedz po angielsku S-W-P-S (es, double-you, pee, es)\n"
            "albo I love S-W-P-S - pedzel zacznie malowac literami SWPS w serduszkach.\n\n"
            "Sterowanie:\n"
            "L = pedzel literowy wl./wyl.\n"
            "SPACE = zakoncz obraz\n"
            "C = wyczysc plotno\n"
            "S = zapisz obraz teraz\n"
            "ESC = wyjscie\n\n"
            "SPACJA = start"
        ),
        color="white",
        height=30,
        wrapWidth=1600,
    )
    text.draw()
    win.flip()
    keys = event.waitKeys(keyList=["space", "escape"])
    return "escape" not in keys


def show_outro(win, saved_path):
    txt = visual.TextStim(
        win,
        text=(
            "Gotowe. Twoj obraz zostal zapisany.\n\n"
            f"Plik: {saved_path}\n\n"
            "SPACJA = zakoncz"
        ),
        color="white",
        height=32,
        wrapWidth=1700,
    )

    while True:
        reveal_cursor_if_moved(win)
        txt.draw()
        win.flip()
        keys = event.getKeys(["space", "escape"])
        if keys:
            return


def show_checkpoint(win):
    txt = visual.TextStim(
        win,
        text=(
            "Kalibracja zakonczona.\n"
            "Zaraz startuje sesja malowania.\n\n"
            "ENTER = start sesji\n"
            "ESC = wyjscie"
        ),
        color="white",
        height=32,
        wrapWidth=1500,
    )
    txt.draw()
    win.flip()
    keys = event.waitKeys(keyList=["return", "escape"])
    return "escape" not in keys


def show_runtime_error(win, err):
    msg = str(err)
    if len(msg) > 500:
        msg = msg[:500] + "..."
    txt = visual.TextStim(
        win,
        text=(
            "APP 4 - blad wykonania\n\n"
            "Aplikacja nie zamknela sie cicho, tylko przechwycila blad.\n"
            "Skopiuj ten komunikat i wyslij prowadzacemu:\n\n"
            f"{msg}\n\n"
            "SPACJA = zamknij"
        ),
        color="white",
        height=26,
        wrapWidth=1700,
    )
    while True:
        txt.draw()
        win.flip()
        keys = event.getKeys(["space", "escape", "return"])
        if keys:
            return


def run_session(win, collector):
    update_active_screen_size(win)
    view_w = ACTIVE_SCREEN_WIDTH
    view_h = ACTIVE_SCREEN_HEIGHT

    base_canvas = build_base_canvas(CANVAS_W, CANVAS_H)
    canvas = base_canvas.copy()
    frame_tex = np.ascontiguousarray(np.flipud(np.clip(canvas * 2.0 - 1.0, -1.0, 1.0))).astype(np.float32)
    try:
        image = visual.ImageStim(
            win,
            image=frame_tex,
            units="pix",
            size=(view_w, view_h),
            pos=(0, 0),
            interpolate=True,
        )
    except Exception:
        image = visual.ImageStim(
            win,
            image=frame_tex,
            units="pix",
            size=(view_w, view_h),
            pos=(0, 0),
            interpolate=False,
        )

    vignette = None

    status = visual.TextStim(
        win,
        text="",
        color=[0.72, 0.72, 0.72],
        height=14,
        pos=(0, -0.46 * view_h),
        wrapWidth=1800,
    )

    smoother = GazeSmoother()
    voice = VoiceAnalyzer()
    speller = SpellingListener(samplerate=voice.sr)
    voice.listener = speller
    voice.start()
    speller.start()
    letter_mode = False      # True after S-W-P-S is heard (or L key)
    letter_idx = 0           # next letter of "SWPS" to stamp
    last_letter_xy = None    # spacing between letters along the gaze path

    hue = random.random()
    pulse_phase = 0.0

    clock = core.Clock()
    frame_clock = core.Clock()
    start_guard_until = 0.60

    saved_path = None
    render_warned = False
    brush_shape = "circle"
    status_update_t = 0.0
    smooth_rms = 0.0
    smooth_centroid = 0.0
    smooth_zcr = 0.0

    # Snapshots keep only the last ~5-10 s of painting: two layers are cleared
    # alternately every SNAP_WINDOW seconds, and the older one is saved.
    SNAP_WINDOW = 10.0
    recent = [base_canvas.copy(), base_canvas.copy()]
    recent_reset_t = [0.0, SNAP_WINDOW / 2.0]
    next_reset_t = [SNAP_WINDOW, SNAP_WINDOW * 1.5]

    def snapshot_canvas():
        return recent[0] if recent_reset_t[0] <= recent_reset_t[1] else recent[1]

    try:
        while True:
            dt = max(1e-4, frame_clock.getTime())
            frame_clock.reset()

            now_t = clock.getTime()
            if now_t > SESSION_SECONDS:
                break

            for i in (0, 1):
                if now_t >= next_reset_t[i]:
                    recent[i] = base_canvas.copy()
                    recent_reset_t[i] = now_t
                    next_reset_t[i] = now_t + SNAP_WINDOW

            reveal_cursor_if_moved(win)
            keys = event.getKeys(["escape", "space", "c", "s", "l"])
            if "l" in keys:
                letter_mode = not letter_mode
                last_letter_xy = None
            if speller.triggered:
                speller.triggered = False
                letter_mode = True
                last_letter_xy = None
            if "escape" in keys:
                return None
            # Ignore stale SPACE keypress right after calibration/instructions.
            if "space" in keys and now_t >= start_guard_until:
                break
            if "c" in keys:
                canvas = base_canvas.copy()
                recent = [base_canvas.copy(), base_canvas.copy()]
                recent_reset_t = [now_t, now_t]
                next_reset_t = [now_t + SNAP_WINDOW, now_t + SNAP_WINDOW]
            if "s" in keys:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                candidate = HERE / f"app4_artwork_{ts}.png"
                saved_path = save_canvas(snapshot_canvas(), candidate)

            gaze = collector.get_gaze_pix()
            rms, centroid, zcr = voice.get_features(dt)

            # Smooth readout to avoid a "dancing" status line.
            smooth_rms = 0.90 * smooth_rms + 0.10 * rms
            smooth_centroid = 0.90 * smooth_centroid + 0.10 * centroid
            smooth_zcr = 0.90 * smooth_zcr + 0.10 * zcr

            # High mic sensitivity: low noise floor, full brush response at quiet speech.
            rms_floor = 0.004
            rms_eff = max(0.0, rms - rms_floor)
            rms_drive = min(1.0, math.sqrt(rms_eff / 0.03))

            pulse_phase += dt * (1.5 + 6.0 * centroid)
            pulse = 0.5 + 0.5 * math.sin(pulse_phase * 2.0 * math.pi)

            hue = (hue + dt * (0.04 + 0.5 * centroid + 0.22 * zcr + 0.10 * pulse)) % 1.0
            sat = max(0.35, min(1.0, 0.45 + 0.9 * centroid))
            val = max(0.35, min(1.0, 0.45 + 1.15 * rms_drive + 0.2 * pulse))
            rgb = colorsys.hsv_to_rgb(hue, sat, val)
            brush_shape = choose_brush_shape(rms, centroid, zcr)
            brush_texture = max(0.0, min(0.65, 0.08 + 1.4 * zcr + 0.28 * rms_drive))

            if gaze is not None:
                sx, sy, speed = smoother.update(gaze[0], gaze[1], now_t)
                xy = pix_to_canvas(sx, sy)
                if xy is None:
                    continue
                cx, cy = xy

                # Bigger and more permanent-feeling blobs.
                brush_radius = 22.0 + 110.0 * rms_drive + 18.0 * pulse + min(30.0, speed * 0.010)
                brush_alpha = max(0.12, min(0.62, 0.16 + 0.36 * rms_drive + 0.16 * pulse))

                if letter_mode:
                    # Letters S W P S in hearts (with a halo) along the gaze path;
                    # voice loudness sets their size.
                    letter_size = 70.0 + 130.0 * rms_drive + 12.0 * pulse
                    moved = last_letter_xy is None or math.hypot(
                        cx - last_letter_xy[0], cy - last_letter_xy[1]) >= 0.85 * letter_size
                    if moved:
                        letter = SpellingListener.TARGET[letter_idx % len(SpellingListener.TARGET)]
                        letter_idx += 1
                        last_letter_xy = (cx, cy)
                        add_heart_letter_stamp((canvas, recent[0], recent[1]),
                                               cx, cy, letter, letter_size, rgb, hue=hue)
                    blob_targets = ()
                else:
                    blob_targets = (canvas, recent[0], recent[1])

                for target in blob_targets:
                    add_soft_stamp(
                        target,
                        cx,
                        cy,
                        brush_radius,
                        rgb,
                        brush_alpha,
                        shape_kind=brush_shape,
                        texture=brush_texture,
                    )
                    add_impressionistic_splatter(
                        target,
                        cx,
                        cy,
                        rgb,
                        min(1.0, 0.25 + rms_drive * 1.7),
                        shape_kind=brush_shape,
                        texture=brush_texture,
                    )

            # Keep strokes permanent; this app should behave like a paintbrush.
            canvas[:] = np.clip(canvas, 0.0, 1.0)

            frame_tex = np.ascontiguousarray(np.flipud(np.clip(canvas * 2.0 - 1.0, -1.0, 1.0))).astype(np.float32)
            try:
                image.image = frame_tex
                image.draw()
            except Exception as exc:
                if not render_warned:
                    print(f"[APP4] Warning: texture update fallback enabled ({exc})")
                    render_warned = True
                image = visual.ImageStim(
                    win,
                    image=frame_tex,
                    units="pix",
                    size=(view_w, view_h),
                    pos=(0, 0),
                    interpolate=False,
                )
                image.draw()
            if vignette is not None:
                vignette.draw()

            if now_t >= status_update_t:
                status.text = (
                    f"MIC: {voice.mode} | glosnosc={smooth_rms:.3f}  widmo={smooth_centroid:.3f}"
                    f"  ziarnistosc={smooth_zcr:.3f}"
                    f" | pedzel: {'LITERY SWPS' if letter_mode else brush_shape}"
                    f" | mowa: {speller.status} [{speller.heard}]"
                    f" | czas: {int(max(0, SESSION_SECONDS - now_t))}s"
                )
                status_update_t = now_t + 0.18
            status.draw()

            win.flip()
    finally:
        voice.stop()
        speller.stop()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = HERE / f"app4_artwork_{ts}.png"
    saved_path = save_canvas(snapshot_canvas(), candidate)

    return saved_path


# ============================================================================
# 7. MAIN
# ============================================================================
def main():
    eyetracker = connect_eyetracker()
    if eyetracker is None:
        print("Brak eye-trackera. Podlacz Tobii i uruchom ponownie.")
        return

    win = visual.Window(
        size=(SCREEN_WIDTH, SCREEN_HEIGHT),
        units="pix",
        fullscr=FULLSCREEN,
        color=[-0.96, -0.96, -0.96],
        waitBlanking=True,
    )
    spectrum.install_escape(win)  # ESC przerywa eksperyment w kazdym momencie

    update_active_screen_size(win)

    init_hidden_cursor(win)

    try:
        if not show_intro(win):
            return

        cal_result = run_calibration(win, eyetracker)
        if cal_result is None:
            print("Kalibracja anulowana.")
            return

        # Flush key events so held SPACE from previous screens does not end session.
        event.clearEvents(eventType="keyboard")
        core.wait(0.15)
        event.clearEvents(eventType="keyboard")

        if not show_checkpoint(win):
            return

        event.clearEvents(eventType="keyboard")

        collector = GazeCollector(eyetracker, win=win)
        collector.start()

        try:
            try:
                saved_path = run_session(win, collector)
            except Exception as exc:
                print(f"[APP4] Runtime error: {exc}")
                show_runtime_error(win, exc)
                return
            if saved_path is None:
                return
            show_outro(win, saved_path)
        finally:
            collector.stop()

    finally:
        win.close()
        core.quit()


if __name__ == "__main__":
    main()
