#!/usr/bin/env python3
"""
DR7-Studio — Generate 6-Frame Detached Flight Aura (`fly_aura_fx_00..05`) +
6-Frame Wind-Fluttering Flying Body (`fly_body_00..05`) for Tapion (`fly_aura`).

Two-Stage Master-Locked Pipeline (Zero Structural Drift):
  - Stage 1 (2 parallel jobs):
      1. `fly_body_00`: Pure aura-free flying Tapion master on #FF00FF magenta, preserving 100% of
         `fly_aura_00`'s exact horizontal flight posture and `cmove_03`'s clean 1px dark outline.
      2. `fly_aura_fx_00`: Pure character-free horizontal DBZ cyan-white comet flight aura master on
         #FF00FF magenta (solid bright white inner core with ZERO central hole, sky-cyan mid layer,
         jagged electric cyan-blue outer flame spikes, crisp 1px dark pixel outline).
  - Stage 2 (10 parallel jobs, max_workers=5):
      * `fly_body_01..05` locked 1:1 to `fly_body_00`: ONLY mohawk hair spikes, royal-blue scarf tails,
        orange lower coat flap, and blue front loincloth tabard ripple across 5 continuous wind-wave
        phases (60°, 120°, 180°, 240°, 300°); rigid face/eyes/ear/stud/torso/arms/fists/hilt/legs/boots
        remain 100% structurally identical!
      * `fly_aura_fx_01..05` locked 1:1 to `fly_aura_fx_00`: 5 continuous backward-streaming flame wave
        phases (60°, 120°, 180°, 240°, 300°) propagating front-to-back along upper/lower/rear spikes!
"""
from __future__ import annotations

import concurrent.futures
import pathlib
import shutil
import subprocess
import sys
from typing import List, Tuple

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
ROUTE_MEDIA = ROOT / ".agent" / "skills" / "generate2dmedia" / "scripts" / "route_media.py"
SRC_FLY0 = ROOT / "work" / "characters" / "tapion" / "phase1" / "generated" / "fly_aura_00" / "generated.png"
SRC_CMOVE3 = ROOT / "work" / "characters" / "tapion" / "phase1" / "generated" / "cmove_03" / "generated.png"

OUT_DIR = ROOT / "work" / "characters" / "tapion" / "fly_aura_6f"
REFS_DIR = OUT_DIR / "refs"
PROMPTS_DIR = OUT_DIR / "prompts"
GEN_DIR = OUT_DIR / "generated"


def make_infilled_aura_guide() -> pathlib.Path:
    """Create a character-free aura guide from fly_aura_00 by replacing Tapion's interior pixels with solid white/cyan core."""
    im = Image.open(SRC_FLY0).convert("RGB")
    arr = np.array(im, dtype=np.uint8)
    r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)

    is_mag = (r > 190) & (b > 190) & (g < 120)
    is_aura_cyan_white = (~is_mag) & (
        ((r > 205) & (g > 225) & (b > 235))
        | ((b > 175) & (g > 110) & (b > r + 45))
    )
    # Outer dark outline of the aura (adjacent to magenta)
    mag_dil = ndimage.binary_dilation(is_mag, iterations=5)
    outer_outline = (~is_mag) & mag_dil & (r < 55) & (g < 65) & (b < 90)

    # Everything inside (~is_mag) that is NOT aura_cyan_white and NOT outer_outline is Tapion's character body!
    char_inside = (~is_mag) & (~is_aura_cyan_white) & (~outer_outline)
    char_inside = ndimage.binary_dilation(char_inside, iterations=3) & (~is_mag) & (~outer_outline)

    # Distance from non-white outer cyan so deep interior becomes pure white core and outer edge blends sky-cyan
    dist_inside = ndimage.distance_transform_edt(char_inside | ((r > 215) & (g > 235) & (b > 240)))
    out = arr.copy()
    out[char_inside & (dist_inside >= 14)] = [250, 254, 255]
    out[char_inside & (dist_inside < 14)] = [72, 236, 255]

    REFS_DIR.mkdir(parents=True, exist_ok=True)
    p = REFS_DIR / "aura_only_guide_00.png"
    Image.fromarray(out, mode="RGB").save(p)
    return p


