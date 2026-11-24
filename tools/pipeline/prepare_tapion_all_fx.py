#!/usr/bin/env python3
"""
DR7-Studio — Prepare & Register ALL 17 Independent FX Clips (60 frames) of Tapion onto
288x288 canvas (anchor [144, 248], Nearest, 100% clean pocket-free alpha).
Covers 100% of Tapion's detached FX sheets:
  1. `peace_aura_fx` (4f — padded (+16,+24) from Phase 1 256x256 -> exact [144,248] anchor!)
  2. `tele_streak_h_fx` (1f)
  3. `tele_streak_v_fx` (3f)
  4. `atk10_impact_fx` (6f — ground slam at y=248)
  5. `barrier_dome_fx` (5f — pure electric blue pixelated shield sphere, inner body cleanly replaced by dome lattice!)
  6. `mahasenko_hand_fx` (3f — palm flash centered at (144, 176))
  7. `mahasenko_beam_h_fx` (3f — 1->3 horizontal beam centered at y=176, muzzle left -> right +X)
  8. `mahasenko_beam_air_fx` (3f — 1->3 diagonal down-right +X beam centered around (144, 176))
  9. `mahasenko_impact_fx` (5f — 1->5 golden explosion centered at (144, 184))
 10. `antamina_stream_fx` (5f — 1->5 right-to-left source ordered! Muzzle anchored at x=24 shooting right +X at y=176)
 11. `antamina_impact_fx` (4f — 8-point yellow star explosion centered at (144, 176))
 12. `kentaima_wave_fx` (4f — cyan-white crescent blade wave facing +X, centered at (144, 168))
 13. `kentaima_impact_fx` (6f — cyan-blue ground explosion dome planted on boot_y=248!)
 14. `bukadai_vanish_fx` (1f — horizontal speed-vanish blur centered at (144, 192))
 15. `bukadai_sphere_fx` (4f — electric yellow lightning sphere centered at (144, 176))
 16. `bukadai_flash_fx` (1f — 6-spike yellow connector spark centered at (144, 176))
 17. `bukadai_impact_fx` (3f — golden dome + ground dust wave planted on boot_y=248!)
"""
from __future__ import annotations

import pathlib
import shutil
from typing import Tuple

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
P1_FX = ROOT / "work" / "characters" / "tapion" / "phase1" / "fx_slices"
P2_FX_RAW = ROOT / "work" / "characters" / "tapion" / "phase2" / "fx_slices"
OUT_FX = ROOT / "work" / "characters" / "tapion" / "phase2" / "fx_registered_288"

CW, CH = 288, 288
AX, AY = 144, 248


def crisp_quantize_fx(im: Image.Image, scale: float) -> Image.Image:
    """Scale FX to gameplay texel pitch via Nearest and enforce crisp binary pixel alpha (0/255)."""
    nw = max(8, min(276, int(round(im.width * scale))))
    nh = max(8, min(272, int(round(im.height * scale))))
    rim = im.resize((nw, nh), Image.Resampling.NEAREST)
    arr = np.array(rim, dtype=np.uint8)
    vis = arr[:, :, 3] >= 96
    arr[~vis] = [0, 0, 0, 0]
    arr[vis, 3] = 255
    return Image.fromarray(arr, mode="RGBA")


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


