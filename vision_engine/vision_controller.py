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
  An object (a connector) can also carry a wire check: the colours its wires
  must show, in order left to right (or top to bottom), inside a wire area
  drawn once next to it. The area is stored relative to the object's box, so
  it follows the connector wherever the match lands it. The check only runs
  once the object itself is found, and the object is OK only when both pass.
  Wire checks live in vision_config.json, not the model file, so re-teaching
  a part keeps them.
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
MAX_WIRES = 8

# Colours a wire can be checked for, with a swatch (hex) for the UI. Every
# pixel of a wire area is sorted into one of these by _classify_pixels().
WIRE_COLORS = {
    "red": "#e53935", "orange": "#fb8c00", "yellow": "#fdd835",
    "green": "#43a047", "blue": "#1e88e5", "violet": "#8e24aa",
    "pink": "#f06292", "brown": "#795548", "black": "#000000",
    "grey": "#9e9e9e", "white": "#ffffff",
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
    # Wire check, when the object has one. wires_ok is None when it has none.
    wires_ok: Optional[bool] = None
    wires_expected: List[str] = field(default_factory=list)
    wires_found: List[str] = field(default_factory=list)
    wire_zone: Optional[Tuple[int, int, int, int]] = None   # (x, y, w, h) in frame


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


def _default_config() -> dict:
    return {
        "vision_enabled": True,
        "camera_source": "cam1",
        "match_threshold": DEFAULT_MATCH_THRESHOLD,
        "part_mapping": {},
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


# ── Wire colours ──────────────────────────────────────────────────────────────

def _classify_pixels(bgr: np.ndarray) -> np.ndarray:
    """Name every pixel's colour: an array of WIRE_COLORS keys, one per pixel.

    Hue decides the chromatic colours; pixels too grey to have a hue fall to
    black / grey / white by brightness. Dark orange and red read as brown.
    OpenCV hue runs 0-180.
    """
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = hsv[..., 0].astype(int)
    s = hsv[..., 1].astype(int)
    v = hsv[..., 2].astype(int)
    out = np.full(h.shape, "grey", dtype=object)

    chroma = (s >= 60) & (v >= 60)
    for name, lo, hi in (("red", 0, 8), ("orange", 8, 20), ("yellow", 20, 36),
                         ("green", 36, 85), ("blue", 85, 128), ("violet", 128, 148),
                         ("pink", 148, 170), ("red", 170, 181)):
        out[chroma & (h >= lo) & (h < hi)] = name
    out[chroma & (h < 20) & (v < 130)] = "brown"

    grey = ~chroma
    out[grey & (v < 80)] = "black"
    out[grey & (v >= 170) & (s < 60)] = "white"
    return out


def detect_wire_colors(frame: np.ndarray, zone: Tuple[int, int, int, int],
                       direction: str, colors: List[str]) -> List[str]:
    """The wire colours seen across `zone`, in order along `direction`.

    `direction` is "lr" (wires run top-bottom, read left to right) or "tb"
    (wires run left-right, read top to bottom). Only the colours in `colors`
    are looked for, so background in any other colour is ignored. Each line
    across the wires is labelled with the colour most of it shows; runs of one
    colour become one wire, and slivers too thin to be a wire are dropped.
    """
    x, y, w, h = zone
    roi = frame[y:y + h, x:x + w]
    wanted = list(dict.fromkeys(colors))
    if roi.size == 0 or not wanted:
        return []
    labels = _classify_pixels(roi)
    if direction == "tb":
        labels = labels.T                   # now each column is one line across
    thickness, length = labels.shape

    # One label per position along the axis: the wanted colour covering the
    # most of that line, if it covers enough of it to be a wire and not a
    # speck. None where no wanted colour does.
    counts = np.stack([(labels == c).sum(axis=0) for c in wanted])   # (n, length)
    best = counts.argmax(axis=0)
    strong = counts.max(axis=0) >= max(1, int(thickness * 0.35))
    line = [wanted[b] if ok else None for b, ok in zip(best, strong)]

    def _runs(seq):
        runs = []
        for lab in seq:
            if runs and runs[-1][0] == lab:
                runs[-1][1] += 1
            else:
                runs.append([lab, 1])
        return runs

    # Drop runs too thin to be a wire, then fold what is left: neighbouring
    # runs of one colour split only by a sliver are one wire.
    min_run = max(2, length // 40)
    cleaned = []
    for lab, n in _runs(line):
        cleaned += [lab if n >= min_run else None] * n
    found = []
    gap = 0
    for lab, n in _runs(cleaned):
        if lab is None:
            gap = n
            continue
        if not (found and found[-1] == lab and gap < min_run):
            found.append(lab)
        gap = 0
    return found


def wire_zone_in_frame(box: Tuple[int, int, int, int], zone: dict,
                       frame_shape) -> Optional[Tuple[int, int, int, int]]:
    """A wire area stored relative to its object, placed against where the
    object was found in this frame and clipped to the frame."""
    fh, fw = frame_shape[:2]
    x0 = max(0, box[0] + int(zone["dx"]))
    y0 = max(0, box[1] + int(zone["dy"]))
    x1 = min(fw, box[0] + int(zone["dx"]) + int(zone["width"]))
    y1 = min(fh, box[1] + int(zone["dy"]) + int(zone["height"]))
    if x1 - x0 < 3 or y1 - y0 < 3:
        return None
    return (x0, y0, x1 - x0, y1 - y0)


def wire_position_names(count: int, direction: str) -> List[str]:
    """What an operator calls each wire position: Left / Middle / Right, and
    so on, falling back to numbers where words run out."""
    a, m, b = ("Left", "Middle", "Right") if direction == "lr" else ("Top", "Middle", "Bottom")
    if count == 1:
        return ["Wire"]
    if count == 2:
        return [a, b]
    if count == 3:
        return [a, m, b]
    return ["%d%s" % (i + 1, " (%s)" % a.lower() if i == 0 else
                      " (%s)" % b.lower() if i == count - 1 else "")
            for i in range(count)]


def _best_match(gray_frame: np.ndarray, templates: List[np.ndarray]):
    """(score, box, compared): the best of `templates` anywhere in the frame.
    Templates larger than the frame are skipped and not counted."""
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
    return best_score, best_box, compared


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
            self._model_cache[part_number] = model_cfg
            return model_cfg
        except (OSError, ValueError, KeyError):
            return None

    def has_model(self, part_number: str) -> bool:
        return self._model_path(part_number) is not None

    def get_mapped_parts(self) -> dict:
        return dict(self.config.get("part_mapping", {}))

    # ── Wire checks ─────────────────────────────────────────────────────────

    def locate_objects(self, part_number: str, frame: np.ndarray) -> List[ObjectResult]:
        """Where each object of a part matches best in `frame`, found or not.

        For placing wire areas: unlike inspect() this works with vision
        switched off, and hands back the best box even below the threshold
        (ok says whether it reached it) so the operator can still see where
        the object landed. Empty when the part has no usable model.
        """
        model = self._load_model(part_number)
        if model is None:
            return []
        threshold = model.get("match_threshold",
                              self.config.get("match_threshold", DEFAULT_MATCH_THRESHOLD))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        out = []
        for obj in model.get("objects", []):
            score, box, _ = _best_match(gray, obj["templates"])
            out.append(ObjectResult(name=obj["name"], ok=score >= threshold,
                                    score=max(score, 0.0), box=box))
        return out

    def wire_checks(self, part_number: str) -> Dict[int, dict]:
        """{object index: {"colors", "direction", "zone"}} for a part."""
        raw = self.config.get("wire_checks", {}).get(part_number, {})
        return {int(k): v for k, v in raw.items() if v and v.get("colors")}

    def set_wire_check(self, part_number: str, k: int, check: Optional[dict]):
        """Save (or with None, remove) the wire check of object `k`."""
        all_checks = self.config.setdefault("wire_checks", {})
        part = all_checks.setdefault(part_number, {})
        if check:
            part[str(k)] = {
                "colors": list(check["colors"]),
                "direction": check.get("direction", "lr"),
                "zone": {n: int(check["zone"][n]) for n in ("dx", "dy", "width", "height")},
            }
        else:
            part.pop(str(k), None)
        if not part:
            all_checks.pop(part_number, None)
        save_vision_config(self.config)

    # ── Production Inspection ───────────────────────────────────────────────

    def inspect(self, part_number: str, frame: Optional[np.ndarray] = None) -> VisionResult:
        """Judge one frame against a taught part.

        By default captures a fresh frame from the configured camera — the
        same path production uses. Pass `frame` to judge a still image
        instead, without needing the part in front of a camera at all.
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

        # Each object is searched for on its own, exactly as a whole part used
        # to be: the best of its templates anywhere in the frame.
        results = []
        for obj in objects:
            templates = obj["templates"]
            best_score, best_box, compared = _best_match(gray_frame, templates)

            print(f"[VISION DEBUG] pno={part_number} object={obj['name']!r} "
                  f"frame={gray_frame.shape[1]}x{gray_frame.shape[0]} "
                  f"brightness={gray_frame.mean():.1f} templates={[(t.shape[1], t.shape[0]) for t in templates]} "
                  f"compared={compared} best_score={best_score:.3f}")

            if compared == 0:
                return _error(
                    f"Every template{' of ' + obj['name'] if len(objects) > 1 else ''} "
                    f"is larger than this frame "
                    f"({gray_frame.shape[1]}x{gray_frame.shape[0]}) — "
                    f"re-teach the part at this resolution, or use a larger test image"
                )
            results.append(ObjectResult(name=obj["name"], ok=best_score >= threshold,
                                       score=best_score, box=best_box))

        # Wire colours, for each object that has a check -- judged only where
        # the object was actually found, since its box places the wire area.
        wires = self.wire_checks(part_number)
        for k, r in enumerate(results):
            check = wires.get(k)
            if not check:
                continue
            r.wires_expected = list(check["colors"])
            r.wires_ok = False
            if r.ok and r.box:
                r.wire_zone = wire_zone_in_frame(r.box, check["zone"], frame.shape)
                if r.wire_zone:
                    r.wires_found = detect_wire_colors(
                        frame, r.wire_zone, check.get("direction", "lr"), r.wires_expected)
                    r.wires_ok = r.wires_found == r.wires_expected
                print(f"[VISION DEBUG] pno={part_number} object={r.name!r} "
                      f"wires expected={r.wires_expected} found={r.wires_found}")
                r.ok = r.wires_ok

        elapsed = int((time.time() - start) * 1000)
        weakest = min(results, key=lambda r: r.score)

        if all(r.ok for r in results):
            return VisionResult(
                ok=True, judgement="OK", part_number=part_number,
                match_score=weakest.score, threshold=threshold,
                processing_time_ms=elapsed,
                match_box=weakest.box, frame=frame, objects=results,
            )
        missing = [r for r in results if r.score < threshold]
        errors = []
        if missing and len(results) == 1:
            errors.append(f"No match found (score {weakest.score:.2f} < {threshold})")
        elif missing:
            errors.append("Not found: " + ", ".join(
                f"{r.name} ({r.score:.2f})" for r in missing))
        for r in results:
            if r.score >= threshold and r.wires_ok is False:
                errors.append(
                    ("Wire colours" if len(results) == 1 else f"{r.name} wires") +
                    f" wrong: expected {'-'.join(r.wires_expected)}, "
                    f"found {'-'.join(r.wires_found) or 'none'}")
        error = "; ".join(errors)
        return VisionResult(
            ok=False, judgement="NG", part_number=part_number,
            match_score=weakest.score, threshold=threshold,
            processing_time_ms=elapsed,
            error=error,
            match_box=weakest.box, frame=frame, objects=results,
        )

    # ── Model Building ──────────────────────────────────────────────────────

    def build_and_save_model(
        self, part_number: str, images: List[np.ndarray],
        roi: Union[dict, List[dict], List[List[dict]]],
        match_threshold: float = DEFAULT_MATCH_THRESHOLD,
        object_names: Optional[List[str]] = None,
    ) -> str:
        """Crop the templates for every object of a part and save them as its model.

        `roi` is a single box applied to every image, one box per image, or --
        for a part checked as several objects -- one list of boxes per image,
        holding each object's box in the same order on every image. Per-image
        boxes matter whenever the part is not rigidly fixtured: a shared box
        lands on background in any reference where the part sat elsewhere, and a
        background template matches the live background at a high score — which
        would pass an empty fixture.
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
        self.config.get("wire_checks", {}).pop(part_number, None)
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
        }

    def set_model_threshold(self, part_number: str, threshold: float):
        """Rewrite a taught model's own threshold.

        A model carries the threshold it was taught with and that value wins over
        the global default at inspection time, so tuning a part has to reach into
        the .npz rather than the config file.
        """
        path = self._model_path(part_number)
        if path is None:
            raise ValueError(f"No model file mapped to '{part_number}'.")

        data = np.load(path, allow_pickle=True)
        model_cfg = json.loads(str(data["config"]))
        model_cfg["match_threshold"] = float(threshold)

        # Every array rides along untouched -- all objects' templates, not just
        # the first object's.
        save_dict = {k: data[k] for k in data.files if k != "config"}
        save_dict["config"] = json.dumps(model_cfg)
        data.close()
        np.savez_compressed(path, **save_dict)
        self._model_cache.pop(part_number, None)

    def map_model_file(self, part_number: str, filename: str):
        """Point a part number at an existing model file in vision_models/."""
        if not os.path.exists(os.path.join(_MODELS_DIR, filename)):
            raise ValueError(f"Model file '{filename}' not found.")
        self.config.setdefault("part_mapping", {})[part_number] = filename
        save_vision_config(self.config)
        self._model_cache.pop(part_number, None)
