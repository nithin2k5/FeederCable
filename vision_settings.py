"""
vision_settings.py
===================
Vision Settings configuration page.
Vision model management (Template Matching).
Allows adding new parts (teaching the golden sample), drawing ROI,
and testing the dataset against the live camera.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import os
import json

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

def render(parent):
    """Render the Vision Settings configuration page."""
    from vision_engine.vision_controller import (
        VisionController, load_vision_config, save_vision_config, DEFAULT_MATCH_THRESHOLD,
    )

    v_cfg = load_vision_config()
    ctrl = VisionController()

    style = ttk.Style()
    style.configure("CS.TLabelframe", background="black", foreground="white", bordercolor="#444")
    style.configure("CS.TLabelframe.Label", background="black", foreground="#aaa", font=("Arial", 10, "bold"))

    content = tk.Frame(parent, bg="black")
    content.pack(fill="both", expand=True, padx=15, pady=10)

    if not _cv2_ok:
        warn = tk.Label(content, text="⚠  opencv-python not installed.",
                        bg="#331a00", fg="#ff9800", font=("Arial", 10, "bold"), pady=6)
        warn.pack(fill="x", pady=(0, 8))

    vision_lf = ttk.LabelFrame(content, text="👁  Vision Model Management  (Template Matching)", style="CS.TLabelframe")
    vision_lf.pack(fill="both", expand=True, padx=6, pady=(10, 4))

    v_inner = tk.Frame(vision_lf, bg="black", padx=10, pady=6)
    v_inner.pack(fill="both", expand=True)

    # --- Row 1: Settings ---
    settings_row = tk.Frame(v_inner, bg="black")
    settings_row.pack(fill="x", pady=(0, 6))

    tk.Label(settings_row, text="Match Threshold:", bg="black", fg="#999", font=("Arial", 9)).pack(side="left")
    ent_threshold = tk.Entry(settings_row, bg="#111", fg="white", font=("Arial", 10),
                             insertbackground="white", width=6)
    ent_threshold.insert(0, str(v_cfg.get("match_threshold", DEFAULT_MATCH_THRESHOLD)))
    ent_threshold.pack(side="left", padx=(4, 16))

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

    cols = ("PART NUMBER", "MODEL FILE", "REFERENCES", "CREATED", "STATUS")
    tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=4)
    sb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)

    for c, w in (("PART NUMBER", 130), ("MODEL FILE", 150), ("REFERENCES", 55),
                 ("CREATED", 140), ("STATUS", 130)):
        tree.heading(c, text="REFS" if c == "REFERENCES" else c)
        tree.column(c, width=w, anchor="center")

    _ORPHAN_PREFIX = "!unmapped:"

    def _refresh_model_table():
        tree.delete(*tree.get_children())
        ctrl.reload_config()
        models_dir = os.path.join(os.path.dirname(__file__), "vision_models")

        mapped_files = set()
        for pno, filename in sorted(ctrl.get_mapped_parts().items()):
            mapped_files.add(filename)
            info = ctrl.model_info(pno)
            if info is None:
                tree.insert("", "end", iid=pno,
                            values=(pno, filename, "—", "—", "⚠ FILE MISSING"))
            else:
                tree.insert("", "end", iid=pno,
                            values=(pno, filename, info["references"],
                                    info["created"], "✓ Ready"))

        # Model files on disk that no part number resolves to. Production cannot
        # reach these, so surface them rather than letting them look installed.
        if os.path.exists(models_dir):
            for f in sorted(os.listdir(models_dir)):
                if f.endswith(".npz") and f not in mapped_files:
                    tree.insert("", "end", iid=_ORPHAN_PREFIX + f,
                                values=("—", f, "—", "—", "⚠ NOT MAPPED"))

    _refresh_model_table()

    def _selected_part():
        """Selected part number, or None (with an explanation shown) if unusable."""
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a part from the table first.")
            return None
        if sel[0].startswith(_ORPHAN_PREFIX):
            messagebox.showwarning(
                "Not Mapped",
                "This model file is not mapped to any part number, so production "
                "cannot use it.\n\nRe-teach the part with 'Add New Part Dataset', "
                "or map it from the Test Console camera settings.")
            return None
        return sel[0]

    # --- Row 3: Buttons ---
    btn_row = tk.Frame(v_inner, bg="black")
    btn_row.pack(fill="x")

    def _build_model():
        _, cam_w, cam_h = ctrl.cam_settings()
        _open_template_builder(parent, cam_w, cam_h, _refresh_model_table)

    def _delete_model():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a part from the table first.")
            return
        if sel[0].startswith(_ORPHAN_PREFIX):
            filename = sel[0][len(_ORPHAN_PREFIX):]
            if not messagebox.askyesno("Confirm", f"Delete unmapped model file '{filename}'?"):
                return
            try:
                os.remove(os.path.join(os.path.dirname(__file__), "vision_models", filename))
            except OSError as e:
                messagebox.showerror("Delete", str(e))
                return
            _refresh_model_table()
            messagebox.showinfo("Deleted", f"'{filename}' deleted.")
            return

        pno = sel[0]
        if not messagebox.askyesno("Confirm", f"Delete dataset for '{pno}'?"):
            return
        ctrl.delete_model(pno)
        _refresh_model_table()
        messagebox.showinfo("Deleted", f"Dataset for '{pno}' deleted.")

    def _test_model():
        pno = _selected_part()
        if pno is None:
            return

        # Runs the exact inspect() path production uses, so a pass here means a
        # pass on the line.
        ctrl.reload_config()
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

    def _connect_camera():
        import configparser
        cam_cfg_path = os.path.join(os.path.dirname(__file__), "camera_cfg.ini")
        cfg = configparser.ConfigParser()
        if os.path.exists(cam_cfg_path):
            cfg.read(cam_cfg_path)
        else:
            cfg.add_section("CAMERA")
            
        def _save_cam():
            try:
                idx = int(cam_var.get())
                if "CAMERA" not in cfg.sections():
                    cfg.add_section("CAMERA")
                cfg.set("CAMERA", "cam1_index", str(idx))
                cfg.set("CAMERA", "cam1_enabled", "True")
                with open(cam_cfg_path, "w") as f:
                    cfg.write(f)
                messagebox.showinfo("Camera", f"Camera {idx} connected and saved.")
                cam_win.destroy()
            except ValueError:
                messagebox.showerror("Error", "Invalid camera index.")

        cam_win = tk.Toplevel(parent)
        cam_win.title("Connect Camera")
        cam_win.geometry("300x150")
        cam_win.configure(bg="#222")
        cam_win.transient(parent)
        cam_win.grab_set()

        tk.Label(cam_win, text="Select Camera Index:", bg="#222", fg="white", font=("Arial", 10)).pack(pady=10)
        
        cam_var = tk.StringVar(value=cfg.get("CAMERA", "cam1_index", fallback="0") if cfg.has_section("CAMERA") else "0")
        cam_combo = ttk.Combobox(cam_win, textvariable=cam_var, values=["Detecting..."], state="readonly")
        cam_combo.pack(pady=5)
        
        def _detect_cams():
            import cv2
            cams = []
            for i in range(6):
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    cams.append(str(i))
                    cap.release()
            if not cams:
                cams = ["0", "1", "2", "3", "4", "5"]
            
            def _update_ui():
                try:
                    cam_combo.config(values=cams)
                    if cam_var.get() not in cams and cams:
                        cam_var.set(cams[0])
                except:
                    pass
            cam_win.after(0, _update_ui)
            
        import threading
        threading.Thread(target=_detect_cams, daemon=True).start()
        
        tk.Button(cam_win, text="Save & Connect", bg="#00838f", fg="white", bd=0, padx=10, pady=5, command=_save_cam).pack(pady=10)

    btn_build = tk.Button(btn_row, text="📷  Add New Part Dataset", bg="#4a148c", fg="white",
                          font=("Arial", 10, "bold"), bd=0, padx=14, pady=5,
                          cursor="hand2", activebackground="#7b1fa2", command=_build_model)
    btn_build.pack(side="left", padx=(0, 8))

    btn_camera = tk.Button(btn_row, text="📹  Connect Camera", bg="#00838f", fg="white",
                           font=("Arial", 10, "bold"), bd=0, padx=14, pady=5,
                           cursor="hand2", activebackground="#00acc1", command=_connect_camera)
    btn_camera.pack(side="left", padx=(0, 8))

    btn_test = tk.Button(btn_row, text="🔍  Test Selected Part", bg="#e65100", fg="white",
                         font=("Arial", 10, "bold"), bd=0, padx=14, pady=5,
                         cursor="hand2", activebackground="#ff9800", command=_test_model)
    btn_test.pack(side="left", padx=(0, 8))

    btn_del = tk.Button(btn_row, text="🗑  Delete Selected", bg="#b71c1c", fg="white",
                        font=("Arial", 10, "bold"), bd=0, padx=14, pady=5,
                        cursor="hand2", activebackground="#d32f2f", command=_delete_model)
    btn_del.pack(side="left")

    # --- Bottom: Save ---
    bottom = tk.Frame(content, bg="black")
    bottom.pack(fill="x", pady=(10, 0))

    def _save():
        try:
            threshold = float(ent_threshold.get().strip())
        except ValueError:
            messagebox.showerror("Validation", "Threshold must be a number.")
            return
        if not 0.0 < threshold <= 1.0:
            messagebox.showerror(
                "Validation",
                "Threshold must be between 0 and 1.\n\n"
                "This is a normalized correlation score — 1.0 is a perfect match. "
                "Values below ~0.5 will pass almost any frame.")
            return

        v_cfg["vision_enabled"] = vision_enabled_var.get()
        v_cfg["match_threshold"] = threshold
        save_vision_config(v_cfg)
        messagebox.showinfo("Saved", "Vision settings saved successfully.\nChanges apply on next test run.")

    btn_save = tk.Button(bottom, text="💾  Save Settings", bg="#0d47a1", fg="white",
                         font=("Arial", 11, "bold"), bd=0, padx=20, pady=8,
                         cursor="hand2", activebackground="#1565c0", command=_save)
    btn_save.pack(side="right")


# ═══════════════════════════════════════════════════════════════════════════════
# Template Model Builder Dialog
# ═══════════════════════════════════════════════════════════════════════════════

def _open_template_builder(parent, width, height, on_done_callback):
    """
    Unified Template Match Builder UI.
    Flow:
      1. Enter Part Number
      2. Upload Images
      3. Draw Box
      4. Save
    """
    if not _cv2_ok or not _pil_ok:
        messagebox.showerror("Error", "OpenCV and Pillow are required.", parent=parent)
        return

    win = tk.Toplevel(parent)
    win.title("Create Vision Dataset")
    win.geometry("900x620")
    win.configure(bg="#222")
    win.transient(parent)
    win.grab_set()

    current_frame = {"value": None}
    captured_images = []
    roi_state = {"roi": None, "drawing": False, "start": None, "end": None}
    photo_ref = {"photo": None}

    # --- Left: Video / Image Display ---
    left = tk.Frame(win, bg="#222")
    left.pack(side="left", fill="both", expand=True, padx=8, pady=8)

    lbl_video = tk.Label(left, bg="black", text="[ No Image Loaded ]", fg="#666", font=("Arial", 14), cursor="crosshair")
    lbl_video.pack(fill="both", expand=True)

    # --- Right: Controls & Workflow Steps ---
    right = tk.Frame(win, bg="#333", width=260)
    right.pack(side="right", fill="y", padx=8, pady=8)
    right.pack_propagate(False)

    tk.Label(right, text="Template Builder", bg="#333", fg="#e8a000",
             font=("Arial", 14, "bold")).pack(pady=(15, 15))

    # STEP 1: Part Number
    step1_lf = tk.LabelFrame(right, text=" Step 1: Part Number ", bg="#333", fg="white", font=("Arial", 10, "bold"))
    step1_lf.pack(fill="x", padx=10, pady=5)
    
    ent_pno = tk.Entry(step1_lf, bg="#111", fg="white", font=("Arial", 12), insertbackground="white", width=20)
    ent_pno.pack(padx=10, pady=10)
    ent_pno.focus_set()

    # STEP 2: Upload Images
    step2_lf = tk.LabelFrame(right, text=" Step 2: Upload Images ", bg="#333", fg="white", font=("Arial", 10, "bold"))
    step2_lf.pack(fill="x", padx=10, pady=5)
    
    btn_upload = tk.Button(step2_lf, text="📁  Select Images", bg="#0277bd", fg="white",
                            font=("Arial", 10, "bold"), bd=0, padx=10, pady=6, cursor="hand2")
    btn_upload.pack(fill="x", padx=10, pady=8)
    lbl_status = tk.Label(step2_lf, text="0 images loaded", bg="#333", fg="#ccc", font=("Arial", 9))
    lbl_status.pack(pady=(0, 8))

    # STEP 3: Draw ROI
    step3_lf = tk.LabelFrame(right, text=" Step 3: Draw Target Box ", bg="#333", fg="white", font=("Arial", 10, "bold"))
    step3_lf.pack(fill="x", padx=10, pady=5)
    
    info_txt = "Click and drag directly on\nthe image to highlight\nthe physical part."
    tk.Label(step3_lf, text=info_txt, bg="#333", fg="#aaa", font=("Arial", 9)).pack(pady=10)
    lbl_roi_info = tk.Label(step3_lf, text="ROI: Not Drawn", bg="#333", fg="#ff9800", font=("Arial", 9, "bold"))
    lbl_roi_info.pack(pady=(0, 10))

    # STEP 4: Save
    step4_lf = tk.Frame(right, bg="#333")
    step4_lf.pack(fill="x", padx=10, pady=15)
    
    btn_save = tk.Button(step4_lf, text="💾  Save Dataset", bg="#1b5e20", fg="white",
                         font=("Arial", 11, "bold"), bd=0, padx=10, pady=8,
                         cursor="hand2", state="disabled")
    btn_save.pack(fill="x")

    def _render_frame(*args):
        if current_frame["value"] is None:
            return

        frame = current_frame["value"].copy()
        disp = frame.copy()

        roi = roi_state["roi"]
        if roi:
            cv2.rectangle(disp, (roi["x"], roi["y"]),
                          (roi["x"] + roi["width"], roi["y"] + roi["height"]),
                          (0, 255, 0), 2)
        elif roi_state["start"] and roi_state["end"] and roi_state["drawing"]:
            cv2.rectangle(disp, roi_state["start"], roi_state["end"], (255, 0, 0), 2)

        disp_rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(disp_rgb)
        
        lw = lbl_video.winfo_width()
        lh = lbl_video.winfo_height()
        if lw > 10 and lh > 10:
            img.thumbnail((lw, lh), Image.Resampling.LANCZOS)
        
        photo_ref["photo"] = ImageTk.PhotoImage(img)
        lbl_video.config(image=photo_ref["photo"], text="")

    def _upload():
        from tkinter import filedialog
        filepaths = filedialog.askopenfilenames(
            parent=win,
            title="Select Reference Images",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp")]
        )
        
        added = 0
        for fp in filepaths:
            img = cv2.imread(fp)
            if img is not None:
                img_resized = cv2.resize(img, (width, height))
                captured_images.append(img_resized)
                added += 1
                
        if added > 0:
            current_frame["value"] = captured_images[0]
            lbl_status.config(text=f"{len(captured_images)} images loaded", fg="#76ff03")
            if len(captured_images) >= 3 and roi_state["roi"] is not None:
                btn_save.config(state="normal")
            win.update_idletasks()
            _render_frame()

    btn_upload.config(command=_upload)

    def _save_model():
        pno = ent_pno.get().strip().upper()
        if not pno:
            messagebox.showwarning("Validation", "Please enter a Part Number in Step 1.", parent=win)
            return
            
        if len(captured_images) < 3:
            messagebox.showwarning("Validation", "Please upload at least 3 reference images.", parent=win)
            return

        roi = roi_state["roi"]
        if not roi:
            messagebox.showwarning("Validation", "Please draw a target box on the image.", parent=win)
            return
            
        if roi["width"] < 10 or roi["height"] < 10:
            messagebox.showerror("ROI Error", "ROI is too small for matching.", parent=win)
            return

        try:
            from vision_engine.vision_controller import VisionController, DEFAULT_MATCH_THRESHOLD
            build_ctrl = VisionController()
            path = build_ctrl.build_and_save_model(
                part_number=pno,
                images=captured_images,
                roi=roi,
                match_threshold=float(build_ctrl.config.get("match_threshold", DEFAULT_MATCH_THRESHOLD))
            )
            messagebox.showinfo("Success",
                f"Dataset saved and mapped to part '{pno}'.\n\n"
                f"References: {len(captured_images)}\n"
                f"File: {os.path.basename(path)}\n"
                f"Captured at: {width}x{height}", parent=win)
            win.destroy()
            if on_done_callback:
                on_done_callback()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=win)

    btn_save.config(command=_save_model)

    # --- Mouse events for seamless ROI drawing ---
    def _scale_coords(event):
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
        if current_frame["value"] is None: return
        rx, ry = _scale_coords(event)
        if rx is not None:
            roi_state["drawing"] = True
            roi_state["start"] = (rx, ry)
            roi_state["end"] = (rx, ry)
            _render_frame()

    def _mouse_drag(event):
        if not roi_state["drawing"]: return
        rx, ry = _scale_coords(event)
        if rx is not None:
            roi_state["end"] = (rx, ry)
            _render_frame()

    def _mouse_up(event):
        if not roi_state["drawing"]: return
        roi_state["drawing"] = False
        
        if roi_state["start"] and roi_state["end"]:
            x1, y1 = roi_state["start"]
            x2, y2 = roi_state["end"]
            x, y = min(x1, x2), min(y1, y2)
            w, h = abs(x2 - x1), abs(y2 - y1)
            if w > 10 and h > 10:
                roi_state["roi"] = {"x": x, "y": y, "width": w, "height": h}
                lbl_roi_info.config(text=f"ROI Set: {w}x{h} px", fg="#76ff03")
                if len(captured_images) >= 3:
                    btn_save.config(state="normal")
            else:
                roi_state["roi"] = None
                lbl_roi_info.config(text="Box too small, try again", fg="#ff5555")
                btn_save.config(state="disabled")
                
        roi_state["start"] = None
        roi_state["end"] = None
        _render_frame()

    lbl_video.bind("<ButtonPress-1>", _mouse_down)
    lbl_video.bind("<B1-Motion>", _mouse_drag)
    lbl_video.bind("<ButtonRelease-1>", _mouse_up)