def make_pure_barrier_dome(raw_path: pathlib.Path, idx: int) -> Image.Image:
    """Extract pure blue/cyan/white barrier sphere and infill any central character pixels with crisp 2x2 blue dither."""
    src = Image.open(raw_path).convert("RGBA")
    # In `vòng tròn bảo vệ.png`, body height is ~110px (already ~1.0x gameplay scale!); cap max size at 268px.
    sc = min(1.0, 268.0 / max(1, src.width), 268.0 / max(1, src.height))
    rim = crisp_quantize_fx(src, sc)
    arr = np.array(rim, dtype=np.uint8)
    vis = arr[:, :, 3] > 0
    r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
    # Pure electric shield colors: strong blue/cyan (b > r + 20) or bright white sonic ribbon (r>185 & g>210 & b>225)
    is_shield = vis & (((b - r) > 18) | ((r > 185) & (g > 210) & (b > 225)))
    non_shield = vis & ~is_shield
    out = arr.copy()
    if idx <= 3:
        # Solid/dithered sphere phases 0..3: replace character pixels inside sphere with authentic 2x2 royal-blue lattice!
        yy, xx = np.indices(arr.shape[:2])
        checker = ((xx // 2 + yy // 2) % 2) == 0
        out[non_shield & checker] = [28, 96, 232, 255]
        out[non_shield & ~checker] = [56, 148, 252, 255]
    else:
        # Phase 4 (dissolving particle ring): simply make inner character pixels transparent!
        out[non_shield] = [0, 0, 0, 0]
    return place_on_288(Image.fromarray(out, mode="RGBA"), mode="center", ref_y=182)


def main() -> int:
    if OUT_FX.exists():
        shutil.rmtree(OUT_FX)
    OUT_FX.mkdir(parents=True, exist_ok=True)

    # 1. Pad Phase 1 256x256 FX slices by (+16, +24) -> exact [144, 248] anchor preservation!
    for p1_png in sorted(P1_FX.glob("*.png")):
        im = Image.open(p1_png).convert("RGBA")
        c = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        c.paste(im, (16, 24))
        c.save(OUT_FX / p1_png.name)

    # 2. Barrier dome 00..04 (pure body-free shield FX!)
    for i in range(5):
        make_pure_barrier_dome(P2_FX_RAW / f"barrier_dome_{i:02d}.png", i).save(OUT_FX / f"barrier_dome_{i:02d}.png")

    # 3. Mahasenko FX (source zoom ~2.2x -> scale 0.50x to match 125px hero!)
    for i in range(3):
        im = crisp_quantize_fx(Image.open(P2_FX_RAW / f"maha_hand_{i:02d}.png"), 0.44)
        place_on_288(im, mode="center", ref_y=176).save(OUT_FX / f"maha_hand_{i:02d}.png")
    for i in range(3):
        im = crisp_quantize_fx(Image.open(P2_FX_RAW / f"maha_beam_h_{i:02d}.png"), 0.62)
        place_on_288(im, mode="muzzle_left", ref_y=176, left_x=22).save(OUT_FX / f"maha_beam_h_{i:02d}.png")
    for i in range(3):
        im = crisp_quantize_fx(Image.open(P2_FX_RAW / f"maha_beam_air_{i:02d}.png"), 0.62)
        place_on_288(im, mode="center", ref_y=176).save(OUT_FX / f"maha_beam_air_{i:02d}.png")
    for i in range(5):
        im = crisp_quantize_fx(Image.open(P2_FX_RAW / f"maha_impact_{i:02d}.png"), 0.54)
        place_on_288(im, mode="center", ref_y=180).save(OUT_FX / f"maha_impact_{i:02d}.png")

    # 4. Antamina FX (1->5 stream anchored at muzzle_left x=20 so stream grows forward +X cleanly!)
    for i in range(5):
        im = crisp_quantize_fx(Image.open(P2_FX_RAW / f"anta_stream_{i:02d}.png"), 0.48)
        place_on_288(im, mode="muzzle_left", ref_y=176, left_x=20).save(OUT_FX / f"anta_stream_{i:02d}.png")
    for i in range(4):
        im = crisp_quantize_fx(Image.open(P2_FX_RAW / f"anta_impact_{i:02d}.png"), 0.52)
        place_on_288(im, mode="center", ref_y=176).save(OUT_FX / f"anta_impact_{i:02d}.png")

    # 5. Kentaima FX (wave centered, impact planted on ground y=248!)
    for i in range(4):
        im = crisp_quantize_fx(Image.open(P2_FX_RAW / f"kenta_wave_{i:02d}.png"), 0.52)
        place_on_288(im, mode="center", ref_y=168).save(OUT_FX / f"kenta_wave_{i:02d}.png")
    for i in range(6):
        im = crisp_quantize_fx(Image.open(P2_FX_RAW / f"kenta_impact_{i:02d}.png"), 0.72)
        place_on_288(im, mode="ground").save(OUT_FX / f"kenta_impact_{i:02d}.png")

    # 6. Bukadai FX (Bukadai.png is 1.0x native 125px scale; hitimpact budakai is ~1.8x -> 0.50x!)
    im_bv = crisp_quantize_fx(Image.open(P2_FX_RAW / "bukadai_vanish_00.png"), 1.0)
    place_on_288(im_bv, mode="center", ref_y=196).save(OUT_FX / "bukadai_vanish_00.png")
    for i in range(4):
        im = crisp_quantize_fx(Image.open(P2_FX_RAW / f"bukadai_sphere_{i:02d}.png"), 0.92)
        place_on_288(im, mode="center", ref_y=172).save(OUT_FX / f"bukadai_sphere_{i:02d}.png")
    im_bf = crisp_quantize_fx(Image.open(P2_FX_RAW / "bukadai_flash_00.png"), 0.75)
    place_on_288(im_bf, mode="center", ref_y=176).save(OUT_FX / "bukadai_flash_00.png")
    for i in range(3):
        im = crisp_quantize_fx(Image.open(P2_FX_RAW / f"bukadai_impact_{i:02d}.png"), 0.48)
        place_on_288(im, mode="ground").save(OUT_FX / f"bukadai_impact_{i:02d}.png")

    # Render 3-bg overview sheet of all 60 registered FX frames!
    all_fx = sorted(OUT_FX.glob("*.png"))
    cols = 10
    rows = (len(all_fx) + cols - 1) // cols
    cell = 144
    sheet = Image.new("RGBA", (cols * cell, rows * cell), (18, 22, 30, 255))
    draw = ImageDraw.Draw(sheet)
    for idx, fp in enumerate(all_fx):
        ri, ci = divmod(idx, cols)
        x0, y0 = ci * cell, ri * cell
        # Left half light bg, right half dark bg inside cell to verify both borders!
        bg = Image.new("RGBA", (cell, cell), (22, 26, 36, 255))
        bg.paste(Image.new("RGBA", (cell // 2, cell), (235, 238, 244, 255)), (0, 0))
        sub = Image.open(fp).resize((cell, cell), Image.Resampling.NEAREST)
        bg.alpha_composite(sub)
        sheet.paste(bg, (x0, y0))
        draw.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], outline=(70, 80, 100, 255))
        draw.text((x0 + 3, y0 + 2), fp.stem, fill=(255, 110, 40, 255))
    sheet.save(OUT_FX.parent / "qa_all_60_fx_light_dark.png")
    print(f"[FX REGISTERED] Total 288x288 FX frames: {len(all_fx)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
