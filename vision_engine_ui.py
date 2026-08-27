import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
from PIL import Image, ImageTk
import threading
import time
from vision_engine.reference_model import build_reference_model
import numpy as np
import os

class ReferenceModelBuilderUI(tk.Toplevel):
    def __init__(self, parent, cam_index, width, height):
        super().__init__(parent)
        self.title("Build Reference Model")
        self.geometry("900x650")
        self.configure(bg="#1E1E1E")
        self.cam_index = cam_index
        self.cam_width = width
        self.cam_height = height
        
        self.cap = None
        self.running = False
        self.current_frame = None
        
        self.captured_images = []
        self.roi = None
        
        # UI Styling (Modern Dark Theme)
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure frames and labels
        style.configure("Dark.TFrame", background="#1E1E1E")
        style.configure("Sidebar.TFrame", background="#2D2D30")
        style.configure("Title.TLabel", background="#2D2D30", foreground="#FFFFFF", font=("Segoe UI", 14, "bold"))
        style.configure("Status.TLabel", background="#2D2D30", foreground="#AAAAAA", font=("Segoe UI", 11))
        
        # Configure modern flat buttons
        style.configure("Action.TButton", font=("Segoe UI", 11, "bold"), foreground="white", padding=8)
        style.map("Action.TButton", background=[("active", "#454545")])
        
        style.configure("Capture.TButton", font=("Segoe UI", 11, "bold"), foreground="white", background="#2E7D32", padding=8)
        style.map("Capture.TButton", background=[("active", "#1B5E20")])
        
        style.configure("Build.TButton", font=("Segoe UI", 11, "bold"), foreground="white", background="#C62828", padding=8)
        style.map("Build.TButton", background=[("active", "#B71C1C"), ("disabled", "#555555")])

        # Layout
        self.left_frame = ttk.Frame(self, style="Dark.TFrame")
        self.left_frame.pack(side="left", fill="both", expand=True, padx=15, pady=15)
        
        # Add a subtle border around the video feed
        self.video_container = tk.Frame(self.left_frame, bg="#000000", bd=2, relief="flat")
        self.video_container.pack(fill="both", expand=True)
        
        self.lbl_video = tk.Label(self.video_container, bg="black")
        self.lbl_video.pack(fill="both", expand=True)
        
        self.right_frame = ttk.Frame(self, style="Sidebar.TFrame", width=280)
        self.right_frame.pack(side="right", fill="y")
        self.right_frame.pack_propagate(False)
        
        # Sidebar content with padding
        sidebar_content = tk.Frame(self.right_frame, bg="#2D2D30")
        sidebar_content.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(sidebar_content, text="Reference Builder", style="Title.TLabel").pack(pady=(0, 20))
        
        self.lbl_status = ttk.Label(sidebar_content, text="Images: 0 / 10", style="Status.TLabel")
        self.lbl_status.pack(pady=(0, 20))
        
        self.btn_capture = ttk.Button(sidebar_content, text="📸 Capture Image", style="Capture.TButton", command=self.capture_image)
        self.btn_capture.pack(fill="x", pady=8)
        
        self.btn_upload = ttk.Button(sidebar_content, text="📁 Upload Dataset", style="Action.TButton", command=self.upload_dataset)
        self.btn_upload.pack(fill="x", pady=8)
        
        self.btn_set_roi = ttk.Button(sidebar_content, text="🎯 Draw ROI", style="Action.TButton", command=self.toggle_roi_mode)
        self.btn_set_roi.pack(fill="x", pady=8)
        
        # Spacer
        tk.Frame(sidebar_content, bg="#2D2D30", height=40).pack(fill="x")
        
        self.btn_build = ttk.Button(sidebar_content, text="⚙️ Build & Save Model", style="Build.TButton", command=self.build_model, state="disabled")
        self.btn_build.pack(fill="x", side="bottom", pady=20)
        
        # ROI Drawing
        self.roi_mode = False
        self.rect_start = None
        self.rect_end = None
        self.lbl_video.bind("<ButtonPress-1>", self.on_mouse_down)
        self.lbl_video.bind("<B1-Motion>", self.on_mouse_drag)
        self.lbl_video.bind("<ButtonRelease-1>", self.on_mouse_up)
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.start_camera()

    def start_camera(self):
        self.running = True
        self.show_live_feed = True
        threading.Thread(target=self.update_frame, daemon=True).start()

    def _update_display_frame(self):
        if self.current_frame is None:
            return
        disp_frame = self.current_frame.copy()
        
        # --- IMPROVED BOUNDING BOX VISUALS ---
        if self.roi:
            x, y, w, h = self.roi['x'], self.roi['y'], self.roi['width'], self.roi['height']
            
            # 1. Darken the outside of the ROI so the part pops
            overlay = disp_frame.copy()
            cv2.rectangle(overlay, (0, 0), (disp_frame.shape[1], disp_frame.shape[0]), (0, 0, 0), -1)
            overlay[y:y+h, x:x+w] = disp_frame[y:y+h, x:x+w]
            cv2.addWeighted(overlay, 0.7, disp_frame, 0.3, 0, disp_frame)
            
            # 2. Draw a highly visible box (Thick green with black inner/outer border)
            cv2.rectangle(disp_frame, (x-2, y-2), (x+w+2, y+h+2), (0, 0, 0), 2) # Outer shadow
            cv2.rectangle(disp_frame, (x, y), (x+w, y+h), (0, 255, 0), 3)       # Main bright box
            
        elif self.rect_start and self.rect_end and self.roi_mode:
            x1, y1 = self.rect_start
            x2, y2 = self.rect_end
            x, y = min(x1, x2), min(y1, y2)
            w, h = abs(x2 - x1), abs(y2 - y1)
            if w > 0 and h > 0:
                # Live drawing box (Cyan with shadow)
                cv2.rectangle(disp_frame, (x-1, y-1), (x+w+1, y+h+1), (0, 0, 0), 2)
                cv2.rectangle(disp_frame, (x, y), (x+w, y+h), (255, 255, 0), 2)
        
        disp_frame = cv2.cvtColor(disp_frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(disp_frame)
        
        # Scale to fit window while keeping aspect ratio
        lbl_w, lbl_h = self.lbl_video.winfo_width(), self.lbl_video.winfo_height()
        if lbl_w > 10 and lbl_h > 10:
            img.thumbnail((lbl_w, lbl_h), Image.Resampling.LANCZOS)
        
        def _set_ui(pil_img=img):
            try:
                self.photo = ImageTk.PhotoImage(pil_img)
                self.lbl_video.config(image=self.photo)
            except:
                pass
        
        self.after(0, _set_ui)

    def update_frame(self):
        self.cap = cv2.VideoCapture(self.cam_index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.running = False
            return
            
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cam_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cam_height)
        
        while self.running:
            ret, frame = self.cap.read()
            if ret and self.show_live_feed:
                self.current_frame = frame.copy()
                self._update_display_frame()
            time.sleep(0.03)

    def capture_image(self):
        if self.current_frame is not None:
            if len(self.captured_images) >= 10:
                messagebox.showwarning("Limit Reached", "You have already captured the maximum of 10 reference images.")
                return
            self.captured_images.append(self.current_frame.copy())
            self.lbl_status.config(text=f"Images: {len(self.captured_images)} / 10")
            if len(self.captured_images) >= 6:
                self.btn_build.config(state="normal")
            
            # Flash effect
            self.lbl_video.config(bg="white")
            self.after(50, lambda: self.lbl_video.config(bg="black"))

    def upload_dataset(self):
        file_paths = filedialog.askopenfilenames(
            title="Select Images for Dataset",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp"), ("All Files", "*.*")]
        )
        if not file_paths:
            return
            
        added = 0
        for path in file_paths:
            if len(self.captured_images) >= 10:
                messagebox.showwarning("Limit Reached", "Maximum of 10 reference images reached.")
                break
                
            img = cv2.imread(path)
            if img is not None:
                self.captured_images.append(img)
                added += 1
                
        self.lbl_status.config(text=f"Images: {len(self.captured_images)} / 10")
        if len(self.captured_images) >= 6:
            self.btn_build.config(state="normal")
            
        if added > 0:
            messagebox.showinfo("Upload", f"Successfully uploaded {added} image(s).")
            self.show_live_feed = False
            if self.captured_images:
                self.current_frame = self.captured_images[0].copy()
                self._update_display_frame()

    def toggle_roi_mode(self):
        self.roi_mode = not self.roi_mode
        if self.roi_mode:
            self.btn_set_roi.config(text="✖ Cancel ROI")
            self.roi = None
        else:
            self.btn_set_roi.config(text="🎯 Draw ROI")
            self.roi = None
            self.rect_start = None
            self.rect_end = None
        self._update_display_frame()

    def on_mouse_down(self, event):
        if self.roi_mode:
            lbl_w, lbl_h = self.lbl_video.winfo_width(), self.lbl_video.winfo_height()
            if self.current_frame is None: return
            fh, fw = self.current_frame.shape[:2]
            
            scale = min(lbl_w/fw, lbl_h/fh)
            dw, dh = int(fw * scale), int(fh * scale)
            
            ox, oy = (lbl_w - dw) // 2, (lbl_h - dh) // 2
            
            if ox <= event.x <= ox + dw and oy <= event.y <= oy + dh:
                rx = int((event.x - ox) / scale)
                ry = int((event.y - oy) / scale)
                self.rect_start = (rx, ry)
                self.rect_end = (rx, ry)
                self._update_display_frame()

    def on_mouse_drag(self, event):
        if self.roi_mode and self.rect_start:
            lbl_w, lbl_h = self.lbl_video.winfo_width(), self.lbl_video.winfo_height()
            if self.current_frame is None: return
            fh, fw = self.current_frame.shape[:2]
            scale = min(lbl_w/fw, lbl_h/fh)
            dw, dh = int(fw * scale), int(fh * scale)
            ox, oy = (lbl_w - dw) // 2, (lbl_h - dh) // 2
            
            ex = max(ox, min(event.x, ox + dw))
            ey = max(oy, min(event.y, oy + dh))
            
            rx = int((ex - ox) / scale)
            ry = int((ey - oy) / scale)
            self.rect_end = (rx, ry)
            self._update_display_frame()

    def on_mouse_up(self, event):
        if self.roi_mode and self.rect_start and self.rect_end:
            x1, y1 = self.rect_start
            x2, y2 = self.rect_end
            x, y = min(x1, x2), min(y1, y2)
            w, h = abs(x2 - x1), abs(y2 - y1)
            if w > 10 and h > 10:
                self.roi = {"x": x, "y": y, "width": w, "height": h}
                self.roi_mode = False
                self.btn_set_roi.config(text="🗑 Clear ROI")
            self.rect_start = None
            self.rect_end = None
            self._update_display_frame()

    def build_model(self):
        if len(self.captured_images) < 6:
            messagebox.showerror("Error", "Need at least 6 images.")
            return
            
        roi = self.roi
        if not roi:
            if self.current_frame is not None:
                h, w = self.current_frame.shape[:2]
                roi = {"x": 0, "y": 0, "width": w, "height": h}
            elif self.captured_images:
                h, w = self.captured_images[0].shape[:2]
                roi = {"x": 0, "y": 0, "width": w, "height": h}
            else:
                messagebox.showerror("Error", "No frame available to determine size.")
                return
                
        try:
            model = build_reference_model(self.captured_images, roi)
            
            initial_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vision_models")
            os.makedirs(initial_dir, exist_ok=True)
            save_path = filedialog.asksaveasfilename(
                title="Save Reference Model",
                initialdir=initial_dir,
                defaultextension=".ivmodel",
                filetypes=[("IV Model Files", "*.ivmodel"), ("All Files", "*.*")]
            )
            if save_path:
                model.save(save_path)
                messagebox.showinfo("Success", f"Model saved successfully to {save_path}\n\n"
                                               f"References: {model.metadata['num_usable_images']}\n"
                                               f"Average Keypoints: {model.feature_statistics['avg_features']:.1f}\n"
                                               f"Consistency Score: {model.feature_statistics['consistency_score']:.2f}")
                self.on_close()
        except Exception as e:
            messagebox.showerror("Build Error", str(e))

    def on_close(self):
        self.running = False
        if self.cap:
            self.cap.release()
        self.destroy()

def open_builder_ui(parent, cam_index, width, height):
    ui = ReferenceModelBuilderUI(parent, cam_index, width, height)
    ui.grab_set()

class ReferenceModelTesterUI(tk.Toplevel):
    def __init__(self, parent, cam_index, width, height, model_path):
        super().__init__(parent)
        self.title(f"Test Reference Model")
        self.geometry("900x650")
        self.configure(bg="#1E1E1E")
        self.cam_index = cam_index
        self.cam_width = width
        self.cam_height = height
        
        from vision_engine.reference_model import ReferenceModel
        self.model = ReferenceModel.load(model_path)
        
        self.sift = cv2.SIFT_create()
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        self.flann = cv2.FlannBasedMatcher(index_params, search_params)
        
        self.cap = None
        self.running = False
        
        # UI Styling
        style = ttk.Style()
        style.theme_use('clam')
        
        self.left_frame = ttk.Frame(self, style="Dark.TFrame")
        self.left_frame.pack(side="left", fill="both", expand=True, padx=15, pady=15)
        
        self.video_container = tk.Frame(self.left_frame, bg="#000000", bd=2, relief="flat")
        self.video_container.pack(fill="both", expand=True)
        
        self.lbl_video = tk.Label(self.video_container, bg="black")
        self.lbl_video.pack(fill="both", expand=True)
        
        self.right_frame = ttk.Frame(self, style="Sidebar.TFrame", width=280)
        self.right_frame.pack(side="right", fill="y")
        self.right_frame.pack_propagate(False)
        
        sidebar_content = tk.Frame(self.right_frame, bg="#2D2D30")
        sidebar_content.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(sidebar_content, text="Live Testing", style="Title.TLabel").pack(pady=(0, 20))
        
        self.lbl_status = ttk.Label(sidebar_content, text="Waiting...", background="#2D2D30", foreground="#AAAAAA", font=("Segoe UI", 16, "bold"))
        self.lbl_status.pack(pady=20)
        
        self.lbl_matches = ttk.Label(sidebar_content, text="Matches: 0", background="#2D2D30", foreground="#4caf50", font=("Segoe UI", 14))
        self.lbl_matches.pack(pady=10)
        
        self.btn_close = ttk.Button(sidebar_content, text="✖ Close", style="Build.TButton", command=self.on_close)
        self.btn_close.pack(fill="x", side="bottom", pady=20)
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.start_camera()

    def start_camera(self):
        self.running = True
        threading.Thread(target=self.update_frame, daemon=True).start()

    def _preprocess(self, image):
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(blurred)

    def update_frame(self):
        self.cap = cv2.VideoCapture(self.cam_index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.running = False
            return
            
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cam_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cam_height)
        
        ref_desc = self.model.descriptors_list[0] if self.model.descriptors_list else None
        
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                disp_frame = frame.copy()
                
                roi = self.model.roi
                mask = None
                if roi:
                    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
                    x, y, w, h = roi.get("x", 0), roi.get("y", 0), roi.get("width", frame.shape[1]), roi.get("height", frame.shape[0])
                    mask[y:y+h, x:x+w] = 255
                    
                    # Improved visual for test mode bounding box
                    cv2.rectangle(disp_frame, (x-2, y-2), (x+w+2, y+h+2), (0, 0, 0), 2)
                    cv2.rectangle(disp_frame, (x, y), (x+w, y+h), (0, 255, 255), 3)
                
                preprocessed = self._preprocess(frame)
                kp, desc = self.sift.detectAndCompute(preprocessed, mask)
                
                good_matches = 0
                if desc is not None and ref_desc is not None and len(desc) > 1 and len(ref_desc) > 1:
                    try:
                        matches = self.flann.knnMatch(ref_desc, desc, k=2)
                        for m_n in matches:
                            if len(m_n) == 2:
                                m, n = m_n
                                if m.distance < 0.7 * n.distance:
                                    good_matches += 1
                                    
                        # Draw keypoints cleanly (small green dots instead of massive circles)
                        for point in kp:
                            x_pt, y_pt = int(point.pt[0]), int(point.pt[1])
                            cv2.circle(disp_frame, (x_pt, y_pt), 2, (0, 255, 0), -1)
                    except Exception as e:
                        pass
                
                # Update UI
                if good_matches > 15:
                    status_text = "✅ PASS"
                    status_fg = "#4CAF50" # Green
                else:
                    status_text = "❌ FAIL"
                    status_fg = "#F44336" # Red
                    
                disp_frame = cv2.cvtColor(disp_frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(disp_frame)
                
                lbl_w, lbl_h = self.lbl_video.winfo_width(), self.lbl_video.winfo_height()
                if lbl_w > 10 and lbl_h > 10:
                    img.thumbnail((lbl_w, lbl_h), Image.Resampling.LANCZOS)
                
                def _update_ui(st_text=status_text, st_fg=status_fg, matches=good_matches, pil_img=img):
                    try:
                        self.lbl_status.config(text=st_text, foreground=st_fg)
                        self.lbl_matches.config(text=f"Matches: {matches}")
                        self.photo = ImageTk.PhotoImage(pil_img)
                        self.lbl_video.config(image=self.photo)
                    except:
                        pass
                
                self.after(0, _update_ui)
                    
            time.sleep(0.05)

    def on_close(self):
        self.running = False
        if self.cap:
            self.cap.release()
        self.destroy()

def open_tester_ui(parent, cam_index, width, height, model_path):
    ui = ReferenceModelTesterUI(parent, cam_index, width, height, model_path)
    ui.grab_set()
