#!/usr/bin/env python3
"""
DR7-Studio — Tapion Master-Referenced Concept & Pixel QC Gate.
Benchmarks any Tapion sprite frame(s) directly against the Owner-approved
`approved-master-125px.png` canonical master (SHA-256 0965b36e431bcc4f...):
  - 100% binary alpha (semi_alpha_px == 0)
  - Zero magenta spill / pink border fringe
  - Crisp dark outer outline on non-FX body frames (border_dark_frac >= 0.88)
  - Tapion color signature (vermilion-orange mohawk, royal-blue scarf/tabard, golden-orange vest/greaves)
  - Palette distance to canonical master (pal_median_dist <= 26.0 on body pixels)
  - Anti-jitter grounded stance_mid check around anchor_x = 144.0 and boot_y = 247
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
MASTER_125_PATH = ROOT / "work" / "characters" / "tapion" / "approved-master" / "approved-master-125px.png"
LOCK_JSON_PATH = ROOT / "work" / "characters" / "tapion" / "approved-master" / "approval.json"


def verify_master_lock() -> Dict[str, object]:
    lock_doc = json.loads(LOCK_JSON_PATH.read_text(encoding="utf-8"))
    exp_sha = lock_doc["files"]["master_125px"]["sha256"]
    got_sha = hashlib.sha256(MASTER_125_PATH.read_bytes()).hexdigest()
    if got_sha != exp_sha:
        raise RuntimeError(f"QA GATE 0 FAILED: Master 125px SHA mismatch ({got_sha} != {exp_sha})")
    return lock_doc


def load_master_palette() -> Tuple[np.ndarray, Dict[str, float]]:
    verify_master_lock()
    arr = np.array(Image.open(MASTER_125_PATH).convert("RGBA"), dtype=np.uint8)
    vis = arr[:, :, 3] > 0
    rgb = arr[vis][:, :3]
    uniq, cnts = np.unique(rgb, axis=0, return_counts=True)
    canon_pal = uniq[cnts >= 2].astype(np.float32)
    b4 = vis & ~ndimage.binary_erosion(vis, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    bdark = float((b4 & (lum < 50)).sum()) / max(1, int(b4.sum()))
    return canon_pal, {"palette_colors": int(len(canon_pal)), "master_border_dark": round(bdark, 4)}


def audit_frame(
    frame_path: pathlib.Path,
    canon_pal: np.ndarray,
    *,
    allow_fx_border: bool = False,
    check_grounded_stance: bool = False,
) -> Dict[str, object]:
    arr = np.array(Image.open(frame_path).convert("RGBA"), dtype=np.uint8)
    alpha = arr[:, :, 3]
    vis = alpha > 0
    if not vis.any():
        return {"file": frame_path.name, "pass": False, "errors": ["empty_frame"]}

    semi_alpha_px = int(((alpha > 0) & (alpha < 255)).sum())
    ys, xs = np.where(vis)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    w, h = x1 - x0 + 1, y1 - y0 + 1

    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    lum = 0.299 * r + 0.587 * g + 0.114 * b

    magenta_px = int((vis & (r > 160) & (b > 160) & (g < 130) & ((r - g) > 45) & ((b - g) > 45)).sum())
    b4 = vis & ~ndimage.binary_erosion(vis, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    border_pink = int((b4 & ((r - g) > 18) & ((b - g) > 18) & (g < 175)).sum())
    border_dark_frac = float((b4 & (lum < 52)).sum()) / max(1, int(b4.sum()))

    # Tapion color signature checks
    hair_red_orange = int((vis & (r > 165) & (r > g + 25) & (b < 80)).sum())
    royal_blue = int((vis & (b > r + 20) & (b > 75) & (r < 120)).sum())
    gold_vest = int((vis & (r > 160) & (g > 95) & (b < 75)).sum())

    # Exclude bright white/cyan/blue sword slash/aura/dome pixels when measuring body palette distance
    if allow_fx_border:
        fx_bright = ((b > 85) & (b > r + 38)) | ((b > 185) & (g > 165)) | ((r > 205) & (g > 205) & (b > 205)) | ((r > 215) & (g > 180) & (b < 95))
        body_vis = vis & ~fx_bright
        if body_vis.sum() < 100:
            body_vis = vis
    else:
        body_vis = vis

    fg_rgb = arr[body_vis][:, :3].astype(np.float32)
    step = max(1, len(fg_rgb) // 2500)
    samp = fg_rgb[::step]
    dists = np.sqrt(((samp[:, None, :] - canon_pal[None, :, :]) ** 2).sum(axis=2)).min(axis=1)
    pal_median_dist = float(np.median(dists))

    lbl, n_comp = ndimage.label(vis, structure=np.ones((3, 3)))
    tiny_specks = sum(1 for c in range(1, n_comp + 1) if int((lbl == c).sum()) <= 2)

    stance_mid = None
    if y1 >= 240:
        fxs = np.where(vis[max(y0, y1 - 7) : y1 + 1, :])[1]
        if len(fxs) > 0:
            stance_mid = round(0.5 * (int(fxs.min()) + int(fxs.max())), 2)

    errors: List[str] = []
    if semi_alpha_px > 0:
        errors.append(f"semi_alpha_px={semi_alpha_px}")
    if magenta_px > 0:
        errors.append(f"magenta_px={magenta_px}")
    if border_pink > 0:
        errors.append(f"border_pink={border_pink}")
    if not allow_fx_border and border_dark_frac < 0.88:
        errors.append(f"border_dark_frac={border_dark_frac:.3f}<0.88")
    if hair_red_orange < 60:
        errors.append(f"hair_red_orange={hair_red_orange}<60")
    if royal_blue + gold_vest < 80:
        errors.append(f"outfit_sig={royal_blue + gold_vest}<80")
    if pal_median_dist > 26.0:
        errors.append(f"pal_median_dist={pal_median_dist:.1f}>26.0")
    if tiny_specks > 0 and not allow_fx_border:
        errors.append(f"tiny_specks={tiny_specks}")
    if check_grounded_stance:
        if y1 != 247:
            errors.append(f"boot_y={y1}!=247")
        if stance_mid is None or abs(stance_mid - 144.0) > 1.5:
            errors.append(f"stance_mid={stance_mid} outside 144.0±1.5")

    return {
        "file": frame_path.name,
        "pass": len(errors) == 0,
        "errors": errors,
        "bbox": [x0, y0, w, h],
        "y1": y1,
        "stance_mid": stance_mid,
        "border_dark_frac": round(border_dark_frac, 4),
        "hair_px": hair_red_orange,
        "blue_px": royal_blue,
        "gold_px": gold_vest,
        "pal_median_dist": round(pal_median_dist, 2),
        "components": int(n_comp),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", nargs="+", type=pathlib.Path)
    ap.add_argument("--allow-fx-border", action="store_true")
    ap.add_argument("--grounded", action="store_true")
    args = ap.parse_args()
    canon_pal, stats = load_master_palette()
    print(f"[TAPION MASTER QC] {json.dumps(stats)}")
    ok = True
    for fp in args.frames:
        res = audit_frame(fp, canon_pal, allow_fx_border=args.allow_fx_border, check_grounded_stance=args.grounded)
        if not res["pass"]:
            ok = False
        print(f"[{'PASS' if res['pass'] else 'FAIL'}] {res['file']}: bbox={res['bbox']} smid={res['stance_mid']} bdark={res['border_dark_frac']} pal={res['pal_median_dist']} errs={res['errors']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
