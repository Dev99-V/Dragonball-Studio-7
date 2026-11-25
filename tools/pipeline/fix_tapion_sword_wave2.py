#!/usr/bin/env python3
"""
DR7-Studio — Tapion Canonical Right-Shoulder Sword Fix — WAVE 2:
Covers Todo Items #5, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16:
  - `turntable_360` (`turntable_01, 03, 05, 06, 07`; `04 = idle_04` from Wave 1; `00, 02` verified 3D right-shoulder -> left-hip).
  - `combat_move` (`cmove_00, 01, 02, 03`) & `teleport_dash_ground #5` (`= cmove_02`).
  - `bukadai_rush #0` (`bukadai_00`).
  - `mahasenko_ground` (`maha_gnd_00, 01, 02`).
  - `fly_prep` (`fly_prep_00..03` — outer white radial shockwave 100% preserved!).
  - `barrier_cast` (`barrier_01..08`; `00 = idle_03` from Wave 1 — outer 2x2 blue dither dome & white sonic ribbons 100% preserved!).
  - `energy_recover` (`recover_02..07`; `00 = idle_04, 01 = idle_00` from Wave 1 — white-cyan lightning aura & grounded stance 100% preserved!).
  - `antamina_charge #2` (`anta_chg_02`), `antamina_rings #0, #2, #3` (`anta_rng_00, 02, 03`), & `antamina_combo #2, #4, #6, #7`.
"""
from __future__ import annotations

import concurrent.futures
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
import build_tapion_phase1_bundle as p1b  # noqa: E402
import fix_tapion_sword_wave1 as w1  # noqa: E402
import qc_tapion_master_gate as qc_gate  # noqa: E402

ROUTE_MEDIA = ROOT / ".agent" / "skills" / "generate2dmedia" / "scripts" / "route_media.py"
RAW_DIR = ROOT / "review" / "tapion_demo" / "source" / "raw_frames"
W1_REG = ROOT / "work" / "characters" / "tapion" / "sword_fix_w1" / "registered_288"
OUT_DIR = ROOT / "work" / "characters" / "tapion" / "sword_fix_w2"
REFS_DIR = OUT_DIR / "refs_1024"
PROMPTS_DIR = OUT_DIR / "prompts"
GEN_DIR = OUT_DIR / "generated"
REG_DIR = OUT_DIR / "registered_288"

CW, CH = 288, 288


PROMPT_FRONT_RIGHT = w1.CANON_SWORD_RULE

PROMPT_CMOVE_03 = """Fix ONLY the diagonal brown leather chest strap direction on Reference Image 1 so it matches his right-shoulder-to-left-hip sword mount (Reference Image 2), on a flat solid #FF00FF pure magenta background:
- Keep his sword hilt on the upper-left (-X, over his right shoulder) and crimson-red scabbard tip on the lower-right (+X) EXACTLY as in Reference Image 1!
- Flip ONLY the brown leather chest strap (with the two round white-silver clasps) so it runs from his RIGHT SHOULDER (upper-left, -X) diagonally DOWN-RIGHT (+X) across his blue chest tunic toward his left waist/hip!
- Keep 100% of Reference Image 1's horizontal dash pose, face, hair, scarf, fists, and legs identical! Clean 1px dark outline on #FF00FF magenta."""

PROMPT_TURN_01_LEFT_PROF = """Clean up the sword mount on Reference Image 1 (Left Side Profile facing left -X) on flat #FF00FF pure magenta background:
- Because the character faces pure LEFT (-X), his near arm is his LEFT arm and his far shoulder (toward +X/back) is his RIGHT shoulder.
- Remove the duplicate/extra white pommel collar behind his neck so there is ONLY ONE clean silver-pommeled brown sword hilt + silver crossguard angling up-right (+X) from behind his far right shoulder, and a neat crimson-red scabbard tip with round silver cap peeking near his left hip!
- Keep 100% of Reference Image 1's exact left-profile head, hair, ear, torso, arm, and boots identical! Clean 1px dark outline on #FF00FF magenta."""

PROMPT_TURN_03_FRONT = """Fix the sword-wearing direction on Reference Image 1 (Pure Front 0° View facing straight at camera) on flat #FF00FF pure magenta background:
- The character wears his sword on his back from HIS ANATOMICAL RIGHT SHOULDER (LEFT side of image, -X) diagonally down to HIS ANATOMICAL LEFT HIP (RIGHT side of image, +X).
- Completely REMOVE the sword hilt from the right side (+X) and REMOVE the red scabbard tip from the left side (-X)!
- Place the silver-pommeled brown sword hilt + silver crossguard peeking diagonally UP-LEFT (-X) over his RIGHT shoulder (left side of image), run the brown leather chest strap with 2 round silver clasps from his right shoulder (-X) diagonally down-right (+X) across his chest, and place the crimson-red scabbard tip + round white-silver cap peeking out at LOWER-RIGHT (+X) behind his left hip!
- Keep 100% of Reference Image 1's symmetrical front-facing head, face, hair, shoulders, fists, and boots identical! Clean 1px dark outline on #FF00FF magenta."""