PROMPT_FLY_BODY_00 = """Extract and render ONLY the flying character from Reference Image 1 as a razor-sharp 16-bit pixel-art sprite on a solid flat #FF00FF pure magenta background, COMPLETELY REMOVING 100% of the cyan/blue/white energy aura around him!

Use Reference Image 2 ONLY as the clean aura-free outfit/color/outline reference for the exact same character.

CRITICAL ANATOMY & POSE LOCKS FOR FLYING BODY MASTER (FRAME 0):
1. ZERO AURA / ZERO GLOW:
   - Remove 100% of the cyan, sky-blue, and white aura flames/sparks! The background around the character MUST be 100% flat solid #FF00FF pure magenta right up to his clean 1px dark outer outline.
2. EXACT HORIZONTAL FLIGHT POSTURE OF REFERENCE IMAGE 1:
   - Keep the EXACT horizontal/diagonal high-speed flying pose, scale, and camera angle of Reference Image 1:
     * Head & face: spiky vermilion-orange mohawk with crimson rear spikes, shaved tan temple with small yellow triangle stud above pointed Konatsian ear, red eyebrows, fierce green eyes looking forward-right (+X).
     * Neck & back: royal-blue neck scarf with TWO distinct royal-blue scarf tails streaming horizontally back-left (-X) behind his upper arm; silver-pommeled brown sword hilt with silver crossguard angled diagonally up-left (-X) behind his shoulder (do NOT draw a long red scabbard hanging below his front knee — keep the clean tucked lower silhouette of Reference Image 1!).
     * Arms: far/front left arm punching/bracing forward-right (+X) under his chin (dark forest-green sleeve, yellow-gold wrist bracer, brown leather fist); near right arm bent back-left (-X) by his ribcage (dark forest-green sleeve, yellow-gold wrist bracer, brown leather fist).
     * Torso & waist: golden-orange vest/pauldrons over royal-blue chest tunic, diagonal brown leather chest strap with TWO round white-silver clasps, brown belt with square gold buckle, trailing golden-orange coat flap (-X), and royal-blue front loincloth tabard.
     * Legs: rear right leg extended back-left (-X) and front left knee bent/tucked forward (+X) in dark forest-green pants, yellow-gold shin greaves, and brown-gold boots.
3. PIXEL ART QUALITY:
   - Chunky, razor-sharp 16-bit pixel art with clean 1px solid dark outer outline, crisp cel-shaded colors, zero anti-aliasing halo on #FF00FF magenta, zero ground shadow."""


PROMPT_AURA_FX_00 = """Render Reference Image 1 into a razor-sharp 16-bit pixel-art DETACHED HORIZONTAL FLIGHT ENERGY AURA sprite on a solid flat #FF00FF pure magenta background — 100% PURE ENERGY AURA ONLY, WITH ZERO CHARACTER INSIDE!

CRITICAL REQUIREMENTS FOR DETACHED FLIGHT AURA MASTER (FRAME 0):
1. ZERO CHARACTER / SOLID LUMINOUS INNER CORE (NO HOLE IN CENTER):
   - There MUST be NO character, NO face, NO hair, NO clothing inside the aura!
   - The interior center-right region (where a flying character will later be layered on top) MUST be a 100% SOLID,OPAQUE bright pure-white (#F8FFFF / #FFFFFF) high-energy core radiating sharp white spikes outward into a vivid sky-cyan (#3CE8FF) mid-layer and electric cyan-blue (#009CFF / #006CE8) outer flame tongues! NEVER leave a dark, magenta, or hollow hole in the center!
2. EXACT COMET / SHOCKWAVE SHAPE & ORIENTATION OF REFERENCE IMAGE 1:
   - Match Reference Image 1's aerodynamic horizontal flight aura silhouette: compact jagged shockwave crest curving around the right (+X) front nose, and sweeping long pointed jagged energy spikes streaming backward-left (-X) along top-left, mid-left, and bottom-left.
   - Keep the exact same overall bounding-box size and centering on the 1024x1024 #FF00FF magenta canvas as Reference Image 1.
3. PIXEL ART FINISH & CONSISTENT 1PX DARK OUTLINE:
   - Crisp 16-bit Dragon Ball Z pixel-art cel-shading (3-4 clean color steps: pure white core -> bright sky-cyan -> electric azure-cyan -> 1px solid dark navy/black outer pixel outline around the entire aura perimeter so it reads cleanly on both white and dark backgrounds!).
   - Solid flat #FF00FF pure magenta background, zero semi-transparent blur, zero text."""


