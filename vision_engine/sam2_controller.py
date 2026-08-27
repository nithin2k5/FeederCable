import os
import time
import cv2
import numpy as np
import torch

try:
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    _SAM2_AVAILABLE = True
except ImportError:
    _SAM2_AVAILABLE = False

from .vision_controller import VisionResult

# Define paths for SAM2 models
_SAM2_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sam2_models")

class Sam2VisionController:
    """
    Zero-Shot Vision Controller using Meta's SAM 2.
    Allows clients to select a region (bounding box) on a master image,
    and the system extracts the precise part mask without training.
    """
    def __init__(self):
        self._predictor = None
        os.makedirs(_SAM2_DIR, exist_ok=True)
        self.config = {"vision_enabled": True}
        
        # Configuration for the SAM2 model size (tiny, small, base, large)
        self.model_cfg = "sam2_hiera_t.yaml" # Tiny model for speed on CPU/Mac
        self.model_checkpoint = os.path.join(_SAM2_DIR, "sam2_hiera_tiny.pt")

    def reload_config(self):
        self._predictor = None

    def has_model(self, part_number: str) -> bool:
        # SAM 2 is zero-shot, so it doesn't need a specific model per part.
        # It just needs the base checkpoint to exist.
        return os.path.exists(self.model_checkpoint)

    def _get_cam_index(self) -> int:
        import configparser
        cam_cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "camera_cfg.ini")
        if not os.path.exists(cam_cfg_path): return -1
        cfg = configparser.ConfigParser()
        cfg.read(cam_cfg_path)
        return cfg.getint("CAMERA", "cam1_index", fallback=-1)

    def _capture_frame(self):
        idx = self._get_cam_index()
        if idx < 0: return None
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened(): return None
        for _ in range(5): cap.read()
        ret, frame = cap.read()
        cap.release()
        return frame if ret else None
        
    def _initialize_predictor(self):
        if self._predictor is None:
            # Check for Apple Silicon (MPS) or fallback to CPU
            device = "cpu"
            if torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
                
            sam2_model = build_sam2(self.model_cfg, self.model_checkpoint, device=device)
            self._predictor = SAM2ImagePredictor(sam2_model)
            print(f"SAM 2 initialized on {device}")

    def inspect_with_box(self, part_number: str, box_coords: list) -> VisionResult:
        """
        Inspect an image based on a bounding box provided by the client UI.
        box_coords: [x_min, y_min, x_max, y_max]
        """
        start = time.time()
        
        if not _SAM2_AVAILABLE:
            return VisionResult(ok=False, judgement="ERROR", part_number=part_number, 
                                error="SAM 2 package not installed.")

        if not os.path.exists(self.model_checkpoint):
            return VisionResult(ok=False, judgement="ERROR", part_number=part_number, 
                                error=f"SAM 2 checkpoint not found in {_SAM2_DIR}")

        try:
            self._initialize_predictor()
        except Exception as e:
            return VisionResult(ok=False, judgement="ERROR", part_number=part_number, error=str(e))
                
        frame = self._capture_frame()
        if frame is None:
            return VisionResult(ok=False, judgement="ERROR", part_number=part_number, error="Camera not available")
            
        # Convert BGR (OpenCV) to RGB (SAM2 expects RGB)
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        try:
            # 1. Set the image in the predictor
            self._predictor.set_image(image_rgb)
            
            # 2. Provide the bounding box prompt
            input_box = np.array(box_coords)
            
            # 3. Predict the precise mask
            masks, scores, logits = self._predictor.predict(
                box=input_box,
                multimask_output=False # We want the single best mask for the part
            )
            
            best_score = float(scores[0])
            elapsed = int((time.time() - start) * 1000)
            
            # If the model is confident it found an object mask matching the box prompt
            if best_score > 0.8:
                # You now have `masks[0]`, which is a boolean numpy array of the exact part shape!
                # You can save this, compare its area to a golden template, or check for missing pieces.
                return VisionResult(ok=True, judgement="OK", part_number=part_number, 
                                    match_score=best_score, threshold=0.8, processing_time_ms=elapsed)
            else:
                return VisionResult(ok=False, judgement="NG", part_number=part_number, 
                                    match_score=best_score, threshold=0.8, processing_time_ms=elapsed, 
                                    error="Could not confidently segment part in the given box")
                                    
        except Exception as e:
             return VisionResult(ok=False, judgement="ERROR", part_number=part_number, error=str(e))
