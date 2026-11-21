#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PROJEKT 1 - GAZE CHOICE (szybkie demo, Krajbich i in., 2010)

Ustalenia grupy z projekt-1-brief.md:
  - pary neutralnych produktow, jedna para na wybor,
  - strona lewa/prawa losowana i zrownowazona (polowa par zamieniona),
  - punkt centralny 800 ms -> para do odpowiedzi (maks. 10 s) -> "Zapisano" 500 ms,
  - odpowiedz: strzalka lewo/prawo albo F/J,
  - wynik: czas patrzenia na opcje wybrana vs niewybrana, ostatnia sekunda, czas decyzji.

Bez kalibracji w aplikacji: tracker uzywa kalibracji zapisanej wczesniej
w Tobii Pro Eye Tracker Manager. Wzrok mierzony w tle (bez kropki). ESC = koniec.
Test bez trackera (mysz = wzrok):  python projekt1_gaze_choice.py --sim
"""
import csv
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

# Pary neutralnych produktow - podmien na wlasne (brief: 12-20 par)
PAIRS = [
    ("Kubek", "Szklanka"),
    ("Notes", "Zeszyt"),
    ("Dlugopis", "Olowek"),
    ("Recznik", "Koc"),
    ("Lampka", "Swieca"),
    ("Plecak", "Torba"),
]
FIX_S, MAX_RT_S, ITI_S = 0.8, 10.0, 0.5
SIM = "--sim" in sys.argv
FONT = "Arial"
KEYS = {"left": "left", "f": "left", "right": "right", "j": "right"}


class Gaze(spectrum.GazeStream):
    """Strumien z szablonu + lista wszystkich probek (czas SDK w us, (x, y) albo None)."""
    def __init__(self, et):
        super().__init__(et)
        self.samples = []

    def on_sample(self, d, g):
        self.samples.append((d["system_time_stamp"], g))

    def poll(self):
        pass


class MouseGaze:
    """Tylko test: pozycja myszy = wzrok (probka co klatke)."""
    def __init__(self, win):
        self.win, self.mouse, self.samples = win, event.Mouse(win=win, visible=False), []

    def start(self): pass
    def stop(self): pass

    def poll(self):
        x, y = self.mouse.getPos()
        w, h = self.win.size
        self.samples.append((tr.get_system_time_stamp(), (x / w + 0.5, 0.5 - y / h)))


def text(win, msg, pos=(0, 0), height=32, color="white"):
    return visual.TextStim(win, text=msg, pos=pos, height=height, color=color, font=FONT,
                           wrapWidth=win.size[0] * 0.85)


def looking_time(win, samples, t0, t1, size, x0):
    """Czas patrzenia [ms] na lewa i prawa opcje w oknie [t0, t1]."""
    w, h = win.size
    out = {"left": 0.0, "right": 0.0}
    s = [p for p in samples if t0 <= p[0] <= t1]
    for (ta, g), (tb, _) in zip(s, s[1:]):
        if g is None or tb - ta > 100_000:  # brak oka / luka > 100 ms
            continue
        px, py = (g[0] - 0.5) * w, (0.5 - g[1]) * h
        for side, cx in (("left", -x0), ("right", x0)):
            if abs(px - cx) <= size / 2 and abs(py) <= size / 2:
                out[side] += (tb - ta) / 1000
    return out


def one_choice(win, gaze, left, right, size, x0):
    """Punkt centralny -> para do odpowiedzi -> 'Zapisano'. Zwraca slownik z wynikiem."""
    items = []
    for name, cx in ((left, -x0), (right, x0)):
        items += [visual.Rect(win, size, size, pos=(cx, 0), fillColor="#9aa0a8", lineColor=None),
                  text(win, name, pos=(cx, 0), height=56, color="#202020")]
    items.append(text(win, "<-  lub  F                    J  lub  ->", pos=(0, -size * 0.75),
                      height=24, color="grey"))

    t0 = core.getTime()
    while core.getTime() - t0 < FIX_S:
        text(win, "+", height=60).draw()
        win.flip()
        gaze.poll()

    event.clearEvents()
    t_on = tr.get_system_time_stamp()
    t_on_app = core.getTime()
    key = None
    while key is None and core.getTime() - t_on_app < MAX_RT_S:
        for i in items:
            i.draw()
        win.flip()
        gaze.poll()
        keys = event.getKeys(keyList=list(KEYS))
        key = keys[0] if keys else None
    t_end = tr.get_system_time_stamp()

    t0 = core.getTime()
    while core.getTime() - t0 < ITI_S:
        text(win, "Zapisano", height=30, color="grey").draw()
        win.flip()
        gaze.poll()

    side = KEYS.get(key, "none")
    total = looking_time(win, gaze.samples, t_on, t_end, size, x0)
    last = looking_time(win, gaze.samples, t_end - 1_000_000, t_end, size, x0)
    return {"left": left, "right": right, "choice_side": side,
            "choice": left if side == "left" else right if side == "right" else "",
            "rt_ms": round((t_end - t_on) / 1000) if key else "",
            "look_left_ms": round(total["left"]), "look_right_ms": round(total["right"]),
            "last1s_left_ms": round(last["left"]), "last1s_right_ms": round(last["right"])}


def show_result(win, rows):
    h = win.size[1]
    ok = [r for r in rows if r["choice_side"] != "none"]
    if not ok:
        text(win, "Brak odpowiedzi - nie ma wyniku.\n\nSPACJA = koniec").draw()
        win.flip()
        event.waitKeys(keyList=["space"])
        return
    oth = {"left": "right", "right": "left"}
    ch = sum(r[f"look_{r['choice_side']}_ms"] for r in ok) / len(ok)
    un = sum(r[f"look_{oth[r['choice_side']]}_ms"] for r in ok) / len(ok)
    match = sum(r[f"look_{r['choice_side']}_ms"] > r[f"look_{oth[r['choice_side']]}_ms"] for r in ok)
    lc = sum(r[f"last1s_{r['choice_side']}_ms"] for r in ok)
    lu = sum(r[f"last1s_{oth[r['choice_side']]}_ms"] for r in ok)
    share = 100 * lc / (lc + lu) if lc + lu else 50
    rt = sum(r["rt_ms"] for r in ok) / len(ok) / 1000

    items = [text(win, "WYNIK", pos=(0, h * 0.42), height=48),
             text(win, f"Dluzej patrzyles/as na wybrana opcje w {match} z {len(ok)} wyborow.\n"
                       f"W ostatniej sekundzie przed wyborem {share:.0f}% patrzenia bylo na wybranej "
                       f"(50% = bez roznicy).     Sredni czas decyzji: {rt:.1f} s",
                  pos=(0, h * 0.30), height=26)]
    top = max(ch, un) or 1
    for label, val, cx, col in (("wybrana", ch, -h * 0.25, "#5ec8ff"), ("niewybrana", un, h * 0.25, "#777777")):
        bar = h * 0.30 * val / top
        items += [visual.Rect(win, h * 0.15, max(bar, 2), pos=(cx, -h * 0.12 + bar / 2), fillColor=col, lineColor=None),
                  text(win, f"{label}\n{val / 1000:.1f} s", pos=(cx, -h * 0.20), height=28)]
    verdict = ("Wzrok czesciej byl na opcji, ktora potem wybrales/as - jak w badaniu Krajbich i in. (2010)."
               if ch > un else "Tym razem dluzej patrzyles/as na opcje, ktorej nie wybrales/as.")
    items.append(text(win, verdict + "\n\nSPACJA = koniec", pos=(0, -h * 0.36), height=28))
    for i in items:
        i.draw()
    win.flip()
    event.waitKeys(keyList=["space"])


def main():
    et = None
    if not SIM:
        found = [t for t in spectrum.find_all_eyetrackers() if "spectrum" in (t.model or "").lower()]
        if not found:
            print("Nie znaleziono Tobii Pro Spectrum. (Test bez trackera: --sim)")
            return
        et = found[0]

    win = visual.Window(fullscr=True, color="#202020", units="pix")
    win.mouseVisible = False
    spectrum.install_escape(win)

    text(win, "Wybierz opcje, ktora wolisz. Nie ma dobrej lub zlej odpowiedzi.\n\n"
              "Ogladaj pare tak dlugo, jak potrzebujesz, a nastepnie nacisnij\n"
              "strzalke w lewo lub w prawo (albo F / J).\n\n"
              "Przed kazda para patrz na krzyzyk na srodku.\n\nSPACJA = start").draw()
    win.flip()
    event.waitKeys(keyList=["space"])

    gaze = MouseGaze(win) if SIM else Gaze(et)
    gaze.start()
    if not SIM:
        gaze.wait_for_data(timeout=2.0)

    # losowa kolejnosc par, polowa par zamieniona stronami (kontrbalans)
    order = list(PAIRS)
    random.shuffle(order)
    flips = [i % 2 == 1 for i in range(len(order))]
    random.shuffle(flips)

    size, x0 = win.size[1] * 0.4, win.size[0] * 0.25
    rows = []
    for (a, b), flip in zip(order, flips):
        left, right = (b, a) if flip else (a, b)
        rows.append(one_choice(win, gaze, left, right, size, x0))
    gaze.stop()

    out = HERE / "data"
    out.mkdir(exist_ok=True)
    path = out / f"wynik_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=["mode"] + list(rows[0]))
        wr.writeheader()
        wr.writerows({"mode": "simulation" if SIM else "hardware", **r} for r in rows)
    print(f"Zapisano: {path}")

    show_result(win, rows)
    win.close()
    core.quit()


if __name__ == "__main__":
    main()
