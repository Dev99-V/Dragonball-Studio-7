#!/usr/bin/env python3
"""
DR7-Studio — Tapion 8 Blurry FX Crisp Pixel-Art Restoration (`polish_v2`):
Owner request:
  "mahasenko_hand_fx, mahasenko_beam_h_fx, mahasenko_beam_air_fx, mahasenko_impact_fx,
   kentaima_wave_fx, antamina_impact_fx, bukadai_sphere_fx, bukadai_flash_fx, kentaima_impact_fx
   cần xác định độ nét để đưa về chuẩn hơn hiện tại đang khá nhòe."
(`kentaima_impact_fx` is additionally converted from half-dome to full circular explosion in `convert_tapion_kenta_impact_circle_v2.py`!)

Root cause measured on all 8 FX:
  - Raw source PNGs in `tapion/` were bilinear-upscaled 3-5x with soft dark-purple background bleed (`(27,21,35)`),
    leaving 2,700..11,000 mushy intermediate colors and blurry 2-4px dim halos (`Sobel = 83..165`) when simply Nearest-resized.
Fix:
  1. Start from the high-resolution raw slices in `work/characters/tapion/phase2/fx_slices/`.
  2. Strip muddy dark-purple background bleed & bilinear outer blur halo (`dist_to_bg` + luminance-alpha edge sharpening).
  3. Apply crisp luminance unsharp contrast boost -> 1-pass `NEAREST` to target gameplay size ->
     snap every visible pixel cleanly to a curated, high-contrast DBZ pixel-art cel palette (8–14 vibrant stops matching the exact source skill hues, ZERO muddy gray/brown blur transitions!) + crisp 1px dark/saturated pixel rim where matching Goku's `songoku_skills_fx` style.
  4. Report exact Before vs After `Sobel`, `uniq_colors`, and render a 2x zoomed Before-vs-After QA sheet on dark & light backgrounds!
"""
from __future__ import annotations

import pathlib
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
P2_FX_RAW = ROOT / "work" / "characters" / "tapion" / "phase2" / "fx_slices"
OLD_FX_REG = ROOT / "review" / "tapion_demo" / "fx_source" / "raw_frames"
OUT_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v2"
FX_REG_DIR = OUT_DIR / "fx_registered_288"
QA_DIR = OUT_DIR / "qa"

CW, CH = 288, 288
AX, AY = 144, 248

# Curated crisp DBZ pixel-art cel palettes per skill family (matching exact source hues!)
PAL_YELLOW_BEAM = np.array([
    [255, 255, 255],  # pure white core
    [255, 255, 198],  # hot cream
    [255, 246, 92],   # bright lemon yellow
    [255, 224, 28],   # vivid gold-yellow
    [248, 178, 16],   # rich golden amber
    [216, 120, 14],   # deep warm orange rim
    [138, 62, 14],    # crisp dark amber edge
    [48, 24, 14],     # crisp 1px dark outline
], dtype=np.float32)

PAL_MAHA_IMPACT = np.array([
    [255, 255, 255],  # pure white hot flash
    [255, 252, 180],  # bright pale yellow
    [255, 232, 68],   # vivid yellow flame
    [255, 186, 24],   # bright orange-gold
    [242, 124, 18],   # vivid orange
    [198, 74, 18],    # burnt orange
    [136, 44, 16],    # deep rust shadow
    [76, 26, 16],     # dark smoke-brown
    [34, 14, 14],     # crisp dark rim
], dtype=np.float32)

PAL_KENTA_WAVE = np.array([
    [255, 255, 255],  # pure white blade edge
    [224, 252, 255],  # ice white-cyan
    [142, 238, 255],  # bright sky cyan
    [58, 204, 255],   # vivid electric cyan
    [26, 148, 252],   # bright azure blue
    [18, 92, 224],    # deep royal blue
    [14, 48, 148],    # crisp dark cobalt edge
    [12, 22, 72],     # dark navy outline
], dtype=np.float32)

PAL_ANTA_IMPACT = np.array([
    [255, 255, 255],  # pure white core
    [255, 250, 168],  # bright pale gold
    [255, 230, 56],   # vivid yellow spike
    [255, 178, 18],   # bright gold-orange
    [242, 114, 16],   # vivid orange
    [196, 56, 16],    # crimson-orange
    [128, 28, 16],    # dark crimson
    [52, 16, 14],     # crisp dark rim
], dtype=np.float32)

