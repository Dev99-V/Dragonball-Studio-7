#!/usr/bin/env python3
"""
DR7-Studio — Regenerate Tapion `attack_light` Frames #3 (`atk1_03`) & #4 (`atk1_04`).
Owner Requirements (2026-11-25):
  1. Frame #3 (`atk1_03`): Fix missing left arm (`bị mất cánh tay trái`) — BOTH arms (right arm + left arm,
     both dark-green sleeves, yellow-gold wrist bracers, and brown leather gloves) must clearly grip the sword
     hilt together during the wide white-silver crescent downward-right slash. Behind his back (-X) is ONLY
     his flowing royal-blue scarf and empty crimson-red scabbard with silver cap (NEVER a floating hand/arm).
  2. Frame #4 (`atk1_04`): Reference `/workspaces/Dragonball-Studio-7/tapion/tấn công 1.png` — character STILL
     grips the sword hilt with BOTH hands (`nhân vật vẫn còn cầm 2 tay`, NO arm flung behind his back!), empty
     crimson-red scabbard with silver cap on his back (-X), and the sword follow-through continues smoothly
     along the downward circular swing arc toward Frame #5 (`atk1_05`, vertical 90° downward two-handed sword).
  3. Preserve `atk1_00`, `atk1_01`, `atk1_02`, and `atk1_05` unchanged; synchronize character scale to canonical `idle`.
"""
from __future__ import annotations

import concurrent.futures
import pathlib
import subprocess
import sys
from typing import Tuple

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
ROUTE_MEDIA = ROOT / ".agent" / "skills" / "generate2dmedia" / "scripts" / "route_media.py"
SHEET_PATH = ROOT / "tapion" / "tấn công 1.png"
REF_ATK1_05 = ROOT / "work" / "characters" / "tapion" / "phase1" / "generated" / "atk1_05" / "generated.png"
OUT_DIR = ROOT / "work" / "characters" / "tapion" / "atk1_v2"
REFS_DIR = OUT_DIR / "refs"
PROMPTS_DIR = OUT_DIR / "prompts"
GEN_DIR = OUT_DIR / "generated"


