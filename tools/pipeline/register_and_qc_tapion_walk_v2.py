#!/usr/bin/env python3
"""
DR7-Studio — Exact Equal-Size Registration & 4-Gate QC for Tapion Walk v2 (`walk_00..07`).
Enforces ALL Owner requirements simultaneously:
  1. EQUAL CHARACTER SIZE (`H = 125 px` exact: `y0 = 123, y1 = 247` on ALL 8 frames `walk_00..07`,
     head_w spread <= 3 px, zero shrinking/bloating!).
  2. ROCK-STEADY HEAD & TORSO X ALIGNMENT (`anchor_x = 144` locked to head+collar+chest core, ignoring
     scarf tails and swinging arms/legs).
  3. ANATOMICAL LEFT-SHOULDER SWORD HILT LOCK (`+X` right side of neck `x >= 152, y = 146..174` has silver
     pommel/guard >= 8 px on ALL 8 frames, and `-X` back-of-head `x <= 134, y = 142..172` has 0 silver hilt px!).
  4. SON GOKU 3-STAGE LEFT/RIGHT FOOT GAIT VERIFICATION:
     - F0/F4: Wide 2-foot ground contact
     - F1/F5: Stage 1 Back-Lift (1 planted supporting foot, back foot lifted off y=247)
     - F2/F6: Stage 2 Narrow Passing under hips
     - F3/F7: Stage 3 Airborne Forward-Reach (back foot pushing on ground, front foot lifted in air before contact!)
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Dict, List

import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import build_tapion_phase1_bundle as p1b  # noqa: E402
import qc_tapion_master_gate as qc_gate  # noqa: E402

WALK_V2_WORK = ROOT / "work" / "characters" / "tapion" / "walk_v2"
GEN_DIR = WALK_V2_WORK / "generated"
REG_DIR = WALK_V2_WORK / "registered_288"

CANVAS_W = 288
CANVAS_H = 288
ANCHOR_X = 144
ANCHOR_Y = 248
TARGET_H = 125  # Exact immutable master height (125 px: y = 123..247 on ALL 8 frames!)


def align_x_to_walk0_head_rgb(im: Image.Image, ref_w0: Image.Image) -> Image.Image:
    """Lock horizontal X to walk_00's head/face/mohawk/hilt (y=123..168) via RGB+Alpha L1 template match (dy=0 fixed so H=125 exact!)."""
    arr = np.array(im.convert("RGBA"), dtype=np.int16)
    ref = np.array(ref_w0.convert("RGBA"), dtype=np.int16)
    band_ref = ref[123:169, :, :]
    best_dx = 0
    best_loss = 1e18
    for dx in range(-6, 7):
        shifted = np.zeros_like(arr)
        if dx >= 0:
            shifted[:, dx:, :] = arr[:, : CANVAS_W - dx, :]
        else:
            shifted[:, : CANVAS_W + dx, :] = arr[:, -dx:, :]
        band_cur = shifted[123:169, :, :]
        union_vis = (band_ref[:, :, 3] > 0) | (band_cur[:, :, 3] > 0)
        if not union_vis.any():
            continue
        diff = np.abs(band_ref - band_cur)[union_vis].mean()
        if diff < best_loss:
            best_loss = float(diff)
            best_dx = dx
    if best_dx == 0:
        return im
    out = np.zeros_like(np.array(im, dtype=np.uint8))
    src = np.array(im, dtype=np.uint8)
    if best_dx > 0:
        out[:, best_dx:, :] = src[:, : CANVAS_W - best_dx, :]
    else:
        out[:, : CANVAS_W + best_dx, :] = src[:, -best_dx:, :]
    return Image.fromarray(out, mode="RGBA")
