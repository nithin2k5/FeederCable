"""
vision/model.py
===============
Part model: what a taught part looks like, and how a frame is scored against it.

Scoring aggregates across reference templates with a MEDIAN, not a max. With a
max, every reference image you add can only raise the score, so a larger teach
set makes the model more permissive — a wrong part scored 0.815 against a
39-template model built that way. The median requires most references to agree.
"""
import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional

import cv2
import numpy as np

MODEL_VERSION = 2
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vision_models")


@dataclass
class ROISpec:
    """Where on the frame to look. Fixed jig, so position is part of the check."""
    name: str
    x: int
    y: int
    w: int
    h: int
    search_margin: int = 12   # px of jig play tolerated around the taught box


@dataclass
class ROIModel:
    spec: ROISpec
    templates: List[np.ndarray] = field(default_factory=list)
    threshold: float = 0.0
    ok_scores: List[float] = field(default_factory=list)
    ng_scores: List[float] = field(default_factory=list)

    @property
    def margin(self) -> float:
        """Separation between the worst OK sample and the best NG sample."""
        if not self.ok_scores or not self.ng_scores:
            return 0.0
        return min(self.ok_scores) - max(self.ng_scores)


@dataclass
class PartModel:
    part_number: str
    frame_w: int
    frame_h: int
    rois: List[ROIModel] = field(default_factory=list)
    created: str = ""
    camera_settings: dict = field(default_factory=dict)
    version: int = MODEL_VERSION

    @property
    def margin(self) -> float:
        return min((r.margin for r in self.rois), default=0.0)

    # ── persistence ─────────────────────────────────────────────────────────

    def save(self, path: Optional[str] = None) -> str:
        if path is None:
            os.makedirs(MODELS_DIR, exist_ok=True)
            path = os.path.join(MODELS_DIR, f"{self.part_number}.vmodel.npz")

        cfg = {
            "part_number": self.part_number,
            "frame_w": self.frame_w,
            "frame_h": self.frame_h,
            "created": self.created or time.strftime("%Y-%m-%dT%H:%M:%S"),
            "camera_settings": self.camera_settings,
            "version": self.version,
            "rois": [
                {
                    "spec": asdict(r.spec),
                    "threshold": r.threshold,
                    "ok_scores": r.ok_scores,
                    "ng_scores": r.ng_scores,
                    "num_templates": len(r.templates),
                }
                for r in self.rois
            ],
        }
        arrays = {"config": json.dumps(cfg)}
        for i, roi in enumerate(self.rois):
            for j, t in enumerate(roi.templates):
                arrays[f"roi{i}_t{j}"] = t
        np.savez_compressed(path, **arrays)
        return path

    @classmethod
    def load(cls, path: str) -> "PartModel":
        data = np.load(path, allow_pickle=True)
        cfg = json.loads(str(data["config"]))
        if cfg.get("version") != MODEL_VERSION:
            raise ValueError(
                f"Model '{os.path.basename(path)}' is version {cfg.get('version')}, "
                f"this build reads version {MODEL_VERSION}. Re-teach the part."
            )
        rois = []
        for i, rc in enumerate(cfg["rois"]):
            templates = [data[f"roi{i}_t{j}"] for j in range(rc["num_templates"])]
            rois.append(ROIModel(
                spec=ROISpec(**rc["spec"]),
                templates=templates,
                threshold=rc["threshold"],
                ok_scores=rc["ok_scores"],
                ng_scores=rc["ng_scores"],
            ))
        return cls(
            part_number=cfg["part_number"],
            frame_w=cfg["frame_w"], frame_h=cfg["frame_h"],
            rois=rois, created=cfg["created"],
            camera_settings=cfg.get("camera_settings", {}),
            version=cfg["version"],
        )


# ── scoring ─────────────────────────────────────────────────────────────────

def to_gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def search_window(gray: np.ndarray, spec: ROISpec) -> tuple:
    """Sub-image to search: the taught box grown by search_margin. Returns (win, x0, y0)."""
    m = spec.search_margin
    x0, y0 = max(0, spec.x - m), max(0, spec.y - m)
    x1 = min(gray.shape[1], spec.x + spec.w + m)
    y1 = min(gray.shape[0], spec.y + spec.h + m)
    return gray[y0:y1, x0:x1], x0, y0


def locate(gray: np.ndarray, spec: ROISpec, template: np.ndarray) -> tuple:
    """Best (x, y, score) for `template` within the ROI's search window."""
    win, x0, y0 = search_window(gray, spec)
    if template.shape[0] > win.shape[0] or template.shape[1] > win.shape[1]:
        return spec.x, spec.y, float("-inf")
    res = cv2.matchTemplate(win, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    return x0 + max_loc[0], y0 + max_loc[1], float(max_val)


def score_roi(gray: np.ndarray, roi: ROIModel,
              templates: Optional[List[np.ndarray]] = None) -> float:
    """Median match score across reference templates. NaN if none are usable."""
    win, _, _ = search_window(gray, roi.spec)
    pool = roi.templates if templates is None else templates
    scores = []
    for t in pool:
        if t.shape[0] > win.shape[0] or t.shape[1] > win.shape[1]:
            continue
        res = cv2.matchTemplate(win, t, cv2.TM_CCOEFF_NORMED)
        scores.append(float(cv2.minMaxLoc(res)[1]))
    if not scores:
        return float("nan")
    return float(np.median(scores))
