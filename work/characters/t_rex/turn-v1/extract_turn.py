#!/usr/bin/env python3
"""Deterministic clean extraction and 1x registration of T-rex turn_00..04 poses."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[4]
TURN_DIR = ROOT / "work/characters/t_rex/turn-v1"
SHEET_PATH = TURN_DIR / "generated/trex_turn_sheet.png"
OUT_SOURCE = TURN_DIR / "source"
OUT_REVIEW = TURN_DIR / "review"

# Crop boxes for the 3x2 generated sheet (non-overlapping cells).
CELL_BOXES = [
    (0, 80, 488, 430),      # turn_00 (+65 deg pivot initiation)
    (488, 80, 885, 430),    # turn_01 (+30 deg front-right 3/4)
    (885, 70, 1264, 430),   # turn_02 (0 deg dead-front apex)
    (0, 460, 412, 825),     # turn_03 (-30 deg front-left 3/4)
    (412, 460, 920, 825),   # turn_04 (-65 deg left settle)
]

CANVAS_W, CANVAS_H = 384, 256
ANCHOR_X, TARGET_FLOOR_Y = 176, 226
UNIFORM_SCALE = 0.405


def extract_matte_native(crop_rgb: np.ndarray) -> tuple[np.ndarray, dict]:
    """Floodfill exterior white background, detect enclosed pockets, and unmix 1px anti-alias rim."""
    h, w, _ = crop_rgb.shape
    rgb = crop_rgb.astype(np.float32)
    c_min = rgb.min(axis=-1)
    c_max = rgb.max(axis=-1)
    chroma = c_max - c_min

    # Solid white + JPEG near-white background connected from the outer crop borders.
    bg_candidate = (c_min >= 205.0) & (chroma <= 32.0)
    lbl, _ = ndimage.label(bg_candidate)
    border_ids = set(lbl[0, :]) | set(lbl[-1, :]) | set(lbl[:, 0]) | set(lbl[:, -1])
    border_ids.discard(0)
    exterior_bg = np.isin(lbl, list(border_ids))

    # Expand one transition ring into near-white low-chroma AA halo bordering exterior_bg.
    fg = ~exterior_bg
    # Any 4-connected small enclosed pocket (bright neutral <= 16px, NOT interior teeth):
    # First inspect enclosed neutral bright pockets for diagnostics; keep teeth safe.
    enclosed_neutral = bg_candidate & (~exterior_bg)
    p_lbl, p_n = ndimage.label(enclosed_neutral)
    pocket_boxes = []
    # Check if an enclosed bright neutral pocket touches dark teeth interior vs body outline,
    # and clean pure white pockets > 3px that are adjacent to gray AA (gap under arm/tail) if any.
    for pid in range(1, p_n + 1):
        ys, xs = np.where(p_lbl == pid)
        pocket_boxes.append({
            "area": int(len(xs)),
            "x": int(xs.min()),
            "y": int(ys.min()),
            "w": int(xs.max() - xs.min() + 1),
            "h": int(ys.max() - ys.min() + 1),
            "mean_lum": round(float(rgb[p_lbl == pid].mean()), 1),
        })

    # Clean outer 1px AA halo blended toward white around fg:
    # A fg pixel touching exterior_bg that is bright neutral (e.g. >175) is a pure white halo;
    # darker neutral gray boundary pixels are unmixed back toward dark olive-black outline.
    dil_bg = ndimage.binary_dilation(exterior_bg, structure=np.ones((3, 3), dtype=bool))
    rim1 = fg & dil_bg
    alpha = np.where(fg, 255.0, 0.0)

    # Strip pure-white/very-pale neutral JPEG fuzz directly on outer boundary
    pale_rim = rim1 & (c_min >= 165.0) & (chroma <= 36.0)
    alpha[pale_rim] = 0.0
    fg = alpha > 0

    # Second pass rim unmix on surviving outer border pixels against white (255,255,255)
    dil_bg2 = ndimage.binary_dilation(~fg, structure=np.ones((3, 3), dtype=bool))
    rim2 = fg & dil_bg2
    c_min2 = rgb.min(axis=-1)
    chroma2 = rgb.max(axis=-1) - c_min2
    gray_aa = rim2 & (c_min2 >= 95.0) & (chroma2 <= 38.0)
    # Estimate white contamination fraction w_bg and recover pure dark outline color.
    # For pixels >= 195 drop them; for [95..195] pull cleanly toward dark olive-black outline (24,28,20).
    drop_aa = rim2 & (c_min2 >= 180.0) & (chroma2 <= 42.0)
    alpha[drop_aa] = 0.0
    fg = alpha > 0

    fix_mask = rim2 & fg & (c_min2 >= 75.0) & (chroma2 <= 40.0)
    if fix_mask.any():
        # Unmix toward nearby dark interior pixel or canonical outline ~(26, 30, 20)
        t = np.clip((c_min2[fix_mask] - 55.0) / 140.0, 0.0, 0.85)
        target_outline = np.array([26.0, 30.0, 20.0], dtype=np.float32)
        rgb[fix_mask] = rgb[fix_mask] * (1.0 - t[:, None]) + target_outline[None, :] * t[:, None]

    # Keep only the main connected foreground character silhouette (removes stray <=10px noise specks)
    comp_lbl, comp_n = ndimage.label(fg, structure=np.ones((3, 3), dtype=bool))
    if comp_n > 1:
        counts = np.bincount(comp_lbl.ravel())
        counts[0] = 0
        main_id = int(np.argmax(counts))
        fg = comp_lbl == main_id
        alpha = np.where(fg, 255.0, 0.0)

    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = np.clip(np.round(rgb), 0, 255).astype(np.uint8)
    rgba[..., 3] = np.clip(np.round(alpha), 0, 255).astype(np.uint8)
    rgba[~fg, :3] = 0
    return rgba, {"pockets_native": pocket_boxes}


def downscale_pixel_crisp(rgba_native: np.ndarray, scale: float) -> np.ndarray:
    """Premultiplied LANCZOS downscale + crisp binary alpha & outline cleanup."""
    ys, xs = np.where(rgba_native[..., 3] > 0)
    crop = rgba_native[ys.min():ys.max() + 1, xs.min():xs.max() + 1].copy()
    ch, cw, _ = crop.shape
    tw = max(1, int(round(cw * scale)))
    th = max(1, int(round(ch * scale)))

    # Premultiply RGB by alpha cleanly before resampling so transparent pixels never bleed.
    a = crop[..., 3:4].astype(np.float32) / 255.0
    rgb_pre = crop[..., :3].astype(np.float32) * a

    # Resample premultiplied channels and alpha separately with LANCZOS for 1px detail crispness.
    pil_a = Image.fromarray(crop[..., 3], mode="L").resize((tw, th), Image.Resampling.LANCZOS)
    a_ds = np.array(pil_a, dtype=np.float32) / 255.0

    rgb_ds = np.zeros((th, tw, 3), dtype=np.float32)
    for k in range(3):
        ch_img = Image.fromarray(np.clip(np.round(rgb_pre[..., k]), 0, 255).astype(np.uint8), mode="L")
        ch_ds = ch_img.resize((tw, th), Image.Resampling.LANCZOS)
        rgb_ds[..., k] = np.array(ch_ds, dtype=np.float32)

    fg = a_ds >= 0.65
    # Recover unpremultiplied RGB where fg is True
    safe_a = np.maximum(a_ds, 0.25)
    rgb_out = rgb_ds / safe_a[..., None]

    # Ensure strictly 1 connected main body at 1x resolution
    comp_lbl, comp_n = ndimage.label(fg, structure=np.ones((3, 3), dtype=bool))
    if comp_n > 1:
        counts = np.bincount(comp_lbl.ravel())
        counts[0] = 0
        fg = comp_lbl == int(np.argmax(counts))

    # Strip any pale neutral outer boundary speck left from white JPEG AA before clamping
    dil = ndimage.binary_dilation(~fg, structure=np.ones((3, 3), dtype=bool))
    outer = fg & dil
    c_min = rgb_out.min(axis=-1)
    chroma = rgb_out.max(axis=-1) - c_min
    bright_neutral_edge = outer & (c_min >= 120.0) & (chroma <= 35.0)
    if bright_neutral_edge.any():
        rgb_out[bright_neutral_edge] = np.array([28.0, 32.0, 22.0], dtype=np.float32)

    out = np.zeros((th, tw, 4), dtype=np.uint8)
    out[fg, :3] = np.clip(np.round(rgb_out[fg]), 0, 255).astype(np.uint8)
    out[fg, 3] = 255
    return out


def register_to_canvas(sprite: np.ndarray, anchor_x: int = ANCHOR_X, floor_y: int = TARGET_FLOOR_Y) -> tuple[np.ndarray, dict]:
    """Center torso/pelvis horizontally on anchor_x and plant bottom feet on floor_y."""
    sh, sw, _ = sprite.shape
    m = sprite[..., 3] > 0
    ys, xs = np.where(m)

    # Torso/pelvis band excludes long tail whip extremes by weighting central vertical slice (35%..85% of height).
    y_top, y_bot = int(ys.min()), int(ys.max())
    h_span = y_bot - y_top + 1
    band = m & (np.arange(sh)[:, None] >= y_top + int(0.30 * h_span)) & (np.arange(sh)[:, None] <= y_top + int(0.85 * h_span))
    # Further focus on dense vertical column range (where feet/pelvis live) via foot span midpoint vs torso mean.
    foot_band = m & (np.arange(sh)[:, None] >= y_bot - 6)
    _, fxs = np.where(foot_band)
    foot_mid_x = 0.5 * (float(fxs.min()) + float(fxs.max()))
    _, bxs = np.where(band)
    torso_mid_x = float(bxs.mean())
    pivot_x = 0.5 * (foot_mid_x + torso_mid_x)

    dst_x0 = int(round(anchor_x - pivot_x))
    dst_y0 = int(round(floor_y - (y_bot + 1)))

    canvas = np.zeros((CANVAS_H, CANVAS_W, 4), dtype=np.uint8)
    # Clamp copy safely
    cx0 = max(0, dst_x0)
    cy0 = max(0, dst_y0)
    sx0 = cx0 - dst_x0
    sy0 = cy0 - dst_y0
    cw = min(sw - sx0, CANVAS_W - cx0)
    ch = min(sh - sy0, CANVAS_H - cy0)
    canvas[cy0:cy0 + ch, cx0:cx0 + cw] = sprite[sy0:sy0 + ch, sx0:sx0 + cw]

    c_ys, c_xs = np.where(canvas[..., 3] > 0)
    return canvas, {
        "bbox_px": [int(c_xs.min()), int(c_ys.min()), int(c_xs.max() - c_xs.min() + 1), int(c_ys.max() - c_ys.min() + 1)],
        "foot_mid_x": round(foot_mid_x + dst_x0, 2),
        "torso_mid_x": round(torso_mid_x + dst_x0, 2),
        "pivot_x": round(pivot_x + dst_x0, 2),
        "bottom_y": int(c_ys.max() + 1),
    }


def make_visual_audits(frames: list[np.ndarray]) -> None:
    """Create 1x lineup against canonical frames and 4x rim inspection on light/dark/checker."""
    refs = [
        ("idle_0", np.array(Image.open(ROOT / "assets/t_rex/clips/frames/frame-00.png").convert("RGBA"))),
        ("walk_0", np.array(Image.open(ROOT / "work/characters/t_rex/walk-style-v4/walk-00-reference.png").convert("RGBA"))),
        ("front_f38", np.array(Image.open(ROOT / "assets/t_rex/clips/frames/frame-38.png").convert("RGBA"))),
    ]
    all_imgs = [(f"turn_0{i}", f) for i, f in enumerate(frames)] + refs

    # Checkerboard tile 16px
    def bg_tile(h: int, w: int, kind: str) -> Image.Image:
        if kind == "light":
            return Image.new("RGBA", (w, h), (242, 244, 248, 255))
        if kind == "dark":
            return Image.new("RGBA", (w, h), (22, 26, 36, 255))
        arr = np.zeros((h, w, 4), dtype=np.uint8)
        yy, xx = np.indices((h, w))
        c = ((yy // 12 + xx // 12) % 2) == 0
        arr[c] = [196, 202, 210, 255]
        arr[~c] = [148, 154, 166, 255]
        return Image.fromarray(arr, mode="RGBA")

    # 1) Turn lineup + refs on checker & dark/light rows
    cw, ch = 220, 160
    strip = Image.new("RGBA", (cw * len(all_imgs), ch * 3), (0, 0, 0, 255))
    for r_idx, kind in enumerate(["light", "dark", "checker"]):
        row_bg = bg_tile(ch, cw * len(all_imgs), kind)
        strip.paste(row_bg, (0, r_idx * ch))
        for c_idx, (_, img_arr) in enumerate(all_imgs):
            # Crop around anchor [176, 224]: x=[70..290] (220px), y=[80..240] (160px)
            sub = Image.fromarray(img_arr[80:240, 66:286], mode="RGBA")
            strip.alpha_composite(sub, (c_idx * cw, r_idx * ch))
    strip.save(OUT_REVIEW / "turn-lineup-1x.png")

    # 2) 4x zoomed turn poses on light/dark/checker
    zcw, zch = 440, 320
    zoom_sheet = Image.new("RGBA", (zcw * 5, zch * 3), (0, 0, 0, 255))
    for r_idx, kind in enumerate(["light", "dark", "checker"]):
        row_bg = bg_tile(zch, zcw * 5, kind)
        zoom_sheet.paste(row_bg, (0, r_idx * zch))
        for c_idx, f in enumerate(frames):
            sub = Image.fromarray(f[80:240, 66:286], mode="RGBA").resize((zcw, zch), Image.Resampling.NEAREST)
            zoom_sheet.alpha_composite(sub, (c_idx * zcw, r_idx * zch))
    zoom_sheet.save(OUT_REVIEW / "turn-rim-4x.png")


def main() -> None:
    OUT_SOURCE.mkdir(parents=True, exist_ok=True)
    OUT_REVIEW.mkdir(parents=True, exist_ok=True)
    sheet = np.array(Image.open(SHEET_PATH).convert("RGB"))
    frames: list[np.ndarray] = []
    report = {"scale": UNIFORM_SCALE, "anchor_x": ANCHOR_X, "floor_y": TARGET_FLOOR_Y, "frames": []}

    for idx, (x0, y0, x1, y1) in enumerate(CELL_BOXES):
        crop = sheet[y0:y1, x0:x1]
        matte, matte_info = extract_matte_native(crop)
        down = downscale_pixel_crisp(matte, UNIFORM_SCALE)
        canvas, reg_info = register_to_canvas(down)
        out_path = OUT_SOURCE / f"turn_0{idx}.png"
        Image.fromarray(canvas, mode="RGBA").save(out_path)
        frames.append(canvas)
        report["frames"].append({"name": f"turn_0{idx}.png", **reg_info, "pockets_native_count": len(matte_info["pockets_native"])})

    make_visual_audits(frames)
    (OUT_REVIEW / "extract-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