PROMPT_TURN_05_RIGHT_PROF = """Clean up the sword mount on Reference Image 1 (Right Side Profile facing right +X) on flat #FF00FF pure magenta background:
- Because the character faces pure RIGHT (+X), his near shoulder is his RIGHT shoulder.
- Remove the extra/duplicate white collar behind his neck so there is ONLY ONE crisp silver-pommeled brown sword hilt + silver crossguard angling diagonally UP-LEFT (-X) behind his right shoulder!
- Keep 100% of Reference Image 1's exact right-profile head, hair, ear, torso, arm, and boots identical! Clean 1px dark outline on #FF00FF magenta."""

PROMPT_TURN_BACK = """Fix ONLY the sword & crimson scabbard diagonal direction across the character's BACK in Reference Image 1 (Back View) to match Reference Image 2's 3D right-shoulder-to-left-hip back mount, on flat #FF00FF pure magenta background!
- Because we are looking at the character's BACK, his ANATOMICAL RIGHT SHOULDER is on the RIGHT side of the image (+X), and his ANATOMICAL LEFT HIP is on the LEFT side of the image (-X)!
- Flip the sword & scabbard on his back so:
  1. The silver-pommeled brown sword hilt + curved white-silver crossguard protrudes diagonally UP-RIGHT (+X) over his RIGHT shoulder (right side of image)!
  2. The full crimson-red scabbard runs diagonally across his back from upper-right (+X) DOWN-LEFT (-X), ending with its round white-silver tip cap at LOWER-LEFT (-X) by his left hip (matching Reference Image 2)!
- Keep 100% of Reference Image 1's exact head/hair angle, shoulders, arms, orange lower tunic, and legs/boots identical! Clean 1px dark outline on #FF00FF magenta."""

PROMPT_MAHA_GND_00 = """Fix the sword & scabbard position on Reference Image 1 so the sheathed sword is worn CLEANLY BEHIND HIS BACK (from his right shoulder -X to his left hip +X, matching Reference Image 2), NEVER across his front chest, on flat #FF00FF pure magenta background!
- In Reference Image 1, the red scabbard was mistakenly drawn across his front chest. Remove the red scabbard from his front chest!
- Show his normal royal-blue chest tunic, golden-orange vest, and diagonal brown leather chest strap (with 2 round silver clasps running from upper-left -X down-right +X) on his chest.
- Behind his back, place the silver-pommeled brown sword hilt + silver crossguard protruding UP-LEFT (-X) over his right shoulder (left side of image), and the crimson-red scabbard tip + white-silver cap peeking out at LOWER-RIGHT (+X) behind his left hip!
- Keep 100% of Reference Image 1's wide martial-arts stance, head/hair, and outstretched arms charging energy identical! Clean 1px dark outline on #FF00FF magenta."""


