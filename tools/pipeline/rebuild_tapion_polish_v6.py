#!/usr/bin/env python3
"""
DR7-Studio — Tapion Polish v6 Asset Builder:
1. Expands `antamina_charge_orb_fx` to 6 frames (`#0..#5` @ 80ms/frame, centered at `(144,176)`):
   - `#0`: `tapion/1.png` (Exact Sheet Fidelity — initial dot & gather rays)
   - `#1`: `tapion/2.png` (Exact Sheet Fidelity — thin double forming rings)
   - `#2`: `tapion/3.png` (Exact Sheet Fidelity — tight condensed ring + sharp spears, loop beat 1)
   - `#3`: NEW intermediate build-up bridge (`3.png -> 4.png` — expanding double ring + thickening rays, loop beat 2)
   - `#4`: `tapion/4.png` (Exact Sheet Fidelity — full heavy double rings + thick lance spears, loop beat 3)
   - `#5`: NEW overcharge compression-return frame (`4.png -> 3.png` — rotated high-energy shock ring + crackling rays, loop beat 4)
   All 6 frames use 100% pure source yellow/white palette and 100% binary 0/255 alpha!
2. Scales `mahasenko_hand_fx` (`maha_hand_00..02`) down by another 30% (`0.70x` of polish_v5 = `0.49x` of 100% original)
   directly in 1 crisp pass from high-res `work/characters/tapion/phase2/fx_slices/maha_hand_*.png`
   so Tapion's outstretched palm stays 100% visible with clear separation matching `image copy.png`!
3. Renders 3-background QA sheets (including a live hand-clearance composite on `maha_gnd_02.png`!).
"""
from __future__ import annotations

import math
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import rebuild_tapion_antamina_v4 as v4  # noqa: E402
import rebuild_tapion_polish_v5 as v5  # noqa: E402
import sharpen_tapion_9fx_v2 as sh9  # noqa: E402

TAP_DIR = ROOT / "tapion"
RAW_DIR = ROOT / "review" / "tapion_demo" / "source" / "raw_frames"
P2_FX_RAW = ROOT / "work" / "characters" / "tapion" / "phase2" / "fx_slices"
V5_FX_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v5" / "fx_registered_288"

OUT_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v6"
FX_REG_DIR = OUT_DIR / "fx_registered_288"
QA_DIR = OUT_DIR / "qa"

CW, CH = 288, 288
FX_CX, FX_CY = 144, 176
MAHA_HAND_SCALE_V6 = 0.44 * 0.70 * 0.70  # -30% again from polish_v5 (0.2156)

# Pure source yellow-white palette sampled directly from tapion/1..4.png!
SRC_YELLOW_HI = (245, 250, 88, 255)
SRC_YELLOW_EDGE = (238, 244, 74, 255)
SRC_WHITE = (255, 255, 255, 255)


def _draw_tapered_spear(dr: ImageDraw.ImageDraw, cx: float, cy: float, ang_deg: float, r0: float, r1: float, w0: float, w1: float, col: tuple[int, int, int, int]) -> None:
    rad = math.radians(ang_deg)
    ca, sa = math.cos(rad), math.sin(rad)
    px, py = -sa, ca
    pts = [
        (cx + ca * r0 + px * (w0 * 0.5), cy + sa * r0 + py * (w0 * 0.5)),
        (cx + ca * r1 + px * (w1 * 0.5), cy + sa * r1 + py * (w1 * 0.5)),
        (cx + ca * r1 - px * (w1 * 0.5), cy + sa * r1 - py * (w1 * 0.5)),
        (cx + ca * r0 - px * (w0 * 0.5), cy + sa * r0 - py * (w0 * 0.5)),
    ]
    dr.polygon(pts, fill=col)


def _draw_ring_arcs(dr: ImageDraw.ImageDraw, cx: float, cy: float, radius: float, width: int, gap_angles: list[tuple[float, float]], col: tuple[int, int, int, int]) -> None:
    """Draw crisp pixel concentric ring with organic anime break notches."""
    # Draw full ring on temp mask then punch clean angular notches
    tmp = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    tdr = ImageDraw.Draw(tmp)
    r_i = int(round(radius))
    tdr.ellipse([cx - r_i, cy - r_i, cx + r_i, cy + r_i], outline=col, width=width)
    tarr = np.array(tmp, dtype=np.uint8)
    yy, xx = np.indices((CH, CW))
    ang = np.degrees(np.arctan2(yy - cy, xx - cx)) % 360.0
    for a0, a1 in gap_angles:
        if a0 <= a1:
            mask = (ang >= a0) & (ang <= a1)
        else:
            mask = (ang >= a0) | (ang <= a1)
        tarr[mask] = 0
    # Paste non-zero pixels onto target
    ys, xs = np.where(tarr[:, :, 3] > 0)
    for y, x in zip(ys.tolist(), xs.tolist()):
        dr.point((x, y), fill=col)


