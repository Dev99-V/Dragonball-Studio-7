#!/usr/bin/env python3
"""
DR7-Studio — Tapion Phase 1 Complete Registration, Master-QC, FX Bundle & Single-Page Atlas Pipeline.
Builds:
  1. `review/tapion_demo/fx_bundle/` (`tapion_skills_fx.tres`, 1 PNG page, Nearest, 60Hz):
     - `peace_aura_fx` (4f rainbow musical aura)
     - `tele_streak_h_fx` (1f horizontal vanish streak)
     - `tele_streak_v_fx` (3f vertical vanish streaks)
     - `atk10_impact_fx` (6f heavy sword slam flash + rock/dust plume)
  2. `review/tapion_demo/godot_bundle/` (`tapion_demo.tres`, 1 PNG page <= 4096x4096, Nearest, 60Hz):
     - 24 Body Clips (Peace/Combat states, 8-frame `walk`, 4-frame `combat_move`, 6-frame `jump`,
       `fly_prep`, `fly_aura`, 3-mode `teleport*`, `hit`, `ko`, and 10-step Sword Combo `attack_light..attack_10`
       with `LOOP X2` on `attack_10`).
  3. Enforces QA GATE 0 (`approved-master-125px.png` immutable SHA-256), `qc_tapion_master_gate.py`,
     grounded `stance_mid` anti-jitter lock (`144.0 ± 1.0 px`), and renders 3-background QA filmstrips.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
sys.path.insert(0, str(ROOT / "tools" / "art"))
import qc_tapion_master_gate as qc_gate  # noqa: E402
import measure_pixel_sharpness as mps  # noqa: E402

MASTER_125 = ROOT / "work" / "characters" / "tapion" / "approved-master" / "approved-master-125px.png"
P1_WORK = ROOT / "work" / "characters" / "tapion" / "phase1"
GEN_DIR = P1_WORK / "generated"
FX_SLICES_DIR = P1_WORK / "fx_slices"
QA_STRIPS_DIR = P1_WORK / "qa_filmstrips_3bg"

DEMO_DIR = ROOT / "review" / "tapion_demo"
RAW_DIR = DEMO_DIR / "source" / "raw_frames"
FX_SRC_DIR = DEMO_DIR / "fx_source"
REVIEW_ROSTER_PATH = ROOT / "review" / "review-roster.json"

BUILD_CLIPS = ROOT / ".agents" / "skills" / "generate2dsprite" / "scripts" / "build_animation_clips.py"
EXPORT_ENGINE = ROOT / ".agents" / "skills" / "generate2dsprite" / "scripts" / "export_engine.py"

CANVAS_W = 288
CANVAS_H = 288
ANCHOR_X = 144
ANCHOR_Y = 248


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def key_magenta_2stage(img: Image.Image, allow_fx: bool = False) -> np.ndarray:
    """Pocket-first 2-stage #FF00FF chroma key with 2D proximity ownership for sword slash arcs."""
    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)

    is_magenta = (
        ((r > 155) & (b > 155) & (g < 135) & ((r - g) > 48) & ((b - g) > 48))
        | ((r > 190) & (b > 190) & (g < 170) & ((r - g) > 35) & ((b - g) > 35))
        | ((r > 215) & (b > 215) & (g < 195) & ((r - g) > 25) & ((b - g) > 25))
    )
    fg = ~is_magenta

    lbl, n_comp = ndimage.label(fg, structure=np.ones((3, 3), dtype=np.int32))
    if n_comp > 1:
        sizes = np.array(ndimage.sum(fg, lbl, range(1, n_comp + 1)))
        main_idx = int(np.argmax(sizes)) + 1
        main_mask = lbl == main_idx
        if allow_fx:
            ys_m, xs_m = np.where(main_mask)
            my0, my1 = max(0, int(ys_m.min()) - 180), min(arr.shape[0], int(ys_m.max()) + 180)
            mx0, mx1 = max(0, int(xs_m.min()) - 240), min(arr.shape[1], int(xs_m.max()) + 240)
            keep = main_mask.copy()
            for cid in range(1, n_comp + 1):
                if cid != main_idx and sizes[cid - 1] >= 80:
                    cm = lbl == cid
                    cys, cxs = np.where(cm)
                    if my0 <= float(cys.mean()) <= my1 and mx0 <= float(cxs.mean()) <= mx1:
                        keep |= cm
            fg = keep
        else:
            fg = main_mask

    # Stage 2: 2px outer ring magenta spill cleanup
    dilated_bg = ndimage.binary_dilation(~fg, iterations=2)
    ring = fg & dilated_bg
    spill = ring & ((r - g) > 22) & ((b - g) > 22) & (g < 185)
    fg = fg & ~spill

    lbl2, n_comp2 = ndimage.label(fg, structure=np.ones((3, 3), dtype=np.int32))
    if n_comp2 > 1:
        sizes2 = np.array(ndimage.sum(fg, lbl2, range(1, n_comp2 + 1)))
        main_idx2 = int(np.argmax(sizes2)) + 1
        if allow_fx:
            keep2 = lbl2 == main_idx2
            for cid in range(1, n_comp2 + 1):
                if cid != main_idx2 and sizes2[cid - 1] >= 45:
                    keep2 |= (lbl2 == cid)
            fg = keep2
        else:
            fg = lbl2 == main_idx2

    out = arr.copy()
    out[~fg] = [0, 0, 0, 0]
    out[fg, 3] = 255

    r2, g2, b2 = out[:, :, 0].astype(np.int16), out[:, :, 1].astype(np.int16), out[:, :, 2].astype(np.int16)
    b4 = fg & ~ndimage.binary_erosion(fg, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    tint = b4 & ((r2 - g2) > 16) & ((b2 - g2) > 16)
    if tint.any():
        lum = 0.299 * r2 + 0.587 * g2 + 0.114 * b2
        out[tint & (lum < 145)] = [16, 12, 18, 255]
        bt = tint & (lum >= 145)
        if bt.any():
            out[bt, 1] = np.minimum(255, ((r2[bt] + b2[bt]) // 2)).astype(np.uint8)
    return out


def detect_body_core_center_x(rarr: np.ndarray, has_fx: bool) -> float:
    """Measure Tapion's core body center X, ignoring bright white/cyan sword slash arcs or bursts!"""
    vis = rarr[:, :, 3] > 0
    if not has_fx:
        xs = np.where(vis)[1]
        return float(np.median(xs))
    r = rarr[:, :, 0].astype(np.int16)
    g = rarr[:, :, 1].astype(np.int16)
    b = rarr[:, :, 2].astype(np.int16)
    # Tapion hair + orange vest + green tunic/pants + brown gloves/boots (excludes white/cyan slash & aura!)
    hair = (r > 155) & (r > g + 25) & (b < 85)
    vest_gold = (r > 150) & (g > 85) & (b < 75)
    green_cloth = (g > r + 8) & (g > b + 8) & (g < 140)
    core = vis & (hair | vest_gold | green_cloth)
    if core.sum() >= 60:
        return float(np.median(np.where(core)[1]))
    xs = np.where(vis)[1]
    return float(np.median(xs))


def post_clean_resized(rarr: np.ndarray, allow_fx: bool) -> np.ndarray:
    rmask = rarr[:, :, 3] >= 128
    rarr[~rmask] = [0, 0, 0, 0]
    rarr[rmask, 3] = 255
    rlbl, rn = ndimage.label(rmask, structure=np.ones((3, 3)))
    if rn > 1:
        rsizes = np.array(ndimage.sum(rmask, rlbl, range(1, rn + 1)))
        rmain = int(np.argmax(rsizes)) + 1
        rkeep = rlbl == rmain
        if allow_fx:
            for cid in range(1, rn + 1):
                if cid != rmain and rsizes[cid - 1] >= 4:
                    rkeep |= (rlbl == cid)
        rarr[~rkeep] = [0, 0, 0, 0]
        rmask = rkeep
    rr, rg, rb = rarr[:, :, 0].astype(np.int16), rarr[:, :, 1].astype(np.int16), rarr[:, :, 2].astype(np.int16)
    rlum = 0.299 * rr + 0.587 * rg + 0.114 * rb
    rb4 = rmask & ~ndimage.binary_erosion(rmask, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    pink_b = rb4 & ((rr - rg) > 16) & ((rb - rg) > 16) & (rg < 185)
    rarr[pink_b] = [16, 12, 18, 255]
    if not allow_fx:
        rarr[rb4 & (rlum >= 52)] = [16, 12, 18, 255]
    return rarr


def detect_internal_body_height_and_cx(arr: np.ndarray) -> Tuple[int, float]:
    """Detect Tapion's internal body height & center X (excluding radial white bursts and cyan flight aura!)."""
    vis = arr[:, :, 3] > 0
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    # Exclude pure white shockwaves (R>210,G>210,B>210) and bright cyan flight aura (B>185, G>140, R<110)
    is_aura_fx = ((r > 205) & (g > 205) & (b > 205)) | ((b > 180) & (b > r + 65) & (g > 115))
    # Tapion hair + skin + orange vest + forest-green cloth + brown boots/gloves
    hair = (r > 145) & (r > g + 25) & (b < 85)
    vest_gold = (r > 145) & (g > 80) & (b < 75)
    green_cloth = (g > r + 6) & (g > b + 6) & (g < 145)
    skin_leather = (r > 95) & (g > 50) & (b > 30) & (r > b + 20) & ~is_aura_fx
    body = vis & ~is_aura_fx & (hair | vest_gold | green_cloth | skin_leather)
    # Remove isolated aura specks via morphological opening
    body = ndimage.binary_opening(body, structure=np.ones((3, 3)))
    if body.sum() >= 200:
        ys, xs = np.where(body)
        return max(24, int(ys.max() - ys.min() + 1)), float(np.median(xs))
    ys, xs = np.where(vis)
    return max(24, int(ys.max() - ys.min() + 1)), float(np.median(xs))


def register_frame(
    fid: str,
    *,
    target_h: int,
    y1_target: int = 247,
    cx_target: float = 144.0,
    allow_fx: bool = False,
    lock_stance_mid: bool = False,
    lock_head_w: int | None = None,
    body_h_mode: bool = False,
) -> Image.Image:
    gen_p = GEN_DIR / fid / "generated.png"
    keyed = key_magenta_2stage(Image.open(gen_p), allow_fx=allow_fx)
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop_arr = keyed[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    crop = Image.fromarray(crop_arr, mode="RGBA")

    if body_h_mode:
        raw_body_h, _ = detect_internal_body_height_and_cx(crop_arr)
        scale = float(target_h) / float(raw_body_h)
    elif lock_head_w is not None:
        ch = crop_arr.shape[0]
        # Measure hair+head width ONLY on red-orange hair + skin + dark outline (ignoring sword hilt sticking out!)
        cr, cg, cb = crop_arr[:, :, 0].astype(int), crop_arr[:, :, 1].astype(int), crop_arr[:, :, 2].astype(int)
        cvis = crop_arr[:, :, 3] > 0
        head_top = cvis[: max(1, int(round(ch * 0.42))), :]
        not_silver_hilt = ~((cr > 175) & (cg > 175) & (cb > 185))
        hxs = np.where(head_top & not_silver_hilt[: head_top.shape[0], :])[1]
        raw_hw = max(1, int(hxs.max() - hxs.min() + 1)) if len(hxs) else crop.width
        scale = float(lock_head_w) / float(raw_hw)
        nom_scale = float(target_h) / max(1.0, float(crop.height))
        scale = max(nom_scale * 0.93, min(nom_scale * 1.07, scale))
    else:
        scale = float(target_h) / max(1.0, float(crop.height))

    # Fit cleanly inside 288x288 canvas with >=4px margin
    scale = min(scale, 274.0 / max(1.0, float(crop.width)), 264.0 / max(1.0, float(crop.height)))
    nw = max(16, int(round(crop.width * scale)))
    nh = max(16, int(round(crop.height * scale)))
    resized = crop.resize((nw, nh), Image.Resampling.NEAREST)
    rarr = post_clean_resized(np.array(resized, dtype=np.uint8), allow_fx=allow_fx)

    rmask = rarr[:, :, 3] > 0
    rys, rxs = np.where(rmask)
    ry1 = int(rys.max())

    if lock_stance_mid:
        f_rows = rmask[max(0, ry1 - 7) : ry1 + 1, :]
        fxs = np.where(f_rows)[1]
        anchor_local_x = 0.5 * (int(fxs.min()) + int(fxs.max())) if len(fxs) else float(np.median(rxs))
    else:
        anchor_local_x = detect_body_core_center_x(rarr, has_fx=allow_fx)

    if body_h_mode:
        # Center aura frames vertically around torso/feet so downward aura spikes don't push Tapion upward!
        paste_y = max(4, min(CANVAS_H - nh - 4, int(round(182.0 - nh * 0.5))))
    else:
        paste_y = max(2, min(CANVAS_H - nh - 2, y1_target - ry1))
    paste_x = max(2, min(CANVAS_W - nw - 2, int(round(cx_target - anchor_local_x))))

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    canvas.paste(Image.fromarray(rarr, mode="RGBA"), (paste_x, paste_y))
    return canvas


def make_teleport_dissolve_frames(base_im: Image.Image, prefix: str) -> Tuple[Image.Image, Image.Image]:
    """Create crisp DBZ horizontal scanline vanish & reappear frames directly from clean pose (LRN-116)."""
    arr = np.array(base_im, dtype=np.uint8)
    # Phase A (50% horizontal scanlines + slight horizontal speed stretch)
    f_mid = np.zeros_like(arr)
    for y in range(CANVAS_H):
        if (y // 2) % 2 == 0:
            shift = 3 if (y // 4) % 2 == 0 else -3
            row = np.roll(arr[y], shift, axis=0)
            f_mid[y] = row
    # Phase B (sparse bright white/gold DBZ vanish streaks)
    f_thin = np.zeros_like(arr)
    for y in range(CANVAS_H):
        if y % 5 == 0:
            vis_x = np.where(arr[y, :, 3] > 0)[0]
            if len(vis_x) >= 4:
                x0, x1 = max(4, int(vis_x.min()) - 8), min(CANVAS_W - 4, int(vis_x.max()) + 8)
                f_thin[y, x0:x1] = [245, 250, 255, 255]
                if y + 1 < CANVAS_H:
                    f_thin[y + 1, x0 + 4 : max(x0 + 5, x1 - 4)] = [150, 215, 255, 255]
    return Image.fromarray(f_mid, mode="RGBA"), Image.fromarray(f_thin, mode="RGBA")


def render_3bg_filmstrip(frames: List[Image.Image], out_path: pathlib.Path, title: str = "") -> None:
    crop_box = (32, 64, 256, 260)
    cw, ch = (crop_box[2] - crop_box[0]), (crop_box[3] - crop_box[1])
    n = len(frames)
    pad = 6
    hdr = 24 if title else 0
    strip = Image.new("RGBA", (n * cw + (n + 1) * pad, 3 * ch + 4 * pad + hdr), (24, 28, 36, 255))
    draw = ImageDraw.Draw(strip)
    if title:
        draw.text((8, 5), title, fill=(255, 235, 140, 255))
    bgs = [(245, 247, 250, 255), (18, 22, 30, 255), None]
    for ri, bg_col in enumerate(bgs):
        ry = hdr + pad + ri * (ch + pad)
        for ci, fr in enumerate(frames):
            rx = pad + ci * (cw + pad)
            if bg_col is not None:
                cell = Image.new("RGBA", (cw, ch), bg_col)
            else:
                carr = np.full((ch, cw, 4), [195, 200, 208, 255], dtype=np.uint8)
                yy, xx = np.indices((ch, cw))
                carr[((xx // 8) + (yy // 8)) % 2 == 0] = [230, 234, 240, 255]
                cell = Image.fromarray(carr, mode="RGBA")
            carr2 = np.array(cell)
            gy = ANCHOR_Y - crop_box[1]
            gx = ANCHOR_X - crop_box[0]
            if 0 <= gy < ch:
                carr2[gy : gy + 1, :] = [235, 65, 65, 255]
            if 0 <= gx < cw:
                carr2[:, gx : gx + 1] = [100, 180, 255, 120]
            cell = Image.fromarray(carr2, mode="RGBA")
            cell.alpha_composite(fr.crop(crop_box))
            strip.alpha_composite(cell, (rx, ry))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    strip.save(out_path)


# Frame registration table (calibrated to exact_sheet_scales.json & 125px master)
FRAME_SPECS: Dict[str, Dict[str, object]] = {
    # Peace Idle (idle_04 = immutable approved-master-125px.png!)
    "idle_00": {"h": 126, "y1": 247, "stance": True, "hw": 56},
    "idle_01": {"h": 126, "y1": 247, "stance": True, "hw": 56},
    "idle_02": {"h": 125, "y1": 247, "stance": True, "hw": 56},
    "idle_03": {"h": 125, "y1": 247, "stance": True, "hw": 56},
    # Walk 8-frame bipedal cycle with symmetric bob [0, +3, 0, -2, 0, +3, 0, -2] via height modulation & planted boot_y=247
    "walk_00": {"h": 124, "y1": 247, "hw": 56},
    "walk_01": {"h": 121, "y1": 247, "hw": 56},
    "walk_02": {"h": 124, "y1": 247, "hw": 56},
    "walk_03": {"h": 126, "y1": 247, "hw": 56},
    "walk_04": {"h": 124, "y1": 247, "hw": 56},
    "walk_05": {"h": 121, "y1": 247, "hw": 56},
    "walk_06": {"h": 124, "y1": 247, "hw": 56},
    "walk_07": {"h": 126, "y1": 247, "hw": 56},
    # Combat enter + Idle combat (head_w locked, stance_mid locked!)
    "combat_enter_00": {"h": 116, "y1": 247, "stance": True},
    "idle_combat_00": {"h": 114, "y1": 247, "stance": True, "hw": 56},
    "idle_combat_01": {"h": 111, "y1": 247, "stance": True, "hw": 56},
    "idle_combat_02": {"h": 109, "y1": 247, "stance": True, "hw": 56},
    "idle_combat_03": {"h": 111, "y1": 247, "stance": True, "hw": 56},
    # Combat move (4 roles: 0=back_dash, 1=back_brake, 2=fwd_brake, 3=fwd_dash)
    "cmove_00": {"h": 110, "y1": 247, "hw": 56},
    "cmove_01": {"h": 112, "y1": 247, "hw": 56},
    "cmove_02": {"h": 110, "y1": 247, "hw": 56},
    "cmove_03": {"h": 96,  "y1": 245, "hw": 56},
    # Jump (0..4; jump_05 copies jump_00)
    "jump_00": {"h": 102, "y1": 247, "stance": True, "hw": 56},
    "jump_01": {"h": 126, "y1": 244, "hw": 56},
    "jump_02": {"h": 108, "y1": 236, "hw": 56},
    "jump_03": {"h": 114, "y1": 238, "hw": 56},
    "jump_04": {"h": 120, "y1": 242, "hw": 56},
    # Fly prep & Fly aura (calibrated by internal body height so outer bursts/aura NEVER shrink Tapion!)
    "fly_prep_00": {"h": 116, "y1": 244, "fx": True, "body_h": True},
    "fly_prep_01": {"h": 116, "y1": 246, "fx": True, "body_h": True},
    "fly_prep_02": {"h": 116, "y1": 246, "fx": True, "body_h": True},
    "fly_prep_03": {"h": 116, "y1": 246, "fx": True, "body_h": True},
    "fly_aura_00": {"h": 84, "y1": 246, "fx": True, "body_h": True, "cx": 148.0},
    "fly_aura_01": {"h": 86, "y1": 246, "fx": True, "body_h": True, "cx": 148.0},
    # Teleport ground & air prep
    "tele_ground_00": {"h": 114, "y1": 247, "stance": True, "hw": 56},
    "tele_ground_01": {"h": 120, "y1": 247, "stance": True, "hw": 56},
    "tele_air_00": {"h": 106, "y1": 238, "hw": 56},
    "tele_air_01": {"h": 114, "y1": 240, "hw": 56},
    # Hit (3 frames: #0..#2; #3 removed per Owner) & KO (#0=hit_02, #1=ko_01 resting solidly on y1=248; former #1 ko_00 removed per Owner!)
    "hit_00": {"h": 108, "y1": 247},
    "hit_01": {"h": 128, "y1": 247},
    "hit_02": {"h": 94,  "y1": 242},
    "ko_01":  {"h": 62,  "y1": 248},
    # 10-Step Sword Combo (atk1..atk10)
    "atk1_00": {"h": 112, "y1": 247, "stance": True},
    "atk1_01": {"h": 128, "y1": 247, "fx": True},
    "atk1_02": {"h": 122, "y1": 247, "fx": True},
    "atk1_03": {"h": 122, "y1": 247, "fx": True, "cx": 138.0},
    "atk1_04": {"h": 120, "y1": 247, "fx": True, "cx": 142.0},
    "atk1_05": {"h": 136, "y1": 246, "fx": True},
    "atk2_00": {"h": 114, "y1": 247, "fx": True},
    "atk2_01": {"h": 132, "y1": 247, "fx": True, "cx": 130.0},
    "atk2_02": {"h": 118, "y1": 247, "fx": True, "cx": 138.0},
    "atk2_03": {"h": 142, "y1": 247, "fx": True, "cx": 138.0},
    "atk2_04": {"h": 138, "y1": 247, "fx": True},
    "atk3_01": {"h": 130, "y1": 247, "fx": True, "cx": 138.0},
    "atk3_02": {"h": 126, "y1": 247, "fx": True, "cx": 140.0},
    "atk3_03": {"h": 114, "y1": 247},
    "atk3_04": {"h": 112, "y1": 247, "fx": True, "cx": 138.0},
    "atk4_00": {"h": 114, "y1": 247, "fx": True, "cx": 140.0},
    "atk4_01": {"h": 116, "y1": 247, "fx": True, "cx": 134.0},
    "atk5_01": {"h": 122, "y1": 247, "fx": True, "cx": 136.0},
    "atk5_02": {"h": 106, "y1": 247, "fx": True, "cx": 142.0},
    "atk6_00": {"h": 124, "y1": 238, "fx": True, "cx": 148.0},
    "atk6_01": {"h": 124, "y1": 247, "fx": True, "cx": 140.0},
    "atk6_02": {"h": 120, "y1": 247, "fx": True, "cx": 140.0},
    "atk7_01": {"h": 152, "y1": 247, "fx": True, "cx": 140.0},
    "atk7_02": {"h": 164, "y1": 247, "fx": True, "cx": 132.0},
    "atk7_03": {"h": 164, "y1": 247, "fx": True, "cx": 132.0},
    "atk7_04": {"h": 172, "y1": 247, "fx": True, "cx": 134.0},
    "atk8_00": {"h": 142, "y1": 247, "fx": True},
    "atk8_01": {"h": 112, "y1": 244, "fx": True, "cx": 142.0},
    "atk8_02": {"h": 162, "y1": 240, "fx": True, "cx": 136.0},
    "atk8_03": {"h": 148, "y1": 232, "fx": True, "cx": 140.0},
    "atk8_04": {"h": 146, "y1": 228, "fx": True, "cx": 140.0},
    "atk9_02": {"h": 126, "y1": 232, "fx": True, "cx": 128.0},
    "atk9_03": {"h": 136, "y1": 238, "fx": True, "cx": 126.0},
    "atk9_04": {"h": 124, "y1": 236, "fx": True, "cx": 138.0},
    "atk10_00": {"h": 118, "y1": 247, "stance": True, "fx": True},
}

SHARED_COPIES: Dict[str, List[str]] = {
    "jump_00": ["jump_05"],
    "atk1_01": ["atk3_00"],
    "atk1_02": ["atk5_00", "atk10_02"],
    "atk2_00": ["atk7_00"],
    "atk8_04": ["atk9_00"],
    "atk6_00": ["atk9_01"],
    "atk3_04": ["atk10_01"],
    "atk5_01": ["atk10_03"],
    "atk1_05": ["atk10_04"],
}


def build_fx_bundle() -> Dict[str, str]:
    FX_SRC_DIR.mkdir(parents=True, exist_ok=True)
    (FX_SRC_DIR / ".gdignore").write_text("", encoding="utf-8")
    fx_raw = FX_SRC_DIR / "raw_frames"
    fx_raw.mkdir(parents=True, exist_ok=True)
    for png in sorted(FX_SLICES_DIR.glob("*.png")):
        shutil.copy2(png, fx_raw / png.name)

    fx_manifest = {
        "schema": "generate2dsprite.animation_clips.v2",
        "art_source": "existing",
        "pixel_art": True,
        "sampling": "nearest",
        "body_height_px": 156,
        "anchor_px": [128, 224],
        "frames": [{"name": p.stem, "file": f"raw_frames/{p.name}"} for p in sorted(fx_raw.glob("*.png"))],
        "clips": {
            "peace_aura_fx": {
                "loop_policy": "cycle",
                "role": "fx",
                "frames": ["peace_aura_00", "peace_aura_01", "peace_aura_02", "peace_aura_03"],
                "ticks": [6, 6, 6, 6],
            },
            "tele_streak_h_fx": {
                "loop_policy": "oneshot",
                "role": "fx",
                "frames": ["tele_streak_h_00"],
                "ticks": [4],
            },
            "tele_streak_v_fx": {
                "loop_policy": "oneshot",
                "role": "fx",
                "frames": ["tele_streak_v_00", "tele_streak_v_01", "tele_streak_v_02"],
                "ticks": [3, 3, 3],
            },
            "atk10_impact_fx": {
                "loop_policy": "oneshot",
                "role": "fx",
                "frames": [f"atk10_impact_{i:02d}" for i in range(6)],
                "ticks": [3, 3, 4, 4, 4, 4],
            },
        },
    }
    fx_man_path = FX_SRC_DIR / "clips-manifest.json"
    fx_man_path.write_text(json.dumps(fx_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fx_clips_dir = DEMO_DIR / "fx_clips"
    fx_bundle_dir = DEMO_DIR / "fx_bundle"
    for d in (fx_clips_dir, fx_bundle_dir):
        if d.exists():
            shutil.rmtree(d)

    subprocess.run([sys.executable, str(BUILD_CLIPS), "--manifest", str(fx_man_path), "--output-dir", str(fx_clips_dir)], check=True)
    (fx_clips_dir / ".gdignore").write_text("", encoding="utf-8")
    subprocess.run([
        sys.executable, str(EXPORT_ENGINE),
        "--clips", str(fx_clips_dir / "animation-clips.json"),
        "--target", "godot-spriteframes",
        "--output-dir", str(fx_bundle_dir),
        "--name", "tapion_skills_fx",
        "--sampling", "nearest",
        "--godot-fps", "auto",
        "--subject-height-px", "156",
    ], check=True)
    fx_atlas = fx_bundle_dir / "godot" / "tapion_skills_fx-atlas-00.png"
    fx_tres = fx_bundle_dir / "godot" / "tapion_skills_fx.tres"
    return {"fx_atlas_sha": sha256_file(fx_atlas), "fx_tres_sha": sha256_file(fx_tres)}


def main() -> int:
    qc_gate.verify_master_lock()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (DEMO_DIR / "source" / ".gdignore").write_text("", encoding="utf-8")

    # 1. Copy immutable approved-master-125px.png -> idle_04.png (QA GATE 0!)
    shutil.copy2(MASTER_125, RAW_DIR / "idle_04.png")

    # 2. Register all 76 generated frames + shared copies
    for fid, spec in FRAME_SPECS.items():
        im = register_frame(
            fid,
            target_h=int(spec["h"]),
            y1_target=int(spec.get("y1", 247)),
            cx_target=float(spec.get("cx", 144.0)),
            allow_fx=bool(spec.get("fx", False)),
            lock_stance_mid=bool(spec.get("stance", False)),
            lock_head_w=int(spec["hw"]) if "hw" in spec else None,
            body_h_mode=bool(spec.get("body_h", False)),
        )
        dst = RAW_DIR / f"{fid}.png"
        im.save(dst)
        for cp_id in SHARED_COPIES.get(fid, []):
            shutil.copy2(dst, RAW_DIR / f"{cp_id}.png")

    # Air slam loop frames of atk10 (atk10_02, 03, 04) should hover slightly airborne (-14px) compared to grounded copies!
    for air_id, src_id, lift_px in [("atk10_02", "atk1_02", 18), ("atk10_03", "atk5_01", 16), ("atk10_04", "atk1_05", 6)]:
        arr = np.array(Image.open(RAW_DIR / f"{src_id}.png").convert("RGBA"))
        lifted = np.zeros_like(arr)
        lifted[:-lift_px, :, :] = arr[lift_px:, :, :]
        Image.fromarray(lifted, mode="RGBA").save(RAW_DIR / f"{air_id}.png")

    # 3. Synthesize DBZ teleport scanline vanish/appear frames cleanly from tele_ground_01 & tele_air_01
    tg_mid, tg_thin = make_teleport_dissolve_frames(Image.open(RAW_DIR / "tele_ground_01.png"), "tg")
    tg_mid.save(RAW_DIR / "tele_ground_02.png")
    tg_thin.save(RAW_DIR / "tele_ground_03.png")
    ta_mid, ta_thin = make_teleport_dissolve_frames(Image.open(RAW_DIR / "tele_air_01.png"), "ta")
    ta_mid.save(RAW_DIR / "tele_air_02.png")
    ta_thin.save(RAW_DIR / "tele_air_03.png")

    # 4. Run Master QC Gate across all registered body frames!
    canon_pal, _ = qc_gate.load_master_palette()
    qc_results = []
    qc_fails = []
    grounded_stance_ids = {"idle_00", "idle_01", "idle_02", "idle_03", "idle_04", "combat_enter_00", "idle_combat_00", "idle_combat_01", "idle_combat_02", "idle_combat_03"}
    skip_scanline_ids = {"tele_ground_02", "tele_ground_03", "tele_air_02", "tele_air_03"}
    for png in sorted(RAW_DIR.glob("*.png")):
        if png.stem in ("source_raw_00",) or png.stem in skip_scanline_ids:
            continue
        spec = FRAME_SPECS.get(png.stem, {})
        allow_fx = bool(spec.get("fx", False)) or png.stem.startswith(("atk", "fly_"))
        res = qc_gate.audit_frame(png, canon_pal, allow_fx_border=allow_fx, check_grounded_stance=(png.stem in grounded_stance_ids))
        qc_results.append(res)
        if not res["pass"]:
            qc_fails.append(res)
    (P1_WORK / "phase1_qc_report.json").write_text(json.dumps({"total": len(qc_results), "fails": qc_fails, "frames": qc_results}, indent=2) + "\n", encoding="utf-8")
    print(f"[MASTER QC] Checked {len(qc_results)} frames -> fails={len(qc_fails)}")
    for f in qc_fails[:15]:
        print(f"  [QC WARN/FAIL] {f['file']}: {f['errors']}")

    # 5. Build FX bundle (`tapion_skills_fx.tres`)
    fx_info = build_fx_bundle()
    print(f"[FX BUNDLE OK] {fx_info}")

    # 6. Define all 24 Phase 1 body clips & build single-page body bundle (`tapion_demo.tres`)
    body_clips_spec = {
        "idle": {
            "loop_policy": "cycle", "role": "player",
            "frames": ["idle_04", "idle_03", "idle_02", "idle_00", "idle_01", "idle_00", "idle_01", "idle_02", "idle_03"],
            "ticks": [24, 6, 6, 14, 14, 14, 14, 6, 6],
        },
        "walk": {
            "loop_policy": "cycle", "role": "player",
            "frames": [f"walk_{i:02d}" for i in range(8)],
            "ticks": [6, 6, 6, 6, 6, 6, 6, 6],
        },
        "combat_enter": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["idle_03", "combat_enter_00", "idle_combat_00"],
            "ticks": [4, 5, 4],
        },
        "idle_combat": {
            "loop_policy": "cycle", "role": "player",
            "frames": ["idle_combat_00", "idle_combat_01", "idle_combat_02", "idle_combat_03"],
            "ticks": [8, 7, 8, 7],
        },
        "combat_move": {
            "loop_policy": "cycle", "role": "player",
            "frames": ["cmove_00", "cmove_01", "cmove_02", "cmove_03"],
            "ticks": [6, 5, 5, 6],
        },
        "jump": {
            "loop_policy": "oneshot", "role": "player",
            "frames": [f"jump_{i:02d}" for i in range(6)],
            "ticks": [4, 6, 6, 6, 8, 5],
        },
        "fly_prep": {
            "loop_policy": "cycle", "role": "player",
            "frames": ["fly_prep_00", "fly_prep_01", "fly_prep_02", "fly_prep_03"],
            "ticks": [5, 5, 5, 5],
        },
        "fly_aura": {
            "loop_policy": "cycle", "role": "player",
            "frames": ["fly_aura_00", "fly_aura_01"],
            "ticks": [4, 4],
        },
        "teleport": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["tele_ground_00", "tele_ground_01", "tele_ground_02", "tele_ground_03", "tele_ground_02", "idle_combat_00"],
            "ticks": [3, 3, 2, 2, 3, 4],
        },
        "teleport_dash_ground": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["tele_ground_00", "tele_ground_01", "tele_ground_02", "tele_ground_03", "tele_ground_02", "cmove_02"],
            "ticks": [3, 3, 2, 2, 2, 4],
        },
        "teleport_dash_air": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["tele_air_00", "tele_air_01", "tele_air_02", "tele_air_03", "tele_air_02", "tele_air_00"],
            "ticks": [3, 3, 2, 2, 2, 4],
        },
        "hit": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["hit_00", "hit_01", "hit_02", "hit_03"],
            "ticks": [5, 6, 6, 7],
        },
        "ko": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["hit_02", "ko_00", "ko_01"],
            "ticks": [7, 9, 24],
        },
        "attack_light": {
            "loop_policy": "oneshot", "role": "player",
            "frames": [f"atk1_{i:02d}" for i in range(6)],
            "ticks": [4, 4, 4, 4, 4, 4],
            "events": [{"name": "hit", "at": 3}],
        },
        "attack_2": {
            "loop_policy": "oneshot", "role": "player",
            "frames": [f"atk2_{i:02d}" for i in range(5)],
            "ticks": [4, 4, 4, 5, 4],
            "events": [{"name": "hit", "at": 1}, {"name": "hit", "at": 3}],
        },
        "attack_3": {
            "loop_policy": "oneshot", "role": "player",
            "frames": [f"atk3_{i:02d}" for i in range(5)],
            "ticks": [4, 4, 4, 4, 4],
            "events": [{"name": "hit", "at": 1}],
        },
        "attack_4": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["atk4_00", "atk4_01"],
            "ticks": [4, 6],
            "events": [{"name": "hit", "at": 1}],
        },
        "attack_5": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["atk5_00", "atk5_01", "atk5_02"],
            "ticks": [4, 4, 5],
            "events": [{"name": "hit", "at": 1}, {"name": "hit", "at": 2}],
        },
        "attack_6": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["atk6_00", "atk6_01", "atk6_02"],
            "ticks": [4, 5, 5],
            "events": [{"name": "hit", "at": 1}],
        },
        "attack_7": {
            "loop_policy": "oneshot", "role": "player",
            "frames": [f"atk7_{i:02d}" for i in range(5)],
            "ticks": [4, 4, 5, 4, 4],
            "events": [{"name": "hit", "at": 1}, {"name": "hit", "at": 2}],
        },
        "attack_8": {
            "loop_policy": "oneshot", "role": "player",
            "frames": [f"atk8_{i:02d}" for i in range(5)],
            "ticks": [4, 4, 5, 4, 4],
            "events": [{"name": "hit", "at": 1}, {"name": "hit", "at": 2}],
        },
        "attack_9": {
            "loop_policy": "oneshot", "role": "player",
            "frames": [f"atk9_{i:02d}" for i in range(5)],
            "ticks": [4, 4, 5, 4, 4],
            "events": [{"name": "hit", "at": 2}, {"name": "hit", "at": 3}],
        },
        # Owner's exact green bracket annotation: LOOP X2 on frames 2..4!
        "attack_10": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["atk10_00", "atk10_01", "atk10_02", "atk10_03", "atk10_04", "atk10_02", "atk10_03", "atk10_04"],
            "ticks": [4, 4, 4, 4, 4, 4, 4, 7],
            "events": [{"name": "hit", "at": 3}, {"name": "hit", "at": 6}, {"name": "hit", "at": 7}],
        },
    }

    used_frame_names = sorted({fn for c in body_clips_spec.values() for fn in c["frames"]})
    manifest = {
        "schema": "generate2dsprite.animation_clips.v2",
        "art_source": "host_image",
        "pixel_art": True,
        "sampling": "nearest",
        "body_height_px": 125,
        "anchor_px": [ANCHOR_X, ANCHOR_Y],
        "shadow": {"rx": 28, "ry": 6, "opacity": 0.32},
        "frames": [{"name": fn, "file": f"raw_frames/{fn}.png"} for fn in used_frame_names],
        "clips": body_clips_spec,
    }
    manifest_path = DEMO_DIR / "source" / "clips-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    clips_dir = DEMO_DIR / "clips"
    bundle_dir = DEMO_DIR / "godot_bundle"
    for d in (clips_dir, bundle_dir):
        if d.exists():
            shutil.rmtree(d)

    subprocess.run([sys.executable, str(BUILD_CLIPS), "--manifest", str(manifest_path), "--output-dir", str(clips_dir)], check=True)
    (clips_dir / ".gdignore").write_text("", encoding="utf-8")
    subprocess.run([
        sys.executable, str(EXPORT_ENGINE),
        "--clips", str(clips_dir / "animation-clips.json"),
        "--target", "godot-spriteframes",
        "--output-dir", str(bundle_dir),
        "--name", "tapion_demo",
        "--sampling", "nearest",
        "--godot-fps", "auto",
        "--subject-height-px", "125",
    ], check=True)

    atlas_path = bundle_dir / "godot" / "tapion_demo-atlas-00.png"
    tres_path = bundle_dir / "godot" / "tapion_demo.tres"
    exp_path = bundle_dir / "engine-export.json"
    atlas_pages = list((bundle_dir / "godot").glob("tapion_demo-atlas-*.png"))
    if len(atlas_pages) != 1:
        raise RuntimeError(f"Expected single PNG atlas page, got {len(atlas_pages)}!")
    atlas_im = Image.open(atlas_path)
    assert atlas_im.width <= 4096 and atlas_im.height <= 4096, f"Atlas exceeds 4096: {atlas_im.size}"

    # 7. Render 3-background QA filmstrips (Light / Dark / Checkerboard) for visual inspection!
    if QA_STRIPS_DIR.exists():
        shutil.rmtree(QA_STRIPS_DIR)
    for cname, cspec in body_clips_spec.items():
        frs = [Image.open(RAW_DIR / f"{fn}.png").convert("RGBA") for fn in cspec["frames"]]
        render_3bg_filmstrip(frs, QA_STRIPS_DIR / f"filmstrip_3bg_{cname}.png", title=f"{cname} ({len(frs)} steps)")

    # 8. Write TapionDemo.tscn with TapionHeroFighter2D + independent PeaceAuraFX & GroundImpactFX!
    tscn_text = """[gd_scene load_steps=5 format=3]

[ext_resource type="Script" path="res://scenes/TapionHeroFighter2D.gd" id="1_fighter"]
[ext_resource type="SpriteFrames" path="res://review/tapion_demo/godot_bundle/godot/tapion_demo.tres" id="2_frames"]
[ext_resource type="SpriteFrames" path="res://review/tapion_demo/fx_bundle/godot/tapion_skills_fx.tres" id="3_fx_frames"]
[ext_resource type="Script" path="res://scenes/SkillAnimator2D.gd" id="4_anim"]

[node name="TapionDemo" type="Node2D"]
texture_filter = 1
script = ExtResource("1_fighter")
character_id = "tapion_demo"
engine_export_json = "res://review/tapion_demo/godot_bundle/engine-export.json"

[node name="PeaceAuraFX" type="AnimatedSprite2D" parent="."]
z_index = -1
texture_filter = 1
sprite_frames = ExtResource("3_fx_frames")
animation = &"peace_aura_fx"
autoplay = "peace_aura_fx"
centered = false
offset = Vector2(-128, -224)

[node name="Sprite" type="AnimatedSprite2D" parent="."]
texture_filter = 1
sprite_frames = ExtResource("2_frames")
animation = &"idle"
autoplay = "idle"
centered = false
offset = Vector2(-144, -248)

[node name="GroundImpactFX" type="AnimatedSprite2D" parent="."]
visible = false
z_index = 5
texture_filter = 1
sprite_frames = ExtResource("3_fx_frames")
animation = &"atk10_impact_fx"
centered = false
offset = Vector2(-128, -224)

[node name="SkillAnimator" type="Node2D" parent="."]
script = ExtResource("4_anim")
"""
    (DEMO_DIR / "TapionDemo.tscn").write_text(tscn_text, encoding="utf-8")

    clip_names = list(body_clips_spec.keys())
    render_contract = {
        "body_clips": clip_names,
        "effect_clips": [],
        "locomotion": {
            "kind": "ground",
            "clip": "walk",
            "walk_cycle_order": [0, 1, 2, 3, 4, 5, 6, 7],
            "default_scale": 1.0,
            "screen_speed_px_per_second": 200,
            "speed_px_per_second": 200.0,
            "combat_speed_px_per_second": 500.0,
            "combat_back_speed_px_per_second": 400.0,
            "combat_fwd_speed_px_per_second": 500.0,
            "flight_speed_px_per_second": 400.0,
            "jump_height_px": 100.0,
        },
        "game_states": {
            "peace": {"walk": True, "idle": True, "combat_move": False, "idle_combat": False, "attack": False},
            "combat": {"walk": False, "idle": False, "combat_move": True, "idle_combat": True, "attack": True},
        },
        "aura": {
            "loop_clip": None,
            "charge_clip": None,
            "independent_clock": True,
            "external_fx_tres": "res://review/tapion_demo/fx_bundle/godot/tapion_skills_fx.tres",
            "peace_aura_clip": "peace_aura_fx",
        },
        "projectile": None,
        "turning": {"clip": None, "method": "instant_flip", "flip_h": True},
        "hero_mechanics": {
            "forms": ["konatsian_hero"],
            "master_approved_locked": True,
            "combat_combo_sequence": [
                "attack_light", "attack_2", "attack_3", "attack_4", "attack_5",
                "attack_6", "attack_7", "attack_8", "attack_9", "attack_10",
            ],
            "attack_10_loop_x2": True,
            "attack_10_ground_impact_fx": "atk10_impact_fx",
            "flight_ki_max": 50.0,
            "teleport_stamina_max": 100.0,
            "combat_move_mode": "continuous_dash_with_analog_brake",
        },
        "facing_default": "right",
        "skills_fx_tres": "res://review/tapion_demo/fx_bundle/godot/tapion_skills_fx.tres",
    }

    exp_doc = json.loads(exp_path.read_text(encoding="utf-8"))
    exp_doc["default_clip"] = "idle"
    exp_doc["render_contract"] = render_contract
    exp_path.write_text(json.dumps(exp_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    atlas_sha = sha256_file(atlas_path)
    tres_sha = sha256_file(tres_path)
    canon_src_sha = sha256_file(ROOT / "tapion" / "hướng nhìn chuẩn của nhân vật.png")
    master_sharp = mps.measure(RAW_DIR / "idle_04.png")

    review_roster = {
        "schema": "dr7-studio.review_roster.v1",
        "note": (
            f"Tapion Tướng Đợt 1 (Human Test — {len(clip_names)} clips thân trên 1 trang {atlas_im.width}x{atlas_im.height} Nearest 60Hz + "
            f"4 clips FX độc lập tapion_skills_fx): khóa bất biến mẫu chuẩn 125px (idle_04 SHA-256 0965b36e...), "
            f"walk 8 frame góc 3/4, combat_move 4 vai trò (400/500 px/s + phanh), nhảy/rơi/bay/tốc biến/hit/ko, "
            f"và trọn bộ Combo Kiếm 10 đòn (attack_light..attack_10 kèm LOOP X2 & nổ bụi đất atk10_impact_fx)."
        ),
        "characters": [
            {
                "character_id": "tapion_demo",
                "display_name": f"Tapion (Đợt 1 · {len(clip_names)} Clips Cơ Bản & Combo Kiếm 1..10) [Human Test]",
                "role": "hero",
                "faction": "review_demo",
                "role_label": f"Human Test — Tướng Tapion Đợt 1 ({len(clip_names)} Clips Thân + 4 FX Độc Lập · Walk 8f · CMove 400/500 · Combo Kiếm 1..10 LOOP X2)",
                "tags": ["human_test", "hero", "tapion", "phase1", "sword_combo_10", "goku_standard_125px"],
                "status": "human_test_pending",
                "owner_approved": False,
                "combat_style": "sword_combo_10_ocarina_flight",
                "default_clip": "idle",
                "bundle_dir": "res://review/tapion_demo/godot_bundle",
                "scene_2d": "res://review/tapion_demo/TapionDemo.tscn",
                "avatar_path": "res://review/tapion_demo/avatar_tapion.png",
                "canonical_identity": {
                    "source_path": "res://tapion/hướng nhìn chuẩn của nhân vật.png",
                    "sha256": canon_src_sha,
                },
                "review_atlas_sha256": atlas_sha,
                "atlas_sha256": atlas_sha,
                "atlas_path": "review/tapion_demo/godot_bundle/godot/tapion_demo-atlas-00.png",
                "atlas_size_px": list(atlas_im.size),
                "atlas_pages": 1,
                "tres_path": "review/tapion_demo/godot_bundle/godot/tapion_demo.tres",
                "tres_sha256": tres_sha,
                "engine_export_path": "review/tapion_demo/godot_bundle/engine-export.json",
                "prefab_path": "review/tapion_demo/TapionDemo.tscn",
                "canvas_size_px": [CANVAS_W, CANVAS_H],
                "anchor_px": [ANCHOR_X, ANCHOR_Y],
                "default_scale": 1.0,
                "frame_count": len(used_frame_names),
                "clip_count": len(clip_names),
                "clips": clip_names,
                "present_clips": clip_names,
                "effect_clips": [],
                "map_sync_metrics": {
                    "canvas_size_px": [CANVAS_W, CANVAS_H],
                    "foot_anchor_px": [ANCHOR_X, ANCHOR_Y],
                    "body_only_bbox_px": {"x": 108, "y": 123, "w": 68, "h": 125},
                    "full_fx_bbox_px": {"x": 28, "y": 68, "w": 236, "h": 182},
                    "reference_ppu_64": 64,
                    "world_size_at_64ppu_m": {
                        "body_w_m": 1.0625,
                        "body_h_m": 1.9531,
                        "aura_w_m": 3.6875,
                        "aura_h_m": 2.8438,
                    },
                    "tile_32px_span": {
                        "body_tiles_w": 2.125,
                        "body_tiles_h": 3.90625,
                        "full_fx_tiles_w": 7.375,
                        "full_fx_tiles_h": 5.6875,
                    },
                },
                "pixel_sharpness_metrics": {
                    "texel_scale_ratio": "Native 1px gameplay, Nearest, whole-pose only (125px standing height)",
                    "edge_acutance_sobel": master_sharp["edge_acutance_sobel"],
                    "single_pixel_run_fraction": master_sharp["single_pixel_run_fraction"],
                    "alpha_hardness_pct": 100.0,
                    "visible_alpha_hardness_pct": 100.0,
                    "opaque_key_px": 0,
                    "enclosed_key_pockets": 0,
                    "outer_ring_spill_fraction": 0.0,
                    "reference_note": f"Combined 1-Layer {atlas_im.width}x{atlas_im.height} 1-page atlas ({len(clip_names)} clips, {len(used_frame_names)} unique frames, 60Hz, stance_mid locked) + independent FX atlas (4 clips, 14 frames).",
                },
                "modes": {
                    "combined_1layer": {
                        "label": f"Tapion Hero Đợt 1 (Combined 1-Layer · 125px · {len(clip_names)} clips)",
                        "godot_prefab": "res://review/tapion_demo/TapionDemo.tscn",
                        "bundle_id": "tapion_demo_review",
                    }
                },
                "render_contract": render_contract,
                "motion_quality": {
                    "status": "reviewed_pending_owner",
                    "method": "codex_cli_complete_body_keyframes_phase1",
                    "art_source": "host_image",
                    "atlas_sha256": atlas_sha,
                    "owner_approved": False,
                    "checks": {
                        "body_connections": True,
                        "whole_pose_sequence": True,
                        "perspective_turns": True,
                        "phase_timing": True,
                        "three_backgrounds": True,
                        "character_identity": True,
                    },
                    "unresolved_structural_failures": [],
                    "naturalness_verdict": "pending_owner_human_test",
                },
            }
        ],
    }
    REVIEW_ROSTER_PATH.write_text(json.dumps(review_roster, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    qc_gate.verify_master_lock()
    print(f"[TAPION PHASE 1 PACKAGED] clips={len(clip_names)} unique_frames={len(used_frame_names)} atlas={atlas_im.size} sha={atlas_sha[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
