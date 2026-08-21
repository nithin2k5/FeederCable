"""
vision_engine/vision_controller.py
==================================
Local webcam-based vision controller using Template Matching (Normalized Cross-Correlation).
Replaces the fragile Contour/Canny approach with robust industrial template matching.

Methodology:
  - Teach: User draws ROI around the part. The image patch inside the ROI becomes the 'Template'.
  - Inspect: Capture live frame. Search for the Template across the frame using cv2.matchTemplate.
  - Result: If the highest match score > threshold, it's OK (Part is present and correct).
"""
import cv2
import numpy as np
import json
import os
import time
from dataclasses import dataclass
from typing import Optional, Dict, List


@dataclass
class VisionResult:
    """Structured result from a vision inspection."""
    ok: bool
    judgement: str              # "OK", "NG", "ERROR"
    part_number: str = ""
    match_score: float = 0.0    # 1.0 = perfect match, lower = worse
    threshold: float = 0.0
    processing_time_ms: int = 0
    error: Optional[str] = None


_VISION_CFG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vision_config.json")
_MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vision_models")


def _default_config() -> dict:
    return {
        "vision_enabled": True,
        "camera_source": "cam1",
        "match_threshold": 0.75,
        "part_mapping": {}
    }


def load_vision_config() -> dict:
    if os.path.exists(_VISION_CFG_PATH):
        try:
            with open(_VISION_CFG_PATH, "r") as f:
                cfg = json.load(f)
                if "match_threshold" not in cfg:
                    cfg["match_threshold"] = 0.75
                return cfg
        except Exception:
            pass
    return _default_config()


def save_vision_config(cfg: dict):
    with open(_VISION_CFG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)

def get_vision_controller():
    cfg = load_vision_config()
    engine = cfg.get("engine", "template")
    if engine == "yolo":
        try:
            from .yolo_controller import YoloVisionController
            return YoloVisionController()
        except ImportError:
            pass
    elif engine == "sift":
        from .sift_controller import SiftVisionController
        return SiftVisionController()
    return VisionController()

