#!/usr/bin/env python3
"""
DR7-Studio — Tapion Empty Crimson-Red Scabbard Restoration & Canonical Orientation — WAVE 3 (30 Unique Frames):
Covers Todo Items #17, #18, #19, #20, #21, #22, #23:
  - `attack_light` (`atk1_01 [= atk3_00], atk1_03, atk1_04, atk1_05 [-> atk10_04]`).
  - `attack_2` (`atk2_00 [= atk7_00], atk2_01, atk2_02` front-right + `atk2_03, atk2_04` back view).
  - `attack_3` (`atk3_01, atk3_02, atk3_03, atk3_04 [= atk10_01]`; `atk3_00 = atk1_01`).
  - `attack_4` (`atk4_00` front-right + `atk4_01` back-view lunge).
  - `attack_5` (`atk5_01 [-> atk10_03], atk5_02`).
  - `attack_7` (`atk7_01` front-right + `atk7_02, atk7_03, atk7_04` back view; `atk7_00 = atk2_00`).
  - `attack_8` (`atk8_00` back view + `atk8_01, atk8_02, atk8_03, atk8_04 [= atk9_00]` front-right).
  - `attack_9` (`atk6_00 [= atk9_01], atk9_02, atk9_03, atk9_04`; `atk9_00 = atk8_04`).
  - `kentaima_cast` (`kenta_cast_00, kenta_cast_01, kenta_cast_02, kenta_cast_03`).
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
OUT_DIR = ROOT / "work" / "characters" / "tapion" / "sword_fix_w3"
REFS_DIR = OUT_DIR / "refs_1024"
PROMPTS_DIR = OUT_DIR / "prompts"
GEN_DIR = OUT_DIR / "generated"
REG_DIR = OUT_DIR / "registered_288"

CW, CH = 288, 288


PROMPT_EMPTY_SCAB_FRONT_RIGHT = """Add / fix ONLY the character's EMPTY CRIMSON-RED SWORD SCABBARD on his back in Reference Image 1 (matching Reference Image 2's canonical right-shoulder-to-left-hip back strap orientation, EXCEPT the scabbard is EMPTY because the sword is already drawn in his hand(s)!), on a solid flat #FF00FF pure magenta background!

CRITICAL ANATOMICAL SCABBARD RULES (FRONT-RIGHT VIEW):
1. EMPTY SCABBARD DIRECTION (FROM RIGHT SHOULDER -X DOWN-RIGHT TO LEFT HIP +X):
   - Because the sword is ALREADY in his hand(s), DO NOT draw a sword hilt/pommel/crossguard on his shoulder!
   - At UPPER-LEFT (-X, peeking out diagonally up-left just behind his right shoulder / pointed ear / blue scarf): draw the EMPTY MOUTH of the crimson-red scabbard (a short crimson-red scabbard top with its round white-silver throat collar ring, angled ~45° up-left).
   - At LOWER-RIGHT (+X, peeking out diagonally down-right behind his far left hip / ribs / waist): draw the LOWER END of the crimson-red scabbard with its round white-silver end cap!
   - NEVER draw a red scabbard pole sticking out backward-left (-X) behind his lower back or hanging vertically in front of his chest! Remove any backward-left (-X) red scabbard stub completely!
2. 100% PRESERVE POSE, TWO-HANDED/ONE-HANDED SWORD GRIP, BLADE & SLASH VFX:
   - Keep 100% of Reference Image 1's exact head, face, hair, arms, hands, drawn silver sword blade, white slash crescent, and cyan energy wave arc IDENTICAL in shape, position, and size!
   - Razor-sharp 16-bit pixel art with clean 1px dark outer outline on flat #FF00FF pure magenta background."""


PROMPT_EMPTY_SCAB_BACK_VIEW = """Add / fix ONLY the character's EMPTY CRIMSON-RED SWORD SCABBARD strapped diagonally across his BACK in Reference Image 1 (matching Reference Image 2's exact back-view scabbard diagonal!), on a solid flat #FF00FF pure magenta background!

CRITICAL ANATOMICAL SCABBARD RULES (BACK VIEW):
1. EMPTY SCABBARD ACROSS HIS BACK (FROM RIGHT SHOULDER +X DOWN-LEFT TO LEFT HIP -X):
   - In Reference Image 1, the character's BACK is facing the camera while he swings/thrusts his drawn sword.
   - Draw the FULL EMPTY CRIMSON-RED SCABBARD strapped diagonally across his back (over his orange/blue back tunic, underneath his hair spikes):
     * Upper-right (+X, near his anatomical right shoulder): white-silver empty scabbard mouth collar ring (NO sword hilt inside, because the sword is in his hands!).
     * Diagonal crimson-red scabbard body running from upper-right (+X) DOWN-LEFT (-X) across his spine.
     * Lower-left (-X, near his anatomical left hip): round white-silver scabbard tip cap!
2. 100% PRESERVE POSE, DRAWN SWORD & SLASH VFX:
   - Keep 100% of Reference Image 1's exact head, crimson/orange hair spikes, arms, drawn silver sword blade, white slash arc, cyan energy wave, and legs/boots IDENTICAL!
   - Razor-sharp 16-bit pixel art with clean 1px dark outer outline on flat #FF00FF pure magenta background."""


