"""
vision_settings.py
===================
Camera Settings configuration page.
Allows selecting camera devices for Camera 1 and Camera 2,
adjusting resolution, and previewing live feeds.
Includes Vision Model management for contour-based part verification.
Settings are persisted to camera_cfg.ini and vision_config.json.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import configparser
import os
import json
import threading

try:
    import cv2
    _cv2_ok = True
except ImportError:
    _cv2_ok = False

try:
    from PIL import Image, ImageTk
    _pil_ok = True
except ImportError:
    _pil_ok = False

_CFG_PATH = os.path.join(os.path.dirname(__file__), "camera_cfg.ini")

def _load_cfg() -> dict:
    cfg = configparser.ConfigParser()
    cfg.read(_CFG_PATH)
    return {
        "cam1_index":  cfg.getint("CAMERA", "cam1_index",  fallback=-1),
        "cam2_index":  cfg.getint("CAMERA", "cam2_index",  fallback=-1),
        "cam1_width":  cfg.getint("CAMERA", "cam1_width",  fallback=640),
        "cam1_height": cfg.getint("CAMERA", "cam1_height", fallback=480),
        "cam2_width":  cfg.getint("CAMERA", "cam2_width",  fallback=640),
        "cam2_height": cfg.getint("CAMERA", "cam2_height", fallback=480),
        "cam1_enabled": cfg.getboolean("CAMERA", "cam1_enabled", fallback=False),
        "cam2_enabled": cfg.getboolean("CAMERA", "cam2_enabled", fallback=False),
    }

def _save_cfg(d: dict):
    cfg = configparser.ConfigParser()
    cfg["CAMERA"] = {k: str(v) for k, v in d.items()}
    with open(_CFG_PATH, "w") as f:
        cfg.write(f)


def _detect_cameras(max_check=5):
    """Detect available camera devices by index."""
    if not _cv2_ok:
        return []
    cameras = []
    for i in range(max_check):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cameras.append({"index": i, "name": f"Camera {i}", "width": w, "height": h})
            cap.release()
    return cameras


class CameraPreview:
    """Manages a live preview of a single camera in a tkinter Label."""
    def __init__(self, parent_label, cam_index, width=320, height=240):
        self._label = parent_label
        self._cam_index = cam_index
        self._width = width
        self._height = height
        self._cap = None
        self._running = False
        self._photo = None  # prevent GC

    def start(self):
        if not _cv2_ok or not _pil_ok:
            return
        if self._cam_index < 0:
            return
        self._running = True
        threading.Thread(target=self._open_and_stream, daemon=True).start()

    def _open_and_stream(self):
        self._cap = cv2.VideoCapture(self._cam_index, cv2.CAP_DSHOW)
        if not self._cap.isOpened():
            self._running = False
            try:
                self._label.after(0, lambda: self._label.config(text="Failed to open camera", fg="#ff5555"))
            except Exception:
                pass
            return
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._stream_loop()

    def _stream_loop(self):
        if not self._running or self._cap is None or not self._cap.isOpened():
            return
        ret, frame = self._cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (self._width, self._height))
            img = Image.fromarray(frame)
            self._photo = ImageTk.PhotoImage(img)
            try:
                self._label.config(image=self._photo, text="")
                self._label.image = self._photo
            except Exception:
                self.stop()
                return
        if self._running:
            try:
                self._label.after(33, self._stream_loop)  # ~30fps
            except Exception:
                self.stop()

    def stop(self):
        self._running = False
        if self._cap and self._cap.isOpened():
            self._cap.release()
        self._cap = None


RESOLUTIONS = [
    ("320x240", 320, 240),
    ("640x480", 640, 480),
    ("800x600", 800, 600),
    ("1280x720", 1280, 720),
]


def render(parent):
    """Render the Camera Settings configuration page."""
    cfg = _load_cfg()

    style = ttk.Style()
    style.configure("CS.TLabelframe", background="black", foreground="white", bordercolor="#444")
    style.configure("CS.TLabelframe.Label", background="black", foreground="#aaa", font=("Arial", 10, "bold"))

    previews = []  # keep references for cleanup

    content = tk.Frame(parent, bg="black")
    content.pack(fill="both", expand=True, padx=15, pady=10)

    # --- Status bar ---
    if not _cv2_ok:
        warn = tk.Label(content, text="⚠  opencv-python not installed. Run: pip install opencv-python",
                        bg="#331a00", fg="#ff9800", font=("Arial", 10, "bold"), pady=6)
        warn.pack(fill="x", pady=(0, 8))

    # --- Detect cameras ---
    detected = _detect_cameras() if _cv2_ok else []
    cam_options = ["Disabled"] + [f"{c['name']}  (index {c['index']}, {c['width']}x{c['height']})" for c in detected]
    cam_indices = [-1] + [c["index"] for c in detected]

    # --- Top frame: two camera config panels side by side ---
    top = tk.Frame(content, bg="black")
    top.pack(fill="x")
    top.columnconfigure(0, weight=1)
    top.columnconfigure(1, weight=1)

    def _make_cam_panel(parent_frame, col, title, cfg_key_prefix, current_index, current_w, current_h, enabled):
        """Create a camera config panel with device selector, resolution, preview."""
        lf = ttk.LabelFrame(parent_frame, text=title, style="CS.TLabelframe")
        lf.grid(row=0, column=col, sticky="nsew", padx=6, pady=4)

        inner = tk.Frame(lf, bg="black", padx=10, pady=8)
        inner.pack(fill="both", expand=True)

        # Device selector
        tk.Label(inner, text="Device:", bg="black", fg="#999", font=("Arial", 9)).grid(row=0, column=0, sticky="w", pady=4)
        cmb_dev = ttk.Combobox(inner, values=cam_options, state="readonly", width=35)
        # Set current selection
        sel_idx = 0
        if enabled and current_index >= 0:
            for i, ci in enumerate(cam_indices):
                if ci == current_index:
                    sel_idx = i
                    break
        cmb_dev.current(sel_idx)
        cmb_dev.grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        # Resolution selector
        tk.Label(inner, text="Resolution:", bg="black", fg="#999", font=("Arial", 9)).grid(row=1, column=0, sticky="w", pady=4)
        res_options = [r[0] for r in RESOLUTIONS]
        cmb_res = ttk.Combobox(inner, values=res_options, state="readonly", width=15)
        # Find matching resolution
        res_sel = 1  # default 640x480
        for i, (_, rw, rh) in enumerate(RESOLUTIONS):
            if rw == current_w and rh == current_h:
                res_sel = i
                break
        cmb_res.current(res_sel)
        cmb_res.grid(row=1, column=1, sticky="w", padx=8, pady=4)

        inner.columnconfigure(1, weight=1)

        # Preview area
        preview_container = tk.Frame(inner, bg="#111", bd=1, relief="solid", width=320, height=180)
        preview_container.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(8, 4))
        preview_container.pack_propagate(False)
        inner.rowconfigure(2, weight=1)

        preview_lbl = tk.Label(preview_container, text="[ No Preview ]", bg="#111", fg="#444",
                               font=("Arial", 11, "bold"))
        preview_lbl.pack(fill="both", expand=True)

        # Buttons
        btn_frame = tk.Frame(inner, bg="black")
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        preview_obj = {"instance": None}

        def _start_preview():
            if preview_obj["instance"]:
                preview_obj["instance"].stop()
            dev_sel = cmb_dev.current()
            if dev_sel <= 0:
                preview_lbl.config(text="[ No camera selected ]", image="", fg="#888")
                return
            ci = cam_indices[dev_sel]
            res_i = cmb_res.current()
            rw, rh = RESOLUTIONS[res_i][1], RESOLUTIONS[res_i][2]
            # Scale preview to fit container
            pw, ph = min(rw, 320), min(rh, 180)
            preview_obj["instance"] = CameraPreview(preview_lbl, ci, pw, ph)
            preview_obj["instance"].start()
            previews.append(preview_obj["instance"])

        def _stop_preview():
            if preview_obj["instance"]:
                preview_obj["instance"].stop()
                preview_obj["instance"] = None
            preview_lbl.config(text="[ Preview Stopped ]", image="", fg="#444")

        btn_preview = tk.Button(btn_frame, text="▶  Preview", bg="#1b5e20", fg="white",
                                font=("Arial", 9, "bold"), bd=0, padx=12, pady=4,
                                cursor="hand2", activebackground="#2e7d32", command=_start_preview)
        btn_preview.pack(side="left", padx=(0, 6))

        btn_stop = tk.Button(btn_frame, text="■  Stop", bg="#333", fg="#ccc",
                             font=("Arial", 9, "bold"), bd=0, padx=12, pady=4,
                             cursor="hand2", activebackground="#555", command=_stop_preview)
        btn_stop.pack(side="left")

        return {"cmb_dev": cmb_dev, "cmb_res": cmb_res, "preview_obj": preview_obj}

    cam1_panel = _make_cam_panel(top, 0, "📷  Camera 1", "cam1", cfg["cam1_index"], cfg["cam1_width"], cfg["cam1_height"], cfg["cam1_enabled"])
    cam2_panel = _make_cam_panel(top, 1, "📷  Camera 2", "cam2", cfg["cam2_index"], cfg["cam2_width"], cfg["cam2_height"], cfg["cam2_enabled"])

    # ─────────────────────────────────────────────────────────────────────────
    # Vision Model Management Section
    # ─────────────────────────────────────────────────────────────────────────
    from vision_engine.vision_controller import VisionController, load_vision_config, save_vision_config

    v_cfg = load_vision_config()

    vision_lf = ttk.LabelFrame(content, text="👁  Vision Model Management  (Contour Matching)", style="CS.TLabelframe")
    vision_lf.pack(fill="both", expand=True, padx=6, pady=(10, 4))

    v_inner = tk.Frame(vision_lf, bg="black", padx=10, pady=6)
    v_inner.pack(fill="both", expand=True)

    # --- Row 1: Settings ---
    settings_row = tk.Frame(v_inner, bg="black")
    settings_row.pack(fill="x", pady=(0, 6))

    tk.Label(settings_row, text="Camera Source:", bg="black", fg="#999", font=("Arial", 9)).pack(side="left")
    cmb_cam_src = ttk.Combobox(settings_row, values=["cam1", "cam2"], state="readonly", width=6)
    cmb_cam_src.set(v_cfg.get("camera_source", "cam1"))
    cmb_cam_src.pack(side="left", padx=(4, 16))

    tk.Label(settings_row, text="Match Threshold:", bg="black", fg="#999", font=("Arial", 9)).pack(side="left")
    ent_threshold = tk.Entry(settings_row, bg="#111", fg="white", font=("Arial", 10),
                             insertbackground="white", width=6)
    ent_threshold.insert(0, str(v_cfg.get("match_threshold", 0.15)))
    ent_threshold.pack(side="left", padx=(4, 16))

    tk.Label(settings_row, text="Min Contour Area:", bg="black", fg="#999", font=("Arial", 9)).pack(side="left")
    ent_min_area = tk.Entry(settings_row, bg="#111", fg="white", font=("Arial", 10),
                            insertbackground="white", width=6)
    ent_min_area.insert(0, str(v_cfg.get("min_contour_area", 500)))
    ent_min_area.pack(side="left", padx=(4, 16))

    # Vision enabled checkbox
    vision_enabled_var = tk.BooleanVar(value=v_cfg.get("vision_enabled", True))
    chk_enabled = tk.Checkbutton(settings_row, text="Vision Enabled", variable=vision_enabled_var,
                                  bg="black", fg="#76ff03", selectcolor="#111",
                                  activebackground="black", activeforeground="#76ff03",
                                  font=("Arial", 9, "bold"))
    chk_enabled.pack(side="right")

    # --- Row 2: Part → Model mapping table ---
    table_frame = tk.Frame(v_inner, bg="black")
    table_frame.pack(fill="both", expand=True, pady=(0, 6))

    cols = ("PART NUMBER", "MODEL FILE", "REFERENCES", "CREATED")
    tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=4)
    sb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)

    tree.heading("PART NUMBER", text="PART NUMBER")
    tree.heading("MODEL FILE", text="MODEL FILE")
    tree.heading("REFERENCES", text="REFS")
    tree.heading("CREATED", text="CREATED")
    tree.column("PART NUMBER", width=150, anchor="center")
    tree.column("MODEL FILE", width=180, anchor="center")
    tree.column("REFERENCES", width=60, anchor="center")
    tree.column("CREATED", width=150, anchor="center")

    def _refresh_model_table():
        tree.delete(*tree.get_children())
        v_cfg_now = load_vision_config()
        import numpy as np
        models_dir = os.path.join(os.path.dirname(__file__), "vision_models")
        for pno, filename in v_cfg_now.get("part_mapping", {}).items():
            refs = "?"
            created = "?"
            fpath = os.path.join(models_dir, filename)
            if os.path.exists(fpath):
                try:
                    data = np.load(fpath, allow_pickle=True)
                    mcfg = json.loads(str(data["config"]))
                    refs = str(mcfg.get("num_references", "?"))
                    created = mcfg.get("created", "?")
                except Exception:
                    pass
            tree.insert("", "end", iid=pno, values=(pno, filename, refs, created))

    _refresh_model_table()

    # --- Row 3: Buttons ---
    btn_row = tk.Frame(v_inner, bg="black")
    btn_row.pack(fill="x")

    def _build_model():
        """Open a teaching dialog to build a contour reference model for a part number."""
        # Ask for part number
        dlg = tk.Toplevel(parent)
        dlg.title("Build Vision Model — Enter Part Number")
        dlg.geometry("350x120")
        dlg.configure(bg="#222")
        dlg.transient(parent)
        dlg.grab_set()

        tk.Label(dlg, text="Part Number:", bg="#222", fg="white", font=("Arial", 11)).pack(pady=(15, 5))
        ent_pno = tk.Entry(dlg, bg="#111", fg="white", font=("Arial", 12), insertbackground="white", width=25)
        ent_pno.pack(pady=5)
        ent_pno.focus_set()

        def _proceed():
            pno = ent_pno.get().strip().upper()
            if not pno:
                messagebox.showwarning("Validation", "Enter a Part Number.", parent=dlg)
                return
            dlg.destroy()
            # Get camera index from cam1 panel selection
            d1_sel = cam1_panel["cmb_dev"].current()
            r1_sel = cam1_panel["cmb_res"].current()
            ci = cam_indices[d1_sel] if d1_sel > 0 else -1
            w, h = RESOLUTIONS[r1_sel][1], RESOLUTIONS[r1_sel][2]
            if ci < 0:
                messagebox.showerror("Error", "Please select Camera 1 first.", parent=parent)
                return
            _open_contour_builder(parent, pno, ci, w, h, _refresh_model_table)

        tk.Button(dlg, text="Continue →", bg="#1b5e20", fg="white",
                  font=("Arial", 11, "bold"), bd=0, padx=20, pady=6,
                  command=_proceed).pack(pady=5)
        ent_pno.bind("<Return>", lambda e: _proceed())

    def _delete_model():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a part from the table first.")
            return
        pno = sel[0]
        if not messagebox.askyesno("Confirm", f"Delete vision model for '{pno}'?"):
            return
        ctrl = VisionController()
        ctrl.delete_model(pno)
        _refresh_model_table()
        messagebox.showinfo("Deleted", f"Vision model for '{pno}' deleted.")

    def _test_model():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a part from the table first.")
            return
        pno = sel[0]
        ctrl = VisionController()
        result = ctrl.inspect(pno)
        if result.judgement == "OK":
            messagebox.showinfo("Vision Test",
                f"Part: {pno}\nResult: ✅ OK\n"
                f"Match Score: {result.match_score:.4f} (threshold: {result.threshold})\n"
                f"Time: {result.processing_time_ms}ms")
        elif result.judgement == "NG":
            messagebox.showwarning("Vision Test",
                f"Part: {pno}\nResult: ❌ NG\n"
                f"Match Score: {result.match_score:.4f} (threshold: {result.threshold})\n"
                f"Reason: {result.error}\n"
                f"Time: {result.processing_time_ms}ms")
        else:
            messagebox.showerror("Vision Test",
                f"Part: {pno}\nResult: ⚠ ERROR\n"
                f"Error: {result.error}")

    btn_build = tk.Button(btn_row, text="📷  Build Model for Part", bg="#4a148c", fg="white",
                          font=("Arial", 10, "bold"), bd=0, padx=14, pady=5,
                          cursor="hand2", activebackground="#7b1fa2", command=_build_model)
    btn_build.pack(side="left", padx=(0, 8))

    btn_test = tk.Button(btn_row, text="🔍  Test Selected Model", bg="#e65100", fg="white",
                         font=("Arial", 10, "bold"), bd=0, padx=14, pady=5,
                         cursor="hand2", activebackground="#ff9800", command=_test_model)
    btn_test.pack(side="left", padx=(0, 8))

    btn_del = tk.Button(btn_row, text="🗑  Delete Selected", bg="#b71c1c", fg="white",
                        font=("Arial", 10, "bold"), bd=0, padx=14, pady=5,
                        cursor="hand2", activebackground="#d32f2f", command=_delete_model)
    btn_del.pack(side="left")

    # --- Bottom: Save / Detected info ---
    bottom = tk.Frame(content, bg="black")
    bottom.pack(fill="x", pady=(10, 0))

    det_text = f"Detected {len(detected)} camera device(s)" if _cv2_ok else "OpenCV not available"
    tk.Label(bottom, text=det_text, bg="black", fg="#666", font=("Arial", 9)).pack(side="left")

    def _save():
        # Stop all previews
        for p in previews:
            p.stop()

        d1_sel = cam1_panel["cmb_dev"].current()
        d2_sel = cam2_panel["cmb_dev"].current()
        r1_sel = cam1_panel["cmb_res"].current()
        r2_sel = cam2_panel["cmb_res"].current()

        new_cfg = {
            "cam1_index":   cam_indices[d1_sel] if d1_sel > 0 else -1,
            "cam2_index":   cam_indices[d2_sel] if d2_sel > 0 else -1,
            "cam1_width":   RESOLUTIONS[r1_sel][1],
            "cam1_height":  RESOLUTIONS[r1_sel][2],
            "cam2_width":   RESOLUTIONS[r2_sel][1],
            "cam2_height":  RESOLUTIONS[r2_sel][2],
            "cam1_enabled": d1_sel > 0,
            "cam2_enabled": d2_sel > 0,
        }
        _save_cfg(new_cfg)

        # Save vision config
        try:
            v_cfg["vision_enabled"] = vision_enabled_var.get()
            v_cfg["camera_source"] = cmb_cam_src.get()
            v_cfg["match_threshold"] = float(ent_threshold.get().strip())
            v_cfg["min_contour_area"] = int(ent_min_area.get().strip())
            save_vision_config(v_cfg)
        except ValueError:
            messagebox.showerror("Validation", "Threshold must be a number, Min Area must be an integer.")
            return

        messagebox.showinfo("Saved", "Camera and vision settings saved successfully.\nChanges will apply on next test console load.")

    btn_save = tk.Button(bottom, text="💾  Save All Settings", bg="#0d47a1", fg="white",
                         font=("Arial", 11, "bold"), bd=0, padx=20, pady=8,
                         cursor="hand2", activebackground="#1565c0", command=_save)
    btn_save.pack(side="right")

    # Cleanup when leaving page
    def _on_destroy(e):
        if e.widget == content:
            for p in previews:
                p.stop()
    content.bind("<Destroy>", _on_destroy)


# ═══════════════════════════════════════════════════════════════════════════════
# Contour Model Builder Dialog
# ═══════════════════════════════════════════════════════════════════════════════

def _open_contour_builder(parent, part_number, cam_index, width, height, on_done_callback):
    """
    Open a Toplevel window that lets the operator:
    1. See live camera feed with contour overlay
    2. Draw an ROI
    3. Adjust Canny thresholds until contour is clean
    4. Capture 3-5 reference images
    5. Save the contour model for the given part number
    """
    if not _cv2_ok or not _pil_ok:
        messagebox.showerror("Error", "OpenCV and Pillow are required.", parent=parent)
        return

    win = tk.Toplevel(parent)
    win.title(f"Build Contour Model — {part_number}")
    win.geometry("900x620")
    win.configure(bg="#222")
    win.transient(parent)
    win.grab_set()

    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        messagebox.showerror("Error", "Could not open camera.", parent=win)
        win.destroy()
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    running = {"value": True}
    current_frame = {"value": None}
    captured_images = []
    roi_state = {"roi": None, "drawing": False, "start": None, "end": None}

    # --- Left: Video ---
    left = tk.Frame(win, bg="#222")
    left.pack(side="left", fill="both", expand=True, padx=8, pady=8)

    lbl_video = tk.Label(left, bg="black")
    lbl_video.pack(fill="both", expand=True)

    # --- Right: Controls ---
    right = tk.Frame(win, bg="#333", width=250)
    right.pack(side="right", fill="y", padx=8, pady=8)
    right.pack_propagate(False)

    tk.Label(right, text=f"Part: {part_number}", bg="#333", fg="#e8a000",
             font=("Arial", 12, "bold")).pack(pady=(10, 5))

    tk.Label(right, text="Contour Model Builder", bg="#333", fg="white",
             font=("Arial", 10)).pack(pady=(0, 10))

    # Preprocessing sliders
    tk.Label(right, text="─── Preprocessing ───", bg="#333", fg="#888",
             font=("Arial", 9)).pack(fill="x", pady=(5, 2))

    tk.Label(right, text="Canny Low:", bg="#333", fg="#ccc", font=("Arial", 9)).pack(anchor="w", padx=10)
    slider_canny_low = tk.Scale(right, from_=10, to=200, orient="horizontal",
                                 bg="#333", fg="white", highlightbackground="#333",
                                 troughcolor="#111", length=200)
    slider_canny_low.set(50)
    slider_canny_low.pack(padx=10)

    tk.Label(right, text="Canny High:", bg="#333", fg="#ccc", font=("Arial", 9)).pack(anchor="w", padx=10)
    slider_canny_high = tk.Scale(right, from_=50, to=400, orient="horizontal",
                                  bg="#333", fg="white", highlightbackground="#333",
                                  troughcolor="#111", length=200)
    slider_canny_high.set(150)
    slider_canny_high.pack(padx=10)

    lbl_status = tk.Label(right, text="Images: 0 / 5", bg="#333", fg="#ccc",
                          font=("Arial", 10))
    lbl_status.pack(pady=8)

    lbl_contour_info = tk.Label(right, text="Contour: ---", bg="#333", fg="#ccc",
                                font=("Arial", 9))
    lbl_contour_info.pack(pady=2)

    # ROI Button
    btn_roi = tk.Button(right, text="Draw ROI (click & drag)", bg="#0d47a1", fg="white",
                        font=("Arial", 9, "bold"), bd=0, padx=10, pady=4, cursor="hand2")
    btn_roi.pack(fill="x", padx=10, pady=4)

    def _toggle_roi():
        if roi_state["drawing"]:
            roi_state["drawing"] = False
            btn_roi.config(text="Draw ROI (click & drag)", bg="#0d47a1")
        else:
            roi_state["drawing"] = True
            roi_state["roi"] = None
            roi_state["start"] = None
            roi_state["end"] = None
            btn_roi.config(text="Drawing... drag on video", bg="#ff9800")
    btn_roi.config(command=_toggle_roi)

    # Capture button
    btn_capture = tk.Button(right, text="📷  Capture Reference", bg="#1b5e20", fg="white",
                            font=("Arial", 10, "bold"), bd=0, padx=10, pady=6, cursor="hand2")
    btn_capture.pack(fill="x", padx=10, pady=4)

    def _capture():
        if current_frame["value"] is not None and len(captured_images) < 5:
            captured_images.append(current_frame["value"].copy())
            lbl_status.config(text=f"Images: {len(captured_images)} / 5")
            # Flash
            lbl_video.config(bg="white")
            win.after(80, lambda: lbl_video.config(bg="black"))
            if len(captured_images) >= 3:
                btn_save.config(state="normal")
    btn_capture.config(command=_capture)

    # Save button
    btn_save = tk.Button(right, text="💾  Save Model", bg="#b71c1c", fg="white",
                         font=("Arial", 10, "bold"), bd=0, padx=10, pady=6,
                         cursor="hand2", state="disabled")
    btn_save.pack(fill="x", padx=10, pady=(10, 4))

    def _save_model():
        if len(captured_images) < 3:
            messagebox.showwarning("Need More", "Capture at least 3 reference images.", parent=win)
            return

        roi = roi_state["roi"]
        if not roi:
            # Use full frame
            h, w = captured_images[0].shape[:2]
            roi = {"x": 0, "y": 0, "width": w, "height": h}

        preprocessing = {
            "blur_kernel": 5,
            "canny_low": slider_canny_low.get(),
            "canny_high": slider_canny_high.get()
        }

        try:
            from vision_engine.vision_controller import VisionController
            ctrl = VisionController()
            path = ctrl.build_and_save_model(
                part_number=part_number,
                images=captured_images,
                roi=roi,
                preprocessing=preprocessing,
                match_threshold=float(ctrl.config.get("match_threshold", 0.15)),
                min_contour_area=int(ctrl.config.get("min_contour_area", 500)),
            )
            messagebox.showinfo("Success",
                f"Model saved for '{part_number}'\n"
                f"References: {len(captured_images)}\n"
                f"File: {os.path.basename(path)}", parent=win)
            running["value"] = False
            cap.release()
            win.destroy()
            if on_done_callback:
                on_done_callback()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=win)

    btn_save.config(command=_save_model)

    # --- Mouse events for ROI drawing ---
    def _scale_coords(event):
        """Convert label click coords back to original frame coords."""
        if current_frame["value"] is None:
            return None, None
        fh, fw = current_frame["value"].shape[:2]
        lw = lbl_video.winfo_width()
        lh = lbl_video.winfo_height()
        if lw < 10 or lh < 10:
            return None, None
        scale = min(lw / fw, lh / fh)
        dw, dh = int(fw * scale), int(fh * scale)
        ox, oy = (lw - dw) // 2, (lh - dh) // 2
        if not (ox <= event.x <= ox + dw and oy <= event.y <= oy + dh):
            return None, None
        rx = int((event.x - ox) / scale)
        ry = int((event.y - oy) / scale)
        return rx, ry

    def _mouse_down(event):
        if roi_state["drawing"]:
            rx, ry = _scale_coords(event)
            if rx is not None:
                roi_state["start"] = (rx, ry)
                roi_state["end"] = (rx, ry)

    def _mouse_drag(event):
        if roi_state["drawing"] and roi_state["start"]:
            rx, ry = _scale_coords(event)
            if rx is not None:
                roi_state["end"] = (rx, ry)

    def _mouse_up(event):
        if roi_state["drawing"] and roi_state["start"] and roi_state["end"]:
            x1, y1 = roi_state["start"]
            x2, y2 = roi_state["end"]
            x, y = min(x1, x2), min(y1, y2)
            w, h = abs(x2 - x1), abs(y2 - y1)
            if w > 20 and h > 20:
                roi_state["roi"] = {"x": x, "y": y, "width": w, "height": h}
                roi_state["drawing"] = False
                btn_roi.config(text=f"ROI: {w}x{h} @ ({x},{y})", bg="#0d47a1")
            roi_state["start"] = None
            roi_state["end"] = None

    lbl_video.bind("<ButtonPress-1>", _mouse_down)
    lbl_video.bind("<B1-Motion>", _mouse_drag)
    lbl_video.bind("<ButtonRelease-1>", _mouse_up)

    # --- Video loop with contour overlay ---
    photo_ref = {"photo": None}

    def _update():
        if not running["value"]:
            return
        ret, frame = cap.read()
        if not ret:
            win.after(33, _update)
            return

        current_frame["value"] = frame.copy()
        disp = frame.copy()

        # Draw ROI
        roi = roi_state["roi"]
        if roi:
            cv2.rectangle(disp, (roi["x"], roi["y"]),
                          (roi["x"] + roi["width"], roi["y"] + roi["height"]),
                          (0, 255, 0), 2)
            # Extract and draw contour within ROI
            region = frame[roi["y"]:roi["y"]+roi["height"], roi["x"]:roi["x"]+roi["width"]]
        elif roi_state["start"] and roi_state["end"] and roi_state["drawing"]:
            cv2.rectangle(disp, roi_state["start"], roi_state["end"], (255, 0, 0), 2)
            region = None
        else:
            region = frame

        # Contour detection overlay
        if region is not None and region.size > 0:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, slider_canny_low.get(), slider_canny_high.get())
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            edges = cv2.dilate(edges, kernel, iterations=1)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            valid = [c for c in contours if cv2.contourArea(c) >= 500]

            if valid:
                biggest = max(valid, key=cv2.contourArea)
                area = cv2.contourArea(biggest)
                # Offset contours back to full-frame coords
                offset_x = roi["x"] if roi else 0
                offset_y = roi["y"] if roi else 0
                shifted = biggest.copy()
                shifted[:, :, 0] += offset_x
                shifted[:, :, 1] += offset_y
                cv2.drawContours(disp, [shifted], -1, (0, 255, 255), 2)
                win.after(0, lambda a=area: lbl_contour_info.config(
                    text=f"Contour: area={int(a)}, pts={len(biggest)}", fg="#76ff03"))
            else:
                win.after(0, lambda: lbl_contour_info.config(text="Contour: none detected", fg="#ff5555"))

        # Display
        disp_rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(disp_rgb)
        lw, lh = lbl_video.winfo_width(), lbl_video.winfo_height()
        if lw > 10 and lh > 10:
            img.thumbnail((lw, lh), Image.Resampling.LANCZOS)
        photo_ref["photo"] = ImageTk.PhotoImage(img)
        lbl_video.config(image=photo_ref["photo"])

        if running["value"]:
            win.after(33, _update)

    def _on_close():
        running["value"] = False
        cap.release()
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", _on_close)
    win.after(100, _update)
