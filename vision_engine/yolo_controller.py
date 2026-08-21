import os
import time
import cv2

# Ultralytics is required for YOLO
try:
    from ultralytics import YOLO
    _YOLO_AVAILABLE = True
except ImportError:
    _YOLO_AVAILABLE = False

from .vision_controller import VisionResult

_YOLO_MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "yolo_models")

class YoloVisionController:
    """
    Deep Learning Vision Controller using YOLOv8.
    This provides robust object detection and classification for industrial inspection.
    """
    def __init__(self):
        self._models = {}
        os.makedirs(_YOLO_MODELS_DIR, exist_ok=True)
        self.config = {"vision_enabled": True}

    def reload_config(self):
        self._models.clear()

    def has_model(self, part_number: str) -> bool:
        return os.path.exists(os.path.join(_YOLO_MODELS_DIR, f"{part_number}.pt"))

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
        # Let exposure settle
        for _ in range(5): cap.read()
        ret, frame = cap.read()
        cap.release()
        return frame if ret else None

    def inspect(self, part_number: str) -> VisionResult:
        start = time.time()
        
        if not _YOLO_AVAILABLE:
            return VisionResult(ok=False, judgement="ERROR", part_number=part_number, 
                                error="ultralytics package not installed. Run: pip install ultralytics")

        model_path = os.path.join(_YOLO_MODELS_DIR, f"{part_number}.pt")
        
        if not os.path.exists(model_path):
            return VisionResult(ok=False, judgement="ERROR", part_number=part_number, 
                                error=f"YOLO model not found: {part_number}.pt")
        
        if part_number not in self._models:
            try:
                # Load the YOLO model once and cache it
                self._models[part_number] = YOLO(model_path)
            except Exception as e:
                return VisionResult(ok=False, judgement="ERROR", part_number=part_number, error=str(e))
                
        frame = self._capture_frame()
        if frame is None:
            return VisionResult(ok=False, judgement="ERROR", part_number=part_number, error="Camera not available")
            
        model = self._models[part_number]
        # Run inference on the frame
        results = model(frame, verbose=False)
        
        elapsed = int((time.time() - start) * 1000)
        
        if len(results) > 0 and len(results[0].boxes) > 0:
            # Get the highest confidence detection
            best_box = results[0].boxes[0]
            conf = float(best_box.conf)
            class_id = int(best_box.cls)
            class_name = model.names[class_id] if hasattr(model, 'names') else str(class_id)
            
            # Typically, we train YOLO to detect 'GOOD' (class 0) or specific defect classes.
            # Here we assume confidence > 0.7 means a positive detection of the expected part.
            if conf > 0.7:
                if "fail" in class_name.lower() or "ng" in class_name.lower():
                    return VisionResult(ok=False, judgement="NG", part_number=part_number, 
                                        match_score=conf, threshold=0.7, processing_time_ms=elapsed, 
                                        error=f"Defect detected: {class_name}")
                return VisionResult(ok=True, judgement="OK", part_number=part_number, 
                                    match_score=conf, threshold=0.7, processing_time_ms=elapsed)
            else:
                return VisionResult(ok=False, judgement="NG", part_number=part_number, 
                                    match_score=conf, threshold=0.7, processing_time_ms=elapsed, 
                                    error="Confidence too low")
                
        return VisionResult(ok=False, judgement="NG", part_number=part_number, match_score=0.0, 
                            threshold=0.7, processing_time_ms=elapsed, error="Part not detected in frame")
