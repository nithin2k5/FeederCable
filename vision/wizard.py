"""
vision/wizard.py
================
Operator flow for teaching a part: capture -> draw ROI once -> review -> build.

The ROI is drawn on a single anchor image and propagated to the whole set; the
review step shows every crop after alignment so a bad reference can be dropped
before it reaches the model. Nobody draws twenty boxes.
"""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from . import capture, config
from .model import ROISpec
from .teach import (MIN_NG_IMAGES, MIN_OK_IMAGES, MIN_ALIGNMENT_SCORE,
                    TeachError, align_templates, build_part_model)

_BG, _PANEL, _FG = "#1e1e1e", "#2b2b2b", "#e8e8e8"


class TeachWizard(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Teach Part — Vision")
        self.geometry("1040x660")
        self.configure(bg=_BG)

        self.cfg = config.load()
        self.ok_images: list = []
        self.ng_images: list = []
        self.roi = None
        self._drag = None
        self._photo = None
        self._stream = None
        self._live = False

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._start_preview()

    # ── layout ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        left = tk.Frame(self, bg=_BG)
        left.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        self.canvas = tk.Label(left, bg="black", cursor="crosshair",
                               text="[ no image ]", fg="#666")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._down)
        self.canvas.bind("<B1-Motion>", self._move)
        self.canvas.bind("<ButtonRelease-1>", self._up)

        self.hint = tk.Label(left, bg=_BG, fg="#8ab4f8", font=("Arial", 9),
                             text="Drag on the image to draw the ROI around the part.")
        self.hint.pack(fill="x", pady=(6, 0))

        right = tk.Frame(self, bg=_PANEL, width=310)
        right.pack(side="right", fill="y", padx=8, pady=8)
        right.pack_propagate(False)

        def head(t):
            tk.Label(right, text=t, bg=_PANEL, fg="#8ab4f8",
                     font=("Arial", 10, "bold")).pack(anchor="w", padx=12, pady=(12, 2))

        def btn(txt, cmd, colour="#3a3a3a"):
            b = tk.Button(right, text=txt, command=cmd, bg=colour, fg=_FG, bd=0,
                          font=("Arial", 9, "bold"), pady=6, cursor="hand2")
            b.pack(fill="x", padx=12, pady=2)
            return b

        tk.Label(right, text="Teach Part", bg=_PANEL, fg=_FG,
                 font=("Arial", 14, "bold")).pack(pady=(14, 4))

        head("1 · Part number")
        self.ent_part = tk.Entry(right, bg="#111", fg=_FG, insertbackground=_FG,
                                 font=("Consolas", 12), justify="center")
        self.ent_part.pack(fill="x", padx=12, pady=2)

        head(f"2 · OK samples  (>= {MIN_OK_IMAGES})")
        tk.Label(right, bg=_PANEL, fg="#999", font=("Arial", 8), justify="left",
                 text="Re-seat the part between shots.\nUse several physical samples.",
                 ).pack(anchor="w", padx=12)
        btn("Capture OK from camera", lambda: self._capture(self.ok_images), "#1b5e20")
        btn("Load OK images…", lambda: self._load(self.ok_images))
        self.lbl_ok = tk.Label(right, text="0 loaded", bg=_PANEL, fg="#999",
                               font=("Arial", 9))
        self.lbl_ok.pack(anchor="w", padx=12)

        head(f"3 · NG samples  (>= {MIN_NG_IMAGES})")
        tk.Label(right, bg=_PANEL, fg="#999", font=("Arial", 8), justify="left",
                 text="Empty jig. These set the threshold.").pack(anchor="w", padx=12)
        btn("Capture NG from camera", lambda: self._capture(self.ng_images), "#8d3b00")
        btn("Load NG images…", lambda: self._load(self.ng_images))
        self.lbl_ng = tk.Label(right, text="0 loaded", bg=_PANEL, fg="#999",
                               font=("Arial", 9))
        self.lbl_ng.pack(anchor="w", padx=12)

        head("4 · ROI")
        self.lbl_roi = tk.Label(right, text="not drawn", bg=_PANEL, fg="#ff9800",
                                font=("Arial", 9, "bold"))
        self.lbl_roi.pack(anchor="w", padx=12)
        btn("Review aligned crops", self.review)

        head("5 · Build")
        self.btn_build = btn("Build & Save model", self.build, "#0d47a1")

        self.status = tk.Label(right, text="", bg=_PANEL, fg="#999", wraplength=280,
                               justify="left", font=("Arial", 8))
        self.status.pack(fill="x", padx=12, pady=(14, 0))

    # ── preview ─────────────────────────────────────────────────────────────

    def _start_preview(self):
        idx = self.cfg.get("camera_index", -1)
        if idx < 0:
            self._say("No camera configured — load images from disk instead.")
            return

        def run():
            s = capture.acquire(idx, self.cfg.get("frame_w", 640),
                                self.cfg.get("frame_h", 480),
                                self.cfg.get("camera_settings") or None)
            if s is None or not s.wait_until_open():
                if s:
                    s.release()
                self._say("Camera unavailable — load images from disk instead.")
                return
            self._stream, self._live = s, True
            self.after(0, self._tick)

        threading.Thread(target=run, daemon=True).start()

    def _tick(self):
        if not self._live or self._stream is None:
            return
        frame = self._stream.latest()
        if frame is not None:
            self._show(frame)
        self.after(40, self._tick)

    def _anchor(self):
        return self.ok_images[0] if self.ok_images else None

    def _freeze(self):
        """Stop the live feed so the operator can draw on a still anchor."""
        self._live = False
        if self._anchor() is not None:
            self._show(self._anchor())

    # ── image display ───────────────────────────────────────────────────────

    def _show(self, frame):
        disp = frame.copy()
        if disp.ndim == 2:
            disp = cv2.cvtColor(disp, cv2.COLOR_GRAY2BGR)
        if self.roi:
            r = self.roi
            cv2.rectangle(disp, (r["x"], r["y"]),
                          (r["x"] + r["w"], r["y"] + r["h"]), (0, 255, 0), 2)
        elif self._drag:
            cv2.rectangle(disp, self._drag[0], self._drag[1], (255, 120, 0), 2)

        img = Image.fromarray(cv2.cvtColor(disp, cv2.COLOR_BGR2RGB))
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw > 10 and ch > 10:
            img.thumbnail((cw, ch), Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self.canvas.config(image=self._photo, text="")

    def _to_frame_coords(self, ev):
        src = self._anchor() if not self._live else (
            self._stream.latest() if self._stream else None)
        if src is None:
            return None
        fh, fw = src.shape[:2]
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            return None
        scale = min(cw / fw, ch / fh)
        dw, dh = int(fw * scale), int(fh * scale)
        ox, oy = (cw - dw) // 2, (ch - dh) // 2
        if not (ox <= ev.x <= ox + dw and oy <= ev.y <= oy + dh):
            return None
        return int((ev.x - ox) / scale), int((ev.y - oy) / scale)

    def _down(self, ev):
        if not self.ok_images:
            self._say("Capture or load OK images first.")
            return
        self._freeze()
        p = self._to_frame_coords(ev)
        if p:
            self.roi = None
            self._drag = (p, p)
            self._show(self._anchor())

    def _move(self, ev):
        if not self._drag:
            return
        p = self._to_frame_coords(ev)
        if p:
            self._drag = (self._drag[0], p)
            self._show(self._anchor())

    def _up(self, ev):
        if not self._drag:
            return
        (x1, y1), (x2, y2) = self._drag
        self._drag = None
        x, y = min(x1, x2), min(y1, y2)
        w, h = abs(x2 - x1), abs(y2 - y1)
        if w < 20 or h < 20:
            self.lbl_roi.config(text="box too small", fg="#ff5555")
        else:
            self.roi = {"x": x, "y": y, "w": w, "h": h}
            self.lbl_roi.config(text=f"{w}x{h} at ({x},{y})", fg="#76ff03")
        self._show(self._anchor())

    # ── sample collection ───────────────────────────────────────────────────

    def _spec(self):
        return ROISpec(name="part", **self.roi, search_margin=12)

    def _counts(self):
        self.lbl_ok.config(text=f"{len(self.ok_images)} loaded")
        self.lbl_ng.config(text=f"{len(self.ng_images)} loaded")

    def _say(self, msg):
        try:
            self.after(0, lambda: self.status.config(text=msg))
        except Exception:
            pass

    def _capture(self, bucket):
        if self._stream is None:
            self._say("No camera. Use the Load buttons.")
            return
        frame = self._stream.latest()
        if frame is None:
            self._say("No frame available yet.")
            return
        bucket.append(frame.copy())
        self._counts()
        self._say(f"Captured. OK={len(self.ok_images)} NG={len(self.ng_images)}")

    def _load(self, bucket):
        paths = filedialog.askopenfilenames(
            parent=self, title="Select images",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")])
        added = 0
        for p in paths:
            img = cv2.imread(p)
            if img is not None:
                bucket.append(img)
                added += 1
        self._counts()
        self._say(f"Loaded {added} image(s).")
        if bucket is self.ok_images and self.ok_images:
            self._freeze()

    # ── review ──────────────────────────────────────────────────────────────

    def review(self):
        if not self.roi:
            self._say("Draw the ROI first.")
            return
        if len(self.ok_images) < 2:
            self._say("Need at least 2 OK images to review.")
            return

        spec = self._spec()
        crops, offsets, scores = align_templates(self.ok_images, spec)

        win = tk.Toplevel(self)
        win.title("Aligned crops — uncheck any that are wrong")
        win.configure(bg=_BG)
        tk.Label(win, bg=_BG, fg="#8ab4f8", font=("Arial", 9), justify="left",
                 text=("Each crop is the ROI after alignment. Low scores or shifted "
                       f"crops mean the part was not found (< {MIN_ALIGNMENT_SCORE} "
                       "is dropped automatically).")).pack(anchor="w", padx=10, pady=8)

        grid = tk.Frame(win, bg=_BG)
        grid.pack(padx=10, pady=6)
        self._review_refs = []
        keep_vars = []

        for i, (crop, off, sc) in enumerate(zip(crops, offsets, scores)):
            cell = tk.Frame(grid, bg=_PANEL, bd=1, relief="solid")
            cell.grid(row=i // 6, column=i % 6, padx=4, pady=4)
            img = Image.fromarray(crop)
            img.thumbnail((120, 120), Image.Resampling.LANCZOS)
            ph = ImageTk.PhotoImage(img)
            self._review_refs.append(ph)
            tk.Label(cell, image=ph, bg=_PANEL).pack()
            good = sc >= MIN_ALIGNMENT_SCORE
            v = tk.BooleanVar(value=good)
            keep_vars.append(v)
            tk.Checkbutton(cell, text=f"#{i}  {sc:.2f}", variable=v, bg=_PANEL,
                           fg="#76ff03" if good else "#ff5555", selectcolor="#111",
                           activebackground=_PANEL, font=("Consolas", 8)).pack()
            tk.Label(cell, text=f"d({off[0]-spec.x:+d},{off[1]-spec.y:+d})", bg=_PANEL,
                     fg="#777", font=("Consolas", 7)).pack()

        def apply():
            self.ok_images = [im for im, v in zip(self.ok_images, keep_vars) if v.get()]
            self._counts()
            self._say(f"Kept {len(self.ok_images)} OK images.")
            win.destroy()

        tk.Button(win, text="Apply selection", command=apply, bg="#0d47a1", fg=_FG,
                  bd=0, font=("Arial", 10, "bold"), pady=6).pack(fill="x", padx=10, pady=10)

    # ── build ───────────────────────────────────────────────────────────────

    def build(self):
        part = self.ent_part.get().strip().upper()
        if not part:
            self._say("Enter a part number.")
            return
        if not self.roi:
            self._say("Draw the ROI first.")
            return

        try:
            model, report = build_part_model(
                part, self.ok_images, self.ng_images, [self._spec()],
                camera_settings=(self._stream.applied_settings if self._stream else {}))
        except TeachError as e:
            detail = e.report.summary() if e.report else str(e)
            messagebox.showerror(
                "Model refused",
                f"{e}\n\n{detail}\n\n"
                "A model that cannot separate OK from NG would pass everything. "
                "Re-draw the ROI over a region that changes when the part is absent, "
                "or fix the lighting.", parent=self)
            self._say("Build refused — see dialog.")
            return

        path = model.save()
        r = report.rois[0]
        messagebox.showinfo(
            "Model saved",
            f"Part {part} is ready.\n\n"
            f"Threshold   {r.threshold:.3f}  (derived, not typed)\n"
            f"Worst OK    {r.ok_min:.3f}\n"
            f"Best NG     {r.ng_max:.3f}\n"
            f"Margin      {r.margin:+.3f}\n\n"
            f"References  {len(model.rois[0].templates)}\n"
            f"Saved to    {os.path.basename(path)}", parent=self)
        self._say(f"Saved {os.path.basename(path)} (margin {r.margin:+.3f})")

    def close(self):
        self._live = False
        if self._stream is not None:
            self._stream.release()
            self._stream = None
        self.destroy()


def open_wizard(parent):
    return TeachWizard(parent)
