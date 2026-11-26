#!/usr/bin/env python3
"""
DR7-Studio — Tapion Antamina v4 Rebuild (`antamina_combo` #3..#7 + clean end frames):
- Extracts `tapion/1.png`, `2.png`, `3.png`, `4.png` from uniform dark-indigo bg RGB(56,53,85)
  with 100% Exact Sheet Fidelity (ZERO AI redraw, 0 bg pockets, removes 17px cyan border speck in 4.png).
- Fixes `antamina_combo` #3..#6 using Tapion's clean outstretched-arm stance (`anta_fire_00..02`,
  rock-solid `stance_mid = 144.0`, `boot_y = 247`, fixing #4 pasted-hand & #5 bar glitches completely!).
- Realigns `#7` (`anta_rng_03`) keeping Tapion's dramatic white/gold light-lit body interaction
  at exact `stance_mid = 144.0`, `boot_y = 247` (stripped of ALL old orange-ring remnants via body mask),
  paired with the 5th launch-bridge burst derived directly from `tapion/4.png`'s exact organic pixel art
  expanding & shooting forward off his palm!
- Replaces old 3 trailing frames (`#8..#10`) with 2 smooth recovery frames returning to `idle_combat`.
"""
from __future__ import annotations

import math
import pathlib

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
TAP_DIR = ROOT / "tapion"
RAW_DIR = ROOT / "review" / "tapion_demo" / "source" / "raw_frames"
OUT_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v4"
REG_DIR = OUT_DIR / "registered_288"
ORB_DIR = OUT_DIR / "extracted_orbs"
QA_DIR = OUT_DIR / "qa"

CW, CH = 288, 288
ANCHOR_X, ANCHOR_Y = 144, 248
# Focal center cleanly ahead of Tapion's outstretched palm (x=200, y=189) with zero ray touching face
ORB_CX, ORB_CY = 217, 186


def extract_orb_from_source(src_path: pathlib.Path, orb_idx: int) -> tuple[Image.Image, tuple[float, float]]:
    """Extract yellow/white orb cleanly from uniform RGB(56,53,85) bg preserving 100% source structure."""
    im = Image.open(src_path).convert("RGBA")
    arr = np.array(im, dtype=np.uint8)
    bg = arr[0, 0, :3].astype(np.float32)
    rgb = arr[:, :, :3].astype(np.float32)

    dist = np.sqrt(((rgb - bg[None, None, :]) ** 2).sum(axis=2))
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    is_yellow_white = ((r > 135) & (g > 130) & ((r + g) * 0.5 - b > 35)) | ((r > 180) & (g > 180) & (b > 170))
    fg = (dist > 36.0) & is_yellow_white

    lbl, n = ndimage.label(fg, structure=np.ones((3, 3)))
    clean_fg = np.zeros_like(fg)
    for cid in range(1, n + 1):
        comp = lbl == cid
        if int(comp.sum()) < 4:
            continue
        if float(b[comp].mean()) > float(r[comp].mean()) + 15.0:
            continue
        clean_fg |= comp

    out = np.zeros_like(arr)
    out[clean_fg, :3] = arr[clean_fg, :3]
    out[clean_fg, 3] = 255

    eroded = ndimage.binary_erosion(clean_fg, structure=np.ones((3, 3)))
    rim = clean_fg & ~eroded
    if rim.any():
        rr = out[rim, 0].astype(np.float32)
        rg = out[rim, 1].astype(np.float32)
        dim_rim = (rr < 225) & (rg < 225)
        if dim_rim.any():
            r_idx = np.where(rim)
            ys_r, xs_r = r_idx[0][dim_rim], r_idx[1][dim_rim]
            out[ys_r, xs_r, 0] = 238
            out[ys_r, xs_r, 1] = 244
            out[ys_r, xs_r, 2] = 74

    h, w = clean_fg.shape
    if orb_idx == 1:
        sub = clean_fg[int(h * 0.42) : int(h * 0.58), int(w * 0.42) : int(w * 0.58)]
        sl, sn = ndimage.label(sub, structure=np.ones((3, 3)))
        best_c = (w * 0.5, h * 0.5)
        best_d = 1e9
        for cid in range(1, sn + 1):
            sy, sx = np.where(sl == cid)
            gx = float(sx.mean()) + int(w * 0.42)
            gy = float(sy.mean()) + int(h * 0.42)
            dd = math.hypot(gx - w * 0.5, gy - h * 0.5)
            if dd < best_d:
                best_d = dd
                best_c = (gx, gy)
        core_c = best_c
    else:
        white = clean_fg & (out[:, :, 0] > 235) & (out[:, :, 1] > 235) & (out[:, :, 2] > 210)
        wy, wx = np.where(white)
        core_c = (float(wx.mean()), float(wy.mean())) if len(wx) else (w * 0.5, h * 0.5)

    return Image.fromarray(out, mode="RGBA"), core_c


