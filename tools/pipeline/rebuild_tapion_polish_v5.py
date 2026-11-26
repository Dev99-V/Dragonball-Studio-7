#!/usr/bin/env python3
"""
DR7-Studio — Tapion Polish v5 Asset Builder:
1. Detaches `tapion/1.png`, `2.png`, `3.png`, `4.png` (Exact Sheet Fidelity, 0 AI redraw,
   0 bg pockets, 0 cyan speck, pure yellow-white source palette) into 4 standalone centered
   FX frames `antamina_charge_orb_00..03.png` at `(144, 176)` on 288x288 for independent
   60ms looping (`antamina_charge_orb_fx`) in `tapion_skills_fx.tres`.
2. Scales `mahasenko_hand_fx` (`maha_hand_00..02`), `mahasenko_beam_h_fx` (`maha_beam_h_00..02`),
   and `mahasenko_beam_air_fx` (`maha_beam_air_00..02`) down by 30% (`0.70x`) directly in 1 pass
   from high-res raw slices `work/characters/tapion/phase2/fx_slices/` (preserving 100%-scale
   backups in `work/characters/tapion/polish_v2/maha_fx_100pct_backup/`).
3. Cleans `antamina_charge #3` (`anta_chg_03`) & `antamina_rings #0..#2` (`anta_rng_00..02`)
   to pure orb-free outstretched-palm body poses (`anta_fire_00..02`, rock-solid `stance_mid=144.0`,
   `boot_y=247`), drops the old flipped-pose `#3` (`anta_rng_03`), and generates 3 consistent
   white/yellow blast-light-reflected firing frames (`anta_lit_00..02`, exact same silhouette &
   stance as `anta_fire_00..02` with ZERO flipping!) plus `anta_rng_03 = anta_lit_01` bridge.
4. Renders 3-background QA filmstrips for visual inspection before packaging!
"""
from __future__ import annotations

import math
import pathlib
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import rebuild_tapion_antamina_v4 as v4  # noqa: E402
import sharpen_tapion_9fx_v2 as sh9  # noqa: E402

TAP_DIR = ROOT / "tapion"
RAW_DIR = ROOT / "review" / "tapion_demo" / "source" / "raw_frames"
P2_FX_RAW = ROOT / "work" / "characters" / "tapion" / "phase2" / "fx_slices"
V2_FX_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v2" / "fx_registered_288"
MAHA_BKP_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v2" / "maha_fx_100pct_backup"

OUT_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v5"
BODY_REG_DIR = OUT_DIR / "registered_288"
FX_REG_DIR = OUT_DIR / "fx_registered_288"
QA_DIR = OUT_DIR / "qa"

CW, CH = 288, 288
FX_CX, FX_CY = 144, 176
ORB_PALM_CX, ORB_PALM_CY = 217, 186
MAHA_SCALE_MUL = 0.70  # -30% overall size


def build_antamina_charge_orb_fx() -> list[Image.Image]:
    """Extract tapion/1..4.png cleanly and center at (144, 176) on 288x288 for independent 60ms looping."""
    orb_scales = {1: 0.33, 2: 0.34, 3: 0.35, 4: 0.34}
    orb_imgs: list[Image.Image] = []
    for idx in (1, 2, 3, 4):
        raw_orb, core_c = v4.extract_orb_from_source(TAP_DIR / f"{idx}.png", idx)
        centered = v4.scale_orb_to_canvas(raw_orb, core_c, orb_scales[idx], FX_CX, FX_CY)
        arr = np.array(centered, dtype=np.uint8)
        # Guarantee 100% binary 0/255 alpha
        arr[arr[:, :, 3] > 0, 3] = 255
        centered = Image.fromarray(arr, mode="RGBA")
        out_p = FX_REG_DIR / f"antamina_charge_orb_{idx - 1:02d}.png"
        centered.save(out_p)
        ys, xs = np.where(arr[:, :, 3] > 0)
        print(
            f"[ORB FX #{idx - 1}] src=tapion/{idx}.png bbox=({xs.min()},{ys.min()})..({xs.max()},{ys.max()}) "
            f"size={xs.max() - xs.min() + 1}x{ys.max() - ys.min() + 1} px={len(xs)}"
        )
        orb_imgs.append(centered)
    return orb_imgs


