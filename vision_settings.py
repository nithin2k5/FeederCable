"""
vision_settings.py
===================
Vision Settings configuration page.
Strictly for Vision Model management (Contour Matching).
Allows adding new parts (teaching the golden sample), drawing ROI,
and testing the dataset.
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
    from vision_engine.vision_controller import VisionController, load_vision_config, save_vision_config
    
    v_cfg = load_vision_config()

    style = ttk.Style()
    style.configure("CS.TLabelframe", background="black", foreground="white", bordercolor="#444")
    style.configure("CS.TLabelframe.Label", background="black", foreground="#aaa", font=("Arial", 10, "bold"))

    content = tk.Frame(parent, bg="black")
    content.pack(fill="both", expand=True, padx=15, pady=10)

    if not _cv2_ok:
        warn = tk.Label(content, text="⚠  opencv-python not installed.",
                        bg="#331a00", fg="#ff9800", font=("Arial", 10, "bold"), pady=6)
        warn.pack(fill="x", pady=(0, 8))

    vision_lf = ttk.LabelFrame(content, text="👁  Vision Model Management  (Contour Matching)", style="CS.TLabelframe")
    vision_lf.pack(fill="both", expand=True, padx=6, pady=(10, 4))

    v_inner = tk.Frame(vision_lf, bg="black", padx=10, pady=6)
    v_inner.pack(fill="both", expand=True)

    # --- Row 1: Settings ---
    settings_row = tk.Frame(v_inner, bg="black")
    settings_row.pack(fill="x", pady=(0, 6))

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

    cols = ("PART NUMBER", "DATASET/MODEL FILE", "REFERENCES", "CREATED")
    tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=4)
    sb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)

    tree.heading("PART NUMBER", text="PART NUMBER")
    tree.heading("DATASET/MODEL FILE", text="DATASET/MODEL FILE")
    tree.heading("REFERENCES", text="REFS")
    tree.heading("CREATED", text="CREATED")
    tree.column("PART NUMBER", width=150, anchor="center")
    tree.column("DATASET/MODEL FILE", width=180, anchor="center")
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
        dlg = tk.Toplevel(parent)
        dlg.title("Add New Part Dataset")
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
            
            # Open contour builder (offline mode, no camera needed)
            _open_contour_builder(parent, pno, -1, 640, 480, _refresh_model_table)

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
        if not messagebox.askyesno("Confirm", f"Delete dataset for '{pno}'?"):
            return
        ctrl = VisionController()
        ctrl.delete_model(pno)
        _refresh_model_table()
        messagebox.showinfo("Deleted", f"Dataset for '{pno}' deleted.")

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

    btn_build = tk.Button(btn_row, text="📷  Add New Part Dataset", bg="#4a148c", fg="white",
                          font=("Arial", 10, "bold"), bd=0, padx=14, pady=5,
                          cursor="hand2", activebackground="#7b1fa2", command=_build_model)
    btn_build.pack(side="left", padx=(0, 8))

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
            v_cfg["vision_enabled"] = vision_enabled_var.get()
            v_cfg["match_threshold"] = float(ent_threshold.get().strip())
            v_cfg["min_contour_area"] = int(ent_min_area.get().strip())
            save_vision_config(v_cfg)
        except ValueError:
            messagebox.showerror("Validation", "Threshold must be a number, Min Area must be an integer.")
            return

        messagebox.showinfo("Saved", "Vision settings saved successfully.\nChanges apply on next test run.")

    btn_save = tk.Button(bottom, text="💾  Save Settings", bg="#0d47a1", fg="white",
                         font=("Arial", 11, "bold"), bd=0, padx=20, pady=8,
                         cursor="hand2", activebackground="#1565c0", command=_save)
    btn_save.pack(side="right")


# ═══════════════════════════════════════════════════════════════════════════════
# Contour Model Builder Dialog
# ═══════════════════════════════════════════════════════════════════════════════

def _open_contour_builder(parent, part_number, cam_index, width, height, on_done_callback):
    """
    Open a Toplevel window that lets the operator:
    1. Upload reference images (no camera required)
    2. Draw an ROI on the first uploaded image
    3. Adjust Canny thresholds until contour is clean
    4. Save the contour model
    """
    if not _cv2_ok or not _pil_ok:
        messagebox.showerror("Error", "OpenCV and Pillow are required.", parent=parent)
        return

    win = tk.Toplevel(parent)
    win.title(f"Teach Part Dataset — {part_number}")
    win.geometry("900x620")
    win.configure(bg="#222")
    win.transient(parent)
    win.grab_set()

    current_frame = {"value": None}
    captured_images = []
    roi_state = {"roi": None, "drawing": False, "start": None, "end": None}
    photo_ref = {"photo": None}

    # --- Left: Video ---
    left = tk.Frame(win, bg="#222")
    left.pack(side="left", fill="both", expand=True, padx=8, pady=8)

    lbl_video = tk.Label(left, bg="black", text="[ Please Upload Images ]", fg="#666", font=("Arial", 14))
    lbl_video.pack(fill="both", expand=True)

    # --- Right: Controls ---
    right = tk.Frame(win, bg="#333", width=250)
    right.pack(side="right", fill="y", padx=8, pady=8)
    right.pack_propagate(False)

    tk.Label(right, text=f"Part: {part_number}", bg="#333", fg="#e8a000",
             font=("Arial", 12, "bold")).pack(pady=(10, 5))

    tk.Label(right, text="Offline Contour Builder", bg="#333", fg="white",
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

    lbl_status = tk.Label(right, text="Images: 0", bg="#333", fg="#ccc",
                          font=("Arial", 10))
    lbl_status.pack(pady=8)

    lbl_contour_info = tk.Label(right, text="Contour: ---", bg="#333", fg="#ccc",
                                font=("Arial", 9))
    lbl_contour_info.pack(pady=2)

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
            region = frame[roi["y"]:roi["y"]+roi["height"], roi["x"]:roi["x"]+roi["width"]]
        elif roi_state["start"] and roi_state["end"] and roi_state["drawing"]:
            cv2.rectangle(disp, roi_state["start"], roi_state["end"], (255, 0, 0), 2)
            region = None
        else:
            region = frame

        if region is not None and region.size > 0:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if len(region.shape) == 3 else region
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, slider_canny_low.get(), slider_canny_high.get())
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            edges = cv2.dilate(edges, kernel, iterations=1)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            valid = [c for c in contours if cv2.contourArea(c) >= 500]

            if valid:
                biggest = max(valid, key=cv2.contourArea)
                area = cv2.contourArea(biggest)
                offset_x = roi["x"] if roi else 0
                offset_y = roi["y"] if roi else 0
                shifted = biggest.copy()
                shifted[:, :, 0] += offset_x
                shifted[:, :, 1] += offset_y
                cv2.drawContours(disp, [shifted], -1, (0, 255, 255), 2)
                lbl_contour_info.config(text=f"Contour: area={int(area)}, pts={len(biggest)}", fg="#76ff03")
            else:
                lbl_contour_info.config(text="Contour: none detected", fg="#ff5555")

        disp_rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(disp_rgb)
        
        # We need winfo_width/height but they might be 1 on first render
        lw = lbl_video.winfo_width()
        lh = lbl_video.winfo_height()
        if lw > 10 and lh > 10:
            img.thumbnail((lw, lh), Image.Resampling.LANCZOS)
        
        photo_ref["photo"] = ImageTk.PhotoImage(img)
        lbl_video.config(image=photo_ref["photo"], text="")

    slider_canny_low.config(command=_render_frame)
    slider_canny_high.config(command=_render_frame)

    # ROI Button
    btn_roi = tk.Button(right, text="Draw ROI (click & drag)", bg="#0d47a1", fg="white",
                        font=("Arial", 9, "bold"), bd=0, padx=10, pady=4, cursor="hand2")
    btn_roi.pack(fill="x", padx=10, pady=4)

    def _toggle_roi():
        if current_frame["value"] is None:
            messagebox.showwarning("Upload First", "Please upload images before drawing an ROI.", parent=win)
            return
            
        if roi_state["drawing"]:
            roi_state["drawing"] = False
            btn_roi.config(text="Draw ROI (click & drag)", bg="#0d47a1")
        else:
            roi_state["drawing"] = True
            roi_state["roi"] = None
            roi_state["start"] = None
            roi_state["end"] = None
            btn_roi.config(text="Drawing... drag on image", bg="#ff9800")
            _render_frame()
    btn_roi.config(command=_toggle_roi)

    # Upload button
    btn_upload = tk.Button(right, text="📁  Upload Images", bg="#0277bd", fg="white",
                            font=("Arial", 10, "bold"), bd=0, padx=10, pady=6, cursor="hand2")
    btn_upload.pack(fill="x", padx=10, pady=4)

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
            lbl_status.config(text=f"Images: {len(captured_images)}")
            if len(captured_images) >= 3:
                btn_save.config(state="normal")
            
            # Force layout update so _render_frame gets correct label sizes
            win.update_idletasks()
            _render_frame()

    btn_upload.config(command=_upload)

    # Save button
    btn_save = tk.Button(right, text="💾  Save Dataset", bg="#b71c1c", fg="white",
                         font=("Arial", 10, "bold"), bd=0, padx=10, pady=6,
                         cursor="hand2", state="disabled")
    btn_save.pack(fill="x", padx=10, pady=(10, 4))

    def _save_model():
        if len(captured_images) < 3:
            messagebox.showwarning("Need More", "Please upload at least 3 reference images.", parent=win)
            return

        roi = roi_state["roi"]
        if not roi:
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
                f"Dataset saved for '{part_number}'\n" \
                f"References: {len(captured_images)}\n" \
                f"File: {os.path.basename(path)}", parent=win)
            win.destroy()
            if on_done_callback:
                on_done_callback()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=win)

    btn_save.config(command=_save_model)

    # --- Mouse events for ROI drawing ---
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
        if roi_state["drawing"]:
            rx, ry = _scale_coords(event)
            if rx is not None:
                roi_state["start"] = (rx, ry)
                roi_state["end"] = (rx, ry)
                _render_frame()

    def _mouse_drag(event):
        if roi_state["drawing"] and roi_state["start"]:
            rx, ry = _scale_coords(event)
            if rx is not None:
                roi_state["end"] = (rx, ry)
                _render_frame()

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
            _render_frame()

    lbl_video.bind("<ButtonPress-1>", _mouse_down)
    lbl_video.bind("<B1-Motion>", _mouse_drag)
    lbl_video.bind("<ButtonRelease-1>", _mouse_up)