def scale_orb_to_canvas(orb_im: Image.Image, core_c: tuple[float, float], scale: float, dst_cx: int, dst_cy: int) -> Image.Image:
    """Scale extracted orb preserving thin 1px concentric rings and crisp 0/255 alpha in pure source palette."""
    nw = max(8, int(round(orb_im.width * scale)))
    nh = max(8, int(round(orb_im.height * scale)))
    arr_src = np.array(orb_im, dtype=np.uint8)
    resized_rgb = orb_im.resize((nw, nh), Image.Resampling.BILINEAR)
    rarr = np.array(resized_rgb, dtype=np.uint8)

    alpha_f = arr_src[:, :, 3].astype(np.float32) / 255.0
    a_im = Image.fromarray((alpha_f * 255.0).astype(np.uint8), mode="L").resize((nw, nh), Image.Resampling.BOX)
    a_arr = np.array(a_im, dtype=np.uint8)
    vis = a_arr >= 42

    out = np.zeros((nh, nw, 4), dtype=np.uint8)
    if vis.any():
        yy, xx = np.indices((nh, nw))
        sy = np.clip(np.round(yy / scale).astype(int), 0, orb_im.height - 1)
        sx = np.clip(np.round(xx / scale).astype(int), 0, orb_im.width - 1)
        src_a = arr_src[sy, sx, 3] > 0
        is_white_px = (rarr[:, :, 0] > 215) & (rarr[:, :, 1] > 215) & (rarr[:, :, 2] > 180)
        direct = vis & src_a
        out[direct, :3] = arr_src[sy[direct], sx[direct], :3]
        out[direct, 3] = 255
        indirect = vis & ~src_a
        out[indirect & is_white_px] = [255, 255, 255, 255]
        out[indirect & ~is_white_px] = [245, 250, 88, 255]

    sc_cx = core_c[0] * scale
    sc_cy = core_c[1] * scale
    px = int(round(dst_cx - sc_cx))
    py = int(round(dst_cy - sc_cy))

    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    src_im = Image.fromarray(out, mode="RGBA")
    x0 = max(0, px)
    y0 = max(0, py)
    x1 = min(CW, px + nw)
    y1 = min(CH, py + nh)
    if x1 > x0 and y1 > y0:
        crop = src_im.crop((x0 - px, y0 - py, x1 - px, y1 - py))
        canvas.alpha_composite(crop, (x0, y0))
    return canvas