BODY_WIND_PHASES: List[Tuple[str, str]] = [
    (
        "fly_body_01",
        "6-Frame High-Speed Flight Wind-Flutter Cycle — Frame 1 (Phase 60°: Wind Crest Entering Front Spikes & Scarf Base):\n"
        "- RIGID ANATOMY 100% LOCKED TO REFERENCE IMAGE 1: Keep his face, eyes, brow, pointed ear, yellow temple stud, neck collar, sword hilt on back (-X), golden-orange shoulder pauldrons, chest strap + 2 silver clasps, gold belt buckle, BOTH arms/wrists/brown fists, and BOTH legs/greaves/boots in the EXACT SAME pixel position, size, and proportions as Reference Image 1! DO NOT move, resize, or alter his face, limbs, or torso!\n"
        "- WIND FLUTTER (PHASE 1/5): High-speed headwind (+X -> -X) ripples backward:\n"
        "  1. MOHAWK HAIR: Tips of the vermilion-orange & crimson mohawk spikes sweep ~3-4% further backward-upward (-X) with subtle wind separation at the rear crimson tips.\n"
        "  2. BLUE SCARF TAILS (-X): Both royal-blue scarf tails behind his rear arm billow slightly UPWARD at their mid-section while tips flick down.\n"
        "  3. COAT FLAP & BLUE TABARD: Trailing golden-orange side coat tail (-X) lifts slightly upward, and the royal-blue front loincloth tabard ripples slightly backward toward his tucked knee.",
    ),
    (
        "fly_body_02",
        "6-Frame High-Speed Flight Wind-Flutter Cycle — Frame 2 (Phase 120°: Upper Billow Peak on Scarf & Coat Tail):\n"
        "- RIGID ANATOMY 100% LOCKED TO REFERENCE IMAGE 1: Keep his face, eyes, brow, pointed ear, yellow temple stud, neck collar, sword hilt on back (-X), shoulder pauldrons, chest strap + 2 silver clasps, belt buckle, BOTH arms/fists, and BOTH legs/boots 100% IDENTICAL in position and structure to Reference Image 1!\n"
        "- WIND FLUTTER (PHASE 2/5):\n"
        "  1. MOHAWK HAIR: Upper orange spikes press sleekly slightly lower/streamlined backward (-X) while rear crimson spikes flare slightly outward in the slipstream.\n"
        "  2. BLUE SCARF TAILS (-X): Both royal-blue scarf tails reach their HIGHEST upward S-curve wave crest behind his shoulder/arm.\n"
        "  3. COAT FLAP & BLUE TABARD: Trailing golden-orange coat tail (-X) flares upward to its upper wave peak above his rear thigh, and the royal-blue front tabard sweeps back tightly with a crisp wind fold.",
    ),
    (
        "fly_body_03",
        "6-Frame High-Speed Flight Wind-Flutter Cycle — Frame 3 (Phase 180°: Opposite Traveling Wave — Mid-Crest Passing to Rear Tips):\n"
        "- RIGID ANATOMY 100% LOCKED TO REFERENCE IMAGE 1: Keep his face, eyes, brow, pointed ear, yellow temple stud, neck collar, sword hilt on back (-X), shoulder pauldrons, chest strap + 2 silver clasps, belt buckle, BOTH arms/fists, and BOTH legs/boots 100% IDENTICAL in position and structure to Reference Image 1!\n"
        "- WIND FLUTTER (PHASE 3/5 — opposite wave phase to Frame 0):\n"
        "  1. MOHAWK HAIR: Front orange bang and top mohawk spikes flex slightly upward (+2-3%) while middle/rear crimson spikes tuck sleekly inward.\n"
        "  2. BLUE SCARF TAILS (-X): Traveling S-wave moves to the scarf ends — scarf base dips slightly downward while the two pointed blue tips whip sharply UPWARD at the far left (-X).\n"
        "  3. COAT FLAP & BLUE TABARD: Trailing golden-orange coat flap (-X) passes through mid-level with an S-curve tip flicking up, and the blue front tabard relaxes slightly forward.",
    ),
    (
        "fly_body_04",
        "6-Frame High-Speed Flight Wind-Flutter Cycle — Frame 4 (Phase 240°: Lower Trough Whip on Scarf & Coat Flap):\n"
        "- RIGID ANATOMY 100% LOCKED TO REFERENCE IMAGE 1: Keep his face, eyes, brow, pointed ear, yellow temple stud, neck collar, sword hilt on back (-X), shoulder pauldrons, chest strap + 2 silver clasps, belt buckle, BOTH arms/fists, and BOTH legs/boots 100% IDENTICAL in position and structure to Reference Image 1!\n"
        "- WIND FLUTTER (PHASE 4/5):\n"
        "  1. MOHAWK HAIR: Top and rear mohawk spike tips whip slightly downward-back (-X) in a crisp gusts trough.\n"
        "  2. BLUE SCARF TAILS (-X): Both royal-blue scarf tails snap into a clean LOWER S-wave trough (curving slightly lower behind his rear elbow before flicking horizontally left).\n"
        "  3. COAT FLAP & BLUE TABARD: Trailing golden-orange coat tail (-X) dips closer along his extended rear green thigh, while the lower hem of the blue front tabard flutters slightly outward-back.",
    ),
    (
        "fly_body_05",
        "6-Frame High-Speed Flight Wind-Flutter Cycle — Frame 5 (Phase 300°: Recovery Wave Closing Smoothly Back Into Frame 0):\n"
        "- RIGID ANATOMY 100% LOCKED TO REFERENCE IMAGE 1: Keep his face, eyes, brow, pointed ear, yellow temple stud, neck collar, sword hilt on back (-X), shoulder pauldrons, chest strap + 2 silver clasps, belt buckle, BOTH arms/fists, and BOTH legs/boots 100% IDENTICAL in position and structure to Reference Image 1!\n"
        "- WIND FLUTTER (PHASE 5/5 — smoothly bridging back into Frame 0 without duplicating Frame 0):\n"
        "  1. MOHAWK HAIR: Mohawk spikes rise halfway back toward Reference Image 1's neutral swept position, with the very tips trailing slightly behind.\n"
        "  2. BLUE SCARF TAILS (-X): Scarf base begins rising back toward neutral while the far-left pointed blue tips dip slightly downward as the wave exits off the tail ends.\n"
        "  3. COAT FLAP & BLUE TABARD: Golden-orange coat tail (-X) and royal-blue front tabard settle halfway back toward Reference Image 1's silhouette for a seamless 6-frame loop.",
    ),
]


