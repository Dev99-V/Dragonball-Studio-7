#!/usr/bin/env python3
"""Reproduce host imagegen frame extraction without modifying legacy extractor."""
from pathlib import Path
import importlib.util
from PIL import Image
BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("shenron_extractor", BASE / "extract_shenron_frame.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
reference = {key: getattr(module, key) for key in ("REF_X0", "REF_Y0", "REF_W", "REF_H")}
for index, dy in ((2, -2), (3, -1)):
    raw = BASE / f"raw/idle_{index:02d}-host-raw.png"
    width, height = Image.open(raw).size
    if width != height:
        raise ValueError("Expected square host image")
    for key, value in reference.items():
        setattr(module, key, value * width / 1024)
    target = BASE / f"idle_{index:02d}-host-candidate.png"
    image = module.extract_keyframe(raw, dy_px=dy)
    image.save(target)
    print(target, image.getbbox())