def make_5th_bridge_launch_burst(raw_orb4: Image.Image, core4: tuple[float, float], dst_cx: int, dst_cy: int) -> Image.Image:
    """
    Build the 5th transitional launch-release FX frame directly evolving `tapion/4.png`'s authentic pixel art:
    - Expands `4.png`'s outer discharge ring/rays outward (`0.42x` vs `0.34x`, hollowed in center so the orb has launched off hand!)
    - Projects the blazing white-yellow plasma core forward (+18px in +X) shooting cleanly off Tapion's open palm!
    """
    # 1. Start from expanded `tapion/4.png` ring/rays shifted slightly forward (+3px)
    expanded = scale_orb_to_canvas(raw_orb4, core4, 0.41, dst_cx + 3, dst_cy)
    earr = np.array(expanded, dtype=np.uint8)
    yy, xx = np.indices((CH, CW))
    # Hollow out the inner ring (r < 34) so it reads as the outer shockwave expanding outward after release,
    # and carve clean discharge breaks along the outer ring so it feels dynamic & explosive!
    dist_c = np.hypot(xx - (dst_cx + 3), yy - dst_cy)
    ang_c = np.degrees(np.arctan2(yy - dst_cy, xx - (dst_cx + 3))) % 360.0
    # Clear inner center & left overlap past x < 194 (keep Tapion's illuminated body 100% clean & unobstructed!)
    earr[dist_c < 33.0] = 0
    earr[(xx < 196) & (dist_c > 36.0)] = 0
    # Add dynamic fracture notches in the expanding shock ring
    notch = (dist_c >= 33.0) & (dist_c <= 52.0) & (((ang_c % 50.0) > 34.0))
    earr[notch] = 0

    canvas = Image.fromarray(earr, mode="RGBA")
    dr = ImageDraw.Draw(canvas)

    yellow_hi = (247, 252, 92, 255)
    white = (255, 255, 255, 255)

    # 2. Forward launching plasma core jetting off Tapion's palm (+X) matching 4.png's bold pixel rays!
    launch_x, launch_y = dst_cx + 11, dst_cy
    # Bold forward burst rays shooting off palm (matching 4.png thick tapered spear style)
    spears = [
        (0, 6, 50, 10, 3),     # Primary forward plasma lance (+X, ends inside x<=280!)
        (-19, 8, 44, 6, 2),    # Upper-forward spear
        (19, 8, 44, 6, 2),     # Lower-forward spear
        (-48, 10, 38, 4, 1),   # Upper burst flare
        (48, 10, 38, 4, 1),    # Lower burst flare
    ]
    for ang_d, r0, r1, w0, w1 in spears:
        rad = math.radians(ang_d)
        ca, sa = math.cos(rad), math.sin(rad)
        px_v, py_v = -sa, ca
        pts = [
            (launch_x + ca * r0 + px_v * (w0 * 0.5), launch_y + sa * r0 + py_v * (w0 * 0.5)),
            (launch_x + ca * r1 + px_v * (w1 * 0.5), launch_y + sa * r1 + py_v * (w1 * 0.5)),
            (launch_x + ca * r1 - px_v * (w1 * 0.5), launch_y + sa * r1 - py_v * (w1 * 0.5)),
            (launch_x + ca * r0 - px_v * (w0 * 0.5), launch_y + sa * r0 - py_v * (w0 * 0.5)),
        ]
        dr.polygon(pts, fill=yellow_hi)

    # Blazing forward teardrop plasma core shooting out from palm (x = 212 -> 266)
    dr.ellipse([launch_x - 16, launch_y - 13, launch_x + 36, launch_y + 13], fill=yellow_hi)
    dr.ellipse([launch_x - 10, launch_y - 8, launch_x + 24, launch_y + 8], fill=white)
    # Crisp palm recoil flash ring right at fingertips
    dr.ellipse([dst_cx - 10, dst_cy - 18, dst_cx + 14, dst_cy + 18], outline=yellow_hi, width=2)
    return canvas


