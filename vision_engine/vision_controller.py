"""
vision_engine/vision_controller.py
==================================
Webcam-based part verification using Template Matching (Normalized Cross-Correlation).

Methodology:
  - Teach: the operator collects reference images and boxes the part in each one.
    The image patch inside each box becomes a 'Template'. Boxes are per image,
    because a single box applied to every reference crops background wherever the
    part happened to sit elsewhere — and a background template matches the live
    background, which would pass an empty fixture.
  - Inspect: capture a live frame and search for the Template across it with
    cv2.matchTemplate.
  - Result: if the best match score >= threshold the part is present and correct.

Objects:
  A part number can be checked as up to MAX_OBJECTS separate objects (say, both
  connectors and the label). Each object has its own templates and is searched
  for exactly as a single-object part is, against the same threshold; the part
  is OK only when every object is. Combining the verdicts is the only new step,
  so an object is judged no more loosely than a whole part was. A model saved
  before objects existed reads as one object.

Wire colours:
  A part can also carry wire-colour checks: a box where a connector's wires
  leave it, and the colours expected there in order (say blue then black, left
  to right). The box is stored relative to one of the part's objects, so it
  follows that connector wherever it is found in the frame -- on either camera.
  Inside the box every pixel is classed against a named colour palette, each
  expected colour takes its largest blobs, and the blobs' order along the
  wires' direction must equal the expected sequence. A swapped, missing or
  wrong-coloured wire is an NG.
"""
import configparser
import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

from . import camera

DEFAULT_MATCH_THRESHOLD = 0.75
MAX_OBJECTS = 3
MAX_WIRE_CHECKS = 4
MAX_WIRES = 6
# A colour's blob must cover at least this share of the wire box to count as a
# wire rather than a speck of glare or a stray shadow.
DEFAULT_WIRE_MIN_AREA_PCT = 2.0

# OpenCV HSV (H 0-179, S and V 0-255). Pixels are classed in this order and a
# pixel takes the first colour it fits, so the classes never overlap: black
# goes first, so the dark edge of a blue wire reads as black rather than the
# other way round, and the greys go last. Override or extend a colour with
# "wire_colors" in vision_config.json -- {"blue": [[[90,100,56],[130,255,255]]]}.
WIRE_COLORS = {
    "black":  [((0, 0, 0), (179, 255, 55))],
    "red":    [((0, 90, 56), (6, 255, 255)), ((170, 90, 56), (179, 255, 255))],
    "orange": [((7, 120, 140), (20, 255, 255))],
    "brown":  [((7, 60, 56), (20, 255, 139))],
    "yellow": [((21, 100, 100), (34, 255, 255))],
    "green":  [((35, 70, 56), (85, 255, 255))],
    "blue":   [((86, 90, 56), (130, 255, 255))],
    "violet": [((131, 50, 56), (169, 255, 255))],
    "white":  [((0, 0, 180), (179, 45, 255))],
    "grey":   [((0, 0, 56), (179, 45, 179))],
}
# How each colour is drawn on screen (BGR).
WIRE_DRAW_BGR = {
    "black": (60, 60, 60), "red": (40, 40, 230), "orange": (0, 140, 255),
    "brown": (40, 80, 140), "yellow": (0, 220, 240), "green": (60, 200, 60),
    "blue": (230, 120, 30), "violet": (200, 60, 160), "white": (245, 245, 245),
    "grey": (150, 150, 150),
}

_ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
_VISION_CFG_PATH = os.path.join(_ROOT_DIR, "vision_config.json")
_CAM_CFG_PATH = os.path.join(_ROOT_DIR, "camera_cfg.ini")
_MODELS_DIR = os.path.join(_ROOT_DIR, "vision_models")


@dataclass
class ObjectResult:
    """How one object of a part fared in an inspection."""
    name: str
    ok: bool
    score: float = 0.0
    box: Optional[Tuple[int, int, int, int]] = None         # (x, y, w, h) in frame