AURA_STREAM_PHASES: List[Tuple[str, str]] = [
    (
        "fly_aura_fx_01",
        "6-Frame Detached Horizontal Flight Energy Aura Cycle — Frame 1 (Phase 60° Backward Flame Propagation):\n"
        "- Keep the EXACT same overall comet aura size, position, solid pure-white center core (ZERO holes, ZERO character!), vivid sky-cyan mid-layer, electric cyan-blue outer layer, and crisp 1px solid dark outer outline on #FF00FF magenta as Reference Image 1.\n"
        "- STREAMING MOTION (PHASE 1/5): Shift the jagged energy flame tongues ~1/6th of a wave cycle backward-left (-X): new small sharp cyan spikes bud along the right (+X) shockwave nose, the upper and lower swept spikes travel slightly left (-X), and the inner white energy rays pulse slightly longer horizontally.",
    ),
    (
        "fly_aura_fx_02",
        "6-Frame Detached Horizontal Flight Energy Aura Cycle — Frame 2 (Phase 120° Mid-Crest Flare):\n"
        "- Keep the EXACT same overall comet aura bounding size, position, solid pure-white center core (ZERO holes, ZERO character!), color palette, and crisp 1px solid dark outer outline on #FF00FF magenta as Reference Image 1.\n"
        "- STREAMING MOTION (PHASE 2/5): Propagate the flame crests ~2/6ths backward-left (-X): the mid-upper and mid-lower cyan flame tongues flare briskly outward-back while the longest far-left (-X) tail spikes taper slightly shorter as energy sheds backward, and the bright white inner starburst expands slightly.",
    ),
    (
        "fly_aura_fx_03",
        "6-Frame Detached Horizontal Flight Energy Aura Cycle — Frame 3 (Phase 180° Alternating Spike Silhouette):\n"
        "- Keep the EXACT same overall comet aura bounding size, position, solid pure-white center core (ZERO holes, ZERO character!), color palette, and crisp 1px solid dark outer outline on #FF00FF magenta as Reference Image 1.\n"
        "- STREAMING MOTION (PHASE 3/5 — opposite wave phase to Frame 0): Everywhere Reference Image 1 had a spike peak along the left/top/bottom trailing edge, shift the peaks and valleys by half a wavelength so secondary cyan flame tongues thrust out prominently to the far-left (-X) while keeping the overall envelope size identical!",
    ),
    (
        "fly_aura_fx_04",
        "6-Frame Detached Horizontal Flight Energy Aura Cycle — Frame 4 (Phase 240° Rear Tail Surge):\n"
        "- Keep the EXACT same overall comet aura bounding size, position, solid pure-white center core (ZERO holes, ZERO character!), color palette, and crisp 1px solid dark outer outline on #FF00FF magenta as Reference Image 1.\n"
        "- STREAMING MOTION (PHASE 4/5): Propagate the flame wave ~4/6ths backward-left (-X): the trailing left (-X) cyan-blue spikes whip sharply backward, fresh crisp spikes form along the upper-right and lower-right shockwave rim, and the pure-white inner core pulses compactly.",
    ),
    (
        "fly_aura_fx_05",
        "6-Frame Detached Horizontal Flight Energy Aura Cycle — Frame 5 (Phase 300° Closing Wave Into Frame 0):\n"
        "- Keep the EXACT same overall comet aura bounding size, position, solid pure-white center core (ZERO holes, ZERO character!), color palette, and crisp 1px solid dark outer outline on #FF00FF magenta as Reference Image 1.\n"
        "- STREAMING MOTION (PHASE 5/5): Advance the flame wave to 5/6ths of the cycle so the upper, lower, and rear-left (-X) cyan spikes smoothly approach Reference Image 1's spike positions from ahead of the wave without duplicating Frame 0, ensuring a seamless 60FPS loop.",
    ),
]