FRONT_RIGHT_IDS = [
    "atk1_01", "atk1_03", "atk1_04", "atk1_05",
    "atk2_00", "atk2_01", "atk2_02", "atk2_03", "atk2_04",
    "atk3_01", "atk3_02", "atk3_03", "atk3_04",
    "atk4_00",
    "atk5_01", "atk5_02",
    "atk6_00",
    "atk7_01", "atk7_02", "atk7_03", "atk7_04",
    "atk8_00", "atk8_01", "atk8_02", "atk8_03", "atk8_04",
    "atk9_02", "atk9_03", "atk9_04",
    "kenta_cast_00", "kenta_cast_01", "kenta_cast_02", "kenta_cast_03",
]

BACK_VIEW_IDS = [
    "atk4_01",
]


def make_back_scabbard_guide_ref(out_path: pathlib.Path) -> None:
    """Crop pose #4 (back view with empty crimson scabbard +X -> -X) from tapion/tấn công 2.png as Reference Image 2!"""
    sheet = Image.open(ROOT / "tapion" / "tấn công 2.png").convert("RGBA")
    sarr = np.array(sheet)
    bg = sarr[0, 0, :3].astype(int)
    # Last pose on the right of tấn công 2.png
    fg = np.abs(sarr[:, :, :3].astype(int) - bg).max(axis=2) > 10
    lbl_x, nx = ndimage.label(fg.any(axis=0))
    xs = np.where(lbl_x == nx)[0]
    x0, x1 = int(xs.min()), int(xs.max())
    ys = np.where(fg[:, x0 : x1 + 1].any(axis=1))[0]
    y0, y1 = int(ys.min()), int(ys.max())
    sub = sarr[y0 : y1 + 1, x0 : x1 + 1].copy()
    sub[~fg[y0 : y1 + 1, x0 : x1 + 1]] = [0, 0, 0, 0]
    pim = Image.fromarray(sub, mode="RGBA")
    sc = min(700.0 / pim.width, 700.0 / pim.height)
    up = pim.resize((int(round(pim.width * sc)), int(round(pim.height * sc))), Image.Resampling.NEAREST)
    c = Image.new("RGBA", (1024, 1024), (255, 0, 255, 255))
    c.alpha_composite(up, ((1024 - up.width) // 2, (1024 - up.height) // 2))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c.convert("RGB").save(out_path)


def preclean_wrong_scabbard_on_ref(fid: str, src_288: pathlib.Path, out_1024: pathlib.Path) -> None:
    """For frames that had a wrong backward-left (-X) red pole (`atk1_03`, `atk1_04`, `kenta_cast_00..03`, `atk4_01`),
    pre-erase the wrong red scabbard pixels before upscaling to 1024x1024 so Codex doesn't copy the wrong pole!"""
    arr = np.array(Image.open(src_288).convert("RGBA"))
    vis = arr[:, :, 3] > 0
    r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)

    if fid in ("atk1_03", "atk1_04", "kenta_cast_02", "kenta_cast_03", "kenta_cast_01"):
        # Erase crimson-red + white cap pole sticking out to the far left (x < 126, y in [150..205])
        face = vis & (r > 182) & (g > 122) & (b > 85) & (r > b + 38)
        fxs = np.where(face)[1]
        fcx = int(fxs.mean()) if len(fxs) else 146
        pole_zone = np.zeros_like(vis)
        pole_zone[138:208, : max(0, fcx - 18)] = True
        is_red_or_silver = ((r > 120) & (r > g + 35) & (b < 105)) | ((r > 170) & (g > 170) & (b > 175))
        # Keep hair (y < 166 & x > fcx - 28) and blue scarf (b > r + 25)
        erase = vis & pole_zone & is_red_or_silver
        erase = ndimage.binary_dilation(erase, iterations=1) & pole_zone & ~(b > r + 20) & ~((r > 165) & (g > 70) & (b < 55))
        arr[erase] = [0, 0, 0, 0]
        # Remove tiny orphan border pixels left behind
        v2 = arr[:, :, 3] > 0
        lbl, n = ndimage.label(v2, structure=np.ones((3, 3)))
        if n > 1:
            sizes = np.array(ndimage.sum(v2, lbl, range(1, n + 1)))
            main_c = int(np.argmax(sizes)) + 1
            for cid in range(1, n + 1):
                if cid != main_c and sizes[cid - 1] < 25 and (pole_zone & (lbl == cid)).any():
                    arr[lbl == cid] = [0, 0, 0, 0]
    elif fid == "kenta_cast_00":
        # Erase vertical red scabbard hanging on the right side (x >= 162, y in [156..204])
        rzone = np.zeros_like(vis)
        rzone[154:206, 160:188] = True
        is_red = (r > 120) & (r > g + 35) & (b < 105)
        erase = ndimage.binary_dilation(vis & rzone & is_red, iterations=1) & rzone
        arr[erase] = [0, 0, 0, 0]

    ys, xs = np.where(arr[:, :, 3] > 0)
    crop = Image.fromarray(arr[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], mode="RGBA")
    sc = min(720.0 / max(1, crop.width), 720.0 / max(1, crop.height))
    up = crop.resize((int(round(crop.width * sc)), int(round(crop.height * sc))), Image.Resampling.NEAREST)
    c = Image.new("RGBA", (1024, 1024), (255, 0, 255, 255))
    c.alpha_composite(up, ((1024 - up.width) // 2, (1024 - up.height) // 2))
    out_1024.parent.mkdir(parents=True, exist_ok=True)
    c.convert("RGB").save(out_1024)


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


def register_attack_preserving_fx(fid: str, gen_png: pathlib.Path, orig_png: pathlib.Path) -> Image.Image:
    """Register edited attack frame locked 1:1 to orig_png's head/boots AND preserve 100% of orig_png's cyan/white FX arcs!"""
    orig = np.array(Image.open(orig_png).convert("RGBA"))
    ovis = orig[:, :, 3] > 0
    oys, oxs = np.where(ovis)
    orig_h = int(oys.max() - oys.min() + 1)
    orig_y1 = int(oys.max())

    or_, og_, ob_ = orig[:, :, 0].astype(int), orig[:, :, 1].astype(int), orig[:, :, 2].astype(int)
    o_hair = ovis & (or_ > 145) & (or_ > og_ + 28) & (ob_ < 72)
    o_boots = ovis & (or_ > 110) & (og_ > 55) & (ob_ < 75) & (or_ > ob_ + 35)
    o_face = ovis & (or_ > 182) & (og_ > 122) & (ob_ > 85) & (or_ > ob_ + 38)
    anchor_m = o_hair | o_boots | o_face

    keyed = p1b.key_magenta_2stage(Image.open(gen_png), allow_fx=True)
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop = Image.fromarray(keyed[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], mode="RGBA")

    best_arr = None
    best_score = 1e12
    for th in range(max(48, orig_h - 4), min(276, orig_h + 5)):
        scale = min(float(th) / max(1.0, float(crop.height)), 274.0 / max(1.0, float(crop.width)), 268.0 / max(1.0, float(crop.height)))
        nw = max(16, int(round(crop.width * scale)))
        nh = max(16, int(round(crop.height * scale)))
        resized = crop.resize((nw, nh), Image.Resampling.NEAREST)
        rarr = p1b.post_clean_resized(np.array(resized, dtype=np.uint8), allow_fx=True)
        rys, rxs = np.where(rarr[:, :, 3] > 0)
        base_py = orig_y1 - int(rys.max())
        base_px = int(round(float(np.median(oxs)) - float(np.median(rxs))))
        for dy in range(-4, 5):
            for dx in range(-5, 6):
                px = max(2, min(CW - nw - 2, base_px + dx))
                py = max(2, min(CH - nh - 2, base_py + dy))
                canvas = np.zeros((CH, CW, 4), dtype=np.uint8)
                canvas[py : py + nh, px : px + nw] = rarr
                diff = np.abs(orig[:, :, :3].astype(float) - canvas[:, :, :3].astype(float)).mean(axis=2)
                sc_err = float(diff[anchor_m].mean())
                if sc_err < best_score:
                    best_score = sc_err
                    best_arr = canvas

    assert best_arr is not None
    # Preserve 100% of orig's cyan sword energy waves & detached cyan sparks on atk7/atk8/atk9/kenta_cast!
    if fid.startswith(("atk7_", "atk8_", "atk9_", "kenta_cast_")):
        cyan_fx = ovis & (((ob_ - or_) > 40) & (ob_ > 175) | ((or_ > 215) & (og_ > 235) & (ob_ > 245)))
        # Also include detached spark islands from orig
        lbl_o, n_o = ndimage.label(ovis, structure=np.ones((3, 3)))
        if n_o > 1:
            main_o = int(np.argmax(ndimage.sum(ovis, lbl_o, range(1, n_o + 1)))) + 1
            cyan_fx |= (ovis & (lbl_o != main_o))
        fx_layer = np.where(cyan_fx[:, :, None], orig, 0).astype(np.uint8)
        out_im = Image.fromarray(best_arr, mode="RGBA")
        out_im.alpha_composite(Image.fromarray(fx_layer, mode="RGBA"))
        return out_im

    return Image.fromarray(best_arr, mode="RGBA")


def main() -> int:
    REFS_DIR.mkdir(parents=True, exist_ok=True)
    REG_DIR.mkdir(parents=True, exist_ok=True)

    front_ref = REFS_DIR / "canon_front_scabbard_ref.png"
    w1.make_upscaled_magenta_ref(RAW_DIR / "idle_combat_00.png", front_ref)

    back_ref = REFS_DIR / "canon_back_scabbard_ref.png"
    make_back_scabbard_guide_ref(back_ref)

    jobs: List[Tuple[str, pathlib.Path, pathlib.Path, str]] = []
    for fid in FRONT_RIGHT_IDS:
        sref = REFS_DIR / f"src_{fid}.png"
        preclean_wrong_scabbard_on_ref(fid, RAW_DIR / f"{fid}.png", sref)
        jobs.append((fid, sref, front_ref, PROMPT_EMPTY_SCAB_FRONT_RIGHT))

    for fid in BACK_VIEW_IDS:
        sref = REFS_DIR / f"src_{fid}.png"
        preclean_wrong_scabbard_on_ref(fid, RAW_DIR / f"{fid}.png", sref)
        jobs.append((fid, sref, back_ref, PROMPT_EMPTY_SCAB_BACK_VIEW))

    print(f"=== WAVE 3: Running {len(jobs)} Drawn-Sword Empty Scabbard Codex CLI jobs ===")
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(run_job, fid, sr, r2, pr) for fid, sr, r2, pr in jobs]
        for fut in concurrent.futures.as_completed(futs):
            fid, rc, out = fut.result()
            print(f"[W3 {fid}] rc={rc}", flush=True)
            if rc != 0:
                print(out)
                return rc

    canon_pal, _ = qc_gate.load_master_palette()
    all_ids = FRONT_RIGHT_IDS + BACK_VIEW_IDS
    for fid in all_ids:
        orig_p = RAW_DIR / f"{fid}.png"
        gen_p = GEN_DIR / fid / "generated.png"
        reg_im = register_attack_preserving_fx(fid, gen_p, orig_p)
        out_p = REG_DIR / f"{fid}.png"
        reg_im.save(out_p)
        qc = qc_gate.audit_frame(out_p, canon_pal, allow_fx_border=True, check_grounded_stance=False)
        # Measure crimson scabbard pixel count to prove scabbard is clearly visible!
        arr = np.array(reg_im)
        vis = arr[:, :, 3] > 0
        r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
        red_scab_px = int((vis & (r > 120) & (r > g + 38) & (b > 20) & (b < 105)).sum())
        print(f"[W3 REG {fid:14s}] bbox={qc['bbox']} red_scab_px={red_scab_px} QC={qc['pass']}")
        if not qc["pass"]:
            raise RuntimeError(f"Wave 3 QC failed on {fid}: {qc['errors']}")

    # Render QA overview sheet of ALL Wave 3 outputs!
    all_w3 = [REG_DIR / f"{fid}.png" for fid in all_ids]
    cols = 7
    rows = (len(all_w3) + cols - 1) // cols
    cw, ch = 196, 184  # crop (46, 72, 242, 256)
    sheet = Image.new("RGBA", (cols * cw, rows * (ch + 18)), (26, 30, 42, 255))
    draw = ImageDraw.Draw(sheet)
    for idx, p in enumerate(all_w3):
        ri, ci = divmod(idx, cols)
        x0, y0 = ci * cw, ri * (ch + 18)
        draw.text((x0 + 4, y0 + 2), p.stem, fill=(255, 225, 110, 255))
        cell = Image.new("RGBA", (cw, ch), (236, 239, 245, 255))
        cell.alpha_composite(Image.open(p).convert("RGBA").crop((46, 72, 242, 256)))
        sheet.paste(cell, (x0, y0 + 18))
        draw.rectangle([x0, y0 + 18, x0 + cw - 1, y0 + 18 + ch - 1], outline=(110, 125, 150, 255))
    sheet.save(OUT_DIR / "qa_wave3_all_attacks_fixed.png")
    print(f"[WAVE 3 COMPLETE] Total fixed attack/kentaima frames: {len(all_w3)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