@dataclass
class WireResult:
    """How one wire-colour check fared in an inspection."""
    name: str
    ok: bool
    expected: List[str] = field(default_factory=list)
    found: List[str] = field(default_factory=list)          # in wire order
    # One (colour, (x, y, w, h)) per wire blob picked, in frame coordinates.
    blobs: List[Tuple[str, Tuple[int, int, int, int]]] = field(default_factory=list)
    box: Optional[Tuple[int, int, int, int]] = None         # the wire box in frame
    error: Optional[str] = None


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

    # Diagnostics for the settings-page test view. Production ignores these;
    # they exist so the UI can show *where* the match landed instead of only a
    # number, without duplicating the matching logic outside inspect().
    match_box: Optional[Tuple[int, int, int, int]] = None   # (x, y, w, h) in frame
    frame: Optional[np.ndarray] = None                      # frame that was judged
    # One entry per taught object. match_score / match_box above describe the
    # weakest object, which is the one that decides the verdict -- for a
    # single-object part that is simply the part, as before.
    objects: List[ObjectResult] = field(default_factory=list)
    wires: List[WireResult] = field(default_factory=list)


def _default_config() -> dict:
    return {
        "vision_enabled": True,
        "camera_source": "cam1",
        "match_threshold": DEFAULT_MATCH_THRESHOLD,
        "part_mapping": {},
        "wire_min_area_pct": DEFAULT_WIRE_MIN_AREA_PCT,
    }


def load_vision_config() -> dict:
    cfg = _default_config()
    if os.path.exists(_VISION_CFG_PATH):
        try:
            with open(_VISION_CFG_PATH, "r") as f:
                cfg.update(json.load(f))
        except (OSError, ValueError):
            pass
    return cfg


def save_vision_config(cfg: dict):
    with open(_VISION_CFG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)
        f.write("\n")


def get_vision_controller() -> "VisionController":
    return VisionController()


