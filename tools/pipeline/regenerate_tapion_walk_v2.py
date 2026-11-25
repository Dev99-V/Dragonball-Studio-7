#!/usr/bin/env python3
"""
DR7-Studio — Tapion Walk v2 Regenerator (Goku 3-Stage Left/Right Leg Cycle + Equal Size + Left-Shoulder Hilt Lock).
Uses:
  - Reference 1: `work/characters/tapion/phase1/generated/walk_00/generated.png` (Owner-verified Frame 0 with crystal-clear
    silver sword hilt over Tapion's anatomical LEFT shoulder [+X, right side of neck beneath front hair], diagonal strap
    with 2 silver clasps, and crimson scabbard tip behind right hip [-X]).
  - Reference 2: `work/characters/tapion/phase1/walk_pose_guides/pose_guide_F1..F7.png` (Son Goku approved 8-phase bipedal
    walk guides showing the exact 3-stage foot manipulation per stride: Back-Lift -> Passing -> Airborne Forward-Reach -> Contact).
Generates `walk_01..07` into `work/characters/tapion/walk_v2/generated/walk_01..07/`.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import pathlib
import shutil
import subprocess
import sys
import time
from typing import Dict, List, Tuple

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
ROUTE_MEDIA = ROOT / ".agent" / "skills" / "generate2dmedia" / "scripts" / "route_media.py"
REF_WALK0 = ROOT / "work" / "characters" / "tapion" / "phase1" / "generated" / "walk_00" / "generated.png"
WALK_GUIDES_DIR = ROOT / "work" / "characters" / "tapion" / "phase1" / "walk_pose_guides"
OUT_WORK = ROOT / "work" / "characters" / "tapion" / "walk_v2"
GEN_DIR = OUT_WORK / "generated"
PROMPTS_DIR = OUT_WORK / "prompts"

STRICT_LOCKS = """CRITICAL CHARACTER, SCALE & SWORD SHOULDER LOCKS (MUST MATCH REFERENCE IMAGE 1 100%):
1. EXACT SAME CHARACTER SIZE & PROPORTIONS AS REFERENCE IMAGE 1:
   - Keep the EXACT SAME character height, head size, spiky vermilion-orange mohawk height/width, face proportions, and torso width as Reference Image 1. Do NOT shrink or enlarge the character.
   - Maintain the exact 3/4 front-right (+X) camera angle of Reference Image 1.
2. MANDATORY SWORD HILT ON ANATOMICAL LEFT SHOULDER (+X / RIGHT SIDE OF IMAGE) — NEVER FLIP SHOULDER:
   - Look closely at Reference Image 1: the sword's round white-silver pommel, brown grip, and curved white-silver crossguard stick out diagonally UP-RIGHT (+X) just to the RIGHT of his chin/neck over his ANATOMICAL LEFT SHOULDER (beneath the front orange hair bangs).
   - NEVER draw any sword hilt behind his ear or on the left side (-X) of his head/neck! The top-left behind his ear MUST ONLY show his spiky red-orange hair and flowing blue neck scarf!
   - Keep the brown leather strap running diagonally from his upper-right (anatomical left shoulder, +X) down-left (-X) across his blue chest tunic with the TWO round white-silver clasps, and the crimson-red scabbard tip with white-silver cap peeking out down-left (-X) behind his right hip/coat flap.
3. PIXEL ART & BACKGROUND RULES:
   - Razor-sharp chunky 16-bit pixel-art sprite with clean 1px dark outer outline, crisp cel-shaded colors identical to Reference Image 1, on a flat solid #FF00FF pure magenta background. Zero blur, zero ground shadow, zero text."""

