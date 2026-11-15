#!/usr/bin/env python3
"""Deterministic pocket-first blue-key extractor + 96-color master palette lock for Shenron keyframes.

Preserves identical 1px Nearest sharpness, alpha_hardness_pct == 100%, 0 blue spill,
and exact RGB palette centroids from work/characters/shenron/master-v1/master.png.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage


MASTER_DEFAULT = Path("/workspaces/DR7-Studio/work/characters/shenron/master-v1/master.png")

# Exact raw source grid of source-imggen-raw.jpg mapped onto 384x256 centered at (45, 27) -> 294x201
REF_X0 = 46
REF_Y0 = 193
REF_W = 934
REF_H = 639
DST_W = 294
DST_H = 201
PLACE_X = 45
PLACE_Y = 27


def load_master_palette(master_path: Path) -> np.ndarray:
    """Return unique opaque RGB colors (N, 3) float32 from the approved Master PNG."""
    m_arr = np.array(Image.open(master_path).convert("RGBA"))
    mask = m_arr[:, :, 3] > 0
    return np.unique(m_arr[mask, :3], axis=0).astype(np.float32)


def extract_keyframe(raw_path: Path, master_path: Path = MASTER_DEFAULT, dy_px: int = 0) -> Image.Image:
    """Extract a coherent generated Shenron pose on #0245C8 blue key onto 384x256 100%-hard RGBA."""
    palette = load_master_palette(master_path)
    rgb = np.array(Image.open(raw_path).convert("RGB"))
    h_src, w_src, _ = rgb.shape
    arr = rgb.astype(np.int32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # Pocket-first cobalt blue key (#0245C8): removes outer sky + all negative-space coil loops
    bg_seed = (b - np.maximum(r, g) > 25) & (b > 75)
    near_bg = ndimage.binary_dilation(bg_seed, iterations=2)
    soft_blue = near_bg & ((b - np.maximum(r, g)) > 10) & (b > 55)
    is_bg = bg_seed | soft_blue

    lbl_bg, n_bg = ndimage.label(is_bg, structure=np.ones((3, 3)))
    bg_sizes = np.bincount(lbl_bg.ravel())
    for cid in range(1, n_bg + 1):
        if bg_sizes[cid] < 6:
            is_bg[lbl_bg == cid] = False

    fg = ~is_bg
    lbl_fg, n_fg = ndimage.label(fg, structure=np.ones((3, 3)))
    fg_sizes = np.bincount(lbl_fg.ravel())
    for cid in range(1, n_fg + 1):
        if fg_sizes[cid] <= 10:
            fg[lbl_fg == cid] = False

    rgb_f = rgb.astype(np.float32)
    rim2 = ndimage.binary_dilation(~fg, iterations=2) & fg
    blue_ex = rgb_f[:, :, 2] - np.maximum(rgb_f[:, :, 0], rgb_f[:, :, 1])
    despill = rim2 & (blue_ex > 0)
    rgb_f[despill, 2] = np.maximum(rgb_f[despill, 0], rgb_f[despill, 1])

    luma = rgb_f @ np.array([0.2126, 0.7152, 0.0722])
    sat = rgb_f.max(axis=2) - rgb_f.min(axis=2)
    is_dark = fg & (luma < 64)
    is_red = fg & ((rgb_f[:, :, 0] - rgb_f[:, :, 1]) > 55) & ((rgb_f[:, :, 0] - rgb_f[:, :, 2]) > 40)
    interior = ndimage.binary_erosion(fg, iterations=3)
    is_white = interior & (luma > 195) & (sat < 45)

    sh_scale_x = REF_W / DST_W
    sh_scale_y = REF_H / DST_H
    canvas = np.zeros((256, 384, 4), dtype=np.uint8)
    ys, xs = np.where(fg)
    sx_min, sx_max = int(xs.min()), int(xs.max())
    sy_min, sy_max = int(ys.min()), int(ys.max())

    for ty in range(256):
        sy0 = max(0, int(round(REF_Y0 + (ty - dy_px - PLACE_Y) * sh_scale_y)))
        sy1 = min(h_src, max(sy0 + 1, int(round(REF_Y0 + (ty - dy_px + 1 - PLACE_Y) * sh_scale_y))))
        if sy1 <= sy_min or sy0 > sy_max:
            continue
        for tx in range(384):
            sx0 = max(0, int(round(REF_X0 + (tx - PLACE_X) * sh_scale_x)))
            sx1 = min(w_src, max(sx0 + 1, int(round(REF_X0 + (tx + 1 - PLACE_X) * sh_scale_x))))
            if sx1 <= sx_min or sx0 > sx_max:
                continue
            sub_a = fg[sy0:sy1, sx0:sx1]
            cov = float(sub_a.mean())
            cy, cx = (sy0 + sy1) // 2, (sx0 + sx1) // 2
            center_on = bool(fg[min(cy, h_src - 1), min(cx, w_src - 1)])
            if cov < 0.44 and not (cov >= 0.25 and center_on):
                continue
            sub_rgb = rgb_f[sy0:sy1, sx0:sx1][sub_a]
            sub_d = is_dark[sy0:sy1, sx0:sx1][sub_a]
            sub_w = is_white[sy0:sy1, sx0:sx1][sub_a]
            sub_r = is_red[sy0:sy1, sx0:sx1][sub_a]
            df, wf, rf = float(sub_d.mean()), float(sub_w.mean()), float(sub_r.mean())
            if wf >= 0.30 and wf >= df:
                col = np.median(sub_rgb[sub_w], axis=0)
            elif rf >= 0.30 and df < 0.55:
                col = np.median(sub_rgb[sub_r], axis=0)
            elif df >= 0.34:
                col = np.median(sub_rgb[sub_d], axis=0)
            else:
                nd = ~sub_d
                col = np.median(sub_rgb[nd] if nd.any() else sub_rgb, axis=0)
            canvas[ty, tx, :3] = np.clip(col, 0, 255).astype(np.uint8)
            canvas[ty, tx, 3] = 255

    mask = canvas[:, :, 3] > 0
    lbl, nc = ndimage.label(mask, structure=np.ones((3, 3)))
    sizes = np.bincount(lbl.ravel())
    for cid in range(1, nc + 1):
        if sizes[cid] <= 2:
            mask[lbl == cid] = False
            canvas[lbl == cid] = 0

    b_ex = canvas[:, :, 2].astype(int) - np.maximum(canvas[:, :, 0], canvas[:, :, 1]).astype(int)
    has_blue = mask & (b_ex > 0)
    canvas[has_blue, 2] = np.maximum(canvas[has_blue, 0], canvas[has_blue, 1])

    dist = ndimage.distance_transform_edt(mask)
    inner = ndimage.binary_erosion(mask, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    outer_rim = mask & (~inner)
    thick = ndimage.binary_dilation(dist >= 1.5, iterations=1)
    rl = canvas[:, :, :3].astype(np.float32) @ np.array([0.2126, 0.7152, 0.0722])
    darken = outer_rim & thick & (rl > 68)
    canvas[darken, :3] = np.clip(canvas[darken, :3] * 0.25, 8, 34).astype(np.uint8)

    pts = canvas[mask, :3].astype(np.float32)
    dists = np.linalg.norm(pts[:, None, :] - palette[None, :, :], axis=2)
    canvas[mask, :3] = palette[np.argmin(dists, axis=1)].astype(np.uint8)
    return Image.fromarray(canvas, "RGBA")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Shenron idle keyframe cleanly.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--master", type=Path, default=MASTER_DEFAULT)
    parser.add_argument("--dy", type=int, default=0, help="Optional integer vertical float offset in px")
    args = parser.parse_args()

    out_im = extract_keyframe(args.input, args.master, dy_px=args.dy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out_im.save(args.output)
    arr = np.array(out_im)
    m = arr[:, :, 3] > 0
    b_ex = arr[:, :, 2].astype(int) - np.maximum(arr[:, :, 0], arr[:, :, 1]).astype(int)
    print(
        f"Saved {args.output} bbox={out_im.getbbox()} fg_px={int(m.sum())} "
        f"blue_excess={int((m & (b_ex > 0)).sum())}"
    )


if __name__ == "__main__":
    main()