def make_orb_bridge_3_to_4(raw_orb3: Image.Image, core3: tuple[float, float], raw_orb4: Image.Image, core4: tuple[float, float]) -> Image.Image:
    """
    NEW Frame #3 (loop beat 2: bridges `tapion/3.png` -> `tapion/4.png`):
    - Starts from `tapion/3.png` slightly expanded (`0.38x`) rotated subtly (`+11°`) so rays visibly surge outward
    - Adds an emerging mid-outer energy ring (`r=28..31`, crisp broken arcs) between #2's tight ring (`r=14`) and #4's full outer ring (`r=34`)
    - Thickens the main radial lances & enlarges the blazing white center star (`r=7`) halfway to #4!
    """
    # Base from authentic tapion/3.png scaled up slightly + crisp rotation
    base3 = v4.scale_orb_to_canvas(raw_orb3, core3, 0.37, FX_CX, FX_CY)
    # Rotate around (FX_CX, FX_CY) with NEAREST for authentic 1px crispness
    rot3 = base3.rotate(-11.0, resample=Image.Resampling.NEAREST, center=(FX_CX, FX_CY))
    arr = np.array(rot3, dtype=np.uint8)
    arr[arr[:, :, 3] > 0, 3] = 255
    canvas = Image.fromarray(arr, mode="RGBA")
    dr = ImageDraw.Draw(canvas)

    # Emerging double concentric rings bridging #2 (single r=14) -> #4 (heavy r=17 & r=34)
    _draw_ring_arcs(dr, FX_CX, FX_CY, 16.0, 2, [(38, 52), (165, 180), (288, 302)], SRC_YELLOW_HI)
    _draw_ring_arcs(dr, FX_CX, FX_CY, 30.0, 2, [(12, 34), (105, 130), (195, 224), (275, 298), (332, 350)], SRC_YELLOW_HI)

    # Dynamic thickening spear rays surging outward toward #4's bold diagonal lances
    spears = [
        (-74, 12, 54, 4.5, 1.8),   # Upper-right major lance emerging
        (164, 12, 48, 3.8, 1.5),   # Lower-left major lance emerging
        (-28, 14, 46, 3.2, 1.2),   # Right-upper spear
        (118, 15, 44, 2.8, 1.2),   # Lower-left minor spear
        (16, 15, 42, 2.6, 1.2),    # Right horizontal spark
        (-136, 14, 38, 2.4, 1.0),  # Upper-left spark
        (62, 16, 36, 2.2, 1.0),    # Lower-right spark
    ]
    for ang_d, r0, r1, w0, w1 in spears:
        _draw_tapered_spear(dr, FX_CX, FX_CY, ang_d, r0, r1, w0, w1, SRC_YELLOW_HI)

    # Enlarging spiky white core halfway between #2 (small white star) and #4 (full white disk)
    for ang_d in range(0, 360, 45):
        _draw_tapered_spear(dr, FX_CX, FX_CY, ang_d + 15, 2, 11, 3.2, 1.0, SRC_YELLOW_HI)
    dr.ellipse([FX_CX - 6, FX_CY - 6, FX_CX + 6, FX_CY + 6], fill=SRC_WHITE)

    final_arr = np.array(canvas, dtype=np.uint8)
    final_arr[final_arr[:, :, 3] > 0, 3] = 255
    return Image.fromarray(final_arr, mode="RGBA")