def apply_directional_blast_light(body_im: Image.Image, light_xy: tuple[float, float] = (217.0, 186.0)) -> Image.Image:
    """
    Create a crisp white/yellow directional light-reflected firing pose directly from Tapion's
    exact `anta_fire_00..02` body pixel art:
      - Preserves 100% identical silhouette, hair sweep, scarf flow, sword hilt, boots, `stance_mid`,
        and crisp 1px dark exterior outline on non-lit edges (ZERO pose flipping!).
      - Computes real line-of-sight directional illumination from the blazing Antamina blast at
        `light_xy = (217, 186)` right ahead of his outstretched palm:
        * Front-facing surfaces directly seeing the blast (1–3px deep): crisp pure white
          `(255, 255, 248)` & hot pale lemon-gold `(255, 250, 146)` highlights.
        * Mid-facing bounce light (3–8px inward from right-facing silhouette edges): vibrant golden-yellow
          key-light lift `(255, 234, 88)` preserving cel-shading readability.
        * Back/far-left shadow side: subtle +12% shadow contrast so the blast reflection POPS like DBZ!
    """
    arr = np.array(body_im.convert("RGBA"), dtype=np.uint8)
    out = arr.copy()
    vis = arr[:, :, 3] > 0
    h, w = vis.shape
    yy, xx = np.indices((h, w))

    # 1. Identify crisp 1px outer dark outline vs interior pixels
    er4 = ndimage.binary_erosion(vis, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    outer_border = vis & ~er4
    interior = vis & er4

    r = arr[:, :, 0].astype(np.float32)
    g = arr[:, :, 1].astype(np.float32)
    b = arr[:, :, 2].astype(np.float32)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    is_dark_line = vis & (lum < 48.0)

    # 2. Compute horizontal depth from the right-facing edge of every scanline & local right-exposed segments!
    #    For every row y, find pixels that have transparent space within 1..8 px to their right (+X),
    #    meaning they directly face the energy blast on the right side!
    dist_to_right_open = np.full((h, w), 99, dtype=np.int16)
    for step in range(1, 13):
        shifted_empty = np.zeros_like(vis)
        shifted_empty[:, :-step] = ~vis[:, step:]
        shifted_empty[:, -step:] = True
        newly_hit = vis & shifted_empty & (dist_to_right_open == 99)
        dist_to_right_open[newly_hit] = step

    # Also check diagonal rays toward the light center (217, 186) so top of arm / front of face / front knee
    # catch realistic directional light while the far-back cape/left leg stays shadowed!
    lx, ly = light_xy
    dx_l = lx - xx.astype(np.float32)
    dy_l = ly - yy.astype(np.float32)
    dist_l = np.hypot(dx_l, dy_l)

    # Ray-cast 10 samples toward light center to measure direct line-of-sight exposure (excluding thin interior holes)
    ray_blocked = np.zeros((h, w), dtype=np.float32)
    inv_d = 1.0 / np.maximum(dist_l, 1.0)
    ux = dx_l * inv_d
    uy = dy_l * inv_d
    for s_px in (3.0, 6.0, 10.0, 15.0, 21.0, 28.0, 36.0, 46.0):
        sx = np.clip(np.round(xx + ux * s_px).astype(int), 0, w - 1)
        sy = np.clip(np.round(yy + uy * s_px).astype(int), 0, h - 1)
        # Only count occlusion while sample hasn't passed the light center itself
        before_light = s_px < (dist_l - 2.0)
        ray_blocked += (vis[sy, sx] & before_light).astype(np.float32)

    # Directly exposed to blast if almost unobstructed along ray toward (217, 186)
    exposed = vis & (ray_blocked <= 1.0) & (xx >= 118)
    semi_exposed = vis & (ray_blocked <= 2.0) & (xx >= 122)

    # Zone masks for clean DBZ cel light-reflection bands:
    # (a) Blazing white-yellow rim: 1..3px from right-exposed edge on front half of Tapion (arm, face, front hair, chest, front boot)
    hot_white_rim = (
        interior
        & ~is_dark_line
        & (
            (exposed & (dist_to_right_open <= 3))
            | (vis & (xx >= 184) & (yy >= 166) & (yy <= 206) & (dist_to_right_open <= 5))  # palm & wrist blaze!
        )
    )
    # Also illuminate the front-most right-facing interior spikes of his orange hair & front vest/face rim cleanly
    hot_gold_band = (
        interior
        & ~is_dark_line
        & ~hot_white_rim
        & (
            (exposed & (dist_to_right_open <= 7))
            | (semi_exposed & (dist_to_right_open <= 4))
            | ((xx >= 166) & (yy >= 170) & (yy <= 206) & (dist_l <= 58.0))  # outstretched forearm + cuff glow
        )
    )
    # Soft golden bounce on adjacent front-facing pixels (hair highlight, face cheek, front scarf/vest, front knee)
    warm_bounce = (
        interior
        & ~is_dark_line
        & ~hot_white_rim
        & ~hot_gold_band
        & (semi_exposed & (dist_to_right_open <= 11) & (xx >= 134))
    )
    # Subtle shadow contrast on the far back side (-X) so the blast lighting reads crisply at 1x gameplay zoom!
    back_shadow = interior & ~is_dark_line & (ray_blocked >= 5.0) & (xx <= 136)

    # Apply crisp cel-palette light-reflection colors (pure DBZ white + lemon-yellow + warm gold, ZERO muddy grays!)
    # 1. Back shadow: slight contrast deepen (-14%)
    if back_shadow.any():
        out[back_shadow, 0] = np.clip(r[back_shadow] * 0.86, 0, 255).astype(np.uint8)
        out[back_shadow, 1] = np.clip(g[back_shadow] * 0.85, 0, 255).astype(np.uint8)
        out[back_shadow, 2] = np.clip(b[back_shadow] * 0.88, 0, 255).astype(np.uint8)

    # 2. Warm golden bounce (+38% toward vivid warm gold [255, 232, 92])
    if warm_bounce.any():
        t = 0.36
        out[warm_bounce, 0] = np.clip(r[warm_bounce] * (1.0 - t) + 255.0 * t, 0, 255).astype(np.uint8)
        out[warm_bounce, 1] = np.clip(g[warm_bounce] * (1.0 - t) + 234.0 * t, 0, 255).astype(np.uint8)
        out[warm_bounce, 2] = np.clip(b[warm_bounce] * (1.0 - t) + 96.0 * t, 0, 255).astype(np.uint8)

    # 3. Hot golden key-light band (+72% toward bright lemon-gold [255, 248, 128])
    if hot_gold_band.any():
        t = 0.72
        out[hot_gold_band, 0] = np.clip(r[hot_gold_band] * (1.0 - t) + 255.0 * t, 0, 255).astype(np.uint8)
        out[hot_gold_band, 1] = np.clip(g[hot_gold_band] * (1.0 - t) + 248.0 * t, 0, 255).astype(np.uint8)
        out[hot_gold_band, 2] = np.clip(b[hot_gold_band] * (1.0 - t) + 132.0 * t, 0, 255).astype(np.uint8)

    # 4. Blazing white-gold specular edge closest to the Antamina beam
    if hot_white_rim.any():
        # Closest pixels (palm & very front edge) snap to crisp white-cream [255, 255, 232]
        very_hot = hot_white_rim & ((dist_to_right_open <= 2) | (xx >= 186))
        mid_hot = hot_white_rim & ~very_hot
        if very_hot.any():
            out[very_hot, 0] = 255
            out[very_hot, 1] = 255
            out[very_hot, 2] = 236
        if mid_hot.any():
            out[mid_hot, 0] = 255
            out[mid_hot, 1] = 252
            out[mid_hot, 2] = 164

    # 5. Keep dark exterior outline intact EXCEPT the very brightest palm fingertips touching the blast
    #    where a subtle warm-gold rim outline makes the palm glow cleanly without hurting Master QC border_dark_frac!
    palm_tip_border = outer_border & (xx >= 191) & (yy >= 172) & (yy <= 200) & (dist_to_right_open <= 1)
    if palm_tip_border.any():
        out[palm_tip_border, 0] = 255
        out[palm_tip_border, 1] = 244
        out[palm_tip_border, 2] = 128

    out[vis, 3] = 255
    out[~vis] = 0
    return Image.fromarray(out, mode="RGBA")


def build_antamina_clean_and_lit_body_frames() -> tuple[list[Image.Image], list[Image.Image]]:
    """
    Use Tapion's clean outstretched-palm stance (`anta_fire_00..02`, rock-solid stance_mid=144.0, boot_y=247)
    for orb-free `anta_chg_03`, `anta_rng_00..02`, and build 3 matching white/yellow light-reflected firing
    frames `anta_lit_00..02` + `anta_rng_03 = anta_lit_01` (ZERO pose flipping!).
    """
    body_f = [Image.open(RAW_DIR / f"anta_fire_{i:02d}.png").convert("RGBA") for i in range(3)]
    lit_f = [apply_directional_blast_light(im) for im in body_f]

    # Save orb-free clean outstretched frames
    body_f[0].save(BODY_REG_DIR / "anta_chg_03.png")
    body_f[0].save(BODY_REG_DIR / "anta_rng_00.png")
    body_f[1].save(BODY_REG_DIR / "anta_rng_01.png")
    body_f[2].save(BODY_REG_DIR / "anta_rng_02.png")
    # Drop old flipped anta_rng_03 -> replace with matching pose #1 light-reflected bridge!
    lit_f[1].save(BODY_REG_DIR / "anta_rng_03.png")

    for i in range(3):
        lit_f[i].save(BODY_REG_DIR / f"anta_lit_{i:02d}.png")
        a = np.array(lit_f[i])
        vis = a[:, :, 3] > 0
        ys, xs = np.where(vis)
        by1 = int(ys.max())
        fxs = np.where(vis[max(0, by1 - 7) : by1 + 1, :])[1]
        smid = 0.5 * (int(fxs.min()) + int(fxs.max()))
        print(f"[ANTA LIT #{i}] bbox=({xs.min()},{ys.min()})..({xs.max()},{ys.max()}) boot_y={by1} smid={smid:.1f}")

    # Preserve clean 2-frame recovery (`anta_end_00`, `anta_end_01`)
    Image.open(RAW_DIR / "anta_chg_02.png").convert("RGBA").save(BODY_REG_DIR / "anta_end_00.png")
    Image.open(RAW_DIR / "idle_combat_00.png").convert("RGBA").save(BODY_REG_DIR / "anta_end_01.png")
    return body_f, lit_f


def scale_mahasenko_fx_70pct() -> list[tuple[str, Image.Image, Image.Image]]:
    """
    Reduce `mahasenko_hand_fx`, `mahasenko_beam_h_fx`, and `mahasenko_beam_air_fx` overall size by 30% (`0.70x`)
    directly from high-res `phase2/fx_slices` in 1 crisp cel-quantized pass (preserving 100%-scale backups!).
    """
    MAHA_BKP_DIR.mkdir(parents=True, exist_ok=True)
    specs = [
        *[(f"maha_hand_{i:02d}", 0.44 * MAHA_SCALE_MUL, sh9.PAL_YELLOW_BEAM, "center", 176, 20, 62.0, 220, 1.8, True, (112, 50, 12), 1) for i in range(3)],
        *[(f"maha_beam_h_{i:02d}", 0.62 * MAHA_SCALE_MUL, sh9.PAL_YELLOW_BEAM, "muzzle_left", 176, 20, 60.0, 220, 1.8, True, (112, 50, 12), 1) for i in range(3)],
        *[(f"maha_beam_air_{i:02d}", 0.62 * MAHA_SCALE_MUL, sh9.PAL_YELLOW_BEAM, "center", 176, 20, 60.0, 220, 1.8, True, (112, 50, 12), 1) for i in range(3)],
    ]
    qa_rows: list[tuple[str, Image.Image, Image.Image]] = []
    for fid, sc, pal, mode, ry, lx, bg_lum, upct, urad, do_out, out_rgb, erode_n in specs:
        live_v2 = V2_FX_DIR / f"{fid}.png"
        bkp = MAHA_BKP_DIR / f"{fid}.png"
        if not bkp.is_file() and live_v2.is_file():
            shutil.copy2(live_v2, bkp)
        before_im = Image.open(bkp).convert("RGBA")
        ba = np.array(before_im)
        bys, bxs = np.where(ba[:, :, 3] > 0)
        bw, bh = int(bxs.max() - bxs.min() + 1), int(bys.max() - bys.min() + 1)

        raw_p = P2_FX_RAW / f"{fid}.png"
        crisp = sh9.deblur_and_quantize_fx(
            raw_p,
            sc,
            pal,
            bg_trim_lum=bg_lum,
            unsharp_pct=upct,
            unsharp_rad=urad,
            add_dark_outline=do_out,
            outline_rgb=out_rgb,
            erode_blur_rim=erode_n,
        )
        reg = sh9.place_on_288(crisp, mode=mode, ref_y=ry, left_x=lx)
        out_p = FX_REG_DIR / f"{fid}.png"
        reg.save(out_p)
        aa = np.array(reg)
        ays, axs = np.where(aa[:, :, 3] > 0)
        aw, ah = int(axs.max() - axs.min() + 1), int(ays.max() - ays.min() + 1)
        sob, uc = sh9.measure_sharpness(aa)
        print(
            f"[MAHA -30%] {fid:16s}: {bw:3d}x{bh:3d} -> {aw:3d}x{ah:3d} "
            f"({aw / max(1, bw) * 100:.1f}% x {ah / max(1, bh) * 100:.1f}%) Sobel={sob:.1f} colors={uc}"
        )
        if fid == "maha_beam_air_00":
            # Measure PCA principal axis angle to verify MAHA_BEAM_AIR_BASE_RAD
            pts = np.stack([axs - axs.mean(), ays - ays.mean()], axis=1).astype(np.float64)
            _, _, vt = np.linalg.svd(pts, full_matrices=False)
            vx, vy = vt[0]
            if vx < 0:
                vx, vy = -vx, -vy
            ang = math.atan2(vy, vx)
            print(f"  [PCA maha_beam_air_00] rad={ang:.4f} deg={math.degrees(ang):.2f}")
        qa_rows.append((fid, before_im, reg))
    return qa_rows


def render_3bg_board(items: list[tuple[str, Image.Image]], crop_box: tuple[int, int, int, int], out_path: pathlib.Path) -> None:
    cw, ch = crop_box[2] - crop_box[0], crop_box[3] - crop_box[1]
    bgs = [
        ("DARK", (24, 28, 40, 255)),
        ("LIGHT", (236, 240, 246, 255)),
        ("CHECK", None),
    ]
    board = Image.new("RGBA", (len(items) * cw, len(bgs) * (ch + 20)), (16, 18, 26, 255))
    dr = ImageDraw.Draw(board)
    yy, xx = np.indices((ch, cw))
    chk = ((xx // 10) + (yy // 10)) % 2 == 0
    for ri, (bg_lbl, bg_col) in enumerate(bgs):
        for ci, (flbl, im) in enumerate(items):
            if bg_col is None:
                bga = np.zeros((ch, cw, 4), dtype=np.uint8)
                bga[chk] = [190, 196, 206, 255]
                bga[~chk] = [140, 146, 158, 255]
                tile = Image.fromarray(bga, "RGBA")
            else:
                tile = Image.new("RGBA", (cw, ch), bg_col)
            tile.alpha_composite(im.crop(crop_box))
            x0, y0 = ci * cw, ri * (ch + 20)
            board.paste(tile, (x0, y0 + 20))
            dr.rectangle([x0, y0, x0 + cw - 1, y0 + ch + 19], outline=(80, 92, 112, 255))
            dr.text((x0 + 4, y0 + 4), f"{bg_lbl} {flbl}", fill=(255, 224, 110, 255))
    board.save(out_path)
    print(f"[QA SAVED] {out_path}")


def main() -> int:
    BODY_REG_DIR.mkdir(parents=True, exist_ok=True)
    FX_REG_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    orb_imgs = build_antamina_charge_orb_fx()
    body_f, lit_f = build_antamina_clean_and_lit_body_frames()
    maha_rows = scale_mahasenko_fx_70pct()

    # 1. QA 3-bg sheet for standalone `antamina_charge_orb_fx` (4 frames @ 60ms)
    render_3bg_board(
        [(f"orb#{i} (tapion/{i + 1})", orb_imgs[i]) for i in range(4)],
        (54, 86, 234, 266),
        QA_DIR / "qa_antamina_charge_orb_fx_3bg.png",
    )

    # 2. QA 3-bg sheet comparing `antamina_rings` (#0,#1,#2 clean + #3 bridge lit) AND `anta_lit_00..02` firing loop!
    render_3bg_board(
        [
            ("rng#0 (clean0)", body_f[0]),
            ("rng#1 (clean1)", body_f[1]),
            ("rng#2 (clean2)", body_f[2]),
            ("rng#3 (lit1)", lit_f[1]),
            ("lit#0 (fire0)", lit_f[0]),
            ("lit#1 (fire1)", lit_f[1]),
            ("lit#2 (fire2)", lit_f[2]),
        ],
        (88, 108, 224, 256),
        QA_DIR / "qa_antamina_body_and_lit_v5_3bg.png",
    )

    # 3. QA Before (100%) vs After (70%, -30%) comparison for Mahasenko FX (3 representative frames + all 9)
    maha_items: list[tuple[str, Image.Image]] = []
    for fid, b_im, a_im in maha_rows:
        if fid.endswith("_00") or fid.endswith("_02"):
            maha_items.append((f"100% {fid}", b_im))
            maha_items.append((f"70% {fid}", a_im))
    render_3bg_board(
        maha_items,
        (10, 76, 270, 276),
        QA_DIR / "qa_mahasenko_fx_70pct_3bg.png",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