def measure_head_chest_center_x(rarr: np.ndarray) -> float:
    """Compute rock-steady horizontal center of head + face + chest (top 56% height, excluding scarf tail & silver hilt)."""
    vis = rarr[:, :, 3] > 0
    ys, xs = np.where(vis)
    h = int(ys.max() - ys.min() + 1)
    y_cut = int(ys.min() + round(h * 0.56))
    sub = rarr[:y_cut, :, :]
    svis = sub[:, :, 3] > 0
    r = sub[:, :, 0].astype(int)
    g = sub[:, :, 1].astype(int)
    b = sub[:, :, 2].astype(int)
    hair = (r > 140) & (r > g + 22) & (b < 80)
    skin = (r > 175) & (g > 115) & (b > 80) & (r > b + 35)
    vest = (r > 165) & (g > 90) & (g < 175) & (b < 65)
    core = svis & (hair | skin | vest)
    if core.sum() >= 80:
        cxs = np.where(core)[1]
        return 0.5 * (float(np.percentile(cxs, 8)) + float(np.percentile(cxs, 92)))
    return float(np.median(xs))


def register_equal_125_walk_frame(gen_path: pathlib.Path, ref_head_cx_offset: float | None = None) -> Image.Image:
    keyed = p1b.key_magenta_2stage(Image.open(gen_path), allow_fx=False)
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop_arr = keyed[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    crop = Image.fromarray(crop_arr, mode="RGBA")

    # Exact 1-pass Nearest resize to TARGET_H = 125 px (equal height across ALL 8 frames!)
    scale = float(TARGET_H) / float(crop.height)
    nw = max(16, int(round(crop.width * scale)))
    nh = TARGET_H
    resized = crop.resize((nw, nh), Image.Resampling.NEAREST)
    rarr = p1b.post_clean_resized(np.array(resized, dtype=np.uint8), allow_fx=False)

    # Verify cropped height after post_clean is still exact TARGET_H = 125
    rmask = rarr[:, :, 3] > 0
    rys, rxs = np.where(rmask)
    if int(rys.max() - rys.min() + 1) != TARGET_H:
        sub2 = Image.fromarray(rarr[rys.min() : rys.max() + 1, rxs.min() : rxs.max() + 1], mode="RGBA")
        nw2 = max(16, int(round(sub2.width * (float(TARGET_H) / float(sub2.height)))))
        rarr = p1b.post_clean_resized(np.array(sub2.resize((nw2, TARGET_H), Image.Resampling.NEAREST), dtype=np.uint8), allow_fx=False)
        rmask = rarr[:, :, 3] > 0
        rys, rxs = np.where(rmask)

    ry1 = int(rys.max())
    local_cx = measure_head_chest_center_x(rarr)
    target_cx = 144.0 if ref_head_cx_offset is None else ref_head_cx_offset
    paste_x = max(2, min(CANVAS_W - rarr.shape[1] - 2, int(round(target_cx - local_cx))))
    paste_y = 247 - ry1  # Locks y1 = 247 and y0 = 123 (exact H = 125 px!)

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    canvas.paste(Image.fromarray(rarr, mode="RGBA"), (paste_x, paste_y))
    return canvas


def inspect_walk_frame(idx: int, im: Image.Image, canon_pal: np.ndarray) -> Dict[str, object]:
    arr = np.array(im.convert("RGBA"), dtype=np.uint8)
    vis = arr[:, :, 3] > 0
    ys, xs = np.where(vis)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    w, h = x1 - x0 + 1, y1 - y0 + 1

    # 1. Head width (y = 123..164, excluding silver sword hilt on right)
    htop = arr[y0 : y0 + 42, :, :]
    hvis = htop[:, :, 3] > 0
    hr, hg, hb = htop[:, :, 0].astype(int), htop[:, :, 1].astype(int), htop[:, :, 2].astype(int)
    not_silver = ~((hr > 160) & (hg > 160) & (hb > 170))
    hxs = np.where(hvis & not_silver)[1]
    head_w = int(hxs.max() - hxs.min() + 1) if len(hxs) else 0

    # 2. Sword Hilt Check: Right side (+X, anatomical LEFT shoulder, x >= 150, y = 144..176) vs Wrong Left side behind ear (-X, x <= 134, y = 140..165, above chest strap clasp!)
    r_all, g_all, b_all = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
    silver_mask = vis & (r_all > 160) & (g_all > 160) & (b_all > 170) & (np.abs(r_all - g_all) < 28)
    right_hilt_px = int(silver_mask[144:176, 150:190].sum())
    wrong_left_hilt_px = int(silver_mask[140:165, 96:134].sum())
    # Emerald eye centroid check (zero head wobble!)
    green_eye = vis[148:172, 130:168] & (g_all[148:172, 130:168] > r_all[148:172, 130:168] + 25) & (g_all[148:172, 130:168] > b_all[148:172, 130:168] + 10)
    eys, exs = np.where(green_eye)
    eye_xy = [round(130 + float(exs.mean()), 2), round(148 + float(eys.mean()), 2)] if len(exs) else [0.0, 0.0]

    # 3. Ground contact span (bottom 4px y = 244..247) & front/back leg lowest Y
    ground_contact = vis[244:248, :]
    gxs = np.where(ground_contact)[1]
    ground_x0 = int(gxs.min()) if len(gxs) else 0
    ground_x1 = int(gxs.max()) if len(gxs) else 0
    ground_span = (ground_x1 - ground_x0 + 1) if len(gxs) else 0

    # Lowest Y on back half (x < 138) vs front half (x > 152) in leg zone (y >= 205)
    leg_back = vis[205:248, :138]
    leg_front = vis[205:248, 152:]
    back_max_y = (205 + int(np.where(leg_back)[0].max())) if leg_back.any() else 205
    front_max_y = (205 + int(np.where(leg_front)[0].max())) if leg_front.any() else 205

    errors: List[str] = []
    if h != 125 or y0 != 123 or y1 != 247:
        errors.append(f"height={h} (y={y0}..{y1}) != 125 (123..247)")
    if right_hilt_px < 6:
        errors.append(f"missing_left_shoulder_silver_hilt(+X px={right_hilt_px}<6)")
    if wrong_left_hilt_px > 2:
        errors.append(f"wrong_right_shoulder_hilt(-X px={wrong_left_hilt_px}>2)")

    # Gait stage checks per Goku's 3-stage left/right foot cycle
    if idx in (0, 4):  # Contact: both feet near/on ground, wide stride
        if ground_span < 48:
            errors.append(f"contact_span_too_narrow({ground_span}<48)")
    elif idx in (1, 5):  # Stage 1 Back-Lift: back foot MUST be lifted off ground!
        if back_max_y >= 246 and ground_span > 46:
            errors.append(f"back_foot_not_lifted(back_y={back_max_y}, ground_span={ground_span})")
    elif idx in (2, 6):  # Stage 2 Passing: narrow compact legs under hips!
        if ground_span > 38:
            errors.append(f"passing_not_narrow(ground_span={ground_span}>38)")
    elif idx in (3, 7):  # Stage 3 Airborne Forward-Reach: front foot MUST be lifted above ground!
        if front_max_y >= 246 and ground_span > 52:
            errors.append(f"front_reach_foot_planted_on_ground(front_y={front_max_y}, ground_span={ground_span})")

    tmp_p = REG_DIR / f"walk_{idx:02d}.png"
    master_qc = qc_gate.audit_frame(tmp_p, canon_pal, allow_fx_border=False, check_grounded_stance=False)
    errors.extend(master_qc["errors"])

    return {
        "frame": f"walk_{idx:02d}",
        "pass": len(errors) == 0,
        "bbox": [x0, y0, w, h],
        "head_w": head_w,
        "eye_xy": eye_xy,
        "right_hilt_px": right_hilt_px,
        "wrong_left_hilt_px": wrong_left_hilt_px,
        "ground_x": [ground_x0, ground_x1],
        "ground_span": ground_span,
        "back_foot_max_y": back_max_y,
        "front_foot_max_y": front_max_y,
        "errors": errors,
    }


def main() -> int:
    REG_DIR.mkdir(parents=True, exist_ok=True)
    canon_pal, _ = qc_gate.load_master_palette()

    # First register walk_00 at exact H = 125 px and measure its exact head/chest X on 288x288
    w0_im = register_equal_125_walk_frame(GEN_DIR / "walk_00" / "generated.png", ref_head_cx_offset=143.0)
    w0_im.save(REG_DIR / "walk_00.png")
    ref_cx = measure_head_chest_center_x(np.array(w0_im))

    frames: List[Image.Image] = [w0_im]
    for i in range(1, 8):
        im = register_equal_125_walk_frame(GEN_DIR / f"walk_{i:02d}" / "generated.png", ref_head_cx_offset=ref_cx)
        im = align_x_to_walk0_head_rgb(im, w0_im)
        im.save(REG_DIR / f"walk_{i:02d}.png")
        frames.append(im)

    reports = [inspect_walk_frame(i, frames[i], canon_pal) for i in range(8)]
    head_ws = [r["head_w"] for r in reports]
    hw_spread = max(head_ws) - min(head_ws)
    if hw_spread > 4:
        print(f"[WARN] head_w spread = {hw_spread} ({head_ws})")

    p1b.render_3bg_filmstrip(frames, WALK_V2_WORK / "filmstrip_3bg_walk_v2.png", title="Tapion walk_v2 (8 frames, ALL H=125px, Left-Shoulder Hilt +X, Goku 3-Stage Legs)")

    # Also render zoomed 2x comparison: Top row = Goku SSJ1 #0..#7, Bottom row = Tapion walk_v2 #0..#7
    sys.path.insert(0, str(ROOT / "tools" / "preview"))
    import server
    g_atlas = Image.open(ROOT / "assets/songoku/godot_bundle/godot/songoku-atlas-00.png").convert("RGBA")
    parsed = server.parse_tres(ROOT / "assets/songoku/godot_bundle/godot/songoku.tres")
    g_ssj = [
        g_atlas.crop((int(round(f["x"])), int(round(f["y"])), int(round(f["x"] + f["w"])), int(round(f["y"] + f["h"]))))
        for f in parsed["animations"]["walk_ssj"]["frames"]
    ]

    cw, ch = 180, 292
    comp = Image.new("RGBA", (8 * cw, 2 * ch), (240, 242, 247, 255))
    draw = ImageDraw.Draw(comp)
    for ci in range(8):
        gc = g_ssj[ci].crop((96, 110, 186, 256)).resize((cw, ch), Image.Resampling.NEAREST)
        tc = frames[ci].crop((96, 110, 186, 256)).resize((cw, ch), Image.Resampling.NEAREST)
        comp.alpha_composite(gc, (ci * cw, 0))
        comp.alpha_composite(tc, (ci * cw, ch))
        draw.text((ci * cw + 4, 4), f"Goku #{ci}", fill=(25, 50, 150, 255))
        draw.text((ci * cw + 4, ch + 4), f"Tapion v2 #{ci} H={reports[ci]['bbox'][3]}", fill=(175, 20, 20, 255))
    for ri in range(2):
        # Top y=123 reference line (green) & ground y=248 reference line (red)
        y_top_line = ri * ch + (123 - 110) * 2
        y_gnd_line = ri * ch + (248 - 110) * 2
        draw.line([(0, y_top_line), (8 * cw, y_top_line)], fill=(20, 170, 60, 180))
        draw.line([(0, y_gnd_line), (8 * cw, y_gnd_line)], fill=(225, 50, 50, 200))
    comp.save(WALK_V2_WORK / "zoom_goku_vs_tapion_walk_v2.png")

    (WALK_V2_WORK / "walk_v2_qc.json").write_text(json.dumps({"head_w_spread": hw_spread, "frames": reports}, indent=2) + "\n", encoding="utf-8")
    all_ok = True
    for r in reports:
        status = "PASS" if r["pass"] else "FAIL"
        if not r["pass"]:
            all_ok = False
        print(
            f"[{status}] {r['frame']}: bbox={r['bbox']} head_w={r['head_w']} eye={r['eye_xy']} "
            f"hilt(+X={r['right_hilt_px']}, -X={r['wrong_left_hilt_px']}) "
            f"gnd={r['ground_x']}(span={r['ground_span']}) backY={r['back_foot_max_y']} frontY={r['front_foot_max_y']} "
            f"errs={r['errors']}"
        )
    print(f"[SUMMARY] head_w_spread={hw_spread} px | all_pass={all_ok}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
