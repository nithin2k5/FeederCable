"""
vision_engine/vision_controller.py
==================================
Local webcam-based vision controller using contour matching.
Follows KEYENCE-style golden-sample methodology:
  - Teach: capture reference images of a good part, extract contour shape
  - Inspect: capture live frame, extract contour, compare via Hu Moments
  - Result: OK / NG / ERROR

No external KEYENCE hardware required. Uses OpenCV contour matching
with the webcam configured in camera_cfg.ini.
"""
import cv2
import numpy as np
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple


@dataclass
class VisionResult:
    """Structured result from a vision inspection."""
    ok: bool
    judgement: str              # "OK", "NG", "ERROR"
    part_number: str = ""
    match_score: float = 0.0    # 0.0 = perfect match, higher = worse
    threshold: float = 0.0
    processing_time_ms: int = 0
    contour_found: bool = False
    error: Optional[str] = None


_VISION_CFG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vision_config.json")
_MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vision_models")


def _default_config() -> dict:
    return {
        "vision_enabled": True,
        "camera_source": "cam1",
        "match_threshold": 0.15,
        "min_contour_area": 500,
        "preprocessing": {
            "blur_kernel": 5,
            "canny_low": 50,
            "canny_high": 150
        },
        "part_mapping": {}
    }


def load_vision_config() -> dict:
    if os.path.exists(_VISION_CFG_PATH):
        try:
            with open(_VISION_CFG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return _default_config()


def save_vision_config(cfg: dict):
    with open(_VISION_CFG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)


class VisionController:
    """
    Headless, production-grade vision controller.
    Uses webcam + OpenCV contour matching to verify part presence.
    """

    def __init__(self):
        self.config = load_vision_config()
        self._model_cache: Dict[str, dict] = {}

    def reload_config(self):
        self.config = load_vision_config()
        self._model_cache.clear()

    # ── Camera ──────────────────────────────────────────────────────────────

    def _get_cam_index(self) -> int:
        """Resolve the camera index from camera_cfg.ini based on vision_config source."""
        import configparser
        cam_cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "camera_cfg.ini")
        cfg = configparser.ConfigParser()
        cfg.read(cam_cfg_path)
        source = self.config.get("camera_source", "cam1")
        key = f"{source}_index"
        return cfg.getint("CAMERA", key, fallback=-1)

    def _capture_frame(self) -> Optional[np.ndarray]:
        """Capture a single frame from the configured webcam."""
        cam_index = self._get_cam_index()
        if cam_index < 0:
            return None
        cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            return None
        # Allow camera to auto-expose
        for _ in range(5):
            cap.read()
        ret, frame = cap.read()
        cap.release()
        return frame if ret else None

    # ── Contour Extraction ──────────────────────────────────────────────────

    def _extract_main_contour(
        self, image: np.ndarray, preprocessing: dict, min_area: int = 500
    ) -> Optional[np.ndarray]:
        """Extract the largest valid contour from an image region."""
        if image is None or image.size == 0:
            return None

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()

        blur_k = preprocessing.get("blur_kernel", 5)
        if blur_k % 2 == 0:
            blur_k += 1
        blurred = cv2.GaussianBlur(gray, (blur_k, blur_k), 0)

        canny_low = preprocessing.get("canny_low", 50)
        canny_high = preprocessing.get("canny_high", 150)
        edges = cv2.Canny(blurred, canny_low, canny_high)

        # Dilate to close small gaps in contour
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=1)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        valid = [c for c in contours if cv2.contourArea(c) >= min_area]
        if not valid:
            return None

        return max(valid, key=cv2.contourArea)

    @staticmethod
    def _crop_roi(frame: np.ndarray, roi: dict) -> np.ndarray:
        """Crop frame to the ROI rectangle."""
        x = max(0, roi.get("x", 0))
        y = max(0, roi.get("y", 0))
        w = roi.get("width", frame.shape[1])
        h = roi.get("height", frame.shape[0])
        return frame[y:y+h, x:x+w].copy()

    # ── Model I/O ───────────────────────────────────────────────────────────

    def _model_path(self, part_number: str) -> Optional[str]:
        filename = self.config.get("part_mapping", {}).get(part_number)
        if not filename:
            return None
        path = os.path.join(_MODELS_DIR, filename)
        return path if os.path.exists(path) else None

    def _load_model(self, part_number: str) -> Optional[dict]:
        """Load a contour reference model for a given part number."""
        if part_number in self._model_cache:
            return self._model_cache[part_number]

        path = self._model_path(part_number)
        if path is None:
            return None

        try:
            data = np.load(path, allow_pickle=True)
            model_cfg = json.loads(str(data["config"]))

            contours = []
            i = 0
            while f"contour_{i}" in data:
                contours.append(data[f"contour_{i}"])
                i += 1

            model_cfg["reference_contours"] = contours
            self._model_cache[part_number] = model_cfg
            return model_cfg
        except Exception:
            return None

    def has_model(self, part_number: str) -> bool:
        """Check whether a vision model exists for the given part number."""
        return self._model_path(part_number) is not None

    def get_mapped_parts(self) -> dict:
        """Return the part_mapping dict from config."""
        return dict(self.config.get("part_mapping", {}))

    # ── Production Inspection ───────────────────────────────────────────────

    def inspect(self, part_number: str) -> VisionResult:
        """
        Perform a single-shot vision inspection.
        Captures one frame, matches contour against reference.
        """
        start = time.time()

        # 1) Config check
        if not self.config.get("vision_enabled", True):
            return VisionResult(
                ok=False, judgement="ERROR", part_number=part_number,
                error="Vision inspection is disabled in configuration"
            )

        # 2) Load reference model
        model = self._load_model(part_number)
        if model is None:
            return VisionResult(
                ok=False, judgement="ERROR", part_number=part_number,
                error=f"No vision model found for part '{part_number}'"
            )

        ref_contours = model.get("reference_contours", [])
        if not ref_contours:
            return VisionResult(
                ok=False, judgement="ERROR", part_number=part_number,
                error="Reference model contains no contours"
            )

        # 3) Capture frame
        frame = self._capture_frame()
        if frame is None:
            return VisionResult(
                ok=False, judgement="ERROR", part_number=part_number,
                error="Camera not available or failed to capture frame"
            )

        # 4) Crop ROI
        roi = model.get("roi")
        if roi:
            region = self._crop_roi(frame, roi)
        else:
            region = frame

        # 5) Extract contour from live image
        preproc = model.get("preprocessing", self.config.get("preprocessing", {}))
        min_area = model.get("min_contour_area", self.config.get("min_contour_area", 500))
        live_contour = self._extract_main_contour(region, preproc, min_area)

        if live_contour is None:
            elapsed = int((time.time() - start) * 1000)
            return VisionResult(
                ok=False, judgement="NG", part_number=part_number,
                processing_time_ms=elapsed, contour_found=False,
                error="No contour detected in live image — part may be missing"
            )

        # 6) Compare against each reference contour, take best (lowest) score
        best_score = float("inf")
        for ref_c in ref_contours:
            score = cv2.matchShapes(ref_c, live_contour, cv2.CONTOURS_MATCH_I1, 0)
            best_score = min(best_score, score)

        # 7) Area ratio check (live area vs reference average area)
        ref_area = model.get("reference_area", 1.0)
        live_area = float(cv2.contourArea(live_contour))
        area_ratio = live_area / ref_area if ref_area > 0 else 0.0
        area_ok = 0.5 <= area_ratio <= 2.0  # within 50-200% of reference

        threshold = model.get("match_threshold", self.config.get("match_threshold", 0.15))
        shape_ok = best_score < threshold
        ok = shape_ok and area_ok

        elapsed = int((time.time() - start) * 1000)

        if ok:
            return VisionResult(
                ok=True, judgement="OK", part_number=part_number,
                match_score=best_score, threshold=threshold,
                processing_time_ms=elapsed, contour_found=True
            )
        else:
            reasons = []
            if not shape_ok:
                reasons.append(f"shape mismatch (score={best_score:.4f}, threshold={threshold})")
            if not area_ok:
                reasons.append(f"size mismatch (area ratio={area_ratio:.2f})")
            return VisionResult(
                ok=False, judgement="NG", part_number=part_number,
                match_score=best_score, threshold=threshold,
                processing_time_ms=elapsed, contour_found=True,
                error="; ".join(reasons)
            )

    # ── Model Building ──────────────────────────────────────────────────────

    def build_and_save_model(
        self,
        part_number: str,
        images: List[np.ndarray],
        roi: dict,
        preprocessing: Optional[dict] = None,
        match_threshold: float = 0.15,
        min_contour_area: int = 500,
    ) -> str:
        """
        Build a contour reference model from captured images and save it.
        Returns the path to the saved model file.
        Raises ValueError if no valid contours could be extracted.
        """
        if preprocessing is None:
            preprocessing = self.config.get("preprocessing", {
                "blur_kernel": 5, "canny_low": 50, "canny_high": 150
            })

        ref_contours: List[np.ndarray] = []
        ref_areas: List[float] = []

        for img in images:
            cropped = self._crop_roi(img, roi)
            contour = self._extract_main_contour(cropped, preprocessing, min_contour_area)
            if contour is not None:
                ref_contours.append(contour)
                ref_areas.append(float(cv2.contourArea(contour)))

        if not ref_contours:
            raise ValueError(
                "No valid contours extracted from reference images. "
                "Ensure the part is visible and adjust preprocessing if needed."
            )

        model_cfg = {
            "part_number": part_number,
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "roi": roi,
            "match_threshold": match_threshold,
            "min_contour_area": min_contour_area,
            "preprocessing": preprocessing,
            "reference_area": float(np.mean(ref_areas)),
            "num_references": len(ref_contours),
        }

        os.makedirs(_MODELS_DIR, exist_ok=True)
        filename = f"{part_number}.npz"
        model_path = os.path.join(_MODELS_DIR, filename)

        save_dict = {"config": json.dumps(model_cfg)}
        for i, c in enumerate(ref_contours):
            save_dict[f"contour_{i}"] = c
        np.savez_compressed(model_path, **save_dict)

        # Update vision config mapping
        self.config["part_mapping"][part_number] = filename
        save_vision_config(self.config)

        # Invalidate cache
        self._model_cache.pop(part_number, None)

        return model_path

    def delete_model(self, part_number: str):
        """Delete a vision model for the given part number."""
        path = self._model_path(part_number)
        if path and os.path.exists(path):
            os.remove(path)
        self.config.get("part_mapping", {}).pop(part_number, None)
        save_vision_config(self.config)
        self._model_cache.pop(part_number, None)

    # ── Status / Diagnostics ────────────────────────────────────────────────

    def get_status(self) -> str:
        """Quick check: is the configured camera available?"""
        cam_index = self._get_cam_index()
        if cam_index < 0:
            return "NO_CAMERA"
        cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            return "CAMERA_ERROR"
        ret, _ = cap.read()
        cap.release()
        return "READY" if ret else "CAMERA_ERROR"
