#!/usr/bin/env python3
"""
DR7-Studio — Parallel Codex CLI Single-Frame Synthesis Runner for Tapion Phase 2 (All Remaining Skills & Turntable).
Covers 45 unique poses across:
  - Group S2 (21 poses): `turntable_00..03,05..07`, `barrier_01..08`, `recover_02..07`
  - Group S3 (5 poses):  `maha_gnd_00..02`, `maha_air_00..01`
  - Group S4 (11 poses): `anta_chg_00..03`, `anta_rng_00..03`, `anta_fire_00..02`
  - Group S5 (8 poses):  `kenta_cast_00..03`, `bukadai_00..03`
Anchored to `approved-master-1024-magenta.png` (Reference 1) + exact Source Slice Pose Guide (Reference 2).
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
MASTER_1024 = ROOT / "work" / "characters" / "tapion" / "approved-master" / "approved-master-1024-magenta.png"
P2_WORK = ROOT / "work" / "characters" / "tapion" / "phase2"
SLICES_DIR = P2_WORK / "source_slices"
POSE_REFS_DIR = P2_WORK / "pose_refs_1024"
GEN_DIR = P2_WORK / "generated"

IDENTITY_RULES = """CRITICAL IDENTITY & PIXEL FINISH RULES (copy 100% of Reference Image 1's character identity, outfit, colors, and razor-sharp 16-bit pixel finish onto a flat solid #FF00FF pure magenta background):
- Spiky vermilion-orange-red mohawk hair, shaved tan temple with a small golden-yellow triangle stud above the pointed elf-like ear, furrowed reddish-brown brows, emerald-green irises (unless flash/aura-tinted as shown in Reference Image 2).
- Royal-blue neck scarf/collar with flowing blue scarf tails, golden-orange shoulder pauldrons and open side coat flaps over dark forest-green long sleeves and pants, yellow-gold wrist bracers, brown leather gloves, diagonal leather chest strap with two round silver clasps, yellow-gold belt buckle over royal-blue front loincloth tabard, yellow-gold shin greaves and brown-gold boots.
- Preserve 100% of Reference Image 2's exact camera angle, pose, sword/scabbard/ocarina placement, and any attached energy aura, electric barrier sphere, golden ring, or cyan slash wave WITHOUT shrinking the character's body!
- Clean 1px solid dark outer outline on the character body, crisp cel-shaded 16-bit pixel clusters, ZERO blur, ZERO anti-aliased halo on the flat #FF00FF background, no ground shadow, no text, single subject centered on 1024x1024."""


def make_pose_ref_1024(slice_name: str) -> pathlib.Path:
    POSE_REFS_DIR.mkdir(parents=True, exist_ok=True)
    out = POSE_REFS_DIR / f"ref_{slice_name}.png"
    if out.exists():
        return out
    src = Image.open(SLICES_DIR / f"{slice_name}.png").convert("RGBA")
    bbox = src.getbbox()
    crop = src.crop(bbox) if bbox else src
    sc = min(760.0 / max(1, crop.width), 760.0 / max(1, crop.height))
    nw, nh = max(16, int(round(crop.width * sc))), max(16, int(round(crop.height * sc)))
    canvas = Image.new("RGBA", (1024, 1024), (24, 28, 36, 255))
    canvas.alpha_composite(crop.resize((nw, nh), Image.Resampling.NEAREST), ((1024 - nw) // 2, (1024 - nh) // 2))
    canvas.convert("RGB").save(out)
    return out


GROUP_S2: List[Tuple[str, str, str]] = [
    # Turntable 8 angles (turntable_04 = locked approved-master-125px!)
    ("turntable_00", "turntable_00", "360-degree Turnaround Angle 0 (Rear-Left 3/4 Back View) matching Reference Image 2: standing upright seen from rear-left 3/4, spiky red-orange mohawk sweeping left, crimson-red sword scabbard with silver hilt strapped diagonally across his back over the golden-orange coat."),
    ("turntable_01", "turntable_01", "360-degree Turnaround Angle 1 (Pure Left Side Profile -X) matching Reference Image 2: standing upright in clean left profile facing left (-X), spiky mohawk sweeping left, pointed ear with gold triangle stud, sword hilt poking behind shoulder."),
    ("turntable_02", "turntable_02", "360-degree Turnaround Angle 2 (Front-Left 3/4 View facing -X) matching Reference Image 2: standing upright at front-left 3/4 angle facing left (-X), stern emerald eyes, diagonal chest strap with two silver clasps, sword hilt over far shoulder."),
    ("turntable_03", "turntable_03", "360-degree Turnaround Angle 3 (Direct Front 0-degree View) matching Reference Image 2: standing upright facing straight toward the camera symmetrically, both pointed ears visible, mohawk centered, blue scarf and tabard centered, sword hilt behind left shoulder and scabbard tip lower-left."),
    ("turntable_05", "turntable_05", "360-degree Turnaround Angle 5 (Pure Right Side Profile +X) matching Reference Image 2: standing upright in clean right side profile facing right (+X), spiky mohawk sweeping forward-right, pointed ear with gold triangle stud, sword hilt behind back."),
    ("turntable_06", "turntable_06", "360-degree Turnaround Angle 6 (Rear-Right 3/4 Back View) matching Reference Image 2: standing upright seen from rear-right 3/4 back angle, spiky mohawk sweeping right, crimson-red sword scabbard with silver crossguard strapped diagonally across his back."),
    ("turntable_07", "turntable_07", "360-degree Turnaround Angle 7 (Direct Back 180-degree View) matching Reference Image 2: standing upright facing straight away from camera showing full back of red-orange mohawk, blue collar, golden-orange back coat, and full crimson-red sword scabbard strapped diagonally from upper-left to lower-right."),
    # Ocarina Protective Barrier (barrier_01..08; barrier_00 reuses idle_03)
    ("barrier_01", "barrier_01", "Ocarina Barrier Pose 1 matching Reference Image 2: leaping upward into midair with knees tucked, raising both gloved hands holding the small ocarina flute toward his mouth, sword sheathed on back."),
    ("barrier_02", "barrier_02", "Ocarina Barrier Pose 2 matching Reference Image 2: airborne mid-leap tuck facing 3/4 right (+X), positioning hands before playing the ocarina, sword sheathed on back."),
    ("barrier_03", "barrier_03", "Ocarina Barrier Pose 3 matching Reference Image 2: hovering tucked in midair playing the small ocarina flute held to his lips with both hands, sword sheathed on back."),
    ("barrier_04", "barrier_04", "Ocarina Barrier Pose 4 matching Reference Image 2: hovering tucked in midair playing the ocarina inside a crisp pixel-art circular royal-blue and cyan electric energy shield sphere with white lightning arcs."),
    ("barrier_05", "barrier_05", "Ocarina Barrier Pose 5 matching Reference Image 2: hovering in midair playing the ocarina inside an expanding circular blue pixel-dithered energy barrier sphere with a bright white-cyan sonic melody wave swirling horizontally across him."),
    ("barrier_06", "barrier_06", "Ocarina Barrier Pose 6 matching Reference Image 2: hovering in midair playing the ocarina inside a large circular blue electric barrier sphere crackling with white-cyan lightning bolts and a wide swirling white melody ribbon."),
    ("barrier_07", "barrier_07", "Ocarina Barrier Pose 7 matching Reference Image 2: hovering in midair playing the ocarina at peak barrier expansion inside a giant deep-blue and electric-cyan spherical shield crackling with jagged lightning and a thick white sonic wave."),
    ("barrier_08", "barrier_08", "Ocarina Barrier Pose 8 matching Reference Image 2: hovering in midair holding the ocarina as the spherical blue barrier dissolves into a circular ring of crisp cyan-blue pixel particles and fading white sonic wisps."),
    # Ocarina Energy Recover & Regenerate (recover_02..07; recover_00=idle_04, recover_01=idle_00)
    ("recover_02", "recover_02", "Ocarina Energy Recovery Pose 2 matching Reference Image 2: standing firmly on the ground playing the ocarina flute as a crisp white-and-cyan flame aura ignites upward from around his boots with cyan pixel sparks."),
    ("recover_03", "recover_03", "Ocarina Energy Recovery Pose 3 matching Reference Image 2: standing firmly planted playing the ocarina enveloped in a tall blazing white pixel-art ki flame aura crackling with bright cyan-blue lightning arcs, hair illuminated warm gold-orange."),
    ("recover_04", "recover_04", "Ocarina Energy Recovery Pose 4 matching Reference Image 2: standing firmly planted playing the ocarina inside the surging tall white flame aura with dynamic cyan-blue lightning bolts coiling around his body (wave phase B)."),
    ("recover_05", "recover_05", "Ocarina Energy Recovery Pose 5 matching Reference Image 2: standing firmly planted playing the ocarina inside the surging tall white flame aura with crackling cyan-blue electricity and upward white aura spikes (wave phase C)."),
    ("recover_06", "recover_06", "Ocarina Energy Recovery Pose 6 matching Reference Image 2: standing firmly planted playing the ocarina inside the surging tall white flame aura with high flaring white energy peaks and cyan-blue lightning (wave phase D)."),
    ("recover_07", "recover_07", "Ocarina Energy Recovery Pose 7 matching Reference Image 2: standing firmly planted playing the ocarina as the white recovery aura rises and separates into crisp vertical white energy wisps around his head and shoulders."),
]

GROUP_S3: List[Tuple[str, str, str]] = [
    # Mahasenko Ground (3 poses) & Air (2 poses)
    ("maha_gnd_00", "maha_gnd_00", "Mahasenko Ground Pose 0 matching Reference Image 2: wide martial stance twisting torso back, showing the crimson-red sword scabbard diagonally across his back, arms coiling to gather energy."),
    ("maha_gnd_01", "maha_gnd_01", "Mahasenko Ground Pose 1 matching Reference Image 2: stepping and leaning torso forward-right (+X) in a low athletic crouch, drawing right hand to hip before thrusting."),
    ("maha_gnd_02", "maha_gnd_02", "Mahasenko Ground Pose 2 matching Reference Image 2: deep lunging stance thrusting his front open palm straight forward-right (+X) to fire the Mahasenko beam, rear arm pulled back, hair and coat sweeping dynamically."),
    ("maha_air_00", "maha_air_00", "Mahasenko Air Pose 0 matching Reference Image 2: hovering upright in midair facing 3/4 right (+X), front left arm bent with fist raised preparing to fire diagonally downward, sword sheathed on back."),
    ("maha_air_01", "maha_air_01", "Mahasenko Air Pose 1 matching Reference Image 2: hovering in midair extending his front open palm diagonally downward-right (+X) to fire the airborne Mahasenko beam, sword sheathed on back."),
]

GROUP_S4: List[Tuple[str, str, str]] = [
    # Antamina Charge (4), Concentric Rings (4), Fire (3)
    ("anta_chg_00", "anta_chg_00", "Antamina Charge Pose 0 matching Reference Image 2: wide planted stance leaning slightly back with rear right arm raised behind shoulder gathering power, sword sheathed on back."),
    ("anta_chg_01", "anta_chg_01", "Antamina Charge Pose 1 matching Reference Image 2: wide planted stance bringing both gloved hands into a focused martial guard near chest, stern intense gaze right (+X)."),
    ("anta_chg_02", "anta_chg_02", "Antamina Charge Pose 2 matching Reference Image 2: wide planted stance facing 3/4 right (+X) raising front left fist forward at shoulder height, preparing to project energy."),
    ("anta_chg_03", "anta_chg_03", "Antamina Charge Pose 3 matching Reference Image 2: wide planted stance extending front arm horizontally right (+X) projecting a glowing golden-yellow ring and horizontal golden beam core in front of his palm."),
    ("anta_rng_00", "anta_rng_00", "Antamina Rings Pose 0 matching Reference Image 2: wide planted stance extending arm right (+X) surrounded in front by a crisp double golden-yellow energy ring, horizontal gold laser axis, and radial golden pixel sparks."),
    ("anta_rng_01", "anta_rng_01", "Antamina Rings Pose 1 matching Reference Image 2: wide planted stance extending arm right (+X) as the double golden-yellow concentric ring glows brighter with a white-yellow diamond core and denser radial gold sparks."),
    ("anta_rng_02", "anta_rng_02", "Antamina Rings Pose 2 matching Reference Image 2: wide planted stance extending arm right (+X) as the core inside the double golden ring erupts into a blazing 8-point white-yellow starburst with horizontal gold beam."),
    ("anta_rng_03", "anta_rng_03", "Antamina Rings Pose 3 (DBZ Impact Flash Frame) matching Reference Image 2: dramatic high-contrast white-and-black monochrome flash silhouette of Tapion in the same wide stance with an expanding ring of golden-orange pixel sparks in front of him."),
    ("anta_fire_00", "anta_fire_00", "Antamina Fire Pose 0 matching Reference Image 2: wide planted stance facing 3/4 right (+X) with front left open palm extended horizontally right (+X) sustaining the Antamina blast, rear fist at waist."),
    ("anta_fire_01", "anta_fire_01", "Antamina Fire Pose 1 matching Reference Image 2: wide planted stance sustaining the Antamina blast with subtle recoil flutter on hair and blue scarf while front palm stays extended right (+X)."),
    ("anta_fire_02", "anta_fire_02", "Antamina Fire Pose 2 matching Reference Image 2: wide planted stance finishing the Antamina palm projection forward-right (+X) with crisp posture and flowing scarf."),
]

GROUP_S5: List[Tuple[str, str, str]] = [
    # Kentaima (4 poses) & Bukadai (4 body poses)
    ("kenta_cast_00", "kenta_cast_00", "Kentaima Slash Pose 0 matching Reference Image 2: leaping airborne windup holding the shining silver longsword extended diagonally up-left behind him, knees tucked."),
    ("kenta_cast_01", "kenta_cast_01", "Kentaima Slash Pose 1 matching Reference Image 2: overhead two-handed sword swing windup with bright cyan-blue and white crescent energy igniting along the silver blade above his head."),
    ("kenta_cast_02", "kenta_cast_02", "Kentaima Slash Pose 2 matching Reference Image 2: fierce downward sword cleave unleashing a massive towering cyan-blue and white crescent energy wave curving in front on the right (+X) without shrinking Tapion's body."),
    ("kenta_cast_03", "kenta_cast_03", "Kentaima Slash Pose 3 matching Reference Image 2: sword follow-through angled down-right (+X) with a sharp bright cyan-blue crescent blade arc trailing on the right."),
    ("bukadai_00", "bukadai_00", "Bukadai Rush Pose 0 matching Reference Image 2: compact crouched sword-ready stance on the ground facing right (+X), gripping sword at hip preparing a lightning-fast dash."),
    ("bukadai_01", "bukadai_01", "Bukadai Rush Pose 1 matching Reference Image 2: swift downward-right sword slash leaving a clean white-silver crescent blade arc on the right (+X)."),
    ("bukadai_02", "bukadai_02", "Bukadai Rush Pose 2 matching Reference Image 2: low athletic lunge pointing the silver longsword diagonally down-left/forward preparing torocket-dash right (+X)."),
    ("bukadai_03", "bukadai_03", "Bukadai Rush Pose 3 matching Reference Image 2: ultra-high-speed horizontal forward lunge to the right (+X) wrapped in crisp horizontal white speed streaks and a sharp white-silver thrust cone ahead of his blade."),
]


def build_jobs(groups: List[str]) -> List[Dict[str, object]]:
    mapping = {"S2": GROUP_S2, "S3": GROUP_S3, "S4": GROUP_S4, "S5": GROUP_S5}
    jobs: List[Dict[str, object]] = []
    for g in groups:
        for fid, slice_id, desc in mapping[g]:
            ref2 = make_pose_ref_1024(slice_id)
            prompt = (
                f"Upgrade Reference Image 2 into a razor-sharp 16-bit pixel-art sprite matching 100% of Reference Image 1's exact character design, outfit details, colors, and clean 1px dark outline, on a solid flat #FF00FF pure magenta background.\n"
                f"Reference Image 1 is the approved Character Master. Reference Image 2 is the exact pose, camera angle, and equipment/aura/effect layout to preserve faithfully.\n"
                f"POSE TO RENDER: {desc}\n\n{IDENTITY_RULES}"
            )
            jobs.append({"id": fid, "group": g, "ref1": MASTER_1024, "ref2": ref2, "prompt": prompt})
    return jobs


def run_one_job(job: Dict[str, object]) -> Tuple[str, bool, str]:
    fid = str(job["id"])
    out_dir = GEN_DIR / fid
    gen_png = out_dir / "generated.png"
    if gen_png.is_file() and gen_png.stat().st_size > 1024:
        return (fid, True, "cached")
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    prompts_dir = P2_WORK / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    pfile = prompts_dir / f"{fid}.txt"
    pfile.write_text(str(job["prompt"]), encoding="utf-8")
    cmd = [
        sys.executable, str(ROUTE_MEDIA), "image",
        "--route", "codex-cli",
        "--prompt-file", str(pfile),
        "--reference", str(job["ref1"]),
        "--reference", str(job["ref2"]),
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
    ap.add_argument("--groups", nargs="+", choices=["S2", "S3", "S4", "S5", "ALL"], default=["ALL"])
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()

    groups = ["S2", "S3", "S4", "S5"] if "ALL" in args.groups else args.groups
    GEN_DIR.mkdir(parents=True, exist_ok=True)
    jobs = build_jobs(groups)
    if args.only:
        only_set = set(args.only)
        jobs = [j for j in jobs if j["id"] in only_set]

    print(f"[TAPION PHASE 2 GEN] groups={groups} total_jobs={len(jobs)} workers={args.workers}", flush=True)
    t0 = time.time()
    ok_cnt = 0
    fails: List[Tuple[str, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(run_one_job, j): j["id"] for j in jobs}
        for idx, fut in enumerate(concurrent.futures.as_completed(futs), 1):
            fid, ok, msg = fut.result()
            el = time.time() - t0
            if ok:
                ok_cnt += 1
                print(f"  [{idx:02d}/{len(jobs):02d} OK   {el:5.1f}s] {fid} ({'cached' if msg == 'cached' else 'generated'})", flush=True)
            else:
                fails.append((fid, msg))
                print(f"  [{idx:02d}/{len(jobs):02d} FAIL {el:5.1f}s] {fid}: {msg}", flush=True)

    if fails:
        print(f"[RETRY] Retrying {len(fails)} failed jobs with workers=3...", flush=True)
        r_ids = {f[0] for f in fails}
        r_jobs = [j for j in jobs if j["id"] in r_ids]
        fails.clear()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            for fut in concurrent.futures.as_completed([pool.submit(run_one_job, j) for j in r_jobs]):
                fid, ok, msg = fut.result()
                if ok:
                    ok_cnt += 1
                    print(f"  [RETRY OK] {fid}", flush=True)
                else:
                    fails.append((fid, msg))
                    print(f"  [RETRY FAIL] {fid}: {msg}", flush=True)

    print(f"[SUMMARY] ok={ok_cnt}/{len(jobs)} failed={len(fails)} in {time.time() - t0:.1f}s", flush=True)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
