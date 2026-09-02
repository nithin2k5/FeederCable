"""
vision/teach.py
===============
Builds a part model from an OK set and an NG set.

Two rules make this different from typing a threshold into a box:

  - The threshold is derived from measured separation between the two sets.
  - If the sets overlap, the ROI cannot discriminate and the build is REFUSED.
    Failing at teach time is the whole point; a model that silently passes
    everything is worse than no model.
"""
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from .model import PartModel, ROIModel, ROISpec, locate, score_roi, to_gray

MIN_OK_IMAGES = 8
MIN_NG_IMAGES = 3

# An OK image aligning below this against the anchor almost certainly does not
# contain the part — usually an empty-jig shot filed into the OK set by mistake.
MIN_ALIGNMENT_SCORE = 0.30


class TeachError(Exception):
    """Raised when a usable model cannot be built. Carries the report."""
    def __init__(self, message: str, report: Optional["TeachReport"] = None):
        super().__init__(message)
        self.report = report


@dataclass
class ROIReport:
    name: str
    threshold: float = 0.0
    ok_min: float = 0.0
    ok_median: float = 0.0
    ng_max: float = 0.0
    margin: float = 0.0
    dropped: List[int] = field(default_factory=list)
    verdict: str = ""

    @property
    def usable(self) -> bool:
        return self.verdict == "OK"


@dataclass
class TeachReport:
    part_number: str
    rois: List[ROIReport] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.rois) and all(r.usable for r in self.rois) and not self.problems

    def summary(self) -> str:
        lines = [f"Part {self.part_number}: {'READY' if self.ok else 'NOT USABLE'}"]
        for r in self.rois:
            lines.append(
                f"  {r.name:<12} threshold {r.threshold:.3f}  "
                f"OK>={r.ok_min:.3f}  NG<={r.ng_max:.3f}  margin {r.margin:+.3f}  {r.verdict}"
            )
        lines.extend(f"  ! {p}" for p in self.problems)
        return "\n".join(lines)


def align_templates(images: List[np.ndarray], spec: ROISpec) -> tuple:
    """Crop each image at the ROI, correcting for small shifts between shots.

    Returns (templates, offsets, scores). The first image is the anchor.
    """
    anchor = to_gray(images[0])
    anchor_crop = anchor[spec.y:spec.y + spec.h, spec.x:spec.x + spec.w]

    templates = [anchor_crop]
    offsets = [(spec.x, spec.y)]
    scores = [1.0]

    for img in images[1:]:
        gray = to_gray(img)
        x, y, score = locate(gray, spec, anchor_crop)
        templates.append(gray[y:y + spec.h, x:x + spec.w])
        offsets.append((x, y))
        scores.append(score)

    return templates, offsets, scores


def _leave_one_out_scores(ok_grays: List[np.ndarray], roi: ROIModel) -> List[float]:
    """Score each OK image against a model built from the *other* references."""
    scores = []
    for i, gray in enumerate(ok_grays):
        others = [t for j, t in enumerate(roi.templates) if j != i]
        if not others:
            continue
        scores.append(score_roi(gray, roi, templates=others))
    return [s for s in scores if not np.isnan(s)]


def _derive_threshold(ok_scores: List[float], ng_scores: List[float]) -> tuple:
    """Return (threshold, verdict). Threshold sits midway between the sets."""
    if not ok_scores:
        return 0.0, "no usable OK samples"
    ok_min = min(ok_scores)

    if not ng_scores:
        # Weaker fallback: no measured NG floor, so back off from the OK spread.
        spread = float(np.std(ok_scores))
        return max(0.0, ok_min - 3 * spread), "OK-only (no NG samples — weak)"

    ng_max = max(ng_scores)
    if ok_min <= ng_max:
        return 0.0, (
            f"CANNOT DISCRIMINATE: worst OK ({ok_min:.3f}) is not above "
            f"best NG ({ng_max:.3f})"
        )
    return (ok_min + ng_max) / 2.0, "OK"


def build_part_model(
    part_number: str,
    ok_images: List[np.ndarray],
    ng_images: List[np.ndarray],
    specs: List[ROISpec],
    camera_settings: Optional[dict] = None,
) -> tuple:
    """Build and validate a model. Returns (PartModel, TeachReport).

    Raises TeachError if the model would not discriminate.
    """
    report = TeachReport(part_number=part_number)

    if len(ok_images) < MIN_OK_IMAGES:
        report.problems.append(
            f"Need at least {MIN_OK_IMAGES} OK images, got {len(ok_images)}.")
    if ng_images and len(ng_images) < MIN_NG_IMAGES:
        report.problems.append(
            f"Need at least {MIN_NG_IMAGES} NG images, got {len(ng_images)}.")
    if not specs:
        report.problems.append("No ROI defined.")
    if report.problems:
        raise TeachError("; ".join(report.problems), report)

    h, w = ok_images[0].shape[:2]
    for img in ok_images + ng_images:
        if img.shape[:2] != (h, w):
            report.problems.append(
                "All teach images must share one resolution — re-capture the set.")
            raise TeachError(report.problems[-1], report)

    ng_grays = [to_gray(i) for i in ng_images]
    rois: List[ROIModel] = []

    for spec in specs:
        r = ROIReport(name=spec.name)

        templates, _, align_scores = align_templates(ok_images, spec)

        keep = [i for i, s in enumerate(align_scores) if s >= MIN_ALIGNMENT_SCORE]
        r.dropped = [i for i in range(len(templates)) if i not in keep]
        if len(keep) < MIN_OK_IMAGES:
            r.verdict = (f"only {len(keep)} of {len(templates)} OK images contain "
                         f"the part at this ROI")
            report.rois.append(r)
            continue

        kept_templates = [templates[i] for i in keep]
        kept_grays = [to_gray(ok_images[i]) for i in keep]

        roi = ROIModel(spec=spec, templates=kept_templates)
        roi.ok_scores = _leave_one_out_scores(kept_grays, roi)
        roi.ng_scores = [s for s in (score_roi(g, roi) for g in ng_grays)
                         if not np.isnan(s)]

        roi.threshold, r.verdict = _derive_threshold(roi.ok_scores, roi.ng_scores)
        r.threshold = roi.threshold
        r.ok_min = min(roi.ok_scores) if roi.ok_scores else 0.0
        r.ok_median = float(np.median(roi.ok_scores)) if roi.ok_scores else 0.0
        r.ng_max = max(roi.ng_scores) if roi.ng_scores else 0.0
        r.margin = roi.margin

        report.rois.append(r)
        if r.usable or r.verdict.startswith("OK-only"):
            rois.append(roi)

    if not rois or any(not r.usable and not r.verdict.startswith("OK-only")
                       for r in report.rois):
        raise TeachError(
            "Model would not discriminate between OK and NG samples.", report)

    model = PartModel(
        part_number=part_number,
        frame_w=w, frame_h=h,
        rois=rois,
        camera_settings=camera_settings or {},
    )
    return model, report