WALK_V2_SPECS: List[Tuple[str, str, str]] = [
    (
        "walk_01",
        "pose_guide_F1.png",
        "8-Frame Walk Cycle — Frame 1 (Right Leg Supporting + Left Leg Back-Lift Stage 1, matching Reference Image 2's exact leg/foot positions):\n"
        "- SUPPORTING RIGHT (NEAR) LEG: Foreground right leg (brighter forest-green pants, yellow-gold shin greave, brown-gold boot) stands firmly under the torso with its boot sole PLANTED FLAT HORIZONTALLY ON THE GROUND.\n"
        "- LIFTED LEFT (FAR) LEG: Background left leg (darker-shaded green pants behind the right thigh) bends at the knee behind (-X) with its boot CLEARLY LIFTED HIGH OFF THE GROUND (~12% of body height above the floor line, toe angled downward-left, NOT touching the ground!).\n"
        "- ARMS: Far (left) gloved fist pulling slightly back from full extension on the right (+X), near (right) gloved hand swinging closer to the hip on the left (-X).\n"
        "- SWORD LOCK: Silver sword hilt (round silver pommel + brown grip + silver guard) MUST protrude diagonally UP-RIGHT (+X) over his anatomical left shoulder right beneath his front hair bangs, identical to Reference Image 1!",
    ),
    (
        "walk_02",
        "pose_guide_F2.png",
        "8-Frame Walk Cycle — Frame 2 (Right Leg Supporting + Left Leg Passing Stage 2, matching Reference Image 2's exact leg/foot positions):\n"
        "- NARROW PASSING LEGS: Foreground right (near) leg stands straight upright directly beneath the hips with its boot planted flat on the ground at center; background left (far, darker-shaded) leg passes forward immediately BEHIND the standing right leg so the lower legs form a narrow, compact passing silhouette under the blue front tabard.\n"
        "- ARMS: Both brown-gloved hands relaxed near waist/hip level as the arms pass neutral.\n"
        "- SIZE & SWORD LOCK: Keep head, hair, and total body height IDENTICAL to Reference Image 1 (do NOT stretch him taller!). Silver sword hilt MUST protrude diagonally UP-RIGHT (+X) over his anatomical left shoulder beneath his front orange bangs, identical to Reference Image 1!",
    ),
    (
        "walk_03",
        "pose_guide_F3.png",
        "8-Frame Walk Cycle — Frame 3 (Right Leg Pushing Back + Left Leg Airborne Forward-Reach Stage 3, matching Reference Image 2's exact leg/foot positions):\n"
        "- PUSHING RIGHT (NEAR) LEG: Foreground right leg extends backward-left (-X) with its boot pushing off on the ground behind.\n"
        "- REACHING LEFT (FAR) LEG IN AIR: Background left leg (darker-shaded green pants emerging from behind the blue front tabard) reaches forward-right (+X) with knee slightly raised and its boot CLEARLY LIFTED ABOVE THE GROUND (~8% above floor line, heel leading forward in mid-air before touchdown — do NOT plant the front foot flat on the ground yet!).\n"
        "- ARMS: Near (right) gloved fist swinging forward across waist/lower chest, far (left) arm tucked back behind torso.\n"
        "- SWORD LOCK: Silver sword hilt MUST remain diagonally UP-RIGHT (+X) over his anatomical left shoulder beneath his front orange bangs, identical to Reference Image 1 (NEVER behind his ear!).",
    ),
    (
        "walk_04",
        "pose_guide_F4.png",
        "8-Frame Walk Cycle — Frame 4 (Left Leg Forward Contact + Right Leg Extended Back — exact opposite leg phase to Reference Image 1, matching Reference Image 2's leg positions):\n"
        "- FRONT LEFT (FAR) LEG: Background left leg (emerging on the right side +X from beneath the blue front loincloth tabard, slightly deeper shading) steps forward-right (+X) with its boot planted on the ground ahead.\n"
        "- BACK RIGHT (NEAR) LEG: Foreground right leg (clearly connected to the front-left golden-orange side coat flap in the foreground) extends backward-left (-X) with its boot touching the ground behind.\n"
        "- ARMS: Foreground near (right) arm with yellow wrist bracer and brown glove swings forward-right across the lower chest/hip; far (left) arm is tucked back behind the torso (mostly hidden behind chest).\n"
        "- CRITICAL SWORD HILT LOCK: Even though the legs/arms are opposite to Frame 0, his torso still faces 3/4 front-right (+X), so the silver sword hilt (round silver pommel + brown grip + silver crossguard) MUST STILL stick out diagonally UP-RIGHT (+X) over his anatomical LEFT shoulder right beneath his front orange hair bangs, and the red scabbard tip MUST STILL peek out down-left (-X) behind his hip! ZERO hilt behind his ear!",
    ),
    (
        "walk_05",
        "pose_guide_F5.png",
        "8-Frame Walk Cycle — Frame 5 (Left Leg Supporting + Right Leg Back-Lift Stage 1, matching Reference Image 2's exact leg/foot positions):\n"
        "- SUPPORTING LEFT (FAR) LEG: Background left leg stands firmly directly beneath the torso/blue tabard with its boot sole PLANTED FLAT HORIZONTALLY ON THE GROUND.\n"
        "- LIFTED RIGHT (NEAR) LEG: Foreground right leg (in front, below the golden-orange side coat flap) bends sharply at the knee behind (-X) with its brown-gold boot CLEARLY LIFTED HIGH OFF THE GROUND (~12% of body height above the floor line, sole facing back-left in mid-air, NOT touching the ground!).\n"
        "- ARMS: Near (right) gloved hand slightly forward near waist, far (left) arm tucked behind torso.\n"
        "- CRITICAL SWORD HILT LOCK: Silver sword hilt (pommel + grip + guard) MUST protrude diagonally UP-RIGHT (+X) over his anatomical LEFT shoulder beneath his front orange hair bangs, identical to Reference Image 1! ZERO hilt on the left (-X) behind his ear!",
    ),
    (
        "walk_06",
        "pose_guide_F6.png",
        "8-Frame Walk Cycle — Frame 6 (Left Leg Supporting + Right Leg Passing Stage 2, matching Reference Image 2's exact leg/foot positions):\n"
        "- NARROW PASSING LEGS (FOREGROUND LEG PASSING): Background left (far, darker-shaded) leg stands straight upright planted flat on the ground at center; foreground right (near, brighter green pants & gold greave) knee bends slightly as the right leg swings forward IN FRONT OF the standing left leg (right boot hovered just slightly above the floor in a compact narrow passing silhouette).\n"
        "- ARMS: Both gloved hands passing close beside the waist.\n"
        "- SIZE & SWORD LOCK: Keep head, hair, and total body height IDENTICAL to Reference Image 1 (do NOT stretch him taller!). Silver sword hilt MUST protrude diagonally UP-RIGHT (+X) over his anatomical left shoulder beneath his front orange bangs, identical to Reference Image 1!",
    ),
    (
        "walk_07",
        "pose_guide_F7.png",
        "8-Frame Walk Cycle — Frame 7 (Left Leg Pushing Back + Right Leg Airborne Forward-Reach Stage 3, matching Reference Image 2's exact leg/foot positions):\n"
        "- PUSHING LEFT (FAR) LEG: Background left (darker-shaded) leg pushes off on the ground behind (-X), boot planted on the floor at the back.\n"
        "- REACHING RIGHT (NEAR) LEG HIGH IN AIR: Foreground right (brighter green pants & gold greave) leg swings forward-right (+X) with knee raised and its brown-gold boot CLEARLY LIFTED IN MID-AIR (~10% above the floor line, reaching forward-right before stepping down into Frame 0 — DO NOT plant the front right boot on the ground!).\n"
        "- ARMS: Far (left) gloved fist swinging forward-right (+X), near (right) gloved hand swinging slightly back-left (-X), smoothly preparing to connect into Frame 0.\n"
        "- SWORD LOCK: Silver sword hilt MUST protrude diagonally UP-RIGHT (+X) over his anatomical left shoulder beneath his front orange bangs, identical to Reference Image 1!",
    ),
]