def make_orb_overcharge_4_to_3(raw_orb4: Image.Image, core4: tuple[float, float]) -> Image.Image:
    """
    NEW Frame #5 (loop beat 4: overcharge-compress return bridging `tapion/4.png` -> `tapion/3.png`):
    - Compresses `tapion/4.png` (`0.29x` vs `0.34x`) and rotates `+22°` so the double rings visibly spin & snap inward
    - Adds crackling outer discharge needles & tight bright white star core so looping `#2 -> #3 -> #4 -> #5 -> #2`
      feels like a live, surging, rotating DBZ Ki sphere building pressure to explode!
    """
    comp4 = v4.scale_orb_to_canvas(raw_orb4, core4, 0.28, FX_CX, FX_CY)
    rot4 = comp4.rotate(24.0, resample=Image.Resampling.NEAREST, center=(FX_CX, FX_CY))
    arr = np.array(rot4, dtype=np.uint8)
    # Carve clean dynamic energy cracks through the outer ring so it feels spinning/crackling instead of a static copy of #4
    yy, xx = np.indices((CH, CW))
    dist = np.hypot(xx - FX_CX, yy - FX_CY)
    ang = np.degrees(np.arctan2(yy - FX_CY, xx - FX_CX)) % 360.0
    crack = (dist >= 22.0) & (dist <= 34.0) & (((ang + 15.0) % 60.0) > 36.0)
    arr[crack] = 0
    arr[arr[:, :, 3] > 0, 3] = 255

    canvas = Image.fromarray(arr, mode="RGBA")
    dr = ImageDraw.Draw(canvas)

    # Crisp high-energy outer crackling rays rotating into #2 (`3.png`)'s angles!
    crackles = [
        (-95, 18, 56, 3.8, 1.4),
        (-36, 18, 54, 3.6, 1.2),
        (145, 16, 50, 3.2, 1.2),
        (78, 20, 44, 2.4, 1.0),
        (184, 22, 46, 2.0, 1.0),
        (-148, 20, 40, 2.2, 1.0),
        (28, 22, 42, 2.0, 1.0),
    ]
    for ang_d, r0, r1, w0, w1 in crackles:
        _draw_tapered_spear(dr, FX_CX, FX_CY, ang_d, r0, r1, w0, w1, SRC_YELLOW_HI)

    # Tight pulsing white hot star core snapping into #2's tight core
    for ang_d in range(0, 360, 60):
        _draw_tapered_spear(dr, FX_CX, FX_CY, ang_d - 10, 2, 10, 2.8, 1.0, SRC_WHITE)
    dr.ellipse([FX_CX - 5, FX_CY - 5, FX_CX + 5, FX_CY + 5], fill=SRC_WHITE)

    final_arr = np.array(canvas, dtype=np.uint8)
    final_arr[final_arr[:, :, 3] > 0, 3] = 255
    return Image.fromarray(final_arr, mode="RGBA")


def build_antamina_charge_orb_6f() -> list[Image.Image]:
    """Build all 6 frames of `antamina_charge_orb_fx` (#0..#1 intro -> #2,#3,#4,#5 seamless pulsing loop @ 80ms)."""
    orb_scales = {1: 0.33, 2: 0.34, 3: 0.35, 4: 0.34}
    raw_orbs: dict[int, tuple[Image.Image, tuple[float, float]]] = {}
    for idx in (1, 2, 3, 4):
        raw_orbs[idx] = v4.extract_orb_from_source(TAP_DIR / f"{idx}.png", idx)

    f0 = v4.scale_orb_to_canvas(raw_orbs[1][0], raw_orbs[1][1], orb_scales[1], FX_CX, FX_CY)
    f1 = v4.scale_orb_to_canvas(raw_orbs[2][0], raw_orbs[2][1], orb_scales[2], FX_CX, FX_CY)
    f2 = v4.scale_orb_to_canvas(raw_orbs[3][0], raw_orbs[3][1], orb_scales[3], FX_CX, FX_CY)
    f3 = make_orb_bridge_3_to_4(raw_orbs[3][0], raw_orbs[3][1], raw_orbs[4][0], raw_orbs[4][1])
    f4 = v4.scale_orb_to_canvas(raw_orbs[4][0], raw_orbs[4][1], orb_scales[4], FX_CX, FX_CY)
    f5 = make_orb_overcharge_4_to_3(raw_orbs[4][0], raw_orbs[4][1])

    frames = [f0, f1, f2, f3, f4, f5]
    for i, im in enumerate(frames):
        arr = np.array(im, dtype=np.uint8)
        arr[arr[:, :, 3] > 0, 3] = 255
        im = Image.fromarray(arr, mode="RGBA")
        frames[i] = im
        out_p = FX_REG_DIR / f"antamina_charge_orb_{i:02d}.png"
        im.save(out_p)
        ys, xs = np.where(arr[:, :, 3] > 0)
        semi = int(((arr[:, :, 3] > 0) & (arr[:, :, 3] < 255)).sum())
        print(
            f"[ORB 6F #{i}] bbox=({xs.min()},{ys.min()})..({xs.max()},{ys.max()}) "
            f"size={xs.max() - xs.min() + 1}x{ys.max() - ys.min() + 1} px={len(xs)} semi_alpha={semi}"
        )
    return frames


