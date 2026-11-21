# -*- coding: utf-8 -*-
"""
Przygotowanie bodzcow: ujednolicenie tla do jednego poziomu (RGB 230,230,230)
i wspolne plotno 1536x1024 px. Oryginaly w badania/ NIE sa zmieniane.

Uzycie (potrzebne: opencv-python-headless, pillow, numpy):
    python prepare_stimuli.py            -> stimuli/*.png + stimuli.json
    python prepare_stimuli.py --preview  -> dodatkowo stimuli_preview.png (kontrolka wzrokowa)

Pseudonimy: REAL_01..06 (natural face), AI_01..06 (ai face), kolejnosc wg nazwy pliku.
Nazwy oryginalow NIE trafiaja do stimuli.json - tylko skrot SHA-256 pliku.
"""
import hashlib, json, sys
from pathlib import Path
import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
SRC = HERE.parent.parent / "badania"
OUT = HERE / "stimuli"
BG_TOL = 17                   # max. roznica koloru od modelu tla (0-255), by piksel uznac za tlo
BG = 230                      # jeden poziom tla (RGB 230,230,230)
W, H = 1536, 1024             # wspolne plotno (rozmiar obrazow AI)
SETS = {"REAL": SRC / "natural face", "AI": SRC / "ai face"}


def _bg_model(small):
    """Dopasowuje gladki model tla (wielomian 2. stopnia na kanal) do pikseli przy bokach i gorze kadru."""
    sh, sw = small.shape[:2]
    yy, xx = np.mgrid[0:sh, 0:sw]
    border = np.zeros((sh, sw), bool)
    border[:, : int(0.08 * sw)] = True
    border[:, int(0.92 * sw):] = True
    border[: int(0.04 * sh), :] = True
    gray = small.mean(axis=2)
    use = border & (gray > 150)
    u, v = xx / sw, yy / sh
    basis = np.stack([np.ones_like(u), u, v, u * u, v * v, u * v], -1)
    model = np.zeros(small.shape, np.float32)
    for c in range(3):
        y = small[..., c].astype(np.float32)
        sel = use.copy()
        for _ in range(4):                      # iteracyjne odrzucanie odstajacych
            coef, *_ = np.linalg.lstsq(basis[sel], y[sel], rcond=None)
            fit = basis @ coef
            sel = use & (np.abs(y - fit) < 12)
        model[..., c] = fit
    return model


def person_mask(img):
    """Tlo = piksele bliskie modelowi tla i polaczone z brzegiem kadru; reszta = osoba z ubraniem."""
    h, w = img.shape[:2]
    scale = 800 / max(h, w)
    small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    small = cv2.GaussianBlur(small, (0, 0), 0.8)
    dist = np.abs(small.astype(np.float32) - _bg_model(small)).max(axis=2)
    cand = (dist < BG_TOL).astype(np.uint8)
    n, lab = cv2.connectedComponents(cand, connectivity=4)
    touch = set(lab[:, 0]) | set(lab[:, -1]) | set(lab[0, :])
    touch |= {l for l in lab[-1, :] if l}
    touch.discard(0)
    bgm = np.isin(lab, list(touch))
    fg = (~bgm).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg)
    if n > 1:
        fg = (lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    inv = 1 - fg
    n, lab, stats, _ = cv2.connectedComponentsWithStats(inv)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < 0.02 * sh * sw:
            fg[lab == i] = 1
    fg = cv2.resize(fg.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
    return cv2.GaussianBlur((fg > 0.5).astype(np.float32), (0, 0), 1.2)


# Reguly AOI - IDENTYCZNE dla wszystkich 12 bodzcow, wzgledem ramki twarzy (detektor Haara).
# (x, y, w, h) = ramka twarzy; wspolrzedne w pikselach plotna 1536x1024.
AOI_RULES = {
    "face":  (0.00, 1.00, 0.00, 1.00),   # x0, x1, y0, y1 jako ulamki ramki twarzy
    "eyes":  (0.05, 0.95, 0.15, 0.50),
    "lower": (0.05, 0.95, 0.55, 1.00),   # usta i dolna czesc twarzy
}


def detect_face_box(canvas):
    gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))
    faces = cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=6, minSize=(300, 300))
    if len(faces) == 0:
        raise RuntimeError("nie wykryto twarzy")
    return [int(v) for v in max(faces, key=lambda f: f[2] * f[3])]


