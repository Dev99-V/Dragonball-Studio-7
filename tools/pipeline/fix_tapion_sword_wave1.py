#!/usr/bin/env python3
"""
DR7-Studio — Tapion Canonical Right-Shoulder Sword Fix — WAVE 1 (21 Unique Frames):
  - Todo #1 & #6: `idle` (`idle_04`, `idle_03`, `idle_02`, `idle_00`, `idle_01`; `idle_03` = `combat_enter #0` & `barrier_00`;
    `idle_04` = `turntable_04` & `recover_00`; `idle_00` = `recover_01`).
  - Todo #2: `walk` (`walk_00..07` — 8 frames, equal 125px height, Goku 3-stage leg cycle).
  - Todo #3: `jump` (`jump_00..04` — 5 unique frames, `jump_05 = jump_00`, idle-synced scale).
  - Todo #4: `hit` (`hit_00, hit_01, hit_02` — 3 frames, `ko #0 = hit_02`).

Canonical Right-Shoulder Sword Wearing Law (Owner 2026-11-25, matching `attack_light #0` / `idle_combat_00`):
  When Tapion faces front-right (+X):
    1. SWORD HILT (round white-silver pommel + brown leather grip + white-silver crossguard) MUST protrude
       diagonally UP-LEFT (-X, on the LEFT side of the image behind his pointed ear, over his ANATOMICAL RIGHT SHOULDER).
       ZERO sword hilt on the right side (+X) beneath his front hair bangs!
    2. CHEST STRAP (diagonal brown leather strap with 2 round white-silver clasps) runs from his RIGHT SHOULDER
       (upper-left, -X) diagonally DOWN-RIGHT (+X) across his blue tunic toward his left hip/waist.
    3. CRIMSON-RED SCABBARD TIP (with round white-silver end cap) peeks out diagonally DOWN-RIGHT (+X, on the
       RIGHT side of the image behind his far left hip/coat flap). ZERO red scabbard tip on the left side (-X)!
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
import qc_tapion_master_gate as qc_gate  # noqa: E402

ROUTE_MEDIA = ROOT / ".agent" / "skills" / "generate2dmedia" / "scripts" / "route_media.py"
RAW_DIR = ROOT / "review" / "tapion_demo" / "source" / "raw_frames"
OUT_DIR = ROOT / "work" / "characters" / "tapion" / "sword_fix_w1"
REFS_DIR = OUT_DIR / "refs_1024"
PROMPTS_DIR = OUT_DIR / "prompts"
GEN_DIR = OUT_DIR / "generated"
REG_DIR = OUT_DIR / "registered_288"

CW, CH = 288, 288


def make_upscaled_magenta_ref(src_288: pathlib.Path, out_1024: pathlib.Path) -> None:
    """Upscale an approved 288x288 sprite 5x Nearest onto a clean 1024x1024 #FF00FF magenta canvas."""
    im = Image.open(src_288).convert("RGBA")
    arr = np.array(im)
    vis = arr[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop = im.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    scale = min(720.0 / max(1, crop.width), 720.0 / max(1, crop.height))
    nw, nh = int(round(crop.width * scale)), int(round(crop.height * scale))
    up = crop.resize((nw, nh), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (1024, 1024), (255, 0, 255, 255))
    canvas.alpha_composite(up, ((1024 - nw) // 2, (1024 - nh) // 2))
    out_1024.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_1024)


CANON_SWORD_RULE = """CRITICAL SWORD-WEARING DIRECTION EDIT (ONLY CHANGE THE SWORD, SCABBARD & CHEST STRAP — KEEP 100% OF POSE, FACE, HAIR, HANDS, ARMS & LEGS IDENTICAL TO REFERENCE IMAGE 1!):

Look at Reference Image 2 (the canonical sword-wearing reference): the character wears his sword strapped across his back from HIS ANATOMICAL RIGHT SHOULDER (LEFT side of image, -X) diagonally down to HIS ANATOMICAL LEFT HIP (RIGHT side of image, +X).

Apply ONLY the following exact anatomical correction to Reference Image 1:
1. MOVE SWORD HILT TO LEFT SIDE OF IMAGE (-X, OVER HIS RIGHT SHOULDER):
   - Completely REMOVE any sword hilt/pommel/guard from the right side (+X) beneath his front orange hair bangs!
   - Place the exact silver-pommeled brown sword hilt + curved white-silver crossguard protruding diagonally UP-LEFT (-X) just behind his pointed ear/neck over his right shoulder (matching Reference Image 2's exact hilt angle and position!).
2. FLIP DIAGONAL CHEST LEATHER STRAP TO MATCH (-X -> +X):
   - Run the brown leather chest strap (with the round white-silver clasps) diagonally from his RIGHT SHOULDER (upper-left, -X) DOWN-RIGHT (+X) toward his left waist/hip!
3. MOVE CRIMSON-RED SCABBARD TIP TO RIGHT SIDE OF IMAGE (+X, BEHIND HIS LEFT HIP):
   - Completely REMOVE any crimson-red scabbard tip / white silver cap from the lower-left (-X) behind his right hand/hip!
   - Place the crimson-red scabbard lower tip + round white-silver end cap peeking out diagonally DOWN-RIGHT (+X) behind his far left hip/coat edge (matching Reference Image 2!).
4. STRICT POSE & PIXEL PRESERVATION:
   - Keep 100% of Reference Image 1's exact head angle, face, eyes, hair spikes, arms, hands (including Ocarina flute if playing flute!), torso posture, leg positions, and boot placement!
   - Razor-sharp 16-bit pixel-art sprite with clean 1px solid dark outer outline on flat solid #FF00FF pure magenta background. Zero blur, zero glow, zero ground shadow."""


PROMPT_HIT_02_SPECIAL = """Fix the sword & crimson scabbard wearing position on Reference Image 1 so the sheathed sword is worn CLEANLY BEHIND HIS BACK (matching Reference Image 2's canonical right-shoulder-to-left-hip back mount), on a solid flat #FF00FF pure magenta background!

CRITICAL REQUIREMENTS FOR KNOCKED-BACK POSE (`hit_02`):
1. SWORD & SCABBARD MUST BE BEHIND HIS BACK — NOT IN FRONT OF HIS CHEST/ARM:
   - In Reference Image 1, the red scabbard was mistakenly drawn lying on top of his front chest/ribs. Move the sheathed sword BEHIND his back!
   - His sword hilt (round white-silver pommel + brown grip + white-silver crossguard) protrudes UP-LEFT (-X) from behind his right shoulder/neck (behind his pointed ear and red-orange hair).
   - Most of the scabbard is hidden behind his arched torso, with ONLY the crimson-red scabbard tip + round white-silver end cap peeking out behind his lower back / far left hip (+X, lower-right behind his blue tabard/hip).
   - Across his blue chest tunic, draw ONLY the diagonal brown leather chest strap with its round silver clasps (running from his right shoulder down-right toward his left hip).
2. KEEP 100% OF REFERENCE IMAGE 1'S KNOCKED-BACK POSE:
   - Keep his exact knocked-back diagonal body angle, pained open-mouth expression, spiky red-orange hair, outstretched left arm/hand, and legs/boots identical to Reference Image 1!
   - Razor-sharp 16-bit pixel art, clean 1px dark outer outline, flat #FF00FF pure magenta background."""


WAVE1_FRAMES = [
    # 5 idle frames
    "idle_04", "idle_03", "idle_02", "idle_00", "idle_01",
    # 8 walk frames
    "walk_00", "walk_01", "walk_02", "walk_03", "walk_04", "walk_05", "walk_06", "walk_07",
    # 5 jump frames
    "jump_00", "jump_01", "jump_02", "jump_03", "jump_04",
    # 3 hit frames
    "hit_00", "hit_01", "hit_02",
]


def run_codex_job(fid: str, canon_ref_path: pathlib.Path) -> Tuple[str, int, str]:
    src_ref = REFS_DIR / f"src_{fid}.png"
    make_upscaled_magenta_ref(RAW_DIR / f"{fid}.png", src_ref)

    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    GEN_DIR.mkdir(parents=True, exist_ok=True)
    prompt = PROMPT_HIT_02_SPECIAL if fid == "hit_02" else CANON_SWORD_RULE
    if fid in ("idle_00", "idle_01", "idle_02"):
        prompt += "\n- IMPORTANT FOR OCARINA FLUTE POSE: Keep both hands holding the silver Ocarina flute near his mouth/chest EXACTLY as in Reference Image 1!"

    pfile = PROMPTS_DIR / f"{fid}.txt"
    pfile.write_text(prompt + "\n", encoding="utf-8")
    out_d = GEN_DIR / fid
    if out_d.exists():
        shutil.rmtree(out_d)

    cmd = [
        sys.executable,
        str(ROUTE_MEDIA),
        "image",
        "--route",
        "codex-cli",
        "--prompt-file",
        str(pfile),
        "--reference",
        str(src_ref),
        "--reference",
        str(canon_ref_path),
        "--size",
        "1024x1024",
        "--out-dir",
        str(out_d),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return fid, proc.returncode, (proc.stdout + "\n" + proc.stderr).strip()


def register_locked_to_original_288(fid: str, gen_png: pathlib.Path, orig_png: pathlib.Path, lock_grounded: bool) -> Image.Image:
    """Register edited 1024x1024 sprite onto 288x288 locked to the exact height, y1, and head/boots RGB-L1 of orig_png!"""
    orig = np.array(Image.open(orig_png).convert("RGBA"))
    ovis = orig[:, :, 3] > 0
    oys, oxs = np.where(ovis)
    orig_h = int(oys.max() - oys.min() + 1)
    orig_y1 = int(oys.max())

    # Unchanged anchor regions on orig: hair crown + tan face + boots!
    or_, og_, ob_ = orig[:, :, 0].astype(int), orig[:, :, 1].astype(int), orig[:, :, 2].astype(int)
    o_face = ovis & (or_ > 182) & (og_ > 122) & (ob_ > 85) & (or_ > ob_ + 38)
    o_boots = ovis & (or_ > 110) & (og_ > 55) & (ob_ < 75) & (or_ > ob_ + 35)
    o_hair = ovis & (or_ > 145) & (or_ > og_ + 28) & (ob_ < 72)
    o_anchor_mask = o_face | o_boots | o_hair

    keyed = p1b.key_magenta_2stage(Image.open(gen_png), allow_fx=False)
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop = Image.fromarray(keyed[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], mode="RGBA")

    # Search exact height: for idle & walk keep EXACT orig_h (e.g. 125px!), for jump/hit allow ±2px if hilt top shifted y0
    h_candidates = [orig_h] if (fid.startswith("idle_") or fid.startswith("walk_")) else list(range(orig_h - 2, orig_h + 4))

    best_im = None
    best_score = 1e12
    for th in h_candidates:
        scale = float(th) / max(1.0, float(crop.height))
        nw = max(16, int(round(crop.width * scale)))
        nh = max(16, int(round(crop.height * scale)))
        resized = crop.resize((nw, nh), Image.Resampling.NEAREST)
        rarr = p1b.post_clean_resized(np.array(resized, dtype=np.uint8), allow_fx=False)
        rmask = rarr[:, :, 3] > 0
        rys, rxs = np.where(rmask)
        ry1 = int(rys.max())

        base_py = orig_y1 - ry1
        if lock_grounded:
            f_rows = rmask[max(0, ry1 - 7) : ry1 + 1, :]
            fxs = np.where(f_rows)[1]
            smid_loc = 0.5 * (int(fxs.min()) + int(fxs.max())) if len(fxs) else float(np.median(rxs))
            base_px = int(round(144.0 - smid_loc))
            dx_range = [-1, 0, 1]
            dy_range = [0]
        else:
            base_px = int(round(float(np.median(oxs)) - float(np.median(rxs))))
            dx_range = list(range(-5, 6))
            dy_range = list(range(-2, 3)) if not fid.startswith("walk_") else [0]

        for dy in dy_range:
            for dx in dx_range:
                px = max(2, min(CW - nw - 2, base_px + dx))
                py = max(2, min(CH - nh - 2, base_py + dy))
                canvas = np.zeros((CH, CW, 4), dtype=np.uint8)
                canvas[py : py + nh, px : px + nw] = rarr
                if lock_grounded:
                    cvis = canvas[:, :, 3] > 0
                    cy1 = int(np.where(cvis)[0].max())
                    cfxs = np.where(cvis[max(0, cy1 - 7) : cy1 + 1, :])[1]
                    c_smid = 0.5 * (int(cfxs.min()) + int(cfxs.max()))
                    if abs(c_smid - 144.0) > 1.0 or cy1 != 247:
                        continue
                rgb_diff = np.abs(orig[:, :, :3].astype(float) - canvas[:, :, :3].astype(float)).mean(axis=2)
                score = float(rgb_diff[o_anchor_mask].mean())
                if score < best_score:
                    best_score = score
                    best_im = Image.fromarray(canvas, mode="RGBA")

    assert best_im is not None, f"Failed registration for {fid}"
    return best_im


def verify_right_shoulder_hilt(arr: np.ndarray, fid: str) -> Dict[str, int]:
    """Verify silver pommel/guard pixels exist on -X (x < face_cx - 8) and NOT on +X (x > face_cx + 10) above shoulders!"""
    vis = arr[:, :, 3] > 0
    r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
    face = vis & (r > 182) & (g > 122) & (b > 85) & (r > b + 38)
    fys, fxs = np.where(face)
    fcx = float(fxs.mean()) if len(fxs) else 144.0
    chin_y = int(fys.max()) if len(fys) else 182

    # Silver pommel/guard above chin_y + 10
    silver = vis & (r > 170) & (g > 170) & (b > 178) & (np.abs(r - b) < 28)
    upper = np.zeros_like(vis)
    upper[: min(CH, chin_y + 10), :] = True
    # Note: for Ocarina flute poses (idle_00..02), silver flute is near mouth (fcx - 10 .. fcx + 14, chin_y - 10 .. chin_y + 8)
    hilt_zone_left = silver & upper
    hilt_zone_left[:, int(round(fcx - 6)) :] = False

    hilt_zone_right = silver & upper
    hilt_zone_right[:, : int(round(fcx + 13))] = False
    if fid in ("idle_00", "idle_01", "idle_02"):
        # Exclude lower flute area near mouth y >= chin_y - 8
        hilt_zone_right[max(0, chin_y - 8) :, :] = False

    # Also check crimson-red scabbard tip in lower body (y > chin_y + 8) on +X vs -X!
    lower = np.zeros_like(vis)
    lower[min(CH, chin_y + 10) :, :] = True
    red_scab = vis & lower & (r > 125) & (r > g + 45) & (b > 20) & (b < 95)
    scab_left = int(red_scab[:, : int(round(fcx - 10))].sum())
    scab_right = int(red_scab[:, int(round(fcx + 4)) :].sum())
    return {
        "hilt_minus_x": int(hilt_zone_left.sum()),
        "hilt_plus_x": int(hilt_zone_right.sum()),
        "scab_minus_x": scab_left,
        "scab_plus_x": scab_right,
    }


def main() -> int:
    REFS_DIR.mkdir(parents=True, exist_ok=True)
    REG_DIR.mkdir(parents=True, exist_ok=True)

    # Canonical sword-wearing reference: idle_combat_00 (crystal-clear right-shoulder -X hilt & +X crimson scabbard tip!)
    canon_ref = REFS_DIR / "canon_right_shoulder_ref.png"
    make_upscaled_magenta_ref(RAW_DIR / "idle_combat_00.png", canon_ref)

    # Step 1: Generate idle_04 FIRST so it becomes the canonical standing reference too!
    print("=== WAVE 1A: Generating canonical standing master `idle_04` ===")
    fid0, rc0, out0 = run_codex_job("idle_04", canon_ref)
    print(f"[{fid0}] rc={rc0}\n{out0}\n", flush=True)
    if rc0 != 0:
        return rc0

    idle04_gen = GEN_DIR / "idle_04" / "generated.png"

    # Step 2: Generate remaining 20 frames in parallel (max_workers=6)!
    rem_frames = [f for f in WAVE1_FRAMES if f != "idle_04"]
    print(f"=== WAVE 1B: Generating {len(rem_frames)} locomotion/hit frames in parallel ===")
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        # Use new idle_04 for upright/walking/jumping poses and canon_ref for combat/hit poses!
        futs = [
            ex.submit(run_codex_job, fid, idle04_gen if (fid.startswith("idle_") or fid.startswith("walk_")) else canon_ref)
            for fid in rem_frames
        ]
        for fut in concurrent.futures.as_completed(futs):
            fid, rc, out = fut.result()
            print(f"[{fid}] rc={rc}", flush=True)
            if rc != 0:
                print(out)
                return rc

    # Step 3: Register all 21 frames locked 1:1 to original 288x288 scale & stance, run Master QC + Sword Direction QC!
    canon_pal, _ = qc_gate.load_master_palette()
    grounded_set = {"idle_04", "idle_03", "idle_02", "idle_00", "idle_01", "jump_00"}
    pairs_for_sheet = []

    for fid in WAVE1_FRAMES:
        orig_p = RAW_DIR / f"{fid}.png"
        gen_p = GEN_DIR / fid / "generated.png"
        reg_im = register_locked_to_original_288(fid, gen_p, orig_p, lock_grounded=(fid in grounded_set))
        out_p = REG_DIR / f"{fid}.png"
        reg_im.save(out_p)
        qc = qc_gate.audit_frame(out_p, canon_pal, allow_fx_border=False, check_grounded_stance=(fid in grounded_set and fid != "jump_00"))
        sw = verify_right_shoulder_hilt(np.array(reg_im), fid)
        print(f"[REG {fid:8s}] bbox={qc['bbox']} y1={qc['y1']} smid={qc['stance_mid']} QC={qc['pass']} sword={sw}")
        if not qc["pass"]:
            raise RuntimeError(f"Master QC failed on {fid}: {qc['errors']}")
        pairs_for_sheet.append((fid, Image.open(orig_p).convert("RGBA"), reg_im))

    # Render Before vs After comparison grid!
    cols = 7
    rows = (len(pairs_for_sheet) + cols - 1) // cols
    cw, ch = 128, 152  # crop (80, 104, 208, 256)
    sheet = Image.new("RGBA", (cols * cw * 2, rows * (ch + 20)), (26, 30, 42, 255))
    draw = ImageDraw.Draw(sheet)
    for idx, (fid, old_im, new_im) in enumerate(pairs_for_sheet):
        ri, ci = divmod(idx, cols)
        x0 = ci * cw * 2
        y0 = ri * (ch + 20)
        draw.text((x0 + 4, y0 + 3), f"{fid}: OLD -> NEW (-X hilt)", fill=(255, 225, 110, 255))
        for sub_i, im in enumerate((old_im, new_im)):
            cell = Image.new("RGBA", (cw, ch), (236, 239, 245, 255) if sub_i == 1 else (215, 220, 230, 255))
            cell.alpha_composite(im.crop((80, 104, 208, 256)))
            sheet.paste(cell, (x0 + sub_i * cw, y0 + 20))
            draw.rectangle([x0 + sub_i * cw, y0 + 20, x0 + (sub_i + 1) * cw - 1, y0 + 20 + ch - 1], outline=(100, 115, 140, 255))
    sheet.save(OUT_DIR / "qa_wave1_before_vs_after.png")
    print("[WAVE 1 COMPLETE] Saved qa_wave1_before_vs_after.png!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