def scale_mahasenko_hand_fx_v6() -> list[tuple[str, Image.Image, Image.Image]]:
    """Reduce `mahasenko_hand_fx` (`maha_hand_00..02`) by another 30% (`0.70x` of polish_v5) crisp 1-pass from raw slices."""
    rows: list[tuple[str, Image.Image, Image.Image]] = []
    for i in range(3):
        fid = f"maha_hand_{i:02d}"
        before_im = Image.open(V5_FX_DIR / f"{fid}.png").convert("RGBA")
        ba = np.array(before_im)
        bys, bxs = np.where(ba[:, :, 3] > 0)
        bw, bh = int(bxs.max() - bxs.min() + 1), int(bys.max() - bys.min() + 1)

        crisp = sh9.deblur_and_quantize_fx(
            P2_FX_RAW / f"{fid}.png",
            MAHA_HAND_SCALE_V6,
            sh9.PAL_YELLOW_BEAM,
            bg_trim_lum=62.0,
            unsharp_pct=220,
            unsharp_rad=1.8,
            add_dark_outline=True,
            outline_rgb=(112, 50, 12),
            erode_blur_rim=1,
        )
        reg = sh9.place_on_288(crisp, mode="center", ref_y=176, left_x=20)
        reg.save(FX_REG_DIR / f"{fid}.png")
        aa = np.array(reg)
        ays, axs = np.where(aa[:, :, 3] > 0)
        aw, ah = int(axs.max() - axs.min() + 1), int(ays.max() - ays.min() + 1)
        sob, uc = sh9.measure_sharpness(aa)
        print(
            f"[MAHA HAND -30% v6] {fid}: {bw:2d}x{bh:2d} -> {aw:2d}x{ah:2d} "
            f"({aw / max(1, bw) * 100:.1f}% x {ah / max(1, bh) * 100:.1f}%) Sobel={sob:.1f} colors={uc}"
        )
        rows.append((fid, before_im, reg))
    return rows


def main() -> int:
    FX_REG_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    orb_frames = build_antamina_charge_orb_6f()
    maha_rows = scale_mahasenko_hand_fx_v6()

    # 1. QA 3-bg sheet for 6-frame `antamina_charge_orb_fx` (#0..#1 intro, #2..#5 loop @ 80ms)
    labels = [
        "#0 intro (1.png)",
        "#1 intro (2.png)",
        "#2 LOOP (3.png)",
        "#3 LOOP (bridge)",
        "#4 LOOP (4.png)",
        "#5 LOOP (return)",
    ]
    v5.render_3bg_board(
        list(zip(labels, orb_frames)),
        (54, 86, 234, 266),
        QA_DIR / "qa_antamina_charge_orb_6f_3bg.png",
    )

    # 2. QA composite verifying `mahasenko_hand_fx` (-30% v6) sits CLEARLY IN FRONT of Tapion's outstretched hand!
    # Runtime spawn formula:
    #   hand_pos = anchor (144, 248) + MAHASENKO_GND_HAND_OFFSET (92, -64) = (236, 184)
    #   fx_center = hand_pos + aim_dir * 32 = (268, 184)  [note: maha_hand_00 is ~60px wide -> left edge at 268-30 = 238, +6px clear of fingertips x=232!]
    body_gnd = Image.open(RAW_DIR / "maha_gnd_02.png").convert("RGBA")
    # Build 360x288 preview canvas so right-side burst isn't clipped by 288 border during QA visualization
    comp_items: list[tuple[str, Image.Image]] = []
    for i, (fid, old_im, new_im) in enumerate(maha_rows):
        # OLD v5 position (centered at (240, 187) = overlapping hand!)
        c_old = Image.new("RGBA", (360, 288), (0, 0, 0, 0))
        c_old.alpha_composite(body_gnd, (0, 0))
        c_old.alpha_composite(old_im, (240 - 144, 187 - 176))
        # NEW v6 position: -30% size & placed cleanly ahead at center=(266, 184) (left edge = 236 > fingertips 232!)
        c_new = Image.new("RGBA", (360, 288), (0, 0, 0, 0))
        c_new.alpha_composite(body_gnd, (0, 0))
        c_new.alpha_composite(new_im, (266 - 144, 184 - 176))
        comp_items.append((f"OLD v5 #{i}", c_old))
        comp_items.append((f"NEW v6 -30% #{i}", c_new))

    v5.render_3bg_board(
        comp_items,
        (96, 118, 326, 256),
        QA_DIR / "qa_mahasenko_hand_clearance_3bg.png",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