def aoi_from_face(box):
    x, y, w, h = box
    out = {"face_box_detected": [x, y, w, h]}
    for name, (x0, x1, y0, y1) in AOI_RULES.items():
        out[name] = [round(x + x0 * w), round(y + y0 * h), round(x + x1 * w), round(y + y1 * h)]  # l, t, r, b
    out["background"] = "everything outside the 'face' rectangle (hair, clothing, backdrop, screen outside image)"
    return out


def process(path):
    raw = path.read_bytes()
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    alpha = person_mask(img)[..., None]
    bg = np.full_like(img, BG, dtype=np.uint8)
    out = (img * alpha + bg * (1 - alpha)).clip(0, 255).astype(np.uint8)
    # wspolne plotno: skala do wysokosci H, boki dopelnione tym samym tlem
    s = H / h
    nw = int(round(w * s))
    out = cv2.resize(out, (nw, H), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    canvas = np.full((H, W, 3), BG, np.uint8)
    if nw >= W:
        x0 = (nw - W) // 2
        canvas[:] = out[:, x0:x0 + W]
    else:
        x0 = (W - nw) // 2
        canvas[:, x0:x0 + nw] = out
    return canvas, hashlib.sha256(raw).hexdigest(), (w, h), (nw, H, x0)


def main():
    OUT.mkdir(exist_ok=True)
    meta, previews = [], []
    for cat, folder in SETS.items():
        files = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
        assert len(files) == 6, f"{folder}: oczekiwano 6 plikow, jest {len(files)}"
        for i, p in enumerate(files, 1):
            sid = f"{cat}_{i:02d}"
            canvas, sha, (ow, oh), (nw, nh, x0) = process(p)
            cv2.imwrite(str(OUT / f"{sid}.png"), canvas)
            gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
            bgpix = canvas[5, 5].tolist()[::-1]
            meta.append({
                "stimulus_id": sid, "category": cat, "filename": f"stimuli/{sid}.png",
                "original_sha256": sha, "original_size_px": [ow, oh],
                "width_px": W, "height_px": H,
                "mean_brightness": round(float(gray.mean()), 2),
                "background_rgb": bgpix,
                "source": "provided by researcher (WhatsApp JPEG; origin not documented)",
                "license_or_consent_status": "researcher stated on 2026-11-21 that permission/consent is held; no document attached",
                "generator_name_and_version": ("unknown - not provided" if cat == "AI" else None),
                "mask_or_roi_coordinates": aoi_from_face(detect_face_box(canvas)),
                "processing": "GrabCut person mask; background replaced with RGB(230,230,230); scaled to height 1024, padded with same background to 1536x1024",
            })
            ov = canvas.copy()
            for name, col in (("face", (0, 160, 0)), ("eyes", (0, 0, 220)), ("lower", (220, 0, 0))):
                l, t, r, b = meta[-1]["mask_or_roi_coordinates"][name]
                cv2.rectangle(ov, (l, t), (r, b), col, 3)
            previews.append(cv2.resize(ov, (384, 256), interpolation=cv2.INTER_AREA))
    (HERE / "stimuli.json").write_text(json.dumps(
        {"background_level": BG, "canvas_px": [W, H], "stimuli": meta}, indent=2, ensure_ascii=False), encoding="utf-8")
    if "--preview" in sys.argv:
        rows = [np.hstack(previews[r * 4:(r + 1) * 4]) for r in range(3)]
        cv2.imwrite(str(HERE / "stimuli_preview.png"), np.vstack(rows))
    print(f"OK: {len(meta)} bodzcow -> {OUT}")


if __name__ == "__main__":
    main()
