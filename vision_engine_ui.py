"""
vision_engine_ui.py
====================
Professional industrial vision workflow UI.

Provides two Toplevel windows:
  - ReferenceModelBuilderUI  : dataset capture / upload → ROI → build → save .ivmodel
  - ReferenceModelTesterUI   : live camera inference against a loaded .ivmodel
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
from PIL import Image, ImageTk
import threading
import time
import numpy as np

from vision_engine.reference_model import build_reference_model, ReferenceModel
from vision_engine.reference_model.features import FeatureExtractor

# ─── Shared colour palette (dark industrial theme) ────────────────────────────
BG        = "#1a1a2e"   # main background
PANEL     = "#16213e"   # side-panel background
CARD      = "#0f3460"   # card / section background
ACCENT    = "#e94560"   # accent red
SUCCESS   = "#00b894"   # green
WARNING   = "#fdcb6e"   # amber
DANGER    = "#d63031"   # red
TEXT      = "#dfe6e9"   # primary text
SUBTEXT   = "#b2bec3"   # secondary text
BORDER    = "#2d3436"   # border / divider
BTN_BLUE  = "#0078D7"
BTN_DARK  = "#2d3436"

FONT_H1   = ("Segoe UI", 13, "bold")
FONT_H2   = ("Segoe UI", 11, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_MONO = ("Consolas",  10)
FONT_TINY = ("Segoe UI",  9)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _btn(parent, text, command, bg=BTN_BLUE, fg="white",
         width=None, font=FONT_BODY, pady=8, padx=14, state="normal"):
    kw = dict(text=text, command=command, bg=bg, fg=fg, font=font,
              bd=0, padx=padx, pady=pady, cursor="hand2",
              activebackground=_darken(bg), activeforeground=fg, state=state)
    b = tk.Button(parent, **kw)
    if width:
        b.config(width=width)
    return b


def _darken(hex_color):
    try:
        r = max(0, int(hex_color[1:3], 16) - 30)
        g = max(0, int(hex_color[3:5], 16) - 30)
        b = max(0, int(hex_color[5:7], 16) - 30)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


def _sep(parent):
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=12, pady=6)


def _label(parent, text, font=FONT_BODY, fg=TEXT, bg=PANEL, anchor="w", **kw):
    return tk.Label(parent, text=text, font=font, fg=fg, bg=bg, anchor=anchor, **kw)


# ─── Shared frame-display mixin ───────────────────────────────────────────────

class _VideoMixin:
    """Mixin that handles coordinate-mapped display and ROI drawing on a tk.Label."""

    def _display_frame_on_label(self, lbl: tk.Label, bgr_frame: np.ndarray,
                                roi=None, rect_start=None, rect_end=None,
                                roi_mode=False, extra_draw=None):
        disp = bgr_frame.copy()
        if roi:
            cv2.rectangle(disp,
                          (roi["x"], roi["y"]),
                          (roi["x"] + roi["width"], roi["y"] + roi["height"]),
                          (0, 229, 153), 2)
            # Dim area outside ROI
            overlay = disp.copy()
            h, w = disp.shape[:2]
            overlay[:roi["y"]] = (overlay[:roi["y"]] * 0.35).astype(np.uint8)
            overlay[roi["y"]+roi["height"]:] = (overlay[roi["y"]+roi["height"]:] * 0.35).astype(np.uint8)
            overlay[:, :roi["x"]] = (overlay[:, :roi["x"]] * 0.35).astype(np.uint8)
            overlay[:, roi["x"]+roi["width"]:] = (overlay[:, roi["x"]+roi["width"]:] * 0.35).astype(np.uint8)
            disp = overlay
            cv2.rectangle(disp,
                          (roi["x"], roi["y"]),
                          (roi["x"] + roi["width"], roi["y"] + roi["height"]),
                          (0, 229, 153), 2)
        elif roi_mode and rect_start and rect_end:
            cv2.rectangle(disp, rect_start, rect_end, (253, 203, 110), 2)

        if extra_draw:
            extra_draw(disp)

        rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        lw, lh = lbl.winfo_width(), lbl.winfo_height()
        if lw > 10 and lh > 10:
            pil.thumbnail((lw, lh), Image.Resampling.LANCZOS)

        def _push(img=pil):
            try:
                self._ph = ImageTk.PhotoImage(img)
                lbl.config(image=self._ph, text="")
            except Exception:
                pass

        lbl.after(0, _push)

    def _map_event_to_frame(self, event, lbl, frame):
        lw, lh = lbl.winfo_width(), lbl.winfo_height()
        fh, fw = frame.shape[:2]
        scale = min(lw / fw, lh / fh)
        dw, dh = int(fw * scale), int(fh * scale)
        ox, oy = (lw - dw) // 2, (lh - dh) // 2
        if ox <= event.x <= ox + dw and oy <= event.y <= oy + dh:
            rx = int((event.x - ox) / scale)
            ry = int((event.y - oy) / scale)
            return rx, ry
        return None, None

    def _clamp_event_to_frame(self, event, lbl, frame):
        lw, lh = lbl.winfo_width(), lbl.winfo_height()
        fh, fw = frame.shape[:2]
        scale = min(lw / fw, lh / fh)
        dw, dh = int(fw * scale), int(fh * scale)
        ox, oy = (lw - dw) // 2, (lh - dh) // 2
        ex = max(ox, min(event.x, ox + dw))
        ey = max(oy, min(event.y, oy + dh))
        return int((ex - ox) / scale), int((ey - oy) / scale)


# ═══════════════════════════════════════════════════════════════════════════════
# BUILDER UI
# ═══════════════════════════════════════════════════════════════════════════════

class ReferenceModelBuilderUI(tk.Toplevel, _VideoMixin):
    """
    Dataset capture / upload → ROI selection → build → save .ivmodel
    """

    MAX_IMAGES = 10
    MIN_IMAGES = 6

    def __init__(self, parent, cam_index, width, height):
        super().__init__(parent)
        self.title("Vision Model Builder")
        self.geometry("1100x680")
        self.minsize(900, 600)
        self.configure(bg=BG)
        self.resizable(True, True)

        self.cam_index  = cam_index
        self.cam_width  = width
        self.cam_height = height

        self.cap            = None
        self.running        = False
        self.show_live_feed = True
        self.current_frame  = None

        self.captured_images  = []   # list[np.ndarray]
        self.roi              = None
        self.roi_mode         = False
        self.rect_start       = None
        self.rect_end         = None

        self._ph = None  # prevent GC

        self._build_ui()
        self._refresh_gallery()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        if cam_index >= 0:
            self._start_camera()
        else:
            self._set_placeholder("No camera connected.\nUpload images to begin.")

    # ── UI Construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header bar ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=CARD, height=52)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="⬡  Vision Model Builder",
                 font=("Segoe UI", 14, "bold"), bg=CARD, fg=TEXT).pack(side="left", padx=20, pady=12)

        self.lbl_model_name_display = tk.Label(hdr, text="Unsaved", font=FONT_TINY,
                                               bg=CARD, fg=SUBTEXT)
        self.lbl_model_name_display.pack(side="left", padx=8)

        # ── Main area ──────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        # Left: video preview
        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(12, 6), pady=12)

        viewer_hdr = tk.Frame(left, bg=PANEL, height=32)
        viewer_hdr.pack(fill="x")
        viewer_hdr.pack_propagate(False)
        tk.Label(viewer_hdr, text="LIVE PREVIEW  /  REFERENCE IMAGE",
                 font=FONT_TINY, bg=PANEL, fg=SUBTEXT).pack(side="left", padx=10, pady=7)
        self.lbl_live_badge = tk.Label(viewer_hdr, text="● LIVE", font=FONT_TINY,
                                       bg=PANEL, fg=SUCCESS)
        self.lbl_live_badge.pack(side="right", padx=10)

        self.lbl_video = tk.Label(left, bg="#0a0a0a", text="Initialising camera…",
                                  fg=SUBTEXT, font=FONT_BODY, cursor="crosshair")
        self.lbl_video.pack(fill="both", expand=True)

        self.lbl_video.bind("<ButtonPress-1>",   self._on_mouse_down)
        self.lbl_video.bind("<B1-Motion>",       self._on_mouse_drag)
        self.lbl_video.bind("<ButtonRelease-1>", self._on_mouse_up)

        # ROI hint bar
        self.lbl_roi_hint = tk.Label(left, text="", bg=BG, fg=WARNING, font=FONT_TINY)
        self.lbl_roi_hint.pack(fill="x", padx=4, pady=2)

        # Gallery strip
        gal_hdr = tk.Frame(left, bg=PANEL, height=28)
        gal_hdr.pack(fill="x", pady=(6, 0))
        gal_hdr.pack_propagate(False)
        tk.Label(gal_hdr, text="CAPTURED REFERENCES", font=FONT_TINY,
                 bg=PANEL, fg=SUBTEXT).pack(side="left", padx=10, pady=5)
        self.lbl_count = tk.Label(gal_hdr, text="0 / 10", font=FONT_TINY,
                                  bg=PANEL, fg=SUBTEXT)
        self.lbl_count.pack(side="right", padx=10)

        self.gallery_frame = tk.Frame(left, bg=BG, height=88)
        self.gallery_frame.pack(fill="x", pady=(0, 4))
        self.gallery_frame.pack_propagate(False)

        # Right panel
        right = tk.Frame(body, bg=PANEL, width=270)
        right.pack(side="right", fill="y", padx=(6, 12), pady=12)
        right.pack_propagate(False)

        self._build_right_panel(right)

    def _build_right_panel(self, parent):
        # Model name
        _label(parent, "MODEL NAME", font=FONT_TINY, fg=SUBTEXT).pack(anchor="w", padx=14, pady=(16, 2))
        self.ent_model_name = tk.Entry(parent, font=FONT_BODY, bg=CARD, fg=TEXT,
                                       insertbackground=TEXT, bd=0, relief="flat")
        self.ent_model_name.insert(0, "PART_001")
        self.ent_model_name.pack(fill="x", padx=14, ipady=6)

        _sep(parent)

        # Step 1 – Acquire
        _label(parent, "STEP 1 — ACQUIRE REFERENCES", font=FONT_TINY, fg=ACCENT).pack(
            anchor="w", padx=14, pady=(4, 6))

        self.btn_capture = _btn(parent, "⊕  Capture from Camera",
                                self.capture_image, bg=SUCCESS)
        self.btn_capture.pack(fill="x", padx=14, pady=(0, 6))

        _btn(parent, "⇪  Upload from Disk",
             self.upload_dataset, bg=BTN_DARK).pack(fill="x", padx=14, pady=(0, 4))

        self.btn_resume = _btn(parent, "↺  Resume Live Feed",
                               self._resume_live_feed, bg=BTN_DARK)
        self.btn_resume.pack(fill="x", padx=14, pady=(0, 4))
        self.btn_resume.config(state="disabled")

        _btn(parent, "✕  Clear All",
             self._clear_all, bg=DANGER, pady=5).pack(fill="x", padx=14, pady=(0, 4))

        _sep(parent)

        # Step 2 – ROI
        _label(parent, "STEP 2 — DEFINE ROI", font=FONT_TINY, fg=ACCENT).pack(
            anchor="w", padx=14, pady=(4, 6))

        self.btn_roi = _btn(parent, "⊡  Draw Bounding Box",
                            self._toggle_roi_mode, bg=BTN_BLUE)
        self.btn_roi.pack(fill="x", padx=14, pady=(0, 6))

        self.lbl_roi_info = _label(parent, "ROI: Full frame (default)",
                                   font=FONT_TINY, fg=SUBTEXT)
        self.lbl_roi_info.pack(anchor="w", padx=14)

        _sep(parent)

        # Step 3 – Build
        _label(parent, "STEP 3 — BUILD & SAVE", font=FONT_TINY, fg=ACCENT).pack(
            anchor="w", padx=14, pady=(4, 6))

        self.btn_build = _btn(parent, "⚙  Build & Save  .ivmodel",
                              self._build_model, bg=ACCENT,
                              state="disabled")
        self.btn_build.pack(fill="x", padx=14, pady=(0, 4))

        _sep(parent)

        # Status area
        self.lbl_progress = _label(parent, "", font=FONT_TINY, fg=SUBTEXT)
        self.lbl_progress.pack(anchor="w", padx=14, pady=(4, 0))

        # Info card
        info = tk.Frame(parent, bg=CARD)
        info.pack(fill="x", padx=14, pady=(12, 4))
        for row in [
            ("Min images required", f"{self.MIN_IMAGES}"),
            ("Max images allowed",  f"{self.MAX_IMAGES}"),
            ("Feature extractor",   "SIFT"),
            ("Output format",       ".ivmodel"),
        ]:
            r = tk.Frame(info, bg=CARD)
            r.pack(fill="x", padx=10, pady=2)
            tk.Label(r, text=row[0], font=FONT_TINY, bg=CARD, fg=SUBTEXT, anchor="w").pack(side="left")
            tk.Label(r, text=row[1], font=("Segoe UI", 9, "bold"),
                     bg=CARD, fg=TEXT, anchor="e").pack(side="right")

    # ── Camera ────────────────────────────────────────────────────────────────

    def _start_camera(self):
        self.running        = True
        self.show_live_feed = True
        self.lbl_live_badge.config(text="● LIVE", fg=SUCCESS)
        threading.Thread(target=self._camera_loop, daemon=True).start()

    def _camera_loop(self):
        self.cap = cv2.VideoCapture(self.cam_index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.running = False
            self.lbl_video.after(0, lambda: self._set_placeholder("Camera failed to open."))
            return
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.cam_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cam_height)
        while self.running:
            ret, frame = self.cap.read()
            if ret and self.show_live_feed:
                self.current_frame = frame.copy()
                self._update_view()
            time.sleep(0.033)

    def _set_placeholder(self, msg):
        self.lbl_video.config(image="", text=msg, fg=SUBTEXT, font=FONT_BODY, bg="#0a0a0a")

    def _resume_live_feed(self):
        self.show_live_feed = True
        self.lbl_live_badge.config(text="● LIVE", fg=SUCCESS)
        self.btn_resume.config(state="disabled")

    # ── Display update ────────────────────────────────────────────────────────

    def _update_view(self):
        if self.current_frame is None:
            return
        self._display_frame_on_label(
            self.lbl_video, self.current_frame,
            roi=self.roi,
            rect_start=self.rect_start, rect_end=self.rect_end,
            roi_mode=self.roi_mode
        )

    # ── Acquire ────────────────────────────────────────────────────────────────

    def capture_image(self):
        if self.current_frame is None:
            messagebox.showwarning("No Frame", "No camera frame available to capture.")
            return
        if len(self.captured_images) >= self.MAX_IMAGES:
            messagebox.showwarning("Limit Reached", f"Maximum of {self.MAX_IMAGES} reference images reached.")
            return
        self.captured_images.append(self.current_frame.copy())
        self._on_images_changed()

        # Flash effect
        self.lbl_video.config(bg="white")
        self.after(60, lambda: self.lbl_video.config(bg="#0a0a0a"))

    def upload_dataset(self):
        paths = filedialog.askopenfilenames(
            title="Select Reference Images",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff"), ("All Files", "*.*")]
        )
        if not paths:
            return

        added, skipped = 0, 0
        for p in paths:
            if len(self.captured_images) >= self.MAX_IMAGES:
                skipped += 1
                continue
            img = cv2.imread(p)
            if img is not None:
                self.captured_images.append(img)
                added += 1
            else:
                skipped += 1

        if added == 0:
            messagebox.showwarning("Upload Failed", "No valid images were loaded.")
            return

        self._on_images_changed()
        self._set_status(f"Loaded {added} image(s)." + (f"  {skipped} skipped." if skipped else ""), WARNING)

        # Show the first uploaded image for ROI drawing
        self.show_live_feed = False
        self.lbl_live_badge.config(text="⏸ PAUSED", fg=WARNING)
        self.btn_resume.config(state="normal")
        self.current_frame = self.captured_images[0].copy()
        self._update_view()

    def _clear_all(self):
        if self.captured_images:
            if not messagebox.askyesno("Clear All", "Clear all captured reference images?"):
                return
        self.captured_images.clear()
        self.roi = None
        self.roi_mode = False
        self.rect_start = self.rect_end = None
        self._on_images_changed()
        self._set_status("Cleared.", SUBTEXT)
        self._update_roi_display()
        self.btn_roi.config(text="⊡  Draw Bounding Box", bg=BTN_BLUE)

    # ── Gallery ────────────────────────────────────────────────────────────────

    def _refresh_gallery(self):
        for w in self.gallery_frame.winfo_children():
            w.destroy()

        n = len(self.captured_images)
        for i, img in enumerate(self.captured_images):
            thumb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil   = Image.fromarray(thumb)
            pil.thumbnail((80, 64), Image.Resampling.LANCZOS)
            ph = ImageTk.PhotoImage(pil)

            card = tk.Frame(self.gallery_frame, bg=CARD, padx=1, pady=1)
            card.pack(side="left", padx=4, pady=4)

            lbl = tk.Label(card, image=ph, bg=CARD, cursor="hand2")
            lbl.image = ph
            lbl.pack()

            idx = i
            lbl.bind("<Button-1>", lambda e, ii=idx: self._preview_gallery_image(ii))

            tk.Label(card, text=f"#{i+1}", font=("Segoe UI", 7),
                     bg=CARD, fg=SUBTEXT).pack()

        self.lbl_count.config(text=f"{n} / {self.MAX_IMAGES}")

    def _preview_gallery_image(self, idx):
        self.show_live_feed = False
        self.lbl_live_badge.config(text="⏸ PAUSED", fg=WARNING)
        self.btn_resume.config(state="normal")
        self.current_frame = self.captured_images[idx].copy()
        self._update_view()

    def _on_images_changed(self):
        n = len(self.captured_images)
        self._refresh_gallery()
        ready = n >= self.MIN_IMAGES
        self.btn_build.config(state="normal" if ready else "disabled")
        self._set_status(
            f"{n} reference image(s) acquired.  {'Ready to build!' if ready else f'Need {self.MIN_IMAGES - n} more.'}", 
            SUCCESS if ready else SUBTEXT
        )

    # ── ROI ────────────────────────────────────────────────────────────────────

    def _toggle_roi_mode(self):
        if self.roi:
            # Clear existing ROI
            self.roi = None
            self.roi_mode = False
            self.rect_start = self.rect_end = None
            self.btn_roi.config(text="⊡  Draw Bounding Box", bg=BTN_BLUE)
            self.lbl_roi_hint.config(text="")
            self._update_roi_display()
            self._update_view()
            return

        self.roi_mode = not self.roi_mode
        if self.roi_mode:
            self.btn_roi.config(text="✕  Cancel ROI Draw", bg=WARNING)
            self.lbl_roi_hint.config(
                text="Click and drag on the image to define the inspection region (ROI).")
        else:
            self.btn_roi.config(text="⊡  Draw Bounding Box", bg=BTN_BLUE)
            self.lbl_roi_hint.config(text="")
            self.rect_start = self.rect_end = None
            self._update_view()

    def _update_roi_display(self):
        if self.roi:
            self.lbl_roi_info.config(
                text=f"ROI: x={self.roi['x']} y={self.roi['y']} "
                     f"{self.roi['width']}×{self.roi['height']} px",
                fg=SUCCESS)
        else:
            self.lbl_roi_info.config(text="ROI: Full frame (default)", fg=SUBTEXT)

    def _on_mouse_down(self, event):
        if not self.roi_mode or self.current_frame is None:
            return
        rx, ry = self._map_event_to_frame(event, self.lbl_video, self.current_frame)
        if rx is not None:
            self.rect_start = (rx, ry)
            self.rect_end   = (rx, ry)
            self._update_view()

    def _on_mouse_drag(self, event):
        if not self.roi_mode or not self.rect_start or self.current_frame is None:
            return
        rx, ry = self._clamp_event_to_frame(event, self.lbl_video, self.current_frame)
        self.rect_end = (rx, ry)
        self._update_view()

    def _on_mouse_up(self, event):
        if not self.roi_mode or not self.rect_start or not self.rect_end:
            return
        x1, y1 = self.rect_start
        x2, y2 = self.rect_end
        x, y = min(x1, x2), min(y1, y2)
        w, h = abs(x2 - x1), abs(y2 - y1)
        if w > 20 and h > 20:
            self.roi = {"x": x, "y": y, "width": w, "height": h}
            self.roi_mode = False
            self.btn_roi.config(text="✕  Clear ROI", bg=DANGER)
            self.lbl_roi_hint.config(text="")
            self._update_roi_display()
        else:
            self._set_status("ROI too small. Try again.", DANGER)
        self.rect_start = self.rect_end = None
        self._update_view()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_model(self):
        n = len(self.captured_images)
        if n < self.MIN_IMAGES:
            messagebox.showerror("Not Enough Images", f"Need at least {self.MIN_IMAGES} reference images (have {n}).")
            return

        roi = self.roi
        if not roi:
            if self.captured_images:
                h, w = self.captured_images[0].shape[:2]
                roi = {"x": 0, "y": 0, "width": w, "height": h}
            else:
                messagebox.showerror("Error", "No frame available to determine size.")
                return

        model_name = self.ent_model_name.get().strip() or "PART_001"

        save_path = filedialog.asksaveasfilename(
            title="Save Reference Model",
            initialfile=f"{model_name}.ivmodel",
            defaultextension=".ivmodel",
            filetypes=[("IV Model Files", "*.ivmodel"), ("All Files", "*.*")]
        )
        if not save_path:
            return

        self._set_status("Building model… please wait.", WARNING)
        self.btn_build.config(state="disabled")
        self.update()

        def _worker():
            try:
                from vision_engine.reference_model import ReferenceModelBuilder
                builder = ReferenceModelBuilder()
                builder.model_name = model_name
                for img in self.captured_images:
                    builder.add_reference(img)
                if roi:
                    builder.set_roi(roi["x"], roi["y"], roi["width"], roi["height"])
                model = builder.build()
                model.save(save_path)

                summary = model.get_summary()
                self.after(0, lambda: self._on_build_success(save_path, summary))
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_build_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_build_success(self, path, summary):
        self.btn_build.config(state="normal")
        self._set_status("✔  Model saved successfully.", SUCCESS)
        self.lbl_model_name_display.config(text=path.split("/")[-1].split("\\")[-1])
        messagebox.showinfo("Model Saved", f"Model saved to:\n{path}\n\n{summary}")
        self.on_close()

    def _on_build_error(self, msg):
        self.btn_build.config(state="normal")
        self._set_status(f"✖  Build failed.", DANGER)
        messagebox.showerror("Build Error", msg)

    def _set_status(self, text, fg=SUBTEXT):
        self.lbl_progress.config(text=text, fg=fg)

    # ── Close ──────────────────────────────────────────────────────────────────

    def on_close(self):
        self.running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
# TESTER UI
# ═══════════════════════════════════════════════════════════════════════════════

class ReferenceModelTesterUI(tk.Toplevel, _VideoMixin):
    """
    Live camera inference window. Tests each camera frame against a loaded .ivmodel.
    """
    # Match threshold (good matches needed to call FOUND)
    MATCH_THRESHOLD = 12

    def __init__(self, parent, cam_index, width, height, model_path):
        super().__init__(parent)
        self.title(f"Vision Inference — {model_path.split('/')[-1].split(chr(92))[-1]}")
        self.geometry("1100x680")
        self.minsize(900, 580)
        self.configure(bg=BG)
        self.resizable(True, True)

        self.cam_index  = cam_index
        self.cam_width  = width
        self.cam_height = height

        self._ph = None

        # Load model
        try:
            self.model = ReferenceModel.load(model_path)
        except Exception as exc:
            messagebox.showerror("Load Error", str(exc))
            self.destroy()
            return

        # SIFT + FLANN
        self.extractor = FeatureExtractor()
        FLANN_INDEX_KDTREE = 1
        self.flann = cv2.FlannBasedMatcher(
            dict(algorithm=FLANN_INDEX_KDTREE, trees=5),
            dict(checks=50)
        )

        self.cap     = None
        self.running = False
        self._paused = False
        self._last_result = None   # latest inference result dict

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        if cam_index >= 0:
            self._start_camera()
        else:
            self._set_placeholder("No camera connected.")

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=CARD, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="⬡  Vision Inference Engine",
                 font=("Segoe UI", 14, "bold"), bg=CARD, fg=TEXT).pack(side="left", padx=20, pady=12)

        model_tag = tk.Frame(hdr, bg=CARD)
        model_tag.pack(side="left", padx=8)
        tk.Label(model_tag, text="MODEL",  font=FONT_TINY, bg=CARD, fg=SUBTEXT).pack()
        tk.Label(model_tag, text=self.model.metadata.get("model_name", "—"),
                 font=("Segoe UI", 10, "bold"), bg=CARD, fg=ACCENT).pack()

        self.btn_pause = _btn(hdr, "⏸  Pause", self._toggle_pause,
                              bg=BTN_DARK, pady=6, padx=12)
        self.btn_pause.pack(side="right", padx=12, pady=10)

        # Body
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        # Left: live view
        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(12, 6), pady=12)

        view_hdr = tk.Frame(left, bg=PANEL, height=32)
        view_hdr.pack(fill="x")
        view_hdr.pack_propagate(False)
        tk.Label(view_hdr, text="LIVE CAMERA FEED", font=FONT_TINY,
                 bg=PANEL, fg=SUBTEXT).pack(side="left", padx=10, pady=7)
        self.lbl_fps = tk.Label(view_hdr, text="— fps", font=FONT_TINY,
                                bg=PANEL, fg=SUBTEXT)
        self.lbl_fps.pack(side="right", padx=10)

        # Big verdict banner
        self.lbl_verdict = tk.Label(left, text="◌  INITIALISING",
                                    font=("Segoe UI", 18, "bold"),
                                    bg="#0a0a0a", fg=SUBTEXT,
                                    relief="flat")
        self.lbl_verdict.pack(fill="x")

        self.lbl_video = tk.Label(left, bg="#0a0a0a", cursor="arrow")
        self.lbl_video.pack(fill="both", expand=True)

        # Right panel
        right = tk.Frame(body, bg=PANEL, width=280)
        right.pack(side="right", fill="y", padx=(6, 12), pady=12)
        right.pack_propagate(False)

        self._build_right_panel(right)

    def _build_right_panel(self, parent):
        _label(parent, "INFERENCE METRICS", font=FONT_TINY, fg=SUBTEXT).pack(
            anchor="w", padx=14, pady=(16, 8))

        # Big match counter
        self.lbl_matches = tk.Label(parent, text="0", font=("Segoe UI", 42, "bold"),
                                    bg=PANEL, fg=TEXT)
        self.lbl_matches.pack()
        tk.Label(parent, text="FEATURE MATCHES", font=FONT_TINY, bg=PANEL, fg=SUBTEXT).pack()

        _sep(parent)

        # Confidence bar
        _label(parent, "CONFIDENCE", font=FONT_TINY, fg=SUBTEXT).pack(
            anchor="w", padx=14, pady=(6, 2))
        bar_bg = tk.Frame(parent, bg=CARD, height=14)
        bar_bg.pack(fill="x", padx=14, pady=(0, 6))
        self.conf_bar = tk.Frame(bar_bg, bg=SUCCESS, height=14, width=0)
        self.conf_bar.place(x=0, y=0, relheight=1.0, relwidth=0.0)
        self.lbl_conf = _label(parent, "0.0 %", font=("Segoe UI", 10, "bold"), fg=TEXT)
        self.lbl_conf.pack(anchor="w", padx=14)

        _sep(parent)

        # Model info card
        _label(parent, "LOADED MODEL", font=FONT_TINY, fg=SUBTEXT).pack(
            anchor="w", padx=14, pady=(4, 6))

        info = tk.Frame(parent, bg=CARD)
        info.pack(fill="x", padx=14)
        roi = self.model.roi
        roi_str = f"{roi.get('width', 0)}×{roi.get('height', 0)}" if roi else "Full"
        stats = self.model.feature_statistics
        rows = [
            ("Name",         self.model.metadata.get("model_name", "—")),
            ("References",   str(len(self.model.reference_images))),
            ("ROI",          roi_str),
            ("Avg Features", f"{stats.get('avg_features', 0):.0f}"),
            ("Consistency",  f"{stats.get('consistency_score', 0)*100:.1f}%"),
            ("Created",      self.model.metadata.get("creation_date", "—")[:10]),
        ]
        for k, v in rows:
            r = tk.Frame(info, bg=CARD)
            r.pack(fill="x", padx=10, pady=3)
            tk.Label(r, text=k, font=FONT_TINY, bg=CARD, fg=SUBTEXT, anchor="w").pack(side="left")
            tk.Label(r, text=v, font=("Segoe UI", 9, "bold"), bg=CARD, fg=TEXT, anchor="e").pack(side="right")

        _sep(parent)

        # Threshold control
        _label(parent, "MATCH THRESHOLD", font=FONT_TINY, fg=SUBTEXT).pack(
            anchor="w", padx=14, pady=(4, 2))
        self.var_threshold = tk.IntVar(value=self.MATCH_THRESHOLD)
        thresh_row = tk.Frame(parent, bg=PANEL)
        thresh_row.pack(fill="x", padx=14)
        self.lbl_thresh_val = tk.Label(thresh_row, text=str(self.MATCH_THRESHOLD),
                                       font=("Segoe UI", 10, "bold"), bg=PANEL, fg=TEXT, width=4)
        self.lbl_thresh_val.pack(side="right")
        sld = ttk.Scale(thresh_row, from_=5, to=80, variable=self.var_threshold,
                        orient="horizontal",
                        command=lambda v: self.lbl_thresh_val.config(text=str(int(float(v)))))
        sld.pack(fill="x", side="left", expand=True)

        _sep(parent)

        _btn(parent, "✕  Close", self.on_close, bg=DANGER, pady=7).pack(
            fill="x", padx=14, side="bottom", pady=14)

    # ── Camera + inference ─────────────────────────────────────────────────────

    def _start_camera(self):
        self.running = True
        threading.Thread(target=self._inference_loop, daemon=True).start()

    def _set_placeholder(self, msg):
        self.lbl_video.config(image="", text=msg, fg=SUBTEXT, font=FONT_BODY, bg="#0a0a0a")

    def _toggle_pause(self):
        self._paused = not self._paused
        self.btn_pause.config(text="▶  Resume" if self._paused else "⏸  Pause")

    def _inference_loop(self):
        self.cap = cv2.VideoCapture(self.cam_index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.running = False
            self.after(0, lambda: self._set_placeholder("Camera failed to open."))
            return
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.cam_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cam_height)

        # Pre-load all reference descriptors
        ref_descs = self.model.descriptors_list or []

        t_last = time.time()
        while self.running:
            if self._paused:
                time.sleep(0.05)
                continue

            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            # ── Inference ────────────────────────────────────────────────────
            roi = self.model.roi
            mask = None
            if roi:
                mask = np.zeros(frame.shape[:2], dtype=np.uint8)
                x, y, w, h = roi.get("x", 0), roi.get("y", 0), \
                              roi.get("width", frame.shape[1]), roi.get("height", frame.shape[0])
                mask[y:y+h, x:x+w] = 255

            kp, desc = self.extractor.extract(frame, roi)
            total_good_matches = 0
            best_match_count   = 0

            if desc is not None and len(desc) > 1:
                for ref_desc in ref_descs:
                    if ref_desc is None or len(ref_desc) < 2:
                        continue
                    try:
                        k = min(2, len(ref_desc), len(desc))
                        if k < 2:
                            continue
                        matches = self.flann.knnMatch(ref_desc.astype(np.float32),
                                                      desc.astype(np.float32), k=2)
                        good = sum(1 for m_n in matches
                                   if len(m_n) == 2 and m_n[0].distance < 0.75 * m_n[1].distance)
                        total_good_matches += good
                        best_match_count    = max(best_match_count, good)
                    except Exception:
                        pass

            avg_matches = total_good_matches // max(len(ref_descs), 1)
            threshold   = int(self.var_threshold.get())
            found       = avg_matches >= threshold
            confidence  = min(1.0, avg_matches / max(threshold * 1.5, 1))

            # ── Draw overlay ─────────────────────────────────────────────────
            disp = frame.copy()
            if kp:
                cv2.drawKeypoints(disp, kp, disp, color=(253, 203, 110),
                                  flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
            if roi:
                color = (0, 229, 153) if found else (233, 69, 96)
                cv2.rectangle(disp, (roi["x"], roi["y"]),
                              (roi["x"]+roi["width"], roi["y"]+roi["height"]),
                              color, 3)
                label = f"{'FOUND' if found else 'NOT FOUND'}  [{avg_matches}]"
                cv2.rectangle(disp,
                              (roi["x"], roi["y"] - 30),
                              (roi["x"] + len(label)*11, roi["y"]),
                              color, -1)
                cv2.putText(disp, label,
                            (roi["x"] + 4, roi["y"] - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)

            # ── FPS ──────────────────────────────────────────────────────────
            now  = time.time()
            fps  = 1.0 / max(now - t_last, 0.001)
            t_last = now

            # ── Push to UI ───────────────────────────────────────────────────
            rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            lw, lh = self.lbl_video.winfo_width(), self.lbl_video.winfo_height()
            if lw > 10 and lh > 10:
                pil.thumbnail((lw, lh), Image.Resampling.LANCZOS)

            def _ui(img=pil, f=found, m=avg_matches, c=confidence, fps_=fps):
                try:
                    self._ph = ImageTk.PhotoImage(img)
                    self.lbl_video.config(image=self._ph, text="")

                    if f:
                        self.lbl_verdict.config(
                            text="✔  FOUND", fg=SUCCESS, bg="#0a1a10")
                    else:
                        self.lbl_verdict.config(
                            text="✖  NOT FOUND", fg=DANGER, bg="#1a0a0a")

                    self.lbl_matches.config(text=str(m),
                                            fg=SUCCESS if f else DANGER)
                    self.lbl_conf.config(text=f"{c*100:.1f}%",
                                         fg=SUCCESS if f else DANGER)
                    self.conf_bar.place(relwidth=c)
                    self.lbl_fps.config(text=f"{fps_:.1f} fps")
                except Exception:
                    pass

            self.after(0, _ui)
            time.sleep(0.04)

    # ── Close ──────────────────────────────────────────────────────────────────

    def on_close(self):
        self.running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.destroy()


# ─── Entry-points (called by camera_settings.py) ──────────────────────────────

def open_builder_ui(parent, cam_index, width, height):
    ui = ReferenceModelBuilderUI(parent, cam_index, width, height)
    ui.grab_set()


def open_tester_ui(parent, cam_index, width, height, model_path):
    ui = ReferenceModelTesterUI(parent, cam_index, width, height, model_path)
    ui.grab_set()