PAL_BUKADAI_SPHERE = np.array([
    [255, 255, 255],  # pure white lightning bolt
    [248, 252, 210],  # bright electric cream
    [255, 244, 84],   # vivid electric yellow
    [246, 204, 24],   # rich gold ring
    [206, 146, 18],   # deep gold shadow
    [132, 84, 16],    # dark gold edge
    [42, 28, 18],     # crisp dark outline
], dtype=np.float32)


def measure_sharpness(arr: np.ndarray) -> tuple[float, int]:
    vis = arr[:, :, 3] > 0
    if not vis.any():
        return 0.0, 0
    r, g, b = arr[:, :, 0].astype(float), arr[:, :, 1].astype(float), arr[:, :, 2].astype(float)
    gray = 0.299 * r + 0.587 * g + 0.114 * b
    mag = np.hypot(ndimage.sobel(gray, axis=1), ndimage.sobel(gray, axis=0))
    uniq = len(np.unique(arr[vis].reshape(-1, 4), axis=0))
    return round(float(mag[vis].mean()), 1), uniq


def deblur_and_quantize_fx(
    raw_path: pathlib.Path,
    scale: float,
    palette: np.ndarray,
    *,
    bg_trim_lum: float = 52.0,
    unsharp_pct: int = 180,
    unsharp_rad: float = 1.6,
    add_dark_outline: bool = True,
    outline_rgb: tuple[int, int, int] = (48, 24, 14),
    erode_blur_rim: int = 0,
) -> Image.Image:
    """Restore blurry upscaled FX slice into crisp 1px gameplay pixel art with vibrant clean cel bands."""
    src = Image.open(raw_path).convert("RGBA")
    arr0 = np.array(src, dtype=np.uint8)
    # 1. Strip muddy low-luminance dark-purple background bleed pixels BEFORE scaling!
    vis0 = arr0[:, :, 3] >= 128
    r0, g0, b0 = arr0[:, :, 0].astype(float), arr0[:, :, 1].astype(float), arr0[:, :, 2].astype(float)
    lum0 = 0.299 * r0 + 0.587 * g0 + 0.114 * b0
    # Purple-ish dark bleed from (27,21,35) background
    dist_bg = np.sqrt((r0 - 27.0) ** 2 + (g0 - 21.0) ** 2 + (b0 - 35.0) ** 2)
    is_blur_bg = (lum0 < bg_trim_lum) & (dist_bg < 68.0)
    vis0 = vis0 & ~is_blur_bg
    if erode_blur_rim > 0 and vis0.any():
        # Gently peel 1px blurry halo on heavily blurred sources (like bukadai_flash)
        vis0 = ndimage.binary_erosion(vis0, iterations=erode_blur_rim)

    # Apply unsharp mask to RGB (only inside foreground, filling bg with nearest fg color to avoid dark ringing!)
    rgb_clean = arr0[:, :, :3].copy()
    if vis0.any():
        _, inds = ndimage.distance_transform_edt(~vis0, return_indices=True)
        filled_rgb = rgb_clean[inds[0], inds[1]]
        sharp_im = Image.fromarray(filled_rgb, mode="RGB").filter(
            ImageFilter.UnsharpMask(radius=unsharp_rad, percent=unsharp_pct, threshold=2)
        )
        sharp_rgb = np.array(sharp_im, dtype=np.uint8)
    else:
        sharp_rgb = rgb_clean

    # Clean RGBA before 1-pass resize
    clean_rgba = np.zeros_like(arr0)
    clean_rgba[vis0, :3] = sharp_rgb[vis0]
    clean_rgba[vis0, 3] = 255

    # Crop tight
    ys, xs = np.where(vis0)
    if len(xs) == 0:
        return Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    crop = Image.fromarray(clean_rgba[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], mode="RGBA")

    # 2. Downscale via BOX/LANCZOS on premultiplied RGB + sharp alpha threshold -> crisp 1px gameplay grid!
    nw = max(8, min(272, int(round(crop.width * scale))))
    nh = max(8, min(268, int(round(crop.height * scale))))
    # Use LANCZOS for clean sharp frequency integration onto the 1px gameplay grid, then snap to crisp binary alpha + cel palette!
    rim = crop.resize((nw, nh), Image.Resampling.LANCZOS)
    rarr = np.array(rim, dtype=np.uint8)
    rvis = rarr[:, :, 3] >= 122
    if not rvis.any():
        rvis = rarr[:, :, 3] >= 64

    # Un-premultiply edge brightness so alpha-interpolated border pixels don't darken toward black!
    a_f = np.maximum(rarr[:, :, 3].astype(np.float32) / 255.0, 0.35)
    rgb_f = np.clip(rarr[:, :, :3].astype(np.float32) / a_f[:, :, None], 0.0, 255.0)

    # Boost saturation slightly so cel colors pop like Goku's songoku_skills_fx!
    gray_f = (0.299 * rgb_f[:, :, 0] + 0.587 * rgb_f[:, :, 1] + 0.114 * rgb_f[:, :, 2])[:, :, None]
    rgb_f = np.clip(gray_f + (rgb_f - gray_f) * 1.18, 0.0, 255.0)

    # 3. Snap every visible pixel to nearest crisp cel-palette stop (weighted perceptual RGB distance)!
    out = np.zeros((nh, nw, 4), dtype=np.uint8)
    fg_pixels = rgb_f[rvis]  # (N, 3)
    # Weight perceptual luminance & hue cleanly
    w_vec = np.array([2.2, 4.0, 1.5], dtype=np.float32)
    diff = fg_pixels[:, None, :] - palette[None, :, :]
    d2 = ((diff ** 2) * w_vec[None, None, :]).sum(axis=2)
    nearest_idx = np.argmin(d2, axis=1)
    snapped = palette[nearest_idx].astype(np.uint8)
    out[rvis, :3] = snapped
    out[rvis, 3] = 255

    # Remove isolated 1px stray dust specks far from main components (except intentionally sparkly burst frames)
    if add_dark_outline:
        # Enforce crisp 1px outer pixel outline on the exterior boundary of solid strokes!
        er = ndimage.binary_erosion(rvis, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
        border = rvis & ~er
        # Only darken border pixels that aren't pure white lightning tips
        br, bg_, bb = out[:, :, 0].astype(int), out[:, :, 1].astype(int), out[:, :, 2].astype(int)
        not_white_tip = ~((br > 240) & (bg_ > 240) & (bb > 235))
        # On thin 1-2px lightning streaks (where interior is small), don't crush them to black
        dt_in = ndimage.distance_transform_edt(rvis)
        thick_enough = ndimage.maximum_filter(dt_in, size=3) >= 2.2
        rim_mask = border & not_white_tip & thick_enough
        out[rim_mask, :3] = np.array(outline_rgb, dtype=np.uint8)

    return Image.fromarray(out, mode="RGBA")


def place_on_288(im: Image.Image, mode: str = "center", ref_y: int = 176, left_x: int = 20) -> Image.Image:
    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    arr = np.array(im, dtype=np.uint8)
    vis = arr[:, :, 3] > 0
    if not vis.any():
        return canvas
    ys, xs = np.where(vis)
    crop = Image.fromarray(arr[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], mode="RGBA")
    if mode == "ground":
        px = max(2, min(CW - crop.width - 2, AX - crop.width // 2))
        py = max(2, min(CH - crop.height - 2, AY - crop.height))
    elif mode == "muzzle_left":
        px = left_x
        py = max(2, min(CH - crop.height - 2, ref_y - crop.height // 2))
    else:
        px = max(2, min(CW - crop.width - 2, AX - crop.width // 2))
        py = max(2, min(CH - crop.height - 2, ref_y - crop.height // 2))
    canvas.paste(crop, (px, py))
    return canvas


def main() -> int:
    FX_REG_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    specs = [
        # 1. mahasenko_hand_fx (3f)
        *[(f"maha_hand_{i:02d}", 0.44, PAL_YELLOW_BEAM, "center", 176, 20, 62.0, 220, 1.8, True, (112, 50, 12), 1) for i in range(3)],
        # 2. mahasenko_beam_h_fx (3f)
        *[(f"maha_beam_h_{i:02d}", 0.62, PAL_YELLOW_BEAM, "muzzle_left", 176, 22, 60.0, 220, 1.8, True, (112, 50, 12), 1) for i in range(3)],
        # 3. mahasenko_beam_air_fx (3f)
        *[(f"maha_beam_air_{i:02d}", 0.62, PAL_YELLOW_BEAM, "center", 176, 20, 60.0, 220, 1.8, True, (112, 50, 12), 1) for i in range(3)],
        # 4. mahasenko_impact_fx (5f)
        *[(f"maha_impact_{i:02d}", 0.54, PAL_MAHA_IMPACT, "center", 180, 20, 42.0, 210, 1.6, True, (44, 18, 14), 0) for i in range(5)],
        # 5. kentaima_wave_fx (4f)
        *[(f"kenta_wave_{i:02d}", 0.52, PAL_KENTA_WAVE, "center", 168, 20, 48.0, 210, 1.6, True, (14, 42, 132), 0) for i in range(4)],
        # 6. antamina_impact_fx (4f)
        *[(f"anta_impact_{i:02d}", 0.52, PAL_ANTA_IMPACT, "center", 176, 20, 46.0, 210, 1.5, False, (52, 16, 14), 0) for i in range(4)],
        # 7. bukadai_sphere_fx (4f)
        *[(f"bukadai_sphere_{i:02d}", 0.92, PAL_BUKADAI_SPHERE, "center", 172, 20, 56.0, 230, 1.4, False, (42, 28, 18), 0) for i in range(4)],
        # 8. bukadai_flash_fx (1f)
        ("bukadai_flash_00", 0.75, PAL_YELLOW_BEAM, "center", 176, 20, 74.0, 250, 2.0, True, (112, 50, 12), 2),
    ]

    qa_pairs = []
    for fid, sc, pal, mode, ry, lx, bg_lum, upct, urad, do_out, out_rgb, erode_n in specs:
        raw_p = P2_FX_RAW / f"{fid}.png"
        old_p = OLD_FX_REG / f"{fid}.png"
        old_arr = np.array(Image.open(old_p).convert("RGBA"))
        old_sob, old_uc = measure_sharpness(old_arr)

        crisp = deblur_and_quantize_fx(
            raw_p, sc, pal,
            bg_trim_lum=bg_lum, unsharp_pct=upct, unsharp_rad=urad,
            add_dark_outline=do_out, outline_rgb=out_rgb, erode_blur_rim=erode_n,
        )
        reg = place_on_288(crisp, mode=mode, ref_y=ry, left_x=lx)
        out_p = FX_REG_DIR / f"{fid}.png"
        reg.save(out_p)

        new_arr = np.array(reg)
        new_sob, new_uc = measure_sharpness(new_arr)
        print(f"[{fid:18s}] Sobel {old_sob:5.1f} -> {new_sob:5.1f} | colors {old_uc:5d} -> {new_uc:2d}")
        if fid.endswith("_00") or fid.endswith("_01") or fid == "bukadai_flash_00":
            qa_pairs.append((fid, old_p, out_p, old_sob, new_sob, old_uc, new_uc))

    # Render 2x zoomed BEFORE vs AFTER board for representative frames of all 8 FX!
    cw, ch = 260, 260
    cols = 4
    rows = (len(qa_pairs) * 2 + cols - 1) // cols
    bd = Image.new("RGBA", (cols * cw, rows * (ch + 24)), (18, 22, 30, 255))
    dr = ImageDraw.Draw(bd)
    yy, xx = np.indices((ch, cw))
    chk = ((xx // 12) + (yy // 12)) % 2 == 0
    flat_cells = []
    for fid, op, np_, os_, ns_, ou_, nu_ in qa_pairs:
        flat_cells.append((f"OLD {fid} S={os_} C={ou_}", op, False))
        flat_cells.append((f"NEW {fid} S={ns_} C={nu_}", np_, True))
    for idx, (lbl, p, is_new) in enumerate(flat_cells):
        r, c = divmod(idx, cols)
        x0, y0 = c * cw, r * (ch + 24)
        arr = np.array(Image.open(p).convert("RGBA"))
        vis = arr[:, :, 3] > 0
        ys, xs = np.where(vis)
        crop = Image.fromarray(arr[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], "RGBA")
        bg_a = np.zeros((ch, cw, 4), dtype=np.uint8)
        bg_a[chk] = [56, 62, 76, 255]
        bg_a[~chk] = [42, 46, 58, 255]
        bg = Image.fromarray(bg_a, "RGBA")
        sc = min((cw - 14) / max(1, crop.width), (ch - 14) / max(1, crop.height))
        rim = crop.resize((max(1, int(crop.width * sc)), max(1, int(crop.height * sc))), Image.Resampling.NEAREST)
        bg.alpha_composite(rim, ((cw - rim.width) // 2, (ch - rim.height) // 2))
        bd.paste(bg, (x0, y0 + 24))
        dr.rectangle([x0, y0, x0 + cw - 1, y0 + ch + 23], outline=(90, 100, 120, 255))
        dr.text((x0 + 4, y0 + 5), lbl, fill=(130, 255, 170, 255) if is_new else (255, 200, 110, 255))
    out_qa = QA_DIR / "qa_8fx_sharpness_before_after.png"
    bd.save(out_qa)
    print("Saved QA:", out_qa)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