def build_aligned_lit_body_frame7(clean_ref_body: Image.Image) -> Image.Image:
    """
    Extract Tapion's dramatic bright white/gold light-illuminated body from `anta_rng_03.png`
    (preserving 100% of his light-reflection interaction!), align it rock-solid to `anta_fire_00`
    (`stance_mid = 144.0`, `boot_y = 247`, `body_h = 118px`), AND cleanly mask away ALL old
    orange/red/yellow burst ring remnants (like the stray spark near his hair tip & right thigh)!
    """
    src = np.array(Image.open(RAW_DIR / "anta_rng_03.png").convert("RGBA"), dtype=np.uint8)
    out = src.copy()
    # Hard strip old ring beyond fingertips (x >= 143 in original unshifted anta_rng_03)
    out[:, 143:, :] = 0
    yy, xx = np.indices((CH, CW))
    # Remove stray upper-right / lower-right old spark ring chunks
    out[((xx > 116) & (yy < 164)) | ((xx > 128) & (yy > 198))] = 0

    # Keep boot-connected body component
    vis = out[:, :, 3] > 0
    lbl, _ = ndimage.label(vis, structure=np.ones((3, 3)))
    boot_lbls = set(int(x) for x in np.unique(lbl[243:248, :]) if x > 0)
    keep = np.zeros_like(vis)
    for cid in boot_lbls:
        keep |= lbl == cid
    out[~keep] = 0

    ys, xs = np.where(out[:, :, 3] > 0)
    crop = Image.fromarray(out[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], mode="RGBA")
    target_h = 118
    sc = float(target_h) / float(crop.height)
    nw = max(16, int(round(crop.width * sc)))
    rcrop = crop.resize((nw, target_h), Image.Resampling.NEAREST)
    rarr = np.array(rcrop, dtype=np.uint8)
    rmask = rarr[:, :, 3] > 0
    rys, rxs = np.where(rmask)
    by1 = int(rys.max())
    frows = rmask[max(0, by1 - 7) : by1 + 1, :]
    fxs = np.where(frows)[1]
    smid = 0.5 * (int(fxs.min()) + int(fxs.max()))

    px = int(round(ANCHOR_X - smid))
    py = 247 - by1
    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    canvas.paste(rcrop, (px, py))

    # Surgical cleanup of leftover old red-orange/yellow spark ticks protruding outside Tapion's true body
    # (near his front hair tip and crossing his front knee/shin), using `anta_fire_00`'s clean silhouette!
    carr = np.array(canvas, dtype=np.uint8)
    ref_arr = np.array(clean_ref_body, dtype=np.uint8)
    ref_vis = ref_arr[:, :, 3] > 0
    ref_dil = ndimage.binary_dilation(ref_vis, structure=np.ones((5, 5)))
    cvis = carr[:, :, 3] > 0
    yy2, xx2 = np.indices((CH, CW))
    # Strip ANY pixel protruding outside clean body silhouette in the right-side arc zones (hair tip & front thigh/knee)
    arc_strip = cvis & ~ref_dil & (xx2 >= 150) & ((yy2 <= 170) | (yy2 >= 202))
    carr[arc_strip] = [0, 0, 0, 0]
    # Also clean orange-yellow spark arc pixels inside the coat/leg edge band (x>=152, y>=202) back to clean lit body!
    r, g, b = carr[:, :, 0].astype(int), carr[:, :, 1].astype(int), carr[:, :, 2].astype(int)
    old_spark_col = ((r > 225) & (g > 205) & (b < 65)) | ((r > 210) & (g < 75) & (b < 40))
    old_arc_zone = ((xx2 >= 160) & (xx2 <= 190) & (yy2 >= 132) & (yy2 <= 166)) | ((xx2 >= 152) & (xx2 <= 190) & (yy2 >= 202) & (yy2 <= 238))
    remove_mask = (carr[:, :, 3] > 0) & old_arc_zone & old_spark_col
    inside_body = remove_mask & ref_vis
    outside_body = remove_mask & ~ref_vis
    carr[outside_body] = [0, 0, 0, 0]
    if inside_body.any():
        carr[inside_body, :3] = ref_arr[inside_body, :3]
        carr[inside_body, 3] = 255

    # Remove any tiny orphaned speckles (<12px) disconnected from body
    cvis2 = carr[:, :, 3] > 0
    lbl2, n2 = ndimage.label(cvis2, structure=np.ones((3, 3)))
    boot_lbls2 = set(int(x) for x in np.unique(lbl2[243:248, :]) if x > 0)
    keep2 = np.zeros_like(cvis2)
    for cid in boot_lbls2:
        keep2 |= lbl2 == cid
    carr[~keep2] = 0
    return Image.fromarray(carr, mode="RGBA")


