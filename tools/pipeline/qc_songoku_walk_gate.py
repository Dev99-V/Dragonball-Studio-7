#!/usr/bin/env python3
"""
DR7-Studio — Songoku SSJ1 Walk-Referenced Concept & Pixel QC Gate.
Benchmarks any Songoku SSJ1 sprite frame(s) directly against the Owner-approved
`walk_ssj_00..07` canonical concept (palette, outline darkness/anti-flicker,
binary alpha, 0 magenta/dark pockets, SSJ1 golden hair + sleeveless orange gi +
royal-blue undershirt/sash/boots signature, and 1px sharpness).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "review" / "songoku_hero_demo" / "source" / "raw_frames"


def load_walk_reference_palette() -> Tuple[np.ndarray, Dict[str, float]]:
    """Build canonical RGB palette & baseline metrics from walk_ssj_00..07."""
    rgb_list = []
    border_darks = []
    inner_darks = []
    for i in range(8):
        p = RAW_DIR / f"walk_ssj_{i:02d}.png"
        arr = np.array(Image.open(p).convert("RGBA"), dtype=np.uint8)
        a = arr[:, :, 3] > 0
        rgb_list.append(arr[a][:, :3])
        b4 = a & ~ndimage.binary_erosion(a, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
        r2 = a & ~ndimage.binary_erosion(a, structure=np.ones((3, 3)))
        inner = r2 & ~b4
        lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        border_darks.append(float((b4 & (lum < 45)).sum()) / max(1, int(b4.sum())))
        inner_darks.append(float((inner & (lum < 45)).sum()) / max(1, int(inner.sum())))
    all_rgb = np.concatenate(rgb_list, axis=0)
    # Unique colors appearing >= 4 times across walk_ssj form canonical palette
    uniq, cnts = np.unique(all_rgb, axis=0, return_counts=True)
    canon_pal = uniq[cnts >= 4].astype(np.float32)
    stats = {
        "palette_colors": int(len(canon_pal)),
        "border_dark_min": round(min(border_darks), 4),
        "border_dark_mean": round(float(np.mean(border_darks)), 4),
        "inner_dark_mean": round(float(np.mean(inner_darks)), 4),
    }
    return canon_pal, stats


def audit_frame_against_walk(
    frame_path: pathlib.Path,
    canon_pal: np.ndarray,
    allow_fx_border: bool = False,
) -> Dict[str, object]:
    arr = np.array(Image.open(frame_path).convert("RGBA"), dtype=np.uint8)
    alpha = arr[:, :, 3]
    vis = alpha > 0
    semi_alpha_px = int(((alpha > 0) & (alpha < 255)).sum())
    alpha_hardness_pct = 100.0 * (1.0 - semi_alpha_px / max(1, int(vis.sum())))

    ys, xs = np.where(vis)
    if len(ys) == 0:
        return {"file": frame_path.name, "pass": False, "errors": ["empty_frame"]}

    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    w, h = x1 - x0 + 1, y1 - y0 + 1

    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    lum = 0.299 * r + 0.587 * g + 0.114 * b

    # Magenta spill check
    magenta_px = int((vis & (r > 160) & (b > 160) & (g < 130) & ((r - g) > 45) & ((b - g) > 45)).sum())
    b4 = vis & ~ndimage.binary_erosion(vis, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    border_pink = int((b4 & ((r - g) > 18) & ((b - g) > 18) & (g < 170)).sum())
    border_dark_frac = float((b4 & (lum < 50)).sum()) / max(1, int(b4.sum()))
    border_mean_lum = float(lum[b4].mean()) if b4.any() else 0.0

    # Concept color signatures (must match walk_ssj!)
    # 1. Golden SSJ1 hair in top 55% of sprite
    head_mask = np.zeros_like(vis)
    head_mask[y0 : y0 + max(1, int(round(h * 0.55))), :] = True
    gold_hair = vis & head_mask & (r > 185) & (g > 145) & (b < 155) & ((r - b) > 55)
    gold_hair_px = int(gold_hair.sum())

    # 2. Bright orange martial arts gi
    orange_gi = vis & (r > 175) & (g >= 65) & (g <= 170) & (b < 65) & ((r - g) > 35)
    orange_gi_px = int(orange_gi.sum())

    # 3. Wrong red pants detector (crimson red: R > 150, G < 55, B < 55)
    crimson_red = vis & (r > 150) & (g < 55) & (b < 55)
    crimson_red_px = int(crimson_red.sum())

    # 4. Royal blue undershirt / sash / wristbands / boots
    royal_blue = vis & (b > r + 20) & (b > 80) & (r < 110)
    royal_blue_px = int(royal_blue.sum())

    # 5. Palette distance to canonical walk_ssj (ignoring white/cyan motion streaks if allow_fx_border)
    fg_rgb = arr[vis][:, :3].astype(np.float32)
    # Subsample up to 2500 pixels deterministically for fast exact L2 distance
    step = max(1, len(fg_rgb) // 2500)
    samp = fg_rgb[::step]
    dists = np.sqrt(((samp[:, None, :] - canon_pal[None, :, :]) ** 2).sum(axis=2)).min(axis=1)
    pal_median_dist = float(np.median(dists))
    pal_p90_dist = float(np.percentile(dists, 90))

    # Stray 1-2px detached dust specks check
    lbl, n_comp = ndimage.label(vis, structure=np.ones((3, 3)))
    tiny_specks = 0
    for c in range(1, n_comp + 1):
        sz = int((lbl == c).sum())
        if sz <= 2:
            tiny_specks += 1

    errors: List[str] = []
    if semi_alpha_px > 0:
        errors.append(f"semi_alpha_px={semi_alpha_px}")
    if magenta_px > 0:
        errors.append(f"magenta_px={magenta_px}")
    if border_pink > 0:
        errors.append(f"border_pink={border_pink}")
    if not allow_fx_border and border_dark_frac < 0.90:
        errors.append(f"border_dark_frac={border_dark_frac:.3f}<0.90")
    if gold_hair_px < 120:
        errors.append(f"gold_hair_px={gold_hair_px}<120")
    if orange_gi_px < 200:
        errors.append(f"orange_gi_px={orange_gi_px}<200")
    if royal_blue_px < 120:
        errors.append(f"royal_blue_px={royal_blue_px}<120")
    if crimson_red_px > max(140, int(orange_gi_px * 0.25)):
        errors.append(f"crimson_red_px={crimson_red_px} (possible wrong red pants)")
    if pal_median_dist > 24.0:
        errors.append(f"pal_median_dist={pal_median_dist:.1f}>24.0")
    if tiny_specks > 0 and not allow_fx_border:
        errors.append(f"tiny_specks={tiny_specks}")

    return {
        "file": frame_path.name,
        "pass": len(errors) == 0,
        "errors": errors,
        "bbox": [x0, y0, w, h],
        "y1": y1,
        "alpha_hardness_pct": round(alpha_hardness_pct, 2),
        "magenta_px": magenta_px,
        "border_pink": border_pink,
        "border_dark_frac": round(border_dark_frac, 4),
        "border_mean_lum": round(border_mean_lum, 2),
        "gold_hair_px": gold_hair_px,
        "orange_gi_px": orange_gi_px,
        "royal_blue_px": royal_blue_px,
        "crimson_red_px": crimson_red_px,
        "pal_median_dist": round(pal_median_dist, 2),
        "pal_p90_dist": round(pal_p90_dist, 2),
        "components": int(n_comp),
        "tiny_specks": tiny_specks,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Walk-referenced QC gate for Songoku SSJ1 frames")
    ap.add_argument("frames", nargs="+", type=pathlib.Path)
    ap.add_argument("--allow-fx-border", action="store_true", help="Allow bright outer border pixels from speed/slash FX streaks")
    ap.add_argument("--json-out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    canon_pal, walk_stats = load_walk_reference_palette()
    print(f"[WALK REF] {json.dumps(walk_stats)}")
    results = []
    all_pass = True
    for fp in args.frames:
        res = audit_frame_against_walk(fp, canon_pal, allow_fx_border=args.allow_fx_border)
        results.append(res)
        tag = "PASS" if res["pass"] else "FAIL"
        if not res["pass"]:
            all_pass = False
        print(
            f"[{tag}] {res['file']}: bbox={res['bbox']} y1={res['y1']} "
            f"bdark={res['border_dark_frac']:.3f} blum={res['border_mean_lum']:.1f} pink={res['border_pink']} "
            f"hair={res['gold_hair_px']} gi={res['orange_gi_px']} blue={res['royal_blue_px']} "
            f"pal_med={res['pal_median_dist']:.1f} errs={res['errors']}"
        )
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps({"walk_ref": walk_stats, "frames": results}, indent=2) + "\n", encoding="utf-8")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
