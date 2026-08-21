import os
import time
import cv2
import numpy as np

from .vision_controller import VisionResult
from .reference_model import ReferenceModel

_MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vision_models")

class SiftVisionController:
    """
    SIFT Feature Matching Vision Controller.
    Uses Scale-Invariant Feature Transform to detect objects independently of scale, rotation, and lighting.
    """
    def __init__(self):
        self._models = {}
        os.makedirs(_MODELS_DIR, exist_ok=True)
        self.config = {"vision_enabled": True}
        
        self.sift = cv2.SIFT_create()
        index_params = dict(algorithm=1, trees=5) # FLANN_INDEX_KDTREE
        search_params = dict(checks=50)
        self.flann = cv2.FlannBasedMatcher(index_params, search_params)

    def reload_config(self):
        self._models.clear()

    def has_model(self, part_number: str) -> bool:
        return os.path.exists(os.path.join(_MODELS_DIR, f"{part_number}.ivmodel"))

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

    def _preprocess(self, image):
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(blurred)

    def inspect(self, part_number: str) -> VisionResult:
        start = time.time()
        model_path = os.path.join(_MODELS_DIR, f"{part_number}.ivmodel")
        
        if not os.path.exists(model_path):
            return VisionResult(ok=False, judgement="ERROR", part_number=part_number, 
                                error=f"SIFT model not found: {part_number}.ivmodel")
        
        if part_number not in self._models:
            try:
                self._models[part_number] = ReferenceModel.load(model_path)
            except Exception as e:
                return VisionResult(ok=False, judgement="ERROR", part_number=part_number, error=str(e))
                
        frame = self._capture_frame()
        if frame is None:
            return VisionResult(ok=False, judgement="ERROR", part_number=part_number, error="Camera not available")
            
        model = self._models[part_number]
        
        # We test against the first reference descriptor for fast matching
        ref_desc = model.descriptors_list[0] if model.descriptors_list else None
        
        mask = None
        if model.roi:
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            x, y = model.roi.get("x", 0), model.roi.get("y", 0)
            w, h = model.roi.get("width", frame.shape[1]), model.roi.get("height", frame.shape[0])
            mask[y:y+h, x:x+w] = 255
            
        preprocessed = self._preprocess(frame)
        kp, desc = self.sift.detectAndCompute(preprocessed, mask)
        
        elapsed = int((time.time() - start) * 1000)
        good_matches = 0
        
        if desc is not None and ref_desc is not None and len(desc) > 1 and len(ref_desc) > 1:
            try:
                matches = self.flann.knnMatch(ref_desc, desc, k=2)
                for m_n in matches:
                    if len(m_n) == 2:
                        m, n = m_n
                        if m.distance < 0.7 * n.distance:
                            good_matches += 1
            except Exception as e:
                return VisionResult(ok=False, judgement="ERROR", part_number=part_number, error=str(e))
        
        # Simple threshold logic: > 15 features matched is considered OK
        if good_matches > 15:
            return VisionResult(ok=True, judgement="OK", part_number=part_number, 
                                match_score=good_matches, threshold=15, processing_time_ms=elapsed)
        else:
            return VisionResult(ok=False, judgement="NG", part_number=part_number, 
                                match_score=good_matches, threshold=15, processing_time_ms=elapsed, 
                                error=f"Insufficient matching features ({good_matches} < 15)")