class VisionController:
    """
    Headless, production-grade vision controller.
    Uses webcam + OpenCV Template Matching to verify part presence.
    """

    def __init__(self):
        self.config = load_vision_config()
        self._model_cache: Dict[str, dict] = {}

    def reload_config(self):
        self.config = load_vision_config()
        self._model_cache.clear()

    # ── Camera ──────────────────────────────────────────────────────────────

    def _get_cam_index(self) -> int:
        import configparser
        cam_cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "camera_cfg.ini")
        if not os.path.exists(cam_cfg_path):
            return -1
        cfg = configparser.ConfigParser()
        cfg.read(cam_cfg_path)
        source = self.config.get("camera_source", "cam1")
        key = f"{source}_index"
        return cfg.getint("CAMERA", key, fallback=-1)

    def _capture_frame(self) -> Optional[np.ndarray]:
        cam_index = self._get_cam_index()
        if cam_index < 0:
            return None
        cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            return None
        # Allow auto-exposure to settle
        for _ in range(5):
            cap.read()
        ret, frame = cap.read()
        cap.release()
        return frame if ret else None

    # ── Model I/O ───────────────────────────────────────────────────────────

    def _model_path(self, part_number: str) -> Optional[str]:
        filename = self.config.get("part_mapping", {}).get(part_number)
        if not filename:
            return None
        path = os.path.join(_MODELS_DIR, filename)
        return path if os.path.exists(path) else None

    def _load_model(self, part_number: str) -> Optional[dict]:
        if part_number in self._model_cache:
            return self._model_cache[part_number]

        path = self._model_path(part_number)
        if path is None:
            return None

        try:
            data = np.load(path, allow_pickle=True)
            model_cfg = json.loads(str(data["config"]))

            templates = []
            i = 0
            while f"template_{i}" in data:
                templates.append(data[f"template_{i}"])
                i += 1

            model_cfg["templates"] = templates
            self._model_cache[part_number] = model_cfg
            return model_cfg
        except Exception:
            return None

    def has_model(self, part_number: str) -> bool:
        return self._model_path(part_number) is not None

    def get_mapped_parts(self) -> dict:
        return dict(self.config.get("part_mapping", {}))

    # ── Production Inspection ───────────────────────────────────────────────

    def inspect(self, part_number: str) -> VisionResult:
        start = time.time()

        if not self.config.get("vision_enabled", True):
            return VisionResult(
                ok=False, judgement="ERROR", part_number=part_number,
                error="Vision inspection disabled"
            )

        model = self._load_model(part_number)
        if model is None:
            return VisionResult(
                ok=False, judgement="ERROR", part_number=part_number,
                error=f"No vision model found for '{part_number}'"
            )

        templates = model.get("templates", [])
        if not templates:
            return VisionResult(
                ok=False, judgement="ERROR", part_number=part_number,
                error="Model contains no templates"
            )

        frame = self._capture_frame()
        if frame is None:
            return VisionResult(
                ok=False, judgement="ERROR", part_number=part_number,
                error="Camera not available"
            )

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Test against all saved templates, take the best match
        best_score = -1.0
        for template in templates:
            # Make sure template is not larger than frame
            if template.shape[0] > gray_frame.shape[0] or template.shape[1] > gray_frame.shape[1]:
                continue
            
            res = cv2.matchTemplate(gray_frame, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            best_score = max(best_score, max_val)

        threshold = model.get("match_threshold", self.config.get("match_threshold", 0.75))
        ok = best_score >= threshold
        elapsed = int((time.time() - start) * 1000)

        if ok:
            return VisionResult(
                ok=True, judgement="OK", part_number=part_number,
                match_score=best_score, threshold=threshold,
                processing_time_ms=elapsed
            )
        else:
            return VisionResult(
                ok=False, judgement="NG", part_number=part_number,
                match_score=best_score, threshold=threshold,
                processing_time_ms=elapsed,
                error=f"No match found (score {best_score:.2f} < {threshold})"
            )

    # ── Model Building ──────────────────────────────────────────────────────

    def build_and_save_model(
        self, part_number: str, images: List[np.ndarray], roi: dict, match_threshold: float = 0.75
    ) -> str:
        
        x, y, w, h = roi["x"], roi["y"], roi["width"], roi["height"]
        if w < 10 or h < 10:
            raise ValueError("ROI is too small for template matching.")

        templates = []
        for img in images:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            # Crop the template patch from the full image
            patch = gray[y:y+h, x:x+w]
            templates.append(patch)

        model_cfg = {
            "part_number": part_number,
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "roi": roi,
            "match_threshold": match_threshold,
            "num_references": len(templates),
        }

        os.makedirs(_MODELS_DIR, exist_ok=True)
        filename = f"{part_number}.npz"
        model_path = os.path.join(_MODELS_DIR, filename)

        save_dict = {"config": json.dumps(model_cfg)}
        for i, t in enumerate(templates):
            save_dict[f"template_{i}"] = t
        np.savez_compressed(model_path, **save_dict)

        self.config["part_mapping"][part_number] = filename
        save_vision_config(self.config)
        self._model_cache.pop(part_number, None)

        return model_path

    def delete_model(self, part_number: str):
        path = self._model_path(part_number)
        if path and os.path.exists(path):
            os.remove(path)
        self.config.get("part_mapping", {}).pop(part_number, None)
        save_vision_config(self.config)
        self._model_cache.pop(part_number, None)

    def get_status(self) -> str:
        cam_index = self._get_cam_index()
        if cam_index < 0:
            return "NO_CAMERA"
        cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            return "CAMERA_ERROR"
        ret, _ = cap.read()
        cap.release()
        return "READY" if ret else "CAMERA_ERROR"
