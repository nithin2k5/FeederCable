"""
camera_settings.py
===================
Camera Settings configuration page.
Allows selecting camera devices for Camera 1 and Camera 2,
adjusting resolution, and previewing live feeds.
Settings are persisted to camera_cfg.ini.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import configparser
import os
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
    top.pack(fill="both", expand=True)
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
        preview_container = tk.Frame(inner, bg="#111", bd=1, relief="solid", width=320, height=240)
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
            pw, ph = min(rw, 320), min(rh, 240)
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
        messagebox.showinfo("Saved", "Camera settings saved successfully.\nChanges will apply on next test console load.")

    btn_save = tk.Button(bottom, text="💾  Save Settings", bg="#0d47a1", fg="white",
                         font=("Arial", 11, "bold"), bd=0, padx=20, pady=8,
                         cursor="hand2", activebackground="#1565c0", command=_save)
    btn_save.pack(side="right")

    try:
        from vision_engine_ui import open_builder_ui
        def _open_builder():
            d1_sel = cam1_panel["cmb_dev"].current()
            r1_sel = cam1_panel["cmb_res"].current()
            ci = cam_indices[d1_sel] if d1_sel > 0 else -1
            w, h = RESOLUTIONS[r1_sel][1], RESOLUTIONS[r1_sel][2]
            open_builder_ui(parent, ci, w, h)
            
        btn_build = tk.Button(bottom, text="📷  Build Reference Model", bg="#4a148c", fg="white",
                              font=("Arial", 11, "bold"), bd=0, padx=20, pady=8,
                              cursor="hand2", activebackground="#7b1fa2", command=_open_builder)
        btn_build.pack(side="right", padx=10)

        def _open_tester():
            from tkinter import filedialog
            d1_sel = cam1_panel["cmb_dev"].current()
            r1_sel = cam1_panel["cmb_res"].current()
            ci = cam_indices[d1_sel] if d1_sel > 0 else -1
            w, h = RESOLUTIONS[r1_sel][1], RESOLUTIONS[r1_sel][2]
            
            model_path = filedialog.askdirectory(title="Select Reference Model to Test")
            if not model_path:
                return
                
            try:
                from vision_engine_ui import open_tester_ui
                open_tester_ui(parent, ci, w, h, model_path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open tester: {e}")

        btn_test = tk.Button(bottom, text="🔍  Test Reference", bg="#e65100", fg="white",
                             font=("Arial", 11, "bold"), bd=0, padx=20, pady=8,
                             cursor="hand2", activebackground="#ff9800", command=_open_tester)
        btn_test.pack(side="right", padx=10)
    except ImportError:
        pass

    # Cleanup when leaving page
    def _on_destroy(e):
        if e.widget == content:
            for p in previews:
                p.stop()
    content.bind("<Destroy>", _on_destroy)
