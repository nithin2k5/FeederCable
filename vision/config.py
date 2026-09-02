"""
vision/config.py
================
Camera and enable settings for the vision package.

There is deliberately no part->file mapping here. A model is stored as
`vision_models/<part_number>.vmodel.npz`, so the filename *is* the mapping.
The old design kept a separate mapping table, which let model files exist that
no part number resolved to — invisible until production failed to find one.
"""
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vision.json")

DEFAULTS = {
    "enabled": True,
    "camera_index": -1,
    "frame_w": 640,
    "frame_h": 480,
    # Locking exposure keeps scores stable across a shift. Driver-dependent;
    # capture records what actually took effect.
    "camera_settings": {},
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                cfg.update(json.load(f))
        except (OSError, ValueError):
            pass
    return cfg


def save(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)