class VisionController:
    """Headless part verification against taught templates."""

    def __init__(self):
        self.config = load_vision_config()
        self._model_cache: Dict[str, dict] = {}

    def reload_config(self):
        self.config = load_vision_config()
        self._model_cache.clear()

    # ── Camera ──────────────────────────────────────────────────────────────

    def cam_settings(self) -> tuple:
        """(index, width, height) for the configured camera source."""
        source = self.config.get("camera_source", "cam1")
        if not os.path.exists(_CAM_CFG_PATH):
            return -1, 640, 480
        cfg = configparser.ConfigParser()
        cfg.read(_CAM_CFG_PATH)
        return (
            cfg.getint("CAMERA", f"{source}_index", fallback=-1),
            cfg.getint("CAMERA", f"{source}_width", fallback=640),
            cfg.getint("CAMERA", f"{source}_height", fallback=480),
        )

    def _capture_frame(self) -> Optional[np.ndarray]:
        index, width, height = self.cam_settings()
        if index < 0:
            return None
        return camera.grab(index, width, height)

    def get_status(self) -> str:
        index, width, height = self.cam_settings()
        if index < 0:
            return "NO_CAMERA"
        return "READY" if camera.grab(index, width, height) is not None else "CAMERA_ERROR"

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

            objects = []
            for k, meta in enumerate(model_cfg.get("pieces") or [{}]):
                # Object 1 keeps the pre-objects key names, so a model saved
                # before objects existed loads as a one-object model untouched.
                # The file says "pieces" / "piece{k}_" -- objects' first name --
                # and keeps saying it, so models already taught still load.
                prefix = "template_" if k == 0 else f"piece{k}_template_"
                templates = []
                i = 0
                while f"{prefix}{i}" in data:
                    templates.append(data[f"{prefix}{i}"])
                    i += 1
                name = meta.get("name") or ""
                if name == f"Piece {k + 1}":
                    name = ""           # the old default name, shown as the new one
                objects.append({"name": name or f"Object {k + 1}",
                               "templates": templates})

            model_cfg["objects"] = objects
            model_cfg["templates"] = objects[0]["templates"]
            model_cfg["wire_checks"] = [
                c for c in (model_cfg.get("wire_checks") or [])
                if 0 <= int(c.get("object", 0)) < len(objects)]
            self._model_cache[part_number] = model_cfg
            return model_cfg
        except (OSError, ValueError, KeyError):
            return None

    def has_model(self, part_number: str) -> bool:
        return self._model_path(part_number) is not None

    def get_mapped_parts(self) -> dict:
        return dict(self.config.get("part_mapping", {}))

    def _match_objects(self, model: dict, part_number: str,
                       gray_frame: np.ndarray, threshold: float):
        """Each object searched for on its own, exactly as a whole part used to
        be: the best of its templates anywhere in the frame. Returns
        (results, error) -- error is set when an object had no template that
        fits the frame."""
        objects = model.get("objects", [])
        results = []
        for obj in objects:
            templates = obj["templates"]
            best_score = -1.0
            best_box = None
            compared = 0
            for template in templates:
                if template.shape[0] > gray_frame.shape[0] or template.shape[1] > gray_frame.shape[1]:
                    continue
                res = cv2.matchTemplate(gray_frame, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val > best_score:
                    best_score = max_val
                    best_box = (max_loc[0], max_loc[1], template.shape[1], template.shape[0])
                compared += 1

            print(f"[VISION DEBUG] pno={part_number} object={obj['name']!r} "
                  f"frame={gray_frame.shape[1]}x{gray_frame.shape[0]} "
                  f"brightness={gray_frame.mean():.1f} templates={[(t.shape[1], t.shape[0]) for t in templates]} "
                  f"compared={compared} best_score={best_score:.3f}")

            if compared == 0:
                return results, (
                    f"Every template{' of ' + obj['name'] if len(objects) > 1 else ''} "
                    f"is larger than this frame "
                    f"({gray_frame.shape[1]}x{gray_frame.shape[0]}) — "
                    f"re-teach the part at this resolution, or use a larger test image"
                )
            results.append(ObjectResult(name=obj["name"], ok=best_score >= threshold,
                                       score=best_score, box=best_box))
        return results, None

    def locate_objects(self, part_number: str, frame: np.ndarray) -> List[ObjectResult]:
        """Where each object of a taught part is found in `frame` -- what a wire
        box is anchored to. Empty if the part has no usable model."""
        model = self._load_model(part_number)
        if model is None or not all(p["templates"] for p in model.get("objects", [])):
            return []
        threshold = model.get("match_threshold", self.config.get("match_threshold", DEFAULT_MATCH_THRESHOLD))
        results, _ = self._match_objects(
            model, part_number, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), threshold)
        return results

    def wire_checks(self, part_number: str) -> List[dict]:
        """A taught part's wire-colour checks (copies)."""
        model = self._load_model(part_number)
        return [dict(c) for c in (model or {}).get("wire_checks", [])]

    # ── Wire colours ────────────────────────────────────────────────────────

    def wire_palette(self) -> Dict[str, list]:
        """Colour name -> HSV ranges, the built-in palette with any overrides
        from vision_config.json laid over it."""
        palette = {k: list(v) for k, v in WIRE_COLORS.items()}
        for name, ranges in (self.config.get("wire_colors") or {}).items():
            try:
                palette[str(name).lower()] = [(tuple(lo), tuple(hi)) for lo, hi in ranges]
            except (TypeError, ValueError):
                continue
        return palette

    @staticmethod
    def wire_box(check: dict, anchor: Tuple[int, int, int, int],
                 frame_shape) -> Optional[Tuple[int, int, int, int]]:
        """A check's box in frame coordinates, placed off its anchor object's
        match and clipped to the frame. None if too little of it is in frame."""
        off = check["offset"]
        x0 = anchor[0] + int(off["dx"])
        y0 = anchor[1] + int(off["dy"])
        x1, y1 = x0 + int(off["width"]), y0 + int(off["height"])
        fh, fw = frame_shape[:2]
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, fw), min(y1, fh)
        if x1 - x0 < 4 or y1 - y0 < 4:
            return None
        return x0, y0, x1 - x0, y1 - y0

    def check_wires(self, frame: np.ndarray, box: Tuple[int, int, int, int],
                    expected: List[str], direction: str = "ltr",
                    name: str = "Wires") -> WireResult:
        """Find each expected colour inside `box` and check their order.

        Every pixel is classed against the palette (first fitting colour wins).
        Each expected colour takes as many of its largest blobs as it appears in
        the sequence; the picked blobs, ordered along the wires' direction
        ("ltr" = left to right, "ttb" = top to bottom), must spell out the
        expected sequence exactly.
        """
        expected = [c.lower() for c in expected]
        x, y, w, h = box
        roi = frame[y:y + h, x:x + w]
        result = WireResult(name=name, ok=False, expected=list(expected), box=box)
        if roi.size == 0 or not expected:
            result.error = "empty wire box" if roi.size == 0 else "no colours set"
            return result

        palette = self.wire_palette()
        unknown = [c for c in expected if c not in palette]
        if unknown:
            result.error = "unknown colour " + ", ".join(unknown)
            return result

        hsv = cv2.cvtColor(cv2.GaussianBlur(roi, (5, 5), 0), cv2.COLOR_BGR2HSV)
        taken = np.zeros(hsv.shape[:2], np.uint8)
        masks = {}
        for cname, ranges in palette.items():
            m = np.zeros(hsv.shape[:2], np.uint8)
            for lo, hi in ranges:
                m |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
            m &= cv2.bitwise_not(taken)
            taken |= m
            masks[cname] = m

        pct = float(self.config.get("wire_min_area_pct", DEFAULT_WIRE_MIN_AREA_PCT))
        min_area = max(12, int(w * h * pct / 100.0))
        kernel = np.ones((3, 3), np.uint8)
        axis = 1 if direction == "ttb" else 0
        picked = []         # (position along the wires, colour, (x, y, w, h))
        missing = []
        for cname in dict.fromkeys(expected):
            need = expected.count(cname)
            m = cv2.morphologyEx(masks[cname], cv2.MORPH_OPEN, kernel)
            n, _, stats, cents = cv2.connectedComponentsWithStats(m)
            blobs = sorted((i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= min_area),
                           key=lambda i: -stats[i, cv2.CC_STAT_AREA])[:need]
            if len(blobs) < need:
                missing.append(cname)
            for i in blobs:
                bx, by, bw, bh = (int(v) for v in stats[i, :4])
                picked.append((float(cents[i][axis]), cname, (x + bx, y + by, bw, bh)))

        picked.sort(key=lambda t: t[0])
        result.found = [c for _, c, _ in picked]
        result.blobs = [(c, b) for _, c, b in picked]
        if missing:
            result.error = "no " + ", ".join(missing) + " wire found"
        elif result.found != expected:
            result.error = "saw " + " → ".join(result.found)
        else:
            result.ok = True
        return result

    def _run_wire_checks(self, checks: List[dict], objects: List[ObjectResult],
                         frame: np.ndarray) -> List[WireResult]:
        out = []
        for c in checks:
            name = c.get("name") or "Wires"
            k = int(c.get("object", 0))
            anchor = objects[k].box if 0 <= k < len(objects) else None
            box = self.wire_box(c, anchor, frame.shape) if anchor else None
            if box is None:
                out.append(WireResult(name=name, ok=False, expected=list(c.get("colors", [])),
                                      error="wire box falls outside the frame"))
                continue
            out.append(self.check_wires(frame, box, c.get("colors", []),
                                        c.get("direction", "ltr"), name))
        return out

    # ── Production Inspection ───────────────────────────────────────────────

    def inspect(self, part_number: str, frame: Optional[np.ndarray] = None,
                wire_checks: Optional[List[dict]] = None) -> VisionResult:
        """Judge one frame against a taught part.

        By default captures a fresh frame from the configured camera — the
        same path production uses. Pass `frame` to judge a still image
        instead, without needing the part in front of a camera at all.
        `wire_checks` stands in for the model's own, so the wire-colour editor
        can try unsaved checks through exactly this path.
        """
        start = time.time()

        def _error(msg: str) -> VisionResult:
            return VisionResult(
                ok=False, judgement="ERROR", part_number=part_number, error=msg,
                processing_time_ms=int((time.time() - start) * 1000),
            )

        if not self.config.get("vision_enabled", True):
            return _error("Vision inspection disabled")

        model = self._load_model(part_number)
        if model is None:
            return _error(f"No vision model found for '{part_number}'")

        objects = model.get("objects", [])
        if not objects or not all(p["templates"] for p in objects):
            return _error("Model contains no templates")

        if frame is None:
            frame = self._capture_frame()
            if frame is None:
                return _error("Camera not available")

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        threshold = model.get("match_threshold", self.config.get("match_threshold", DEFAULT_MATCH_THRESHOLD))

        results, err = self._match_objects(model, part_number, gray_frame, threshold)
        if err:
            return _error(err)

        weakest = min(results, key=lambda r: r.score)
        objects_ok = all(r.ok for r in results)

        # Wire colours are judged only once every object is found: the boxes
        # hang off the objects' matches, and off a wrong match they would be
        # looking at the wrong place.
        checks = model.get("wire_checks", []) if wire_checks is None else wire_checks
        wires = self._run_wire_checks(checks, results, frame) if objects_ok else []
        for wr in wires:
            print(f"[VISION DEBUG] pno={part_number} wires={wr.name!r} "
                  f"expected={wr.expected} found={wr.found} ok={wr.ok}")
        elapsed = int((time.time() - start) * 1000)

        if objects_ok and all(w.ok for w in wires):
            return VisionResult(
                ok=True, judgement="OK", part_number=part_number,
                match_score=weakest.score, threshold=threshold,
                processing_time_ms=elapsed,
                match_box=weakest.box, frame=frame, objects=results, wires=wires,
            )
        if not objects_ok and len(results) == 1:
            error = f"No match found (score {weakest.score:.2f} < {threshold})"
        elif not objects_ok:
            error = "Not found: " + ", ".join(
                f"{r.name} ({r.score:.2f})" for r in results if not r.ok)
        else:
            error = "Wire colours: " + "; ".join(
                f"{w.name} expected {' → '.join(w.expected)}, {w.error}"
                for w in wires if not w.ok)
        return VisionResult(
            ok=False, judgement="NG", part_number=part_number,
            match_score=weakest.score, threshold=threshold,
            processing_time_ms=elapsed,
            error=error,
            match_box=weakest.box, frame=frame, objects=results, wires=wires,
        )

    # ── Model Building ──────────────────────────────────────────────────────

    def build_and_save_model(
        self, part_number: str, images: List[np.ndarray],
        roi: Union[dict, List[dict], List[List[dict]]],
        match_threshold: float = DEFAULT_MATCH_THRESHOLD,
        object_names: Optional[List[str]] = None,
        wire_checks: Optional[List[dict]] = None,
    ) -> str:
        """Crop the templates for every object of a part and save them as its model.

        `roi` is a single box applied to every image, one box per image, or --
        for a part checked as several objects -- one list of boxes per image,
        holding each object's box in the same order on every image. Per-image
        boxes matter whenever the part is not rigidly fixtured: a shared box
        lands on background in any reference where the part sat elsewhere, and a
        background template matches the live background at a high score — which
        would pass an empty fixture.

        `wire_checks` are kept as given, less any anchored to an object the
        part no longer has.
        """
        rois = list(roi) if isinstance(roi, (list, tuple)) else [roi] * len(images)
        if len(rois) != len(images):
            raise ValueError(
                f"Got {len(rois)} regions for {len(images)} reference images."
            )
        # Normalise to one list of boxes per image.
        rois = [list(r) if isinstance(r, (list, tuple)) else [r] for r in rois]
        n_objects = len(rois[0]) if rois else 0
        if not 1 <= n_objects <= MAX_OBJECTS:
            raise ValueError(f"A part needs 1 to {MAX_OBJECTS} objects, got {n_objects}.")
        if any(len(r) != n_objects for r in rois):
            raise ValueError("Every reference image needs a box for every object.")
        names = [(n or "").strip() for n in list(object_names or [])[:n_objects]]
        names += [""] * (n_objects - len(names))
        names = [n or f"Object {k + 1}" for k, n in enumerate(names)]

        def _where(n, k):
            return f"reference image {n}" + (f", {names[k]}" if n_objects > 1 else "")

        templates = [[] for _ in range(n_objects)]
        for n, (img, boxes) in enumerate(zip(images, rois), start=1):
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            for k, r in enumerate(boxes):
                if r is None:
                    raise ValueError(f"No region marked on {_where(n, k)}.")
                x, y, w, h = r["x"], r["y"], r["width"], r["height"]
                if w < 10 or h < 10:
                    raise ValueError(f"Region on {_where(n, k)} is too small.")
                if y + h > gray.shape[0] or x + w > gray.shape[1]:
                    raise ValueError(f"Region on {_where(n, k)} falls outside it.")
                templates[k].append(gray[y:y + h, x:x + w])

        model_cfg = {
            "part_number": part_number,
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "pieces": [{"name": names[k], "rois": [b[k] for b in rois]}
                       for k in range(n_objects)],
            "rois": [b[0] for b in rois],   # object 1, for readers from before objects
            "roi": rois[0][0],              # older readers expect a single region
            "match_threshold": match_threshold,
            "num_references": len(images),
            "wire_checks": [c for c in (wire_checks or [])
                            if 0 <= int(c.get("object", 0)) < n_objects],
        }

        os.makedirs(_MODELS_DIR, exist_ok=True)
        filename = f"{part_number}.npz"
        model_path = os.path.join(_MODELS_DIR, filename)

        save_dict = {"config": json.dumps(model_cfg)}
        for k, object_templates in enumerate(templates):
            prefix = "template_" if k == 0 else f"piece{k}_template_"
            for i, t in enumerate(object_templates):
                save_dict[f"{prefix}{i}"] = t
        np.savez_compressed(model_path, **save_dict)

        self.config.setdefault("part_mapping", {})[part_number] = filename
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

    def model_info(self, part_number: str) -> Optional[dict]:
        """Metadata for a taught part, or None if it has no usable model."""
        model = self._load_model(part_number)
        if model is None:
            return None
        templates = model.get("templates", [])
        roi = model.get("roi") or {}
        rois = model.get("rois") or ([roi] if roi else [])
        sizes = ([(t.shape[1], t.shape[0]) for t in templates] if templates else
                 [(r.get("width", 0), r.get("height", 0)) for r in rois])
        objects = model.get("objects", [])
        return {
            "objects": len(objects),
            "object_names": [p["name"] for p in objects],
            "object_template_sizes": [
                (p["templates"][0].shape[1], p["templates"][0].shape[0])
                if p["templates"] else (0, 0) for p in objects],
            "references": model.get("num_references", len(templates)),
            "created": model.get("created", "—"),
            "threshold": model.get("match_threshold", self.config.get("match_threshold", DEFAULT_MATCH_THRESHOLD)),
            "roi": roi,
            "rois": rois,
            "template_size": sizes[0] if sizes else (0, 0),
            "template_sizes": sizes,
            "uniform_templates": len(set(sizes)) <= 1,
            "wire_checks": [dict(c) for c in model.get("wire_checks", [])],
        }

    def _rewrite_model_cfg(self, part_number: str, edit):
        """Apply `edit` to a taught model's config in place, every template
        array riding along untouched -- all objects' templates, not just the
        first object's."""
        path = self._model_path(part_number)
        if path is None:
            raise ValueError(f"No model file mapped to '{part_number}'.")

        data = np.load(path, allow_pickle=True)
        model_cfg = json.loads(str(data["config"]))
        edit(model_cfg)
        save_dict = {k: data[k] for k in data.files if k != "config"}
        save_dict["config"] = json.dumps(model_cfg)
        data.close()
        np.savez_compressed(path, **save_dict)
        self._model_cache.pop(part_number, None)

    def set_model_threshold(self, part_number: str, threshold: float):
        """Rewrite a taught model's own threshold.

        A model carries the threshold it was taught with and that value wins over
        the global default at inspection time, so tuning a part has to reach into
        the .npz rather than the config file.
        """
        self._rewrite_model_cfg(
            part_number, lambda cfg: cfg.__setitem__("match_threshold", float(threshold)))

    def set_model_wire_checks(self, part_number: str, checks: List[dict]):
        """Replace a taught part's wire-colour checks. Each is
        {"name", "object", "offset": {"dx","dy","width","height"}, "colors",
        "direction"}, its offset measured from its object's match box."""
        if len(checks) > MAX_WIRE_CHECKS:
            raise ValueError(f"At most {MAX_WIRE_CHECKS} wire checks per part.")
        clean = []
        for c in checks:
            colors = [str(x).lower() for x in c.get("colors", []) if x]
            if not 1 <= len(colors) <= MAX_WIRES:
                raise ValueError(f"“{c.get('name')}” needs 1 to {MAX_WIRES} wire colours.")
            off = c.get("offset")
            if not off:
                raise ValueError(f"“{c.get('name')}” has no wire box drawn.")
            clean.append({
                "name": (c.get("name") or "").strip() or f"Wires {len(clean) + 1}",
                "object": int(c.get("object", 0)),
                "offset": {k: int(off[k]) for k in ("dx", "dy", "width", "height")},
                "colors": colors,
                "direction": "ttb" if c.get("direction") == "ttb" else "ltr",
            })
        self._rewrite_model_cfg(part_number, lambda cfg: cfg.__setitem__("wire_checks", clean))

    def map_model_file(self, part_number: str, filename: str):
        """Point a part number at an existing model file in vision_models/."""
        if not os.path.exists(os.path.join(_MODELS_DIR, filename)):
            raise ValueError(f"Model file '{filename}' not found.")
        self.config.setdefault("part_mapping", {})[part_number] = filename
        save_vision_config(self.config)
        self._model_cache.pop(part_number, None)