def run_job(fid: str, guide_name: str, desc: str, force: bool = False) -> Tuple[str, bool, str]:
    out_dir = GEN_DIR / fid
    gen_png = out_dir / "generated.png"
    if not force and gen_png.is_file() and gen_png.stat().st_size > 1024:
        return (fid, True, "cached")
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)

    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    prompt_text = (
        "Generate a single full-body 16-bit pixel-art character sprite on a flat solid #FF00FF pure magenta background.\n"
        "Reference Image 1 is the EXACT Character Identity, Scale, and Left-Shoulder Sword Hilt Master (Walk Frame 0).\n"
        "Reference Image 2 is ONLY the bipedal leg/foot & arm pose guide (copy ONLY the leg/foot lift/stride positions from Reference Image 2; NEVER copy Reference Image 2's hair, face, or orange gi).\n\n"
        f"TARGET POSE:\n{desc}\n\n{STRICT_LOCKS}\n"
    )
    pfile = PROMPTS_DIR / f"{fid}.txt"
    pfile.write_text(prompt_text, encoding="utf-8")

    cmd = [
        sys.executable,
        str(ROUTE_MEDIA),
        "image",
        "--route", "codex-cli",
        "--prompt-file", str(pfile),
        "--reference", str(REF_WALK0),
        "--reference", str(WALK_GUIDES_DIR / guide_name),
        "--size", "1024x1024",
        "--out-dir", str(out_dir),
    ]
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=False)
    if res.returncode == 0 and gen_png.is_file():
        return (fid, True, res.stdout.strip()[-160:])
    err = (res.stderr or res.stdout or f"exit {res.returncode}").strip()[-240:]
    return (fid, False, err)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=7)
    args = ap.parse_args()

    GEN_DIR.mkdir(parents=True, exist_ok=True)
    # Copy immutable walk_00 directly into walk_v2/generated/walk_00/generated.png
    w0_dst = GEN_DIR / "walk_00"
    w0_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REF_WALK0, w0_dst / "generated.png")

    specs = WALK_V2_SPECS
    if args.only:
        only_s = set(args.only)
        specs = [s for s in specs if s[0] in only_s]

    print(f"[TAPION WALK V2] Launching {len(specs)} jobs with workers={args.workers}...", flush=True)
    t0 = time.time()
    fails = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(run_job, fid, gname, desc, args.force): fid for (fid, gname, desc) in specs}
        for idx, fut in enumerate(concurrent.futures.as_completed(futs), 1):
            fid, ok, msg = fut.result()
            dt = time.time() - t0
            if ok:
                print(f"  [{idx}/{len(specs)} OK   {dt:5.1f}s] {fid}", flush=True)
            else:
                fails.append((fid, msg))
                print(f"  [{idx}/{len(specs)} FAIL {dt:5.1f}s] {fid}: {msg}", flush=True)

    if fails:
        print(f"[RETRY] Retrying {len(fails)} failed jobs...", flush=True)
        retry_ids = {f[0] for f in fails}
        fails.clear()
        for (fid, gname, desc) in specs:
            if fid in retry_ids:
                _, ok, msg = run_job(fid, gname, desc, True)
                if not ok:
                    fails.append((fid, msg))
                    print(f"  [RETRY FAIL] {fid}: {msg}", flush=True)
                else:
                    print(f"  [RETRY OK] {fid}", flush=True)

    print(f"[DONE] fails={len(fails)} elapsed={time.time() - t0:.1f}s", flush=True)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