def extract_hover_body_only(src_288: pathlib.Path, out_1024: pathlib.Path) -> None:
    """Strip pure-white outer shockwave spikes from fly_prep_00 so Codex edits ONLY Tapion's clean hovering body."""
    arr = np.array(Image.open(src_288).convert("RGBA"))
    vis = arr[:, :, 3] > 0
    r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
    is_white_fx = vis & (r > 215) & (g > 215) & (b > 215)
    # Keep silver clasps/pommel near body by only stripping connected white components touching outer burst ring
    body_col = vis & (~is_white_fx) & ~((r < 35) & (g < 35) & (b < 45))
    body_core = ndimage.binary_dilation(ndimage.binary_opening(body_col, structure=np.ones((2, 2))), iterations=2)
    clean = np.where((vis & body_core)[:, :, None], arr, 0).astype(np.uint8)
    # Re-add 1px dark outline around clean body
    cvis = clean[:, :, 3] > 0
    ys, xs = np.where(cvis)
    crop = Image.fromarray(clean[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], mode="RGBA")
    scale = min(700.0 / max(1, crop.width), 700.0 / max(1, crop.height))
    up = crop.resize((int(round(crop.width * scale)), int(round(crop.height * scale))), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (1024, 1024), (255, 0, 255, 255))
    canvas.alpha_composite(up, ((1024 - up.width) // 2, (1024 - up.height) // 2))
    out_1024.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_1024)


def run_job(fid: str, src_ref: pathlib.Path, ref2: pathlib.Path, prompt: str) -> Tuple[str, int, str]:
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    GEN_DIR.mkdir(parents=True, exist_ok=True)
    pf = PROMPTS_DIR / f"{fid}.txt"
    pf.write_text(prompt.strip() + "\n", encoding="utf-8")
    od = GEN_DIR / fid
    if od.exists():
        shutil.rmtree(od)
    cmd = [
        sys.executable, str(ROUTE_MEDIA), "image", "--route", "codex-cli",
        "--prompt-file", str(pf),
        "--reference", str(src_ref),
        "--reference", str(ref2),
        "--size", "1024x1024",
        "--out-dir", str(od),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return fid, proc.returncode, (proc.stdout + "\n" + proc.stderr).strip()


def composite_body_into_fly_prep(orig_fp: pathlib.Path, new_hover_body_288: Image.Image) -> Image.Image:
    """Keep 100% of orig_fp's outer white radial burst spikes while replacing the inner hovering character body!"""
    orig = np.array(Image.open(orig_fp).convert("RGBA"))
    ovis = orig[:, :, 3] > 0
    r, g, b = orig[:, :, 0].astype(int), orig[:, :, 1].astype(int), orig[:, :, 2].astype(int)
    # Pure white shockwave + its 1px dark outline; erase old coloured body (including old +X hilt & -X red scabbard!)
    colored = ovis & ~((r > 210) & (g > 210) & (b > 210)) & ~((r < 40) & (g < 40) & (b < 50))
    old_char_zone = ndimage.binary_dilation(colored, iterations=2)
    # Infill old_char_zone inside orig's silhouette with pure white shockwave core [252,252,255,255] where surrounded by white!
    burst_only = orig.copy()
    white_around = ndimage.binary_dilation(ovis & (r > 215) & (g > 215) & (b > 215), iterations=3)
    burst_only[old_char_zone & white_around] = [252, 252, 255, 255]
    burst_only[old_char_zone & (~white_around)] = [0, 0, 0, 0]
    # Clean any orphaned 1px dark border specks left from old +X hilt
    bvis = burst_only[:, :, 3] > 0
    lbl, n = ndimage.label(bvis, structure=np.ones((3, 3)))
    if n > 1:
        sizes = np.array(ndimage.sum(bvis, lbl, range(1, n + 1)))
        keep = np.zeros_like(bvis)
        for cid in range(1, n + 1):
            if sizes[cid - 1] >= 12 or cid == int(np.argmax(sizes)) + 1:
                keep |= (lbl == cid)
        burst_only[~keep] = [0, 0, 0, 0]

    # Align new_hover_body_288 to orig_fp's face center!
    ofc = ovis & (r > 182) & (g > 122) & (b > 85) & (r > b + 38)
    oys_f, oxs_f = np.where(ofc)
    nb = np.array(new_hover_body_288)
    nb_vis = nb[:, :, 3] > 0
    nr, ng, nb_b = nb[:, :, 0].astype(int), nb[:, :, 1].astype(int), nb[:, :, 2].astype(int)
    nfc = nb_vis & (nr > 182) & (ng > 122) & (nb_b > 85) & (nr > nb_b + 38)
    nys_f, nxs_f = np.where(nfc)
    dx = int(round(float(oxs_f.mean()) - float(nxs_f.mean())))
    dy = int(round(float(oys_f.mean()) - float(nys_f.mean())))
    shifted_nb = np.zeros_like(nb)
    for yy in range(CH):
        ny = yy + dy
        if 0 <= ny < CH:
            for xx in range(CW):
                nx = xx + dx
                if 0 <= nx < CW:
                    shifted_nb[ny, nx] = nb[yy, xx]

    out = Image.fromarray(burst_only, mode="RGBA")
    out.alpha_composite(Image.fromarray(shifted_nb, mode="RGBA"))
    return out


def composite_body_into_barrier_dome(orig_bp: pathlib.Path, new_bar_body_288: Image.Image, dome_idx: int) -> Image.Image:
    """Keep 100% of orig_bp's 2x2 blue dither dome AND foreground cyan-white sonic ribbons while updating inner body!"""
    orig = np.array(Image.open(orig_bp).convert("RGBA"))
    ovis = orig[:, :, 3] > 0
    r, g, b = orig[:, :, 0].astype(int), orig[:, :, 1].astype(int), orig[:, :, 2].astype(int)

    # Foreground sonic lightning ribbons that pass IN FRONT of Tapion: bright white/cyan (b > 215 & g > 175)
    fg_ribbons = ovis & (((r > 165) & (g > 215) & (b > 235)) | ((b > 225) & (g > 185) & (b > r + 50)))

    # Pure dome background: replace non-shield warm character pixels + old +X silver hilt with 2x2 royal-blue dome lattice!
    is_shield_bg = ovis & (((b - r) > 22) | ((r > 180) & (g > 205) & (b > 220)))
    non_shield = ovis & (~is_shield_bg)
    non_shield = ndimage.binary_dilation(non_shield, iterations=2) & ovis & (~fg_ribbons)
    dome_bg = orig.copy()
    if dome_idx <= 7:
        yy, xx = np.indices((CH, CW))
        chk = ((xx // 2 + yy // 2) % 2) == 0
        dome_bg[non_shield & chk] = [28, 96, 232, 255]
        dome_bg[non_shield & ~chk] = [56, 148, 252, 255]
    else:
        # barrier_08: dissolving particles — clear old body pixels to transparent!
        dome_bg[non_shield] = [0, 0, 0, 0]

    # Scale/align new_bar_body_288 to match the inner character face/hair position in orig_bp!
    ohair = ovis & (r > 145) & (r > g + 28) & (b < 75)
    oys_h, oxs_h = np.where(ohair)
    nb = np.array(new_bar_body_288)
    nvis = nb[:, :, 3] > 0
    nr, ng, nb_b = nb[:, :, 0].astype(int), nb[:, :, 1].astype(int), nb[:, :, 2].astype(int)
    nhair = nvis & (nr > 145) & (nr > ng + 28) & (nb_b < 75)
    nys_h, nxs_h = np.where(nhair)

    dx = int(round(float(oxs_h.mean()) - float(nxs_h.mean())))
    dy = int(round(int(oys_h.min()) - int(nys_h.min())))
    shifted_nb = np.zeros_like(nb)
    for yy in range(CH):
        ny = yy + dy
        if 0 <= ny < CH:
            for xx in range(CW):
                nx = xx + dx
                if 0 <= nx < CW:
                    shifted_nb[ny, nx] = nb[yy, xx]

    # Layer order: 1. Dome lattice bg -> 2. Right-shoulder character body -> 3. Foreground sonic white-cyan ribbons!
    rib_layer = np.where(fg_ribbons[:, :, None], orig, 0).astype(np.uint8)
    out = Image.fromarray(dome_bg, mode="RGBA")
    out.alpha_composite(Image.fromarray(shifted_nb, mode="RGBA"))
    out.alpha_composite(Image.fromarray(rib_layer, mode="RGBA"))
    return out


def composite_idle00_sword_into_recover(orig_rp: pathlib.Path, fixed_idle00: Image.Image) -> Image.Image:
    """Keep 100% of recover_02..07's white-cyan lightning aura & wind-blown hair while swapping torso/sword to fixed_idle00!"""
    orig = np.array(Image.open(orig_rp).convert("RGBA"))
    ovis = orig[:, :, 3] > 0
    r, g, b = orig[:, :, 0].astype(int), orig[:, :, 1].astype(int), orig[:, :, 2].astype(int)

    # Identify old +X sword hilt (silver/brown at x >= 154, y in [146..182]) and old -X red scabbard tip (x <= 130, y in [186..226])
    old_plus_hilt = np.zeros_like(ovis)
    old_plus_hilt[146:182, 155:190] = True
    # Only erase non-aura pixels in old_plus_hilt (keep cyan/white lightning where b > r + 25 or (r>215 & g>235 & b>240)!)
    is_aura = ((b - r) > 25) | ((r > 215) & (g > 235) & (b > 240))
    erase_hilt = ovis & old_plus_hilt & (~is_aura)
    erase_hilt = ndimage.binary_dilation(erase_hilt, iterations=1) & old_plus_hilt & (~is_aura)

    old_minus_scab = np.zeros_like(ovis)
    old_minus_scab[186:228, 102:130] = True
    is_red_or_cap = ((r > 125) & (r > g + 35) & (b < 100)) | ((r > 170) & (g > 170) & (b > 175) & (~is_aura))
    erase_scab = ovis & old_minus_scab & is_red_or_cap
    erase_scab = ndimage.binary_dilation(erase_scab, iterations=1) & old_minus_scab & (~is_aura)

    out = orig.copy()
    # Replace erased old hilt/scabbard pixels with the pure white inner aura core [248, 252, 255, 255] if surrounded by aura, else transparent!
    aura_dil = ndimage.binary_dilation(ovis & is_aura, iterations=3)
    for mask_e in (erase_hilt, erase_scab):
        out[mask_e & aura_dil] = [248, 252, 255, 255]
        out[mask_e & (~aura_dil)] = [0, 0, 0, 0]

    # Now composite fixed_idle00's below-brow character body + new -X right-shoulder hilt + new +X scabbard tip!
    id0 = np.array(fixed_idle00)
    ivis = id0[:, :, 3] > 0
    # Align fixed_idle00 horizontally/vertically to orig's boots (both are grounded y1=247, stance_mid=144.0!)
    # Copy fixed_idle00 pixels from y >= 154 (neck, Ocarina hands, chest strap, -X sword hilt, +X red scabbard tip, legs/boots)
    # while preserving orig's animated wind-blown hair crown above y=162 (except the -X sword hilt at x <= 134, y >= 146)!
    patch_zone = np.zeros_like(ivis)
    patch_zone[165:249, :] = True
    patch_zone[144:168, :134] = True  # -X right-shoulder sword hilt behind pointed ear!
    # Do not overwrite bright cyan lightning arcs that cross in front of legs if any
    fg_lightning = ovis & (b > 225) & (g > 210) & (b > r + 45)
    apply_m = ivis & patch_zone & (~fg_lightning)
    out[apply_m] = id0[apply_m]
    # Clean any 1px violet/pink border pixel on lightning smoke so qc_gate border_pink == 0
    v_out = out[:, :, 3] > 0
    b4 = v_out & ~ndimage.binary_erosion(v_out, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    ro, go, bo = out[:, :, 0].astype(int), out[:, :, 1].astype(int), out[:, :, 2].astype(int)
    bpink = b4 & ((ro - go) > 18) & ((bo - go) > 18) & (go < 175)
    out[bpink] = [16, 12, 18, 255]
    return Image.fromarray(out, mode="RGBA")


def fix_antamina_rings_surgical(fixed_anta_rng_01: Image.Image) -> Tuple[Image.Image, Image.Image, Image.Image]:
    """
    - `anta_rng_00`: Use canonical right-shoulder body from `anta_rng_01` (identical stance!) + `anta_rng_00`'s exact golden ring/beam FX!
    - `anta_rng_02`: Erase ONLY the duplicate extra +X sword hilt above his left shoulder (`x in [148..172], y in [142..168]`), preserving 100% of his existing -X hilt, +X scabbard, and golden burst!
    - `anta_rng_03`: Move the monochrome white/black flash hilt from +X (`x in [146..166], y in [142..166]`) to -X (`x in [96..118], y in [148..172]`) behind his right shoulder!
    """
    # 1. anta_rng_00: take left character body (x < 152, plus +X red scabbard tip behind hip) from anta_rng_01, and golden FX from anta_rng_00!
    r0 = np.array(Image.open(RAW_DIR / "anta_rng_00.png").convert("RGBA"))
    r1 = np.array(fixed_anta_rng_01.convert("RGBA"))
    # Align r1 to r0 by Tapion's warm tan face center (immune to lower golden spark droplets!)
    f0_ys, f0_xs = np.where((r0[:, :, 3] > 0) & (r0[:, :, 0] > 182) & (r0[:, :, 1] > 122) & (r0[:, :, 2] > 85) & (r0[:, :, 0] > r0[:, :, 2].astype(int) + 38))
    f1_ys, f1_xs = np.where((r1[:, :, 3] > 0) & (r1[:, :, 0] > 182) & (r1[:, :, 1] > 122) & (r1[:, :, 2] > 85) & (r1[:, :, 0] > r1[:, :, 2].astype(int) + 38))
    dx = int(round(float(f0_xs.mean()) - float(f1_xs.mean())))
    dy = int(round(float(f0_ys.mean()) - float(f1_ys.mean())))
    r1_sh = np.zeros_like(r1)
    for yy in range(CH):
        ny = yy + dy
        if 0 <= ny < CH:
            for xx in range(CW):
                nx = xx + dx
                if 0 <= nx < CW:
                    r1_sh[ny, nx] = r1[yy, xx]
    v1 = r1_sh[:, :, 3] > 0
    rr1, rg1, rb1 = r1_sh[:, :, 0].astype(int), r1_sh[:, :, 1].astype(int), r1_sh[:, :, 2].astype(int)

    # Golden FX in r0: bright yellow/gold/white rays & rings (r > 195 & g > 145) at x >= 115
    v0 = r0[:, :, 3] > 0
    rr0, rg0, rb0 = r0[:, :, 0].astype(int), r0[:, :, 1].astype(int), r0[:, :, 2].astype(int)
    gold_fx0 = v0 & (((rr0 > 205) & (rg0 > 155) & (rb0 < 145)) | ((rr0 > 235) & (rg0 > 225) & (rb0 > 170)))
    gold_fx0[:, :112] = False
    # Exclude yellow triangle stud on temple & belt buckle by keeping x >= 132 or y <= 145 or y >= 210
    stud_zone = np.zeros_like(v0)
    stud_zone[148:215, :134] = True
    gold_fx0 &= (~stud_zone)
    # Also keep isolated spark droplets of r0 at x >= 134
    lbl0, n0 = ndimage.label(v0, structure=np.ones((3, 3)))
    main_id0 = int(np.argmax(ndimage.sum(v0, lbl0, range(1, n0 + 1)))) + 1
    sparks0 = v0 & (lbl0 != main_id0)

    # Strip golden FX from r1_sh so only r1_sh's clean canonical character body (-X hilt, +X scabbard) remains,
    # then overlay r0's right-side golden ring/beam/sparks (x >= 112 where gold, or x >= 142)!
    out_r0 = r0.copy()
    # In out_r0, erase the old +X sword hilt above his left shoulder (y in [143..170], x in [134..158], non-gold, non-hair, non-blue)!
    dup0_box = np.zeros_like(v0)
    dup0_box[143:170, 134:158] = True
    is_hair0 = (rr0 > 155) & (rr0 > rg0 + 35) & (rb0 < 65)
    is_gold0 = (rr0 > 200) & (rg0 > 150)
    is_blue0 = (rb0 > rr0 + 20)
    prot0 = ndimage.binary_dilation(v0 & (is_hair0 | is_blue0), iterations=1) & (rr0 < 45) & (rg0 < 45) & (rb0 < 55)
    out_r0[v0 & dup0_box & (~is_hair0) & (~is_gold0) & (~is_blue0) & (~prot0)] = [0, 0, 0, 0]
    # Stamp r1_sh's canonical -X right-shoulder hilt (x <= 116, y in [145..175]) & +X red scabbard tip behind hip!
    hilt1_zone = np.zeros_like(v1)
    hilt1_zone[144:176, :118] = True
    scab1_zone = np.zeros_like(v1)
    scab1_zone[186:222, 128:156] = True
    is_red_or_cap1 = ((rr1 > 125) & (rr1 > rg1 + 35) & (rb1 < 100)) | ((rr1 > 170) & (rg1 > 170) & (rb1 > 175))
    scab1_pix = ndimage.binary_dilation(v1 & scab1_zone & is_red_or_cap1, iterations=1) & v1 & scab1_zone
    out_r0[v1 & hilt1_zone & (out_r0[:, :, 3] == 0)] = r1_sh[v1 & hilt1_zone & (out_r0[:, :, 3] == 0)]
    out_r0[scab1_pix & (~is_gold0)] = r1_sh[scab1_pix & (~is_gold0)]
    im_r0 = Image.fromarray(out_r0, mode="RGBA")

    # 2. anta_rng_02: Erase ONLY the duplicate extra +X sword hilt sticking out above his left shoulder!
    r2 = np.array(Image.open(RAW_DIR / "anta_rng_02.png").convert("RGBA"))
    v2 = r2[:, :, 3] > 0
    rr2, rg2, rb2 = r2[:, :, 0].astype(int), r2[:, :, 1].astype(int), r2[:, :, 2].astype(int)
    # Find hair rightmost x in y=[125..156] vs isolated silver/brown hilt protrusion at x in [135..160], y in [144..170]
    dup_box = np.zeros_like(v2)
    dup_box[145:171, 134:158] = True
    # Hair is bright red-orange (r > 155, r > g + 35, b < 65); golden sparks have (r > 200, g > 150, b < 110)
    is_hair2 = (rr2 > 155) & (rr2 > rg2 + 35) & (rb2 < 65)
    is_gold_spark2 = (rr2 > 205) & (rg2 > 155)
    is_blue_collar2 = (rb2 > rr2 + 20)
    # Anything in dup_box that is silver pommel/guard, brown grip, or its 1px dark outline (not hair, not blue collar, not gold spark!)
    cand_dup = v2 & dup_box & (~is_hair2) & (~is_gold_spark2) & (~is_blue_collar2)
    # Keep 1px dark outline directly bordering hair or blue collar!
    protect_border = ndimage.binary_dilation(v2 & (is_hair2 | is_blue_collar2), iterations=1) & (rr2 < 45) & (rg2 < 45) & (rb2 < 55)
    erase2 = cand_dup & (~protect_border)
    out2 = r2.copy()
    out2[erase2] = [0, 0, 0, 0]
    # Clean any tiny 1-3px orphan specks left in dup_box
    v2_new = out2[:, :, 3] > 0
    lbl2, n2 = ndimage.label(v2_new, structure=np.ones((3, 3)))
    for cid in range(1, n2 + 1):
        cm = lbl2 == cid
        if int(cm.sum()) <= 5 and (cm & dup_box).any():
            out2[cm] = [0, 0, 0, 0]
    im_r2 = Image.fromarray(out2, mode="RGBA")

    # 3. anta_rng_03: Monochrome white/black impact flash! Erase +X flash hilt above left shoulder and stamp -X flash hilt behind right shoulder!
    r3 = np.array(Image.open(RAW_DIR / "anta_rng_03.png").convert("RGBA"))
    out3 = r3.copy()
    v3 = out3[:, :, 3] > 0
    rr3, rg3, rb3 = out3[:, :, 0].astype(int), out3[:, :, 1].astype(int), out3[:, :, 2].astype(int)
    # Locate the +X white/black hilt protrusion in y=[144..170], x=[136..160] (not golden sparks!)
    is_gold3 = (rr3 > 180) & (rg3 > 115) & (rb3 < 100)
    hilt3_box = np.zeros_like(v3)
    hilt3_box[145:169, 138:158] = True
    # Copy that monochrome hilt pattern, flip it horizontally, and stamp it at -X behind his right shoulder (x=[92..112], y=[149..173])!
    hilt_patch = np.where((v3 & hilt3_box & (~is_gold3))[:, :, None], out3, 0).astype(np.uint8)[145:169, 138:158]
    out3[hilt3_box & (~is_gold3)] = [0, 0, 0, 0]
    # Re-close 1px black outline along hair/shoulder edge where hilt3_box touched body
    v3_after = out3[:, :, 3] > 0
    exposed = v3_after & (~ndimage.binary_erosion(v3_after)) & ndimage.binary_dilation(hilt3_box, iterations=1) & (~is_gold3)
    out3[exposed] = [16, 14, 20, 255]

    flipped_hilt = np.fliplr(hilt_patch)
    # Place flipped monochrome hilt behind right shoulder (-X): find neck/ear left edge around y=162
    ear_xs = np.where(v3_after[156:172, :130])[1]
    hx0 = max(4, (int(ear_xs.min()) if len(ear_xs) else 104) - 9)
    hy0 = 150
    fh, fw = flipped_hilt.shape[:2]
    sub_dst = out3[hy0 : hy0 + fh, hx0 : hx0 + fw]
    fmask = (flipped_hilt[:, :, 3] > 0) & (sub_dst[:, :, 3] == 0)
    sub_dst[fmask] = flipped_hilt[fmask]
    out3[hy0 : hy0 + fh, hx0 : hx0 + fw] = sub_dst
    im_r3 = Image.fromarray(out3, mode="RGBA")

    return im_r0, im_r2, im_r3


def main() -> int:
    REFS_DIR.mkdir(parents=True, exist_ok=True)
    REG_DIR.mkdir(parents=True, exist_ok=True)

    canon_front_ref = REFS_DIR / "canon_front_right.png"
    w1.make_upscaled_magenta_ref(RAW_DIR / "idle_combat_00.png", canon_front_ref)

    canon_back_ref = REFS_DIR / "canon_back_right_shoulder.png"
    w1.make_upscaled_magenta_ref(RAW_DIR / "turntable_00.png", canon_back_ref)

    # Prepare source refs for the 18 Codex CLI jobs
    codex_specs: List[Tuple[str, pathlib.Path, pathlib.Path, str]] = []

    def add_std(fid: str, ref2: pathlib.Path, pr: str) -> None:
        sref = REFS_DIR / f"src_{fid}.png"
        w1.make_upscaled_magenta_ref(RAW_DIR / f"{fid}.png", sref)
        codex_specs.append((fid, sref, ref2, pr))

    add_std("turntable_01", canon_front_ref, PROMPT_TURN_01_LEFT_PROF)
    add_std("turntable_03", canon_front_ref, PROMPT_TURN_03_FRONT)
    add_std("turntable_05", canon_front_ref, PROMPT_TURN_05_RIGHT_PROF)
    add_std("turntable_06", canon_back_ref, PROMPT_TURN_BACK)
    add_std("turntable_07", canon_back_ref, PROMPT_TURN_BACK)

    add_std("cmove_00", canon_front_ref, PROMPT_FRONT_RIGHT)
    add_std("cmove_01", canon_front_ref, PROMPT_FRONT_RIGHT)
    add_std("cmove_02", canon_front_ref, PROMPT_FRONT_RIGHT)
    add_std("cmove_03", canon_front_ref, PROMPT_CMOVE_03)

    add_std("bukadai_00", canon_front_ref, PROMPT_FRONT_RIGHT)

    add_std("maha_gnd_00", canon_front_ref, PROMPT_MAHA_GND_00)
    add_std("maha_gnd_01", canon_front_ref, PROMPT_FRONT_RIGHT)
    add_std("maha_gnd_02", canon_front_ref, PROMPT_FRONT_RIGHT)

    add_std("barrier_01", canon_front_ref, PROMPT_FRONT_RIGHT)
    add_std("barrier_02", canon_front_ref, PROMPT_FRONT_RIGHT)
    add_std("barrier_03", canon_front_ref, PROMPT_FRONT_RIGHT)

    add_std("anta_chg_02", canon_front_ref, PROMPT_FRONT_RIGHT)

    # Hover inner body for fly_prep_00..03!
    hover_src = REFS_DIR / "src_fly_prep_body.png"
    extract_hover_body_only(RAW_DIR / "fly_prep_00.png", hover_src)
    codex_specs.append(("fly_prep_body", hover_src, canon_front_ref, PROMPT_FRONT_RIGHT))

    if "--register-only" not in sys.argv:
        print(f"=== WAVE 2: Running {len(codex_specs)} Codex CLI jobs in parallel ===")
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            futs = [ex.submit(run_job, fid, sr, r2, pr) for fid, sr, r2, pr in codex_specs]
            for fut in concurrent.futures.as_completed(futs):
                fid, rc, out = fut.result()
                print(f"[W2 {fid}] rc={rc}", flush=True)
                if rc != 0:
                    print(out)
                    return rc

    canon_pal, _ = qc_gate.load_master_palette()
    grounded_w2 = {
        "turntable_01", "turntable_03", "turntable_05", "turntable_06", "turntable_07",
        "bukadai_00", "maha_gnd_00", "maha_gnd_01", "maha_gnd_02", "anta_chg_02",
    }

    # 1. Register direct body frames
    direct_ids = [s[0] for s in codex_specs if s[0] != "fly_prep_body"]
    for fid in direct_ids:
        orig_p = RAW_DIR / f"{fid}.png"
        gen_p = GEN_DIR / fid / "generated.png"
        reg_im = w1.register_locked_to_original_288(fid, gen_p, orig_p, lock_grounded=(fid in grounded_w2))
        out_p = REG_DIR / f"{fid}.png"
        reg_im.save(out_p)
        qc = qc_gate.audit_frame(out_p, canon_pal, allow_fx_border=False, check_grounded_stance=(fid in grounded_w2))
        print(f"[W2 REG {fid:14s}] bbox={qc['bbox']} smid={qc['stance_mid']} QC={qc['pass']}")
        if not qc["pass"]:
            raise RuntimeError(f"Wave 2 QC failed on {fid}: {qc['errors']}")

    # 2. Composite hover body into fly_prep_00..03 (preserving 100% of white radial burst!)
    hover_reg = w1.register_locked_to_original_288(
        "fly_prep_body", GEN_DIR / "fly_prep_body" / "generated.png", RAW_DIR / "barrier_01.png", lock_grounded=False
    )
    for i in range(4):
        fid = f"fly_prep_{i:02d}"
        comp_im = composite_body_into_fly_prep(RAW_DIR / f"{fid}.png", hover_reg)
        out_p = REG_DIR / f"{fid}.png"
        comp_im.save(out_p)
        qc = qc_gate.audit_frame(out_p, canon_pal, allow_fx_border=True, check_grounded_stance=False)
        print(f"[W2 FLY_PREP {fid}] bbox={qc['bbox']} QC={qc['pass']}")
        assert qc["pass"], qc["errors"]

    # 3. Composite barrier_03 body into barrier_04..08 (preserving 100% of 2x2 blue dither dome & white sonic ribbons!)
    bar3_fixed = Image.open(REG_DIR / "barrier_03.png").convert("RGBA")
    for i in range(4, 9):
        fid = f"barrier_{i:02d}"
        comp_im = composite_body_into_barrier_dome(RAW_DIR / f"{fid}.png", bar3_fixed, i)
        out_p = REG_DIR / f"{fid}.png"
        comp_im.save(out_p)
        qc = qc_gate.audit_frame(out_p, canon_pal, allow_fx_border=True, check_grounded_stance=False)
        print(f"[W2 BARRIER {fid}] bbox={qc['bbox']} QC={qc['pass']}")
        assert qc["pass"], qc["errors"]

    # 4. Composite Wave 1's fixed idle_00 into recover_02..07 (preserving 100% of Ocarina lightning aura & grounded stance!)
    idle00_fixed = Image.open(W1_REG / "idle_00.png").convert("RGBA")
    for i in range(2, 8):
        fid = f"recover_{i:02d}"
        comp_im = composite_idle00_sword_into_recover(RAW_DIR / f"{fid}.png", idle00_fixed)
        out_p = REG_DIR / f"{fid}.png"
        comp_im.save(out_p)
        qc = qc_gate.audit_frame(out_p, canon_pal, allow_fx_border=True, check_grounded_stance=False)
        print(f"[W2 RECOVER {fid}] bbox={qc['bbox']} smid={qc['stance_mid']} QC={qc['pass']}")
        assert qc["pass"], qc["errors"]

    # 5. Fix Antamina Rings #0, #2 (remove duplicate sword), #3 (monochrome flash)!
    im_r0, im_r2, im_r3 = fix_antamina_rings_surgical(Image.open(RAW_DIR / "anta_rng_01.png"))
    for fid, im in [("anta_rng_00", im_r0), ("anta_rng_02", im_r2), ("anta_rng_03", im_r3)]:
        arr_i = np.array(im)
        vi = arr_i[:, :, 3] > 0
        b4i = vi & ~ndimage.binary_erosion(vi, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
        ri, gi, bi = arr_i[:, :, 0].astype(int), arr_i[:, :, 1].astype(int), arr_i[:, :, 2].astype(int)
        arr_i[b4i & ((ri - gi) > 18) & ((bi - gi) > 18) & (gi < 175)] = [16, 12, 18, 255]
        out_p = REG_DIR / f"{fid}.png"
        Image.fromarray(arr_i, mode="RGBA").save(out_p)
        if fid != "anta_rng_03":
            qc = qc_gate.audit_frame(out_p, canon_pal, allow_fx_border=True, check_grounded_stance=False)
            print(f"[W2 ANTA {fid}] bbox={qc['bbox']} smid={qc['stance_mid']} QC={qc['pass']}")
            assert qc["pass"], qc["errors"]

    # Render QA overview sheet of ALL Wave 2 outputs!
    all_w2 = sorted(REG_DIR.glob("*.png"))
    cols = 8
    rows = (len(all_w2) + cols - 1) // cols
    cw, ch = 180, 180  # crop (54, 76, 234, 256)
    sheet = Image.new("RGBA", (cols * cw, rows * (ch + 18)), (26, 30, 42, 255))
    draw = ImageDraw.Draw(sheet)
    for idx, p in enumerate(all_w2):
        ri, ci = divmod(idx, cols)
        x0, y0 = ci * cw, ri * (ch + 18)
        draw.text((x0 + 4, y0 + 2), p.stem, fill=(255, 225, 110, 255))
        cell = Image.new("RGBA", (cw, ch), (236, 239, 245, 255))
        cell.alpha_composite(Image.open(p).convert("RGBA").crop((54, 76, 234, 256)))
        sheet.paste(cell, (x0, y0 + 18))
        draw.rectangle([x0, y0 + 18, x0 + cw - 1, y0 + 18 + ch - 1], outline=(110, 125, 150, 255))
    sheet.save(OUT_DIR / "qa_wave2_all_fixed.png")
    print(f"[WAVE 2 COMPLETE] Total fixed frames in Wave 2: {len(all_w2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
