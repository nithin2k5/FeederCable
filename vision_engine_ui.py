import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
from PIL import Image, ImageTk
import threading
import time
from vision_engine.reference_model import build_reference_model
import numpy as np

class ReferenceModelBuilderUI(tk.Toplevel):
    def __init__(self, parent, cam_index, width, height):
        super().__init__(parent)
        self.title("Build Reference Model")
        self.geometry("800x600")
        self.configure(bg="#222")
        self.cam_index = cam_index
        self.cam_width = width
        self.cam_height = height
        
        self.cap = None
        self.running = False
        self.current_frame = None
        
        self.captured_images = []
        self.roi = None
        
        # UI Elements
        self.left_frame = tk.Frame(self, bg="#222")
        self.left_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        self.lbl_video = tk.Label(self.left_frame, bg="black")
        self.lbl_video.pack(fill="both", expand=True)
        
        self.right_frame = tk.Frame(self, bg="#333", width=250)
        self.right_frame.pack(side="right", fill="y", padx=10, pady=10)
        self.right_frame.pack_propagate(False)
        
        tk.Label(self.right_frame, text="Reference Model Builder", bg="#333", fg="white", font=("Arial", 12, "bold")).pack(pady=10)
        
        self.lbl_status = tk.Label(self.right_frame, text="Images: 0 / 10", bg="#333", fg="#ccc", font=("Arial", 10))
        self.lbl_status.pack(pady=5)
        
        self.btn_capture = tk.Button(self.right_frame, text="Capture Image", bg="#1b5e20", fg="white", font=("Arial", 10, "bold"), command=self.capture_image)
        self.btn_capture.pack(fill="x", padx=10, pady=5)
        
        self.btn_upload = tk.Button(self.right_frame, text="Upload Dataset", bg="#4a148c", fg="white", font=("Arial", 10, "bold"), command=self.upload_dataset)
        self.btn_upload.pack(fill="x", padx=10, pady=5)
        
        self.btn_set_roi = tk.Button(self.right_frame, text="Set ROI (Full Image)", bg="#0d47a1", fg="white", font=("Arial", 10, "bold"), command=self.toggle_roi_mode)
        self.btn_set_roi.pack(fill="x", padx=10, pady=5)
        
        self.btn_build = tk.Button(self.right_frame, text="Build & Save Model", bg="#b71c1c", fg="white", font=("Arial", 10, "bold"), command=self.build_model, state="disabled")
        self.btn_build.pack(fill="x", padx=10, pady=20)
        
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
        
        if self.roi:
            cv2.rectangle(disp_frame, (self.roi['x'], self.roi['y']), 
                          (self.roi['x']+self.roi['width'], self.roi['y']+self.roi['height']), 
                          (0, 255, 0), 2)
        elif self.rect_start and self.rect_end and self.roi_mode:
            cv2.rectangle(disp_frame, self.rect_start, self.rect_end, (255, 0, 0), 2)
        
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
            # Stop the live feed and show the first uploaded image so they can draw ROI
            self.show_live_feed = False
            if self.captured_images:
                self.current_frame = self.captured_images[0].copy()
                self._update_display_frame()

    def toggle_roi_mode(self):
        self.roi_mode = not self.roi_mode
        if self.roi_mode:
            self.btn_set_roi.config(text="Draw ROI on Video", bg="#ff9800")
            self.roi = None
        else:
            self.btn_set_roi.config(text="Set ROI (Full Image)", bg="#0d47a1")
            self.roi = None
            self.rect_start = None
            self.rect_end = None
        self._update_display_frame()

    def on_mouse_down(self, event):
        if self.roi_mode:
            # Map click coordinates to original frame resolution
            lbl_w, lbl_h = self.lbl_video.winfo_width(), self.lbl_video.winfo_height()
            if self.current_frame is None: return
            fh, fw = self.current_frame.shape[:2]
            
            # Calculate displayed image size
            scale = min(lbl_w/fw, lbl_h/fh)
            dw, dh = int(fw * scale), int(fh * scale)
            
            # Offsets if centered (Tkinter label centers image by default)
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
                self.btn_set_roi.config(text="Clear ROI", bg="#0d47a1")
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
            
            save_path = filedialog.askdirectory(title="Select directory to save Reference Model")
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
        self.title(f"Test Reference Model - {model_path}")
        self.geometry("800x600")
        self.configure(bg="#222")
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
        
        # UI Elements
        self.left_frame = tk.Frame(self, bg="#222")
        self.left_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        self.lbl_video = tk.Label(self.left_frame, bg="black")
        self.lbl_video.pack(fill="both", expand=True)
        
        self.right_frame = tk.Frame(self, bg="#333", width=250)
        self.right_frame.pack(side="right", fill="y", padx=10, pady=10)
        self.right_frame.pack_propagate(False)
        
        tk.Label(self.right_frame, text="Model Testing", bg="#333", fg="white", font=("Arial", 12, "bold")).pack(pady=10)
        
        self.lbl_status = tk.Label(self.right_frame, text="Waiting...", bg="#333", fg="#ccc", font=("Arial", 11))
        self.lbl_status.pack(pady=10)
        
        self.lbl_matches = tk.Label(self.right_frame, text="Matches: 0", bg="#333", fg="#4caf50", font=("Arial", 14, "bold"))
        self.lbl_matches.pack(pady=10)
        
        self.btn_close = tk.Button(self.right_frame, text="Close", bg="#b71c1c", fg="white", font=("Arial", 10, "bold"), command=self.on_close)
        self.btn_close.pack(fill="x", side="bottom", padx=10, pady=20)
        
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
        
        # We will compare against the first reference descriptor for simplicity
        ref_desc = self.model.descriptors_list[0] if self.model.descriptors_list else None
        
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                disp_frame = frame.copy()
                
                # Apply ROI mask if present
                roi = self.model.roi
                mask = None
                if roi:
                    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
                    x, y, w, h = roi.get("x", 0), roi.get("y", 0), roi.get("width", frame.shape[1]), roi.get("height", frame.shape[0])
                    mask[y:y+h, x:x+w] = 255
                    cv2.rectangle(disp_frame, (x, y), (x+w, y+h), (255, 255, 0), 2)
                
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
                                    
                        # Draw keypoints
                        disp_frame = cv2.drawKeypoints(disp_frame, kp, None, color=(0,255,0), flags=0)
                    except Exception as e:
                        pass
                
                # Update UI
                if good_matches > 15:
                    status_text = "MATCH"
                    status_fg = "#00FF00"
                else:
                    status_text = "NO MATCH"
                    status_fg = "#FF0000"
                    
                disp_frame = cv2.cvtColor(disp_frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(disp_frame)
                
                lbl_w, lbl_h = self.lbl_video.winfo_width(), self.lbl_video.winfo_height()
                if lbl_w > 10 and lbl_h > 10:
                    img.thumbnail((lbl_w, lbl_h), Image.Resampling.LANCZOS)
                
                # Update UI safely from main thread
                def _update_ui(st_text=status_text, st_fg=status_fg, matches=good_matches, pil_img=img):
                    try:
                        self.lbl_status.config(text=st_text, fg=st_fg)
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