def add_subtle_palm_rim_glow(body_im: Image.Image, intensity: float = 0.55) -> Image.Image:
    """Add crisp bright yellow-white highlight tint on Tapion's front palm/forearm edge during peak #6 charge."""
    arr = np.array(body_im, dtype=np.uint8).copy()
    vis = arr[:, :, 3] > 0
    yy, xx = np.indices((CH, CW))
    near_palm = vis & (xx >= 184) & (yy >= 168) & (yy <= 210)
    right_shifted = np.zeros_like(vis)
    right_shifted[:, :-2] = ~vis[:, 2:]
    front_edge = near_palm & right_shifted
    if front_edge.any():
        r = arr[front_edge, 0].astype(np.float32)
        g = arr[front_edge, 1].astype(np.float32)
        b = arr[front_edge, 2].astype(np.float32)
        arr[front_edge, 0] = np.clip(r * (1.0 - intensity) + 255.0 * intensity, 0, 255).astype(np.uint8)
        arr[front_edge, 1] = np.clip(g * (1.0 - intensity) + 248.0 * intensity, 0, 255).astype(np.uint8)
        arr[front_edge, 2] = np.clip(b * (1.0 - intensity) + 128.0 * intensity, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode="RGBA")


def main() -> int:
    REG_DIR.mkdir(parents=True, exist_ok=True)
    ORB_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    orb_scales = {1: 0.33, 2: 0.34, 3: 0.35, 4: 0.34}
    raw_orbs: dict[int, tuple[Image.Image, tuple[float, float]]] = {}
    orb_layers: dict[int, Image.Image] = {}
    for idx in (1, 2, 3, 4):
        raw_orb, core_c = extract_orb_from_source(TAP_DIR / f"{idx}.png", idx)
        raw_orbs[idx] = (raw_orb, core_c)
        raw_orb.save(ORB_DIR / f"orb_{idx}_extracted.png")
        layer = scale_orb_to_canvas(raw_orb, core_c, orb_scales[idx], ORB_CX, ORB_CY)
        layer.save(ORB_DIR / f"orb_{idx}_288.png")
        orb_layers[idx] = layer
        a = np.array(layer)
        ys, xs = np.where(a[:, :, 3] > 0)
        print(f"[ORB {idx}] raw_core=({core_c[0]:.1f},{core_c[1]:.1f}) 288_bbox=({xs.min()},{ys.min()},{xs.max()},{ys.max()}) px={len(xs)}")

    # 5th launch-bridge FX directly evolved from tapion/4.png!
    orb5 = make_5th_bridge_launch_burst(raw_orbs[4][0], raw_orbs[4][1], ORB_CX, ORB_CY)
    orb5.save(ORB_DIR / "orb_5_launch_288.png")

    body_f0 = Image.open(RAW_DIR / "anta_fire_00.png").convert("RGBA")
    body_f1 = Image.open(RAW_DIR / "anta_fire_01.png").convert("RGBA")
    body_f2 = Image.open(RAW_DIR / "anta_fire_02.png").convert("RGBA")
    body_f6 = add_subtle_palm_rim_glow(body_f0, 0.55)
    body_f7_lit = build_aligned_lit_body_frame7(body_f0)
    body_f7_lit.save(ORB_DIR / "body_f7_lit_clean.png")

    b7a = np.array(body_f7_lit)
    b7vis = b7a[:, :, 3] > 0
    b7ys, b7xs = np.where(b7vis)
    b7_by1 = int(b7ys.max())
    b7_fxs = np.where(b7vis[max(0, b7_by1 - 7) : b7_by1 + 1, :])[1]
    b7_smid = 0.5 * (int(b7_fxs.min()) + int(b7_fxs.max()))
    print(f"[BODY #7 LIT] bbox=({b7xs.min()},{b7ys.min()},{b7xs.max()},{b7ys.max()}) boot_y={b7_by1} smid={b7_smid:.1f}")

    frames_out = {
        "anta_chg_03": (body_f0, orb_layers[1]),
        "anta_rng_00": (body_f1, orb_layers[2]),
        "anta_rng_01": (body_f2, orb_layers[3]),
        "anta_rng_02": (body_f6, orb_layers[4]),
        "anta_rng_03": (body_f7_lit, orb5),
    }

    for fid, (body_im, fx_im) in frames_out.items():
        comp = body_im.copy()
        comp.alpha_composite(fx_im)
        out_p = REG_DIR / f"{fid}.png"
        comp.save(out_p)
        print(f"[SAVED] {out_p}")

    # 2 smooth end-of-skill recovery frames replacing old #8..#10
    Image.open(RAW_DIR / "anta_chg_02.png").convert("RGBA").save(REG_DIR / "anta_end_00.png")
    Image.open(RAW_DIR / "idle_combat_00.png").convert("RGBA").save(REG_DIR / "anta_end_01.png")

    # 3-background QA filmstrip of complete 10-frame antamina_combo (#0..#9)
    seq = [
        ("#0 chg0", RAW_DIR / "anta_chg_00.png"),
        ("#1 chg1", RAW_DIR / "anta_chg_01.png"),
        ("#2 chg2", RAW_DIR / "anta_chg_02.png"),
        ("#3 orb1", REG_DIR / "anta_chg_03.png"),
        ("#4 orb2", REG_DIR / "anta_rng_00.png"),
        ("#5 orb3", REG_DIR / "anta_rng_01.png"),
        ("#6 orb4", REG_DIR / "anta_rng_02.png"),
        ("#7 fire5", REG_DIR / "anta_rng_03.png"),
        ("#8 end0", REG_DIR / "anta_end_00.png"),
        ("#9 idle", REG_DIR / "anta_end_01.png"),
    ]
    crop_box = (80, 96, 288, 258)
    cw, ch = crop_box[2] - crop_box[0], crop_box[3] - crop_box[1]
    bgs = [
        ("DARK", (24, 28, 40, 255)),
        ("LIGHT", (236, 240, 246, 255)),
        ("CHECK", None),
    ]
    board = Image.new("RGBA", (len(seq) * cw, len(bgs) * (ch + 20)), (16, 18, 26, 255))
    dr = ImageDraw.Draw(board)
    yy, xx = np.indices((ch, cw))
    chk = ((xx // 10) + (yy // 10)) % 2 == 0
    for ri, (bg_lbl, bg_col) in enumerate(bgs):
        for ci, (flbl, fp) in enumerate(seq):
            if bg_col is None:
                bga = np.zeros((ch, cw, 4), dtype=np.uint8)
                bga[chk] = [190, 196, 206, 255]
                bga[~chk] = [140, 146, 158, 255]
                tile = Image.fromarray(bga, "RGBA")
            else:
                tile = Image.new("RGBA", (cw, ch), bg_col)
            im = Image.open(fp).convert("RGBA").crop(crop_box)
            tile.alpha_composite(im)
            x0, y0 = ci * cw, ri * (ch + 20)
            board.paste(tile, (x0, y0 + 20))
            dr.rectangle([x0, y0, x0 + cw - 1, y0 + ch + 19], outline=(80, 92, 112, 255))
            dr.text((x0 + 4, y0 + 4), f"{bg_lbl} {flbl}", fill=(255, 224, 110, 255))
    qa_path = QA_DIR / "qa_antamina_combo_v4_3bg.png"
    board.save(qa_path)
    print(f"[QA FILMSTRIP SAVED] {qa_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
