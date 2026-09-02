"""
vision/inspect.py
=================
Runtime part-presence check.

Every ROI must pass. The result carries per-ROI scores and each one's distance
from its threshold, so a log line says which check failed and by how much, and
so near-misses are visible before they turn into rejects.
"""
import glob
import os
import time
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from . import capture, config
from .model import MODELS_DIR, PartModel, score_roi, to_gray


@dataclass
class ROIResult:
    name: str
    score: float
    threshold: float

    @property
    def ok(self) -> bool:
        return self.score >= self.threshold

    @property
    def margin(self) -> float:
        return self.score - self.threshold


@dataclass
class InspectResult:
    ok: bool
    judgement: str                     # "OK" | "NG" | "ERROR"
    part_number: str = ""
    rois: List[ROIResult] = field(default_factory=list)
    elapsed_ms: int = 0
    error: Optional[str] = None

    @property
    def worst(self) -> Optional[ROIResult]:
        return min(self.rois, key=lambda r: r.margin) if self.rois else None

    def reason(self) -> str:
        if self.error:
            return self.error
        w = self.worst
        if w is None:
            return self.judgement
        verb = "passed" if self.ok else "failed"
        return (f"{w.name} {verb} at {w.score:.3f} "
                f"(threshold {w.threshold:.3f}, margin {w.margin:+.3f})")


def model_path(part_number: str) -> Optional[str]:
    path = os.path.join(MODELS_DIR, f"{part_number}.vmodel.npz")
    return path if os.path.exists(path) else None


def list_parts() -> List[str]:
    return sorted(
        os.path.basename(p)[: -len(".vmodel.npz")]
        for p in glob.glob(os.path.join(MODELS_DIR, "*.vmodel.npz"))
    )


class Inspector:
    def __init__(self):
        self.config = config.load()
        self._cache: dict = {}

    def reload(self):
        self.config = config.load()
        self._cache.clear()

    def has_model(self, part_number: str) -> bool:
        return model_path(part_number) is not None

    def get_model(self, part_number: str) -> Optional[PartModel]:
        if part_number not in self._cache:
            path = model_path(part_number)
            if path is None:
                return None
            self._cache[part_number] = PartModel.load(path)
        return self._cache[part_number]

    def capture_frame(self) -> Optional[np.ndarray]:
        idx = self.config.get("camera_index", -1)
        if idx < 0:
            return None
        return capture.grab(idx, self.config.get("frame_w", 640),
                            self.config.get("frame_h", 480),
                            self.config.get("camera_settings") or None)

    def inspect(self, part_number: str) -> InspectResult:
        start = time.time()

        def fail(msg):
            return InspectResult(ok=False, judgement="ERROR", part_number=part_number,
                                 error=msg, elapsed_ms=int((time.time() - start) * 1000))

        if not self.config.get("enabled", True):
            return fail("Vision disabled")

        try:
            model = self.get_model(part_number)
        except ValueError as e:
            return fail(str(e))
        if model is None:
            return fail(f"No model taught for '{part_number}'")

        frame = self.capture_frame()
        if frame is None:
            return fail("Camera not available")

        return self.inspect_frame(frame, model, start=start)

    def inspect_frame(self, frame: np.ndarray, model: PartModel,
                      start: Optional[float] = None) -> InspectResult:
        """Score an already-captured frame. Used by the teach UI and by tests."""
        start = start or time.time()
        gray = to_gray(frame)

        if gray.shape[:2] != (model.frame_h, model.frame_w):
            return InspectResult(
                ok=False, judgement="ERROR", part_number=model.part_number,
                elapsed_ms=int((time.time() - start) * 1000),
                error=(f"Frame is {gray.shape[1]}x{gray.shape[0]} but the model was "
                       f"taught at {model.frame_w}x{model.frame_h} — "
                       f"fix the camera resolution or re-teach"))

        results = []
        for roi in model.rois:
            score = score_roi(gray, roi)
            if np.isnan(score):
                return InspectResult(
                    ok=False, judgement="ERROR", part_number=model.part_number,
                    elapsed_ms=int((time.time() - start) * 1000),
                    error=f"ROI '{roi.spec.name}' does not fit the frame")
            results.append(ROIResult(roi.spec.name, score, roi.threshold))

        all_ok = all(r.ok for r in results)
        return InspectResult(
            ok=all_ok, judgement="OK" if all_ok else "NG",
            part_number=model.part_number, rois=results,
            elapsed_ms=int((time.time() - start) * 1000))