def run_codex_image(fid: str, prompt_text: str, refs: List[pathlib.Path]) -> Tuple[str, int, str]:
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    GEN_DIR.mkdir(parents=True, exist_ok=True)
    pfile = PROMPTS_DIR / f"{fid}.txt"
    pfile.write_text(prompt_text.strip() + "\n", encoding="utf-8")
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
    ]
    for r in refs:
        cmd.extend(["--reference", str(r)])
    cmd.extend(["--size", "1024x1024", "--out-dir", str(out_d)])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return fid, proc.returncode, (proc.stdout + "\n" + proc.stderr).strip()


def main() -> int:
    aura_guide = make_infilled_aura_guide()

    # Stage 1: Generate Master Body F0 and Master Aura F0 in parallel!
    stage1_jobs = [
        ("fly_body_00", PROMPT_FLY_BODY_00, [SRC_FLY0, SRC_CMOVE3]),
        ("fly_aura_fx_00", PROMPT_AURA_FX_00, [aura_guide]),
    ]
    print("=== STAGE 1: Generating Master fly_body_00 & fly_aura_fx_00 ===")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(run_codex_image, fid, pr, rfs) for fid, pr, rfs in stage1_jobs]
        for f in concurrent.futures.as_completed(futs):
            fid, rc, out = f.result()
            print(f"[STAGE 1: {fid}] rc={rc}\n{out}\n", flush=True)
            if rc != 0:
                return rc

    body0_png = GEN_DIR / "fly_body_00" / "generated.png"
    aura0_png = GEN_DIR / "fly_aura_fx_00" / "generated.png"

    # Stage 2: Fan out 5 wind-flutter body frames + 5 streaming aura frames in parallel!
    stage2_jobs: List[Tuple[str, str, List[pathlib.Path]]] = []
    for fid, phase_desc in BODY_WIND_PHASES:
        full_p = (
            "Create the next frame of Reference Image 1's high-speed flying 16-bit pixel-art character sprite on a solid flat #FF00FF pure magenta background (ZERO aura, ZERO glow!).\n\n"
            + phase_desc
            + "\n\nPIXEL ART RULES: Exact same character size, palette, and clean 1px solid dark outer outline as Reference Image 1 on flat #FF00FF pure magenta background. Zero blur, zero anti-aliasing halo, zero text."
        )
        stage2_jobs.append((fid, full_p, [body0_png]))

    for fid, phase_desc in AURA_STREAM_PHASES:
        full_p = (
            "Create the next frame of Reference Image 1's detached 16-bit pixel-art horizontal flight energy aura on a solid flat #FF00FF pure magenta background (PURE ENERGY AURA ONLY — ZERO character inside, 100% solid white center core!).\n\n"
            + phase_desc
            + "\n\nPIXEL ART RULES: Crisp 16-bit cel-shaded pixel clusters (pure white core -> bright sky-cyan -> electric cyan-blue -> 1px solid dark navy/black outer outline) on flat #FF00FF pure magenta background. Zero blur, zero holes."
        )
        stage2_jobs.append((fid, full_p, [aura0_png]))

    print("=== STAGE 2: Generating 5 Body Wind-Flutter Frames + 5 Detached Aura Frames ===")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futs = [ex.submit(run_codex_image, fid, pr, rfs) for fid, pr, rfs in stage2_jobs]
        for f in concurrent.futures.as_completed(futs):
            fid, rc, out = f.result()
            print(f"[STAGE 2: {fid}] rc={rc}\n{out}\n", flush=True)
            if rc != 0:
                return rc

    print("[DONE] Generated all 6 fly_body_00..05 & 6 fly_aura_fx_00..05 frames!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
