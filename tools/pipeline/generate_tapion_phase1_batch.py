#!/usr/bin/env python3
"""
DR7-Studio — Parallel Codex CLI Single-Frame Synthesis Runner for Tapion Phase 1.
Generates crisp 1024x1024 #FF00FF single-pose pixel-art frames anchored to
`approved-master-1024-magenta.png` (Reference 1) + exact Pose Guide (Reference 2).
Supports `--batch A` (41 core/locomotion frames) and `--batch B` (35 sword combo frames)
with safe concurrent execution (`--workers 6`) and automatic resume/skip of completed jobs.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import pathlib
import subprocess
import sys
import time
from typing import Dict, List, Tuple

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
ROUTE_MEDIA = ROOT / ".agent" / "skills" / "generate2dmedia" / "scripts" / "route_media.py"
MASTER_1024 = ROOT / "work" / "characters" / "tapion" / "approved-master" / "approved-master-1024-magenta.png"
P1_WORK = ROOT / "work" / "characters" / "tapion" / "phase1"
SLICES_DIR = P1_WORK / "source_slices"
WALK_GUIDES_DIR = P1_WORK / "walk_pose_guides"
POSE_REFS_DIR = P1_WORK / "pose_refs_1024"
GEN_DIR = P1_WORK / "generated"

IDENTITY_RULES = """CRITICAL IDENTITY & PIXEL FINISH RULES (copy 100% of Reference Image 1's character identity, outfit, colors, and razor-sharp 16-bit pixel finish onto a flat solid #FF00FF pure magenta background):
- Spiky vermilion-orange-red mohawk hair sweeping forward-right (+X) with crimson-red back shading, shaved tan temple with a small golden-yellow triangle stud above the pointed elf-like ear, furrowed reddish-brown brows, emerald-green irises.
- Royal-blue neck scarf/collar with flowing blue scarf tails, golden-orange shoulder pauldrons and open side coat flaps over dark forest-green long sleeves and pants, yellow-gold wrist bracers, brown leather gloves, diagonal leather chest strap with two round silver clasps, yellow-gold belt buckle over royal-blue front loincloth tabard, yellow-gold shin greaves and brown-gold boots.
- Carry the sword/scabbard or silver-bladed sword or small flute/ocarina ONLY as shown in the pose description/Reference Image 2.
- Clean 1px solid dark outer outline, crisp cel-shaded 16-bit pixel clusters, ZERO blur, ZERO anti-aliased halo on the flat #FF00FF background, no ground shadow, no text, single full-body character centered on 1024x1024."""


def make_pose_ref_1024(slice_name: str) -> pathlib.Path:
    POSE_REFS_DIR.mkdir(parents=True, exist_ok=True)
    out = POSE_REFS_DIR / f"ref_{slice_name}.png"
    if out.exists():
        return out
    src = Image.open(SLICES_DIR / f"{slice_name}.png").convert("RGBA")
    bbox = src.getbbox()
    crop = src.crop(bbox) if bbox else src
    # Fit inside 740x740 on neutral #181C24 1024x1024 so wide slashes never clip!
    sc = min(740.0 / max(1, crop.width), 740.0 / max(1, crop.height))
    nw, nh = max(16, int(round(crop.width * sc))), max(16, int(round(crop.height * sc)))
    canvas = Image.new("RGBA", (1024, 1024), (24, 28, 36, 255))
    canvas.alpha_composite(crop.resize((nw, nh), Image.Resampling.NEAREST), ((1024 - nw) // 2, (1024 - nh) // 2))
    canvas.convert("RGB").save(out)
    return out


WALK_PHASE_DESCS = [
    ("walk_00", "pose_guide_F0.png", "Walking 3/4 front-right (+X) Phase F0 (Right Contact): near (right) leg stepping forward-right with heel/sole planting, far (left) leg extended back; far (left) arm swinging slightly forward, near (right) arm swinging slightly back tucked close beside the hip. Sword remains sheathed diagonally on back (silver hilt over far shoulder, crimson scabbard tip behind near hip)."),
    ("walk_01", "pose_guide_F1.png", "Walking 3/4 front-right (+X) Phase F1 (Right Down): weight settling onto the front near (right) leg with slight knee bend, back far (left) heel lifting; arms mid-swing close to torso (far arm never dislocated behind near shoulder). Sword remains sheathed on back."),
    ("walk_02", "pose_guide_F2.png", "Walking 3/4 front-right (+X) Phase F2 (Right Passing): upright passing stride with legs crossing close together under the hips, near leg supporting weight while far knee passes forward; arms relaxed near waist. Sword remains sheathed on back."),
    ("walk_03", "pose_guide_F3.png", "Walking 3/4 front-right (+X) Phase F3 (Right High-Point): tall stride push-off as far (left) leg reaches forward-right before contact, near (right) leg pushing behind; upright 3/4 front-right torso. Sword remains sheathed on back."),
    ("walk_04", "pose_guide_F4.png", "Walking 3/4 front-right (+X) Phase F4 (Left Contact): far (left) leg planted forward-right, near (right) leg extended behind; near (right) arm swinging forward, far (left) arm tucked close behind the torso/hip. Sword remains sheathed on back."),
    ("walk_05", "pose_guide_F5.png", "Walking 3/4 front-right (+X) Phase F5 (Left Down): weight absorbed on front far (left) leg with slight knee flex, back near (right) toe lifting; balanced 3/4 front-right torso. Sword remains sheathed on back."),
    ("walk_06", "pose_guide_F6.png", "Walking 3/4 front-right (+X) Phase F6 (Left Passing): legs narrow and passing beneath the hips as near (right) knee swings forward past the supporting far leg; arms close to waist. Sword remains sheathed on back."),
    ("walk_07", "pose_guide_F7.png", "Walking 3/4 front-right (+X) Phase F7 (Left High-Point): tall stride rebound with near (right) leg extending forward-right to complete the cycle, far (left) leg pushing behind. Sword remains sheathed on back."),
]

BATCH_A_SLICES: List[Tuple[str, str, str]] = [
    # Idle peace (playing ocarina -> lowering -> neutral; idle_04 is locked master!)
    ("idle_00", "idle_00", "Standing 3/4 front-right playing a small silver-brown ocarina flute held to his lips with both gloved hands, eyes closed serenely, sword sheathed on back."),
    ("idle_01", "idle_01", "Standing 3/4 front-right playing the small ocarina flute at his lips with subtle finger/breath shift and gentle scarf flutter, sword sheathed on back."),
    ("idle_02", "idle_02", "Standing 3/4 front-right lowering both gloved hands holding the small ocarina to chest height, eyes open looking 3/4 right, sword sheathed on back."),
    ("idle_03", "idle_03", "Standing 3/4 front-right lowering gloved hands down beside his waist/belt, stern expression, sword sheathed on back."),
    # Combat enter + Idle combat (4-frame smooth martial stance bounce)
    ("combat_enter_00", "combat_idle_00", "Guarded martial combat entry stance facing 3/4 right (+X), feet planted wide, raised forearms guarding chest, sword hilt visible at upper-left shoulder and red scabbard tip at lower-right."),
    ("idle_combat_00", "combat_idle_01", "Ready martial combat stance Phase 0 (high stance) facing 3/4 right (+X), wide planted boots, knees slightly bent, both gloved fists raised in fighting guard, sword sheathed across back."),
    ("idle_combat_01", "combat_idle_02", "Ready martial combat stance Phase 1 (descending flex) facing 3/4 right (+X), knees flexing slightly lower (~3px crouch) with planted boots at the exact same stance width, fists in guard, sword sheathed on back."),
    ("idle_combat_02", "combat_idle_03", "Ready martial combat stance Phase 2 (deepest crouch) facing 3/4 right (+X), compact athletic knee bend (~5px lower than high stance) with planted boots, fists tight in guard, sword sheathed on back."),
    ("idle_combat_03", "combat_idle_02", "Ready martial combat stance Phase 3 (rising rebound) facing 3/4 right (+X), rising smoothly back up from crouch with planted boots and slight scarf/coat bounce, fists in guard, sword sheathed on back."),
    # Combat move (4 roles: 0=back_dash, 1=back_brake, 2=fwd_brake, 3=fwd_dash; NO aura!)
    ("cmove_00", "combat_move_00", "Backward evasive dash pose facing right (+X), torso leaning back-left while sliding/dashing backward, front leg extended, fists guarded, sword sheathed on back, NO aura."),
    ("cmove_01", "combat_move_01", "Backward brake/cushion pose facing right (+X), upright athletic recovery stance skidding to a stop from a backward dash, knees bent absorbing momentum, sword sheathed on back, NO aura."),
    ("cmove_02", "combat_move_01", "Forward brake/skid-stop pose facing right (+X), front right-side boot planted firmly ahead skidding to halt forward momentum, torso leaning slightly back to decelerate, arms counter-balancing, sword sheathed on back, NO aura."),
    ("cmove_03", "combat_move_02", "High-speed forward rush/dash pose facing right (+X), torso leaning sharply forward-right in a low aerodynamic charge, trailing leg extended back, hair and blue scarf streaming left, sword sheathed on back, NO aura."),
    # Jump + universal fall (5 unique frames; jump_05 copies jump_00)
    ("jump_00", "jump_00", "Pre-jump takeoff crouch facing 3/4 right (+X), knees deeply bent on ground gathering spring power, arms tucked at sides, sword sheathed on back."),
    ("jump_01", "jump_01", "Upward jump launch pose facing 3/4 right (+X), body stretched tall rising into the air, one knee raised, toes pointed down, sword sheathed on back."),
    ("jump_02", "jump_02", "Midair jump apex tuck facing 3/4 right (+X), knees tucked compactly in midair at peak height, guarded arms, sword sheathed on back."),
    ("jump_03", "jump_02", "Early descent midair pose facing 3/4 right (+X), transitioning from apex tuck into downward descent, legs beginning to extend below, arms rising slightly, sword sheathed on back."),
    ("jump_04", "jump_03", "Airborne universal falling pose facing 3/4 right (+X) matching Reference Image 2: arms raised above shoulders while descending vertically through the air, legs extended downward, hair sweeping up, sword sheathed on back."),
    # Fly prep (4 frames with crisp white shockwave bursts from lơ lửng.png) & Fly aura (2 frames with bright blue flight aura)
    ("fly_prep_00", "fly_prep_00", "Airborne hover burst Phase 0 matching Reference Image 2: hovering tense in midair surrounded by sharp pixel-art white radial shockwave spikes bursting outward around the body, sword sheathed on back."),
    ("fly_prep_01", "fly_prep_01", "Airborne hover burst Phase 1 matching Reference Image 2: hovering in midair with expanding jagged white energy burst ring and radial pixel spikes around him, sword sheathed on back."),
    ("fly_prep_02", "fly_prep_02", "Airborne hover burst Phase 2 matching Reference Image 2: hovering in midair inside a wider jagged white shockwave ring with crisp pixel energy streaks, sword sheathed on back."),
    ("fly_prep_03", "fly_prep_03", "Airborne hover burst Phase 3 matching Reference Image 2: hovering in midair as the outer jagged white circular shockwave ring reaches full expansion around him, sword sheathed on back."),
    ("fly_aura_00", "fly_aura_00", "High-speed horizontal flight Phase 0 matching Reference Image 2: flying horizontally to the right (+X) enveloped in a blazing bright cyan-blue and white spiky pixel-art flight aura streaming behind him, sword sheathed on back."),
    ("fly_aura_01", "fly_aura_01", "High-speed horizontal flight Phase 1 matching Reference Image 2: flying horizontally to the right (+X) with the blazing cyan-blue and white spiky flight aura flaring in its second dynamic wave, sword sheathed on back."),
    # Teleport prep ground & air
    ("tele_ground_00", "tele_ground_00", "Grounded high-speed vanish preparation Pose 0 matching Reference Image 2: tense athletic crouch on ground facing 3/4 right (+X), two fingers/fist poised to dash-vanish, sword sheathed on back."),
    ("tele_ground_01", "tele_ground_01", "Grounded high-speed vanish preparation Pose 1 matching Reference Image 2: snapping upright into vanish trigger on ground facing 3/4 right (+X), sword sheathed on back."),
    ("tele_air_00", "tele_air_00", "Midair vanish preparation Pose 0 matching Reference Image 2: tucked airborne stance facing 3/4 right (+X) preparing to instant-vanish in midair, sword sheathed on back."),
    ("tele_air_01", "tele_air_01", "Midair vanish preparation Pose 1 matching Reference Image 2: extended midair vanish snap facing 3/4 right (+X), sword sheathed on back."),
    # Hit (4 frames) & KO (ko_00 copies hit_03; ko_01 is lying flat!)
    ("hit_00", "hit_00", "Damage reaction Pose 0 matching Reference Image 2: recoiling backward from a light strike, torso jolted back, grimacing face, sword sheathed on back."),
    ("hit_01", "hit_01", "Damage reaction Pose 1 matching Reference Image 2: head snapped upward-back from an uppercut/heavy blow, torso arched upright in pain, sword sheathed on back."),
    ("hit_02", "hit_02", "Damage reaction Pose 2 matching Reference Image 2: knocked airborne tumbling backward-left, red sword scabbard prominent diagonally across body as he is launched."),
    ("hit_03", "hit_03", "Heavy knockdown Pose 3 matching Reference Image 2: crashing down onto knees/side clutching/bracing with the red-scabbarded sword across his torso."),
    ("ko_01", "ko_01", "Defeated KO lying flat horizontally on the ground matching Reference Image 2: lying on his back/side horizontally from left (spiky red-orange head) to right (green pants and gold-brown boots), eyes shut unconscious, zero floating."),
]

BATCH_B_SLICES: List[Tuple[str, str, str]] = [
    # Attack 1 (6 poses)
    ("atk1_00", "atk1_00", "Sword Combo 1 Pose 0 matching Reference Image 2: reaching right hand up behind shoulder to grip the silver sword hilt on his back, preparing to draw."),
    ("atk1_01", "atk1_01", "Sword Combo 1 Pose 1 matching Reference Image 2: drawing the shining silver longsword diagonally above his head, poised to slash downward-right (+X)."),
    ("atk1_02", "atk1_02", "Sword Combo 1 Pose 2 matching Reference Image 2: leaping/stepping into an overhead sword windup, silver blade angled high above head, front knee raised."),
    ("atk1_03", "atk1_03", "Sword Combo 1 Pose 3 matching Reference Image 2: downward-right sword slash with a crisp wide white-and-silver pixel crescent slash arc sweeping from top-right to bottom-right."),
    ("atk1_04", "atk1_04", "Sword Combo 1 Pose 4 matching Reference Image 2: follow-through of the downward sword slash, silver blade extended diagonally down-right (+X)."),
    ("atk1_05", "atk1_05", "Sword Combo 1 Pose 5 matching Reference Image 2: compact midair/follow-through tuck thrusting the silver sword vertically straight downward beneath him."),
    # Attack 2 (5 poses)
    ("atk2_00", "atk2_00", "Sword Combo 2 Pose 0 matching Reference Image 2: low coiled sword stance holding the silver blade angled down-left preparing a lunging thrust."),
    ("atk2_01", "atk2_01", "Sword Combo 2 Pose 1 matching Reference Image 2: explosive forward-right sword lunge with a long sharp white-silver pixel thrust spear-streak shooting diagonally up-right (+X)."),
    ("atk2_02", "atk2_02", "Sword Combo 2 Pose 2 matching Reference Image 2: extended forward sword thrust pose pointing the silver longsword horizontally forward-right (+X)."),
    ("atk2_03", "atk2_03", "Sword Combo 2 Pose 3 matching Reference Image 2: powerful upward rising sword slash with a tall crisp white-silver crescent arc sweeping upward on the right."),
    ("atk2_04", "atk2_04", "Sword Combo 2 Pose 4 matching Reference Image 2: upright sword recovery holding the silver blade raised nearly vertically above his front shoulder."),
    # Attack 3 (4 unique poses: atk3_00 copies atk1_01)
    ("atk3_01", "atk3_01", "Sword Combo 3 Pose 1 matching Reference Image 2: fierce downward vertical cleave with a sharp white-silver crescent slash arc curving down the right side."),
    ("atk3_02", "atk3_02", "Sword Combo 3 Pose 2 matching Reference Image 2: low follow-through stance with the silver sword angled diagonally down-right toward the ground."),
    ("atk3_03", "atk3_03", "Sword Combo 3 Pose 3 matching Reference Image 2: stylishly sheathing/crossing the sword at his shoulder with golden-orange coat flaring."),
    ("atk3_04", "atk3_04", "Sword Combo 3 Pose 4 matching Reference Image 2: wide martial stance pointing the silver sword horizontally forward-right (+X)."),
    # Attack 4 (2 poses)
    ("atk4_00", "atk4_00", "Sword Combo 4 Pose 0 matching Reference Image 2: rapid horizontal sword stab windup with a crisp horizontal white-silver motion blur streak across the blade."),
    ("atk4_01", "atk4_01", "Sword Combo 4 Pose 1 matching Reference Image 2: deep lunging horizontal sword thrust straight to the right (+X), red scabbard angled back-left, silver blade extended straight right."),
    # Attack 5 (2 unique poses: atk5_00 copies atk1_02)
    ("atk5_01", "atk5_01", "Sword Combo 5 Pose 1 matching Reference Image 2: sweeping diagonal downward slash with a bold white-silver crescent blade trail on the right (+X)."),
    ("atk5_02", "atk5_02", "Sword Combo 5 Pose 2 matching Reference Image 2: spinning horizontal follow-through slash wrapped in a wide white-silver circular blade arc around his torso."),
    # Attack 6 (3 poses)
    ("atk6_00", "atk6_00", "Sword Combo 6 Pose 0 matching Reference Image 2: airborne sword windup holding the silver blade angled up-left behind his shoulder while poised in midair."),
    ("atk6_01", "atk6_01", "Sword Combo 6 Pose 1 matching Reference Image 2: heavy diagonal cross-slash downward-right with a thick white-silver crescent sword arc."),
    ("atk6_02", "atk6_02", "Sword Combo 6 Pose 2 matching Reference Image 2: grounded slash follow-through with silver blade extended diagonally down-right (+X)."),
    # Attack 7 (4 unique poses: atk7_00 copies atk2_00; glowing cyan-blue energy sword!)
    ("atk7_01", "atk7_01", "Sword Combo 7 Pose 1 matching Reference Image 2: sweeping low-to-mid horizontal slash surrounded by a vibrant glowing cyan-blue and white crescent energy wave wrapping around from left to right (+X)."),
    ("atk7_02", "atk7_02", "Sword Combo 7 Pose 2 matching Reference Image 2: powerful overhead-to-right arc of glowing cyan-blue and white sword energy surging in a tall wave on the right (+X)."),
    ("atk7_03", "atk7_03", "Sword Combo 7 Pose 3 matching Reference Image 2: sword raised high as the giant cyan-blue energy slash arc sprays luminous blue pixel streaks downward-right."),
    ("atk7_04", "atk7_04", "Sword Combo 7 Pose 4 matching Reference Image 2: sword held aloft as the overhead cyan-blue sword energy arc dissipates into bright blue pixel sparks above and to the right."),
    # Attack 8 (5 poses: rising airborne cyan-blue energy spin slash)
    ("atk8_00", "atk8_00", "Sword Combo 8 Pose 0 matching Reference Image 2: grounded rear-facing/side-turned windup holding the silver sword vertically upward preparing a rising spin slash."),
    ("atk8_01", "atk8_01", "Sword Combo 8 Pose 1 matching Reference Image 2: crouching spin slash wrapped in a bright cyan-blue and white horizontal crescent sword wave."),
    ("atk8_02", "atk8_02", "Sword Combo 8 Pose 2 matching Reference Image 2: rising upward spin slash unleashing a wide sweeping cyan-blue and white energy crescent arc to the right (+X)."),
    ("atk8_03", "atk8_03", "Sword Combo 8 Pose 3 matching Reference Image 2: leaping airborne with sword extended up-left while a curved trail of cyan-blue energy sparks sweeps below and to the right."),
    ("atk8_04", "atk8_04", "Sword Combo 8 Pose 4 matching Reference Image 2: hovering at airborne peak with sword angled up-left and dissipating cyan-blue energy sparks trailing on the right."),
    # Attack 9 (3 unique poses: atk9_00 copies atk8_04, atk9_01 copies atk6_00)
    ("atk9_02", "atk9_02", "Sword Combo 9 Pose 2 matching Reference Image 2: midair horizontal slash firing a bright glowing cyan-blue and white crescent blade wave forward-right (+X)."),
    ("atk9_03", "atk9_03", "Sword Combo 9 Pose 3 matching Reference Image 2: midair follow-through with silver sword extended right and a sweeping arc of cyan-blue energy sparks curving below-right."),
    ("atk9_04", "atk9_04", "Sword Combo 9 Pose 4 matching Reference Image 2: clean midair sword finish holding the silver longsword extended forward-right (+X)."),
    # Attack 10 Heavy (1 unique pose: atk10_00! Because atk10_01=atk3_04, atk10_02=atk1_02, atk10_03=atk5_01, atk10_04=atk1_05!)
    ("atk10_00", "atk10_00", "Sword Combo 10 Heavy Pose 0 matching Reference Image 2: wide planted power stance holding the silver sword diagonally up across his face/chest, gathering strength for the heavy jumping slam."),
]


def build_jobs(batch: str) -> List[Dict[str, object]]:
    jobs: List[Dict[str, object]] = []
    if batch in ("A", "ALL"):
        for fid, guide_file, desc in WALK_PHASE_DESCS:
            prompt = (
                f"Generate a single full-body 16-bit pixel-art sprite on a solid flat #FF00FF pure magenta background.\n"
                f"Reference Image 1 is the EXACT Character Identity & Pixel Style Master. "
                f"Reference Image 2 is ONLY the 8-phase bipedal walk pose/skeleton guide (do NOT copy Reference Image 2's hair, face, or clothes).\n"
                f"POSE TO RENDER: {desc}\n\n{IDENTITY_RULES}"
            )
            jobs.append({
                "id": fid,
                "ref1": MASTER_1024,
                "ref2": WALK_GUIDES_DIR / guide_file,
                "prompt": prompt,
            })
        for fid, slice_id, desc in BATCH_A_SLICES:
            ref2 = make_pose_ref_1024(slice_id)
            prompt = (
                f"Upgrade Reference Image 2 into a razor-sharp 16-bit pixel-art sprite matching 100% of Reference Image 1's exact character design, face, outfit details, colors, and clean 1px dark outline, on a solid flat #FF00FF pure magenta background.\n"
                f"Reference Image 1 is the approved Character Master. Reference Image 2 is the exact pose, camera angle, and equipment/effect layout to preserve faithfully.\n"
                f"POSE TO RENDER: {desc}\n\n{IDENTITY_RULES}"
            )
            jobs.append({
                "id": fid,
                "ref1": MASTER_1024,
                "ref2": ref2,
                "prompt": prompt,
            })
    if batch in ("B", "ALL"):
        for fid, slice_id, desc in BATCH_B_SLICES:
            ref2 = make_pose_ref_1024(slice_id)
            prompt = (
                f"Upgrade Reference Image 2 into a razor-sharp 16-bit pixel-art sprite matching 100% of Reference Image 1's exact character design, face, outfit details, colors, and clean 1px dark outline, on a solid flat #FF00FF pure magenta background.\n"
                f"Reference Image 1 is the approved Character Master. Reference Image 2 is the exact sword-attack pose, blade angle, and white/cyan slash arc geometry to preserve faithfully without shrinking the character's body.\n"
                f"POSE TO RENDER: {desc}\n\n{IDENTITY_RULES}"
            )
            jobs.append({
                "id": fid,
                "ref1": MASTER_1024,
                "ref2": ref2,
                "prompt": prompt,
            })
    return jobs


def run_one_job(job: Dict[str, object]) -> Tuple[str, bool, str]:
    fid = str(job["id"])
    out_dir = GEN_DIR / fid
    gen_png = out_dir / "generated.png"
    if gen_png.is_file() and gen_png.stat().st_size > 1024:
        return (fid, True, "cached")

    # Clean partial failed dir if any
    if out_dir.exists():
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)

    prompts_dir = P1_WORK / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    pfile = prompts_dir / f"{fid}.txt"
    pfile.write_text(str(job["prompt"]), encoding="utf-8")

    cmd = [
        sys.executable,
        str(ROUTE_MEDIA),
        "image",
        "--route", "codex-cli",
        "--prompt-file", str(pfile),
        "--reference", str(job["ref1"]),
        "--reference", str(job["ref2"]),
        "--size", "1024x1024",
        "--out-dir", str(out_dir),
    ]
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=False)
    if res.returncode == 0 and gen_png.is_file():
        return (fid, True, res.stdout.strip()[-180:])
    err = (res.stderr or res.stdout or f"exit {res.returncode}").strip()[-240:]
    return (fid, False, err)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", choices=["A", "B", "ALL"], default="ALL")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()

    GEN_DIR.mkdir(parents=True, exist_ok=True)
    jobs = build_jobs(args.batch)
    if args.only:
        only_set = set(args.only)
        jobs = [j for j in jobs if j["id"] in only_set]

    print(f"[TAPION PHASE 1 GEN] Batch={args.batch} total_jobs={len(jobs)} workers={args.workers}", flush=True)
    t0 = time.time()
    ok_cnt = 0
    fail_list: List[Tuple[str, str]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(run_one_job, j): j["id"] for j in jobs}
        for idx, fut in enumerate(concurrent.futures.as_completed(futs), 1):
            fid, ok, msg = fut.result()
            elapsed = time.time() - t0
            if ok:
                ok_cnt += 1
                print(f"  [{idx:02d}/{len(jobs):02d} OK   {elapsed:5.1f}s] {fid} ({'cached' if msg == 'cached' else 'generated'})", flush=True)
            else:
                fail_list.append((fid, msg))
                print(f"  [{idx:02d}/{len(jobs):02d} FAIL {elapsed:5.1f}s] {fid}: {msg}", flush=True)

    # Automatic 1 retry pass for any transient CLI timeout/error
    if fail_list:
        print(f"[RETRY PASS] Retrying {len(fail_list)} failed jobs with workers=3...", flush=True)
        retry_ids = {f[0] for f in fail_list}
        retry_jobs = [j for j in jobs if j["id"] in retry_ids]
        fail_list.clear()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            for fut in concurrent.futures.as_completed([pool.submit(run_one_job, j) for j in retry_jobs]):
                fid, ok, msg = fut.result()
                if ok:
                    ok_cnt += 1
                    print(f"  [RETRY OK] {fid}", flush=True)
                else:
                    fail_list.append((fid, msg))
                    print(f"  [RETRY FAIL] {fid}: {msg}", flush=True)

    print(f"[SUMMARY] ok={ok_cnt}/{len(jobs)} failed={len(fail_list)} in {time.time() - t0:.1f}s", flush=True)
    return 0 if not fail_list else 1


if __name__ == "__main__":
    raise SystemExit(main())