def make_clean_sheet_crop_magenta(box: Tuple[int, int, int, int], rotate_blade_toward_f5: bool = False) -> Image.Image:
    sheet = Image.open(SHEET_PATH).convert("RGBA")
    sarr = np.array(sheet)
    bg = sarr[0, 0, :3].astype(int)
    x0, y0, x1, y1 = box
    sub = sarr[y0 : y1 + 1, x0 : x1 + 1].copy()
    dist = np.abs(sub[:, :, :3].astype(int) - bg).max(axis=2)
    cand_bg = dist <= 10
    lbl, _ = ndimage.label(cand_bg)
    border_labels = set(lbl[0, :]) | set(lbl[-1, :]) | set(lbl[:, 0]) | set(lbl[:, -1])
    border_labels.discard(0)
    bg_mask = np.isin(lbl, list(border_labels)) | (dist <= 6)
    sub[bg_mask] = [0, 0, 0, 0]
    pim = Image.fromarray(sub, mode="RGBA")

    if rotate_blade_toward_f5:
        # Gently rotate the lower-right sword region ~18 deg clockwise around the hilt so the pose guide
        # visually bridges #3 (45 deg down-right) -> #4 (~63 deg steep down-right) -> #5 (90 deg vertical)!
        w, h = pim.size
        pad_im = Image.new("RGBA", (w + 60, h + 80), (0, 0, 0, 0))
        pad_im.paste(pim, (20, 20))
        parr = np.array(pad_im)
        # Split blade/hilt quadrant (x >= 118, y >= 158 in padded coords) and rotate -19 deg around pivot (132, 182)
        px, py = 132, 182
        yy, xx = np.mgrid[0 : pad_im.height, 0 : pad_im.width]
        sword_zone = (xx >= 116) & (yy >= 156) & ((xx - 116) + (yy - 156) >= 24)
        body_im = Image.fromarray(np.where(sword_zone[:, :, None], 0, parr).astype(np.uint8), mode="RGBA")
        sword_im = Image.fromarray(np.where(sword_zone[:, :, None], parr, 0).astype(np.uint8), mode="RGBA")
        sword_rot = sword_im.rotate(-19.0, resample=Image.Resampling.NEAREST, center=(px, py))
        comb = Image.new("RGBA", pad_im.size, (0, 0, 0, 0))
        comb.alpha_composite(body_im)
        comb.alpha_composite(sword_rot)
        c_arr = np.array(comb)
        ys, xs = np.where(c_arr[:, :, 3] > 0)
        pim = comb.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))

    scale = min(740.0 / pim.width, 740.0 / pim.height)
    nw, nh = int(round(pim.width * scale)), int(round(pim.height * scale))
    up = pim.resize((nw, nh), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (1024, 1024), (255, 0, 255, 255))
    canvas.alpha_composite(up, ((1024 - nw) // 2, (1024 - nh) // 2))
    return canvas.convert("RGB")


PROMPT_ATK1_03 = """Upgrade Reference Image 2 into a razor-sharp 16-bit pixel-art sprite matching 100% of Reference Image 1's exact character identity, head/body proportions, outfit details, two-handed sword grip, colors, and clean 1px dark outline, on a solid flat #FF00FF pure magenta background.

Reference Image 1 is the approved Character Reference showing his exact two-handed sword grip (BOTH arms — near right arm AND far/front left arm — wearing dark forest-green sleeves, yellow-gold wrist bracers, and TWO brown leather gloves gripping the silver sword hilt together).
Reference Image 2 is the exact Sword Slash Pose #3 layout and wide white-and-silver crescent slash arc to render cleanly.

CRITICAL ANATOMY & POSE REQUIREMENTS FOR POSE #3 (ZERO MISSING ARMS):
1. BOTH ARMS & BOTH HANDS MUST GRIP THE SWORD HILT TOGETHER (DO NOT OMIT THE LEFT ARM!):
   - Near right arm (extending forward-downward from under the left/near golden-orange shoulder pauldron): dark forest-green long sleeve, yellow-gold wrist bracer, and brown leather glove gripping the sword hilt.
   - Far/front LEFT ARM (extending downward from under the right/front golden-orange shoulder pauldron beneath his chin and blue neck scarf): MUST BE CLEARLY VISIBLE — dark forest-green long sleeve, yellow-gold wrist bracer, and SECOND brown leather glove gripping the sword hilt right alongside the right glove (two-handed downward slash, matching Reference Image 1's two-handed grip!).
2. BACK & EMPTY RED SCABBARD (NO BACKWARD ARM OR FLOATING HAND!):
   - Tilting diagonally up-left (-X) behind his upper back/shoulder is ONLY his empty crimson-red sword scabbard with a round white-silver end cap alongside his flowing royal-blue neck scarf tails (matching Reference Image 2). NEVER draw an arm, sleeve, or brown glove behind his back! And do NOT draw a second sword hilt on his shoulder because the sword is already in his two hands.
3. SWORD & CRISP WHITE-SILVER CRESCENT SLASH ARC:
   - Both brown-gloved hands grip the hilt of the straight silver sword angled ~45 degrees downward-right (+X) in front of his lower torso/thighs, unleashing a bold, razor-sharp 16-bit pixel-art white-and-light-silver crescent slash arc sweeping smoothly from upper-right (near hair-top level) down in a wide curved crescent to the sword tip at bottom-right, exactly matching Reference Image 2's arc geometry without shrinking the character's body!
4. BODY & LEGS:
   - Dynamic forward-leaning slash lunge matching Reference Image 2: spiky vermilion-orange mohawk sweeping forward-right (+X) with crimson back spikes, shaved tan temple with small yellow triangle stud above pointed ear, fierce eyes looking down-right; royal-blue front loincloth tabard, right leg (-X) extended back-left and left leg (+X) bent forward-right in green pants, yellow-gold shin greaves, and brown-gold boots.
5. PIXEL FINISH:
   - Clean 1px solid dark outer outline, crisp cel-shaded 16-bit pixel clusters (ZERO blur, ZERO anti-aliased halo on flat #FF00FF pure magenta background, zero ground shadow, zero text), centered on 1024x1024."""


PROMPT_ATK1_04 = """Upgrade Reference Image 2 into a razor-sharp 16-bit pixel-art sprite matching 100% of Reference Image 1's exact character identity, head/body proportions, outfit details, two-handed sword grip, colors, and clean 1px dark outline, on a solid flat #FF00FF pure magenta background.

Reference Image 1 is the approved Frame #5 of this exact sword combo (where BOTH arms — left arm and right arm — grip the sword hilt together pointing straight vertically downward at 90 degrees).
Reference Image 2 is Frame #4 (the in-between follow-through pose immediately BEFORE Reference Image 1, bridging from a 45-degree downward-right slash continuously into Reference Image 1's 90-degree vertical downward sword).

CRITICAL ANATOMY & MOTION-ARC REQUIREMENTS FOR POSE #4:
1. MANDATORY TWO-HANDED SWORD GRIP (CHARACTER STILL HOLDS THE SWORD WITH BOTH HANDS — NEVER ONE-HANDED!):
   - Just like Reference Image 1, BOTH arms MUST come forward-downward from under his two golden-orange shoulder pauldrons:
     * Near right arm (dark forest-green sleeve + yellow-gold wrist bracer + brown leather glove) AND
     * Far/front left arm (dark forest-green sleeve + yellow-gold wrist bracer + second brown leather glove)
     BOTH brown leather gloves MUST grip the sword hilt side-by-side together in front of his waist/hips!
   - NEVER fling an arm backward behind his back!
2. SWORD CONTINUING ALONG THE SWING ARC TOWARD FRAME #5 (~65 DEGREES STEEP DOWNWARD-RIGHT):
   - Position the two gloved hands and straight silver crossguard/blade angled STEEPLY DOWNWARD-RIGHT at ~65 degrees from horizontal (about 5 o'clock — clearly steeper and closer to vertical than 45 degrees, smoothly continuing along the circular downward swing arc directly toward Reference Image 1's 90-degree straight-down vertical sword!).
   - Clean straight double-edged silver pixel-art blade with crisp bright white-cyan edge highlight (no giant wide crescent FX), matching Reference Image 1 & Reference Image 2.
3. BACK & EMPTY RED SCABBARD:
   - Behind his upper back (-X), draw ONLY his flowing royal-blue scarf tails and the empty crimson-red sword scabbard with a round white-silver end cap tilting diagonally back-left (matching Reference Image 2). Do NOT draw a sword hilt in the scabbard since the sword is in his two hands, and NEVER turn the red scabbard into a backward arm!
4. BODY & LEGS:
   - Forward-leaning compact follow-through stance smoothly bridging into Reference Image 1: spiky vermilion-orange mohawk sweeping forward-right (+X), shaved tan temple with yellow triangle stud above pointed ear, royal-blue neck scarf and front tabard, diagonal chest leather strap with round silver clasps, right leg (-X) trailing down-left and left leg (+X) bent tucked under the coat flap in dark forest-green pants, yellow-gold shin greaves, and brown-gold boots.
5. PIXEL FINISH:
   - Clean 1px solid dark outer outline, crisp cel-shaded 16-bit pixel clusters (ZERO blur, ZERO anti-aliased halo on flat #FF00FF pure magenta background, zero ground shadow, zero text), centered on 1024x1024."""


def run_job(fid: str, prompt_path: pathlib.Path, ref2_path: pathlib.Path) -> Tuple[str, int, str]:
    import shutil
    job_out = GEN_DIR / fid
    if job_out.exists():
        shutil.rmtree(job_out)
    cmd = [
        sys.executable,
        str(ROUTE_MEDIA),
        "image",
        "--route",
        "codex-cli",
        "--prompt-file",
        str(prompt_path),
        "--reference",
        str(REF_ATK1_05),
        "--reference",
        str(ref2_path),
        "--size",
        "1024x1024",
        "--out-dir",
        str(job_out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return fid, proc.returncode, (proc.stdout + "\n" + proc.stderr).strip()


def main() -> int:
    REFS_DIR.mkdir(parents=True, exist_ok=True)
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    GEN_DIR.mkdir(parents=True, exist_ok=True)

    ref3 = make_clean_sheet_crop_magenta((876, 116, 1155, 408), rotate_blade_toward_f5=False)
    ref4 = make_clean_sheet_crop_magenta((1250, 121, 1479, 413), rotate_blade_toward_f5=True)
    ref3_path = REFS_DIR / "guide_atk1_03.png"
    ref4_path = REFS_DIR / "guide_atk1_04.png"
    ref3.save(ref3_path)
    ref4.save(ref4_path)

    p3 = PROMPTS_DIR / "atk1_03.txt"
    p4 = PROMPTS_DIR / "atk1_04.txt"
    p3.write_text(PROMPT_ATK1_03 + "\n", encoding="utf-8")
    p4.write_text(PROMPT_ATK1_04 + "\n", encoding="utf-8")

    jobs = [
        ("atk1_03_take1", p3, ref3_path),
        ("atk1_04_take1", p4, ref4_path),
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(run_job, fid, pp, rp) for fid, pp, rp in jobs]
        for f in concurrent.futures.as_completed(futs):
            fid, rc, out = f.result()
            print(f"[{fid}] rc={rc}\n{out}\n")
            if rc != 0:
                return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
