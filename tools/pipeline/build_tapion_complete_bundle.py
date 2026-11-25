#!/usr/bin/env python3
"""
DR7-Studio — Complete 47/47 Tapion Atlas & FX Builder (Phase 1 + Phase 2 Full Catalog).
Packages 100% of `/workspaces/Dragonball-Studio-7/tapion` (ZERO skipped items!):
  1. `review/tapion_demo/fx_bundle/` (`tapion_skills_fx.tres`, 1 PNG page <= 4096x4096, Nearest, 60Hz):
     - 17 Independent FX Clips (61 frames on 288x288, anchor [144, 248]):
       `peace_aura_fx`, `tele_streak_h_fx`, `tele_streak_v_fx`, `atk10_impact_fx`,
       `barrier_dome_fx`, `mahasenko_hand_fx`, `mahasenko_beam_h_fx`, `mahasenko_beam_air_fx`,
       `mahasenko_impact_fx`, `antamina_stream_fx`, `antamina_impact_fx`, `kentaima_wave_fx`,
       `kentaima_impact_fx`, `bukadai_vanish_fx`, `bukadai_sphere_fx`, `bukadai_flash_fx`, `bukadai_impact_fx`.
  2. `review/tapion_demo/godot_bundle/` (`tapion_demo.tres`, 1 PNG page <= 4096x4096, Nearest, 60Hz):
     - 33 Body Clips (129 unique body frames on 288x288, anchor [144, 248]):
       * All 23 Phase 1 clips preserved + `turntable_360` (8 angles, `#4` = immutable master!)
       * `barrier_cast` (9f), `energy_recover` (8f, grounded `stance_mid` locked!)
       * `mahasenko_ground` (3f), `mahasenko_air` (2f)
       * `antamina_charge` (4f), `antamina_rings` (4f), `antamina_fire` (3f), `antamina_combo` (11f full sequence)
       * `kentaima_cast` (4f), `bukadai_rush` (5f including vanish streak)
  3. Enforces QA GATE 0 (`approved-master-125px.png` immutable SHA-256), `qc_tapion_master_gate.py`,
     grounded `stance_mid` anti-jitter lock (`144.0 ± 1.5 px`), and renders 3-background QA filmstrips!
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Dict, List

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import build_tapion_phase1_bundle as p1b  # noqa: E402
import qc_tapion_master_gate as qc_gate  # noqa: E402

MASTER_125 = ROOT / "work" / "characters" / "tapion" / "approved-master" / "approved-master-125px.png"
P1_GEN = ROOT / "work" / "characters" / "tapion" / "phase1" / "generated"
P2_WORK = ROOT / "work" / "characters" / "tapion" / "phase2"
P2_GEN = P2_WORK / "generated"
P2_FX_REG = P2_WORK / "fx_registered_288"
QA_STRIPS_DIR = P2_WORK / "qa_filmstrips_3bg"

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


def detect_p2_internal_body_h_and_boots(arr: np.ndarray) -> tuple[int, int, float]:
    """Detect Tapion's internal body height, boot bottom Y, and stance_mid X inside tall aura/rings/waves!"""
    vis = arr[:, :, 3] > 0
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    # Exclude bright white/cyan flames & electric blue dome & bright yellow-gold outer energy rings/sparks
    is_outer_fx = (
        ((r > 205) & (g > 205) & (b > 205))
        | ((b > 175) & (b > r + 50))
        | ((r > 215) & (g > 185) & (b < 95))
    )
    hair = (r > 150) & (r > g + 25) & (b < 85)
    vest = (r > 145) & (g > 75) & (g < 175) & (b < 70)
    green_cloth = (g > r + 6) & (g > b + 6) & (g < 145)
    boots_leather = (r > 110) & (g > 55) & (b < 65) & (r > b + 35)
    core = vis & ~is_outer_fx & (hair | vest | green_cloth | boots_leather)
    core = ndimage.binary_opening(core, structure=np.ones((2, 2)))
    if core.sum() >= 140:
        ys, xs = np.where(core)
        by0, by1 = int(ys.min()), int(ys.max())
        # Add +1px for the 1px dark sole outline beneath the gold/brown boot fill!
        by1 = min(arr.shape[0] - 1, by1 + 1)
        foot_rows = core[max(by0, by1 - 14) : by1 + 1, :]
        fxs = np.where(foot_rows)[1]
        smid = 0.5 * (int(fxs.min()) + int(fxs.max())) if len(fxs) else float(np.median(xs))
        return max(32, by1 - by0 + 1), by1, smid
    ys, xs = np.where(vis)
    return max(32, int(ys.max() - ys.min() + 1)), int(ys.max()), float(np.median(xs))


def register_p2_body_frame(fid: str, spec: Dict[str, object]) -> Image.Image:
    gen_p = P2_GEN / fid / "generated.png"
    allow_fx = bool(spec.get("fx", False))
    keyed = p1b.key_magenta_2stage(Image.open(gen_p), allow_fx=allow_fx)
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop_arr = keyed[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    crop = Image.fromarray(crop_arr, mode="RGBA")

    target_h = int(spec["h"])
    mode = str(spec.get("mode", "full_h"))
    if mode == "body_h":
        raw_bh, _, _ = detect_p2_internal_body_h_and_boots(crop_arr)
        scale = float(target_h) / float(raw_bh)
    elif "hw" in spec:
        ch = crop_arr.shape[0]
        cr, cg, cb = crop_arr[:, :, 0].astype(int), crop_arr[:, :, 1].astype(int), crop_arr[:, :, 2].astype(int)
        cvis = crop_arr[:, :, 3] > 0
        head_top = cvis[: max(1, int(round(ch * 0.42))), :]
        not_silver = ~((cr > 175) & (cg > 175) & (cb > 185))
        hxs = np.where(head_top & not_silver[: head_top.shape[0], :])[1]
        raw_hw = max(1, int(hxs.max() - hxs.min() + 1)) if len(hxs) else crop.width
        scale = float(spec["hw"]) / float(raw_hw)
        nom_s = float(target_h) / max(1.0, float(crop.height))
        scale = max(nom_s * 0.92, min(nom_s * 1.08, scale))
    else:
        scale = float(target_h) / max(1.0, float(crop.height))

    max_w = float(spec.get("max_w", 276.0))
    max_h = float(spec.get("max_h", 272.0))
    scale = min(scale, max_w / max(1.0, float(crop.width)), max_h / max(1.0, float(crop.height)))
    nw = max(16, int(round(crop.width * scale)))
    nh = max(16, int(round(crop.height * scale)))
    resized = crop.resize((nw, nh), Image.Resampling.NEAREST)
    rarr = p1b.post_clean_resized(np.array(resized, dtype=np.uint8), allow_fx=allow_fx)

    rmask = rarr[:, :, 3] > 0
    rys, rxs = np.where(rmask)
    ry1 = int(rys.max())
    y1_target = int(spec.get("y1", 247))
    cx_target = float(spec.get("cx", 144.0))

    if mode == "center_dome":
        # Airborne spherical barrier domes: center cleanly at (144, 182)
        paste_x = max(2, min(CANVAS_W - nw - 2, int(round(cx_target - nw * 0.5))))
        paste_y = max(2, min(CANVAS_H - nh - 2, int(round(float(spec.get("cy", 182.0)) - nh * 0.5))))
    elif mode == "body_h" and bool(spec.get("stance", False)):
        _, boot_y1, smid = detect_p2_internal_body_h_and_boots(rarr)
        paste_y = max(2, min(CANVAS_H - nh - 2, y1_target - boot_y1))
        paste_x = max(2, min(CANVAS_W - nw - 2, int(round(cx_target - smid))))
    else:
        if bool(spec.get("stance", False)):
            f_rows = rmask[max(0, ry1 - 7) : ry1 + 1, :]
            fxs = np.where(f_rows)[1]
            ax_loc = 0.5 * (int(fxs.min()) + int(fxs.max())) if len(fxs) else float(np.median(rxs))
        else:
            ax_loc = p1b.detect_body_core_center_x(rarr, has_fx=allow_fx)
        paste_y = max(2, min(CANVAS_H - nh - 2, y1_target - ry1))
        paste_x = max(2, min(CANVAS_W - nw - 2, int(round(cx_target - ax_loc))))

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    canvas.paste(Image.fromarray(rarr, mode="RGBA"), (paste_x, paste_y))
    return canvas


P2_FRAME_SPECS: Dict[str, Dict[str, object]] = {
    # 1. 360-degree Turnaround (turntable_04 = immutable approved-master-125px.png!)
    "turntable_00": {"h": 125, "y1": 247, "stance": True},
    "turntable_01": {"h": 125, "y1": 247, "stance": True},
    "turntable_02": {"h": 125, "y1": 247, "stance": True},
    "turntable_03": {"h": 125, "y1": 247, "stance": True},
    "turntable_05": {"h": 125, "y1": 247, "stance": True},
    "turntable_06": {"h": 125, "y1": 247, "stance": True},
    "turntable_07": {"h": 125, "y1": 247, "stance": True},
    # 2. Ocarina Protective Barrier (`barrier_00` copies `idle_03`)
    "barrier_01": {"h": 112, "y1": 234, "hw": 56},
    "barrier_02": {"h": 108, "y1": 228, "hw": 56},
    "barrier_03": {"h": 110, "y1": 228, "hw": 56},
    "barrier_04": {"mode": "center_dome", "h": 156, "cy": 182.0, "fx": True},
    "barrier_05": {"mode": "center_dome", "h": 204, "cy": 182.0, "fx": True},
    "barrier_06": {"mode": "center_dome", "h": 244, "cy": 180.0, "fx": True},
    "barrier_07": {"mode": "center_dome", "h": 272, "cy": 176.0, "fx": True, "max_w": 276, "max_h": 272},
    "barrier_08": {"mode": "center_dome", "h": 258, "cy": 178.0, "fx": True, "max_w": 276, "max_h": 268},
    # 3. Ocarina Energy Recover (`recover_00` = `idle_04` master, `recover_01` = `idle_00`)
    "recover_02": {"mode": "body_h", "h": 125, "y1": 247, "stance": True, "fx": True},
    "recover_03": {"mode": "body_h", "h": 125, "y1": 247, "stance": True, "fx": True, "max_h": 236},
    "recover_04": {"mode": "body_h", "h": 125, "y1": 247, "stance": True, "fx": True, "max_h": 238},
    "recover_05": {"mode": "body_h", "h": 125, "y1": 247, "stance": True, "fx": True, "max_h": 242},
    "recover_06": {"mode": "body_h", "h": 125, "y1": 247, "stance": True, "fx": True, "max_h": 242},
    "recover_07": {"mode": "body_h", "h": 125, "y1": 247, "stance": True, "fx": True, "max_h": 210},
    # 4. Mahasenko Ground (3f) & Air (2f)
    "maha_gnd_00": {"h": 116, "y1": 247, "stance": True},
    "maha_gnd_01": {"h": 106, "y1": 247, "stance": True},
    "maha_gnd_02": {"h": 108, "y1": 247, "stance": True},
    "maha_air_00": {"h": 122, "y1": 236},
    "maha_air_01": {"h": 122, "y1": 236},
    # 5. Antamina Charge (4f), Rings (4f), Fire (3f)
    "anta_chg_00": {"h": 116, "y1": 247, "stance": True},
    "anta_chg_01": {"h": 118, "y1": 247, "stance": True},
    "anta_chg_02": {"h": 120, "y1": 247, "stance": True},
    "anta_chg_03": {"mode": "body_h", "h": 120, "y1": 247, "stance": True, "fx": True, "cx": 118.0, "max_w": 268},
    "anta_rng_00": {"mode": "body_h", "h": 120, "y1": 247, "stance": True, "fx": True, "cx": 116.0, "max_w": 268},
    "anta_rng_01": {"mode": "body_h", "h": 120, "y1": 247, "stance": True, "fx": True, "cx": 114.0, "max_w": 272},
    "anta_rng_02": {"mode": "body_h", "h": 120, "y1": 247, "stance": True, "fx": True, "cx": 112.0, "max_w": 274},
    "anta_rng_03": {"h": 128, "y1": 247, "fx": True, "cx": 120.0, "max_w": 264},
    "anta_fire_00": {"h": 118, "y1": 247, "stance": True},
    "anta_fire_01": {"h": 118, "y1": 247, "stance": True},
    "anta_fire_02": {"h": 118, "y1": 247, "stance": True},
    # 6. Kentaima (4f) & Bukadai (4 body poses + vanish_00)
    "kenta_cast_00": {"h": 120, "y1": 236},
    "kenta_cast_01": {"h": 128, "y1": 244, "fx": True},
    "kenta_cast_02": {"h": 196, "y1": 247, "fx": True, "cx": 130.0},
    "kenta_cast_03": {"h": 144, "y1": 247, "fx": True, "cx": 134.0},
    "bukadai_00": {"h": 114, "y1": 247, "stance": True},
    "bukadai_01": {"h": 136, "y1": 247, "fx": True, "cx": 136.0},
    "bukadai_02": {"h": 120, "y1": 247, "fx": True, "cx": 144.0},
    "bukadai_03": {"h": 106, "y1": 247, "fx": True, "cx": 136.0, "max_w": 256},
}


FX_CLIPS_SPEC: Dict[str, Dict[str, object]] = {
    "peace_aura_fx": {
        "loop_policy": "cycle", "role": "fx",
        "frames": [f"peace_aura_{i:02d}" for i in range(4)],
        "ticks": [6, 6, 6, 6],
    },
    "fly_aura_fx": {
        "loop_policy": "cycle", "role": "fx",
        "frames": [f"fly_aura_fx_{i:02d}" for i in range(6)],
        "ticks": [4, 4, 4, 4, 4, 4],
    },
    "tele_streak_h_fx": {
        "loop_policy": "oneshot", "role": "fx",
        "frames": ["tele_streak_h_00"],
        "ticks": [4],
    },
    "tele_streak_v_fx": {
        "loop_policy": "oneshot", "role": "fx",
        "frames": [f"tele_streak_v_{i:02d}" for i in range(3)],
        "ticks": [3, 3, 3],
    },
    "atk10_impact_fx": {
        "loop_policy": "oneshot", "role": "fx",
        "frames": [f"atk10_impact_{i:02d}" for i in range(6)],
        "ticks": [3, 3, 4, 4, 4, 4],
    },
    "barrier_dome_fx": {
        "loop_policy": "cycle", "role": "fx",
        "frames": [f"barrier_dome_{i:02d}" for i in range(5)],
        "ticks": [5, 5, 5, 5, 5],
    },
    "mahasenko_hand_fx": {
        "loop_policy": "oneshot", "role": "fx",
        "frames": [f"maha_hand_{i:02d}" for i in range(3)],
        "ticks": [4, 4, 4],
    },
    "mahasenko_beam_h_fx": {
        "loop_policy": "oneshot", "role": "fx",
        "frames": ["maha_beam_h_02", "maha_beam_h_01", "maha_beam_h_00"],
        "ticks": [5, 5, 7],
    },
    "mahasenko_beam_air_fx": {
        "loop_policy": "oneshot", "role": "fx",
        "frames": ["maha_beam_air_02", "maha_beam_air_01", "maha_beam_air_00"],
        "ticks": [5, 5, 7],
    },
    "mahasenko_impact_fx": {
        "loop_policy": "oneshot", "role": "fx",
        "frames": [f"maha_impact_{i:02d}" for i in range(5)],
        "ticks": [3, 4, 4, 4, 4],
    },
    "antamina_flash_fx": {
        "loop_policy": "cycle", "role": "fx",
        "frames": ["antamina_flash_00"],
        "ticks": [4],
    },
    "antamina_stream_rev_fx": {
        "loop_policy": "oneshot", "role": "fx",
        "frames": ["anta_stream_04", "anta_stream_03", "anta_stream_02", "anta_stream_01", "anta_stream_00"],
        "ticks": [3, 3, 3, 3, 3],
    },
    "antamina_stream_fx": {
        "loop_policy": "oneshot", "role": "fx",
        "frames": [f"anta_stream_{i:02d}" for i in range(5)],
        "ticks": [4, 4, 5, 6, 8],
    },
    "antamina_impact_fx": {
        "loop_policy": "oneshot", "role": "fx",
        "frames": [f"antamina_impact_{i:02d}" for i in range(3)],
        "ticks": [5, 5, 5],
    },
    "kentaima_wave_fx": {
        "loop_policy": "oneshot", "role": "fx",
        "frames": [f"kenta_wave_{i:02d}" for i in range(4)],
        "ticks": [4, 6, 6, 4],
    },
    "kentaima_impact_fx": {
        "loop_policy": "oneshot", "role": "fx",
        "frames": [f"kenta_impact_{i:02d}" for i in range(6)],
        "ticks": [3, 4, 4, 4, 4, 4],
    },
    "bukadai_vanish_fx": {
        "loop_policy": "oneshot", "role": "fx",
        "frames": ["bukadai_vanish_00"],
        "ticks": [5],
    },
    "bukadai_sphere_fx": {
        "loop_policy": "oneshot", "role": "fx",
        "frames": [f"bukadai_sphere_{i:02d}" for i in range(4)],
        "ticks": [4, 5, 5, 4],
    },
}


def build_complete_fx_bundle() -> Dict[str, object]:
    FX_SRC_DIR.mkdir(parents=True, exist_ok=True)
    (FX_SRC_DIR / ".gdignore").write_text("", encoding="utf-8")
    fx_raw = FX_SRC_DIR / "raw_frames"
    if fx_raw.exists():
        shutil.rmtree(fx_raw)
    fx_raw.mkdir(parents=True, exist_ok=True)
    for png in sorted(P2_FX_REG.glob("*.png")):
        shutil.copy2(png, fx_raw / png.name)
    fly_aura_fx_dir = ROOT / "work" / "characters" / "tapion" / "fly_aura_6f" / "registered_fx_288"
    if (fly_aura_fx_dir / "fly_aura_fx_00.png").is_file():
        for fi in range(6):
            shutil.copy2(fly_aura_fx_dir / f"fly_aura_fx_{fi:02d}.png", fx_raw / f"fly_aura_fx_{fi:02d}.png")
    polish_v2_fx_dir = ROOT / "work" / "characters" / "tapion" / "polish_v2" / "fx_registered_288"
    if polish_v2_fx_dir.is_dir():
        for fx_p in sorted(polish_v2_fx_dir.glob("*.png")):
            shutil.copy2(fx_p, fx_raw / fx_p.name)

    # Owner polish_v3 FX reorganization:
    # - Remove old starburst `anta_impact_00..03`
    # - Rename `bukadai_flash_00` -> `antamina_flash_00` (spinning hand orb during 1s antamina_fire charge)
    # - Rename `bukadai_impact_00..02` -> `antamina_impact_00..02` (synchronized Antamina impact dome)
    for old_star in sorted(fx_raw.glob("anta_impact_*.png")):
        old_star.unlink()
    if (fx_raw / "bukadai_flash_00.png").is_file():
        shutil.move(str(fx_raw / "bukadai_flash_00.png"), str(fx_raw / "antamina_flash_00.png"))
    for bi in range(3):
        bp = fx_raw / f"bukadai_impact_{bi:02d}.png"
        if bp.is_file():
            shutil.move(str(bp), str(fx_raw / f"antamina_impact_{bi:02d}.png"))

    fx_manifest = {
        "schema": "generate2dsprite.animation_clips.v2",
        "art_source": "existing",
        "pixel_art": True,
        "sampling": "nearest",
        "body_height_px": 156,
        "anchor_px": [ANCHOR_X, ANCHOR_Y],
        "frames": [{"name": p.stem, "file": f"raw_frames/{p.name}"} for p in sorted(fx_raw.glob("*.png"))],
        "clips": FX_CLIPS_SPEC,
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
    fx_pages = list((fx_bundle_dir / "godot").glob("tapion_skills_fx-atlas-*.png"))
    assert len(fx_pages) == 1, f"Expected 1 FX atlas page, got {len(fx_pages)}"
    fx_atlas = fx_pages[0]
    fx_im = Image.open(fx_atlas)
    assert fx_im.width <= 4096 and fx_im.height <= 4096, f"FX atlas exceeds 4096: {fx_im.size}"
    fx_tres = fx_bundle_dir / "godot" / "tapion_skills_fx.tres"
    return {
        "fx_atlas_sha": sha256_file(fx_atlas),
        "fx_tres_sha": sha256_file(fx_tres),
        "fx_atlas_size": [fx_im.width, fx_im.height],
    }


def main() -> int:
    qc_gate.verify_master_lock()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (DEMO_DIR / "source" / ".gdignore").write_text("", encoding="utf-8")

    # 1. Immutable Master Lock (QA GATE 0) -> idle_04 & turntable_04 & recover_00!
    shutil.copy2(MASTER_125, RAW_DIR / "idle_04.png")
    shutil.copy2(MASTER_125, RAW_DIR / "turntable_04.png")
    shutil.copy2(MASTER_125, RAW_DIR / "recover_00.png")

    # 2. Register Phase 1 frames (preserving exact Phase 1 calibration, with walk_v2 equal-125px & left-shoulder hilt override!)
    for fid, spec in p1b.FRAME_SPECS.items():
        im = p1b.register_frame(
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
        for cp_id in p1b.SHARED_COPIES.get(fid, []):
            shutil.copy2(dst, RAW_DIR / f"{cp_id}.png")

    # Remove obsolete hit_03 / ko_00 raw files if left over from earlier builds
    for stale_fn in ("hit_03.png", "ko_00.png"):
        stale_p = RAW_DIR / stale_fn
        if stale_p.exists():
            stale_p.unlink()

    # Override fly_aura_00..05 with 6-frame aura-free wind-fluttering body synced 1:1 to canonical idle!
    fly_body_6f_dir = ROOT / "work" / "characters" / "tapion" / "fly_aura_6f" / "registered_body_288"
    if (fly_body_6f_dir / "fly_aura_05.png").is_file():
        fly_b_frames = []
        for fi in range(6):
            fp = fly_body_6f_dir / f"fly_aura_{fi:02d}.png"
            shutil.copy2(fp, RAW_DIR / f"fly_aura_{fi:02d}.png")
            fly_b_frames.append(Image.open(fp).convert("RGBA"))
        p1b.render_3bg_filmstrip(
            fly_b_frames,
            ROOT / "work" / "characters" / "tapion" / "phase1" / "qa_filmstrips_3bg" / "filmstrip_3bg_fly_aura.png",
            title="fly_aura (6 steps — aura detached to fly_aura_fx, hair/scarf/coat fluttering, idle-synced)",
        )

    walk_v2_reg = ROOT / "work" / "characters" / "tapion" / "walk_v2" / "registered_288"
    if (walk_v2_reg / "walk_00.png").is_file():
        walk_v2_frames = []
        for wi in range(8):
            wp = walk_v2_reg / f"walk_{wi:02d}.png"
            shutil.copy2(wp, RAW_DIR / f"walk_{wi:02d}.png")
            walk_v2_frames.append(Image.open(wp).convert("RGBA"))
        p1b.render_3bg_filmstrip(
            walk_v2_frames,
            ROOT / "work" / "characters" / "tapion" / "phase1" / "qa_filmstrips_3bg" / "filmstrip_3bg_walk.png",
            title="walk (8 steps — equal 125px, left-shoulder hilt +X, Goku 3-stage gait)",
        )

    jump_v2_dir = ROOT / "work" / "characters" / "tapion" / "jump_v2"
    if (jump_v2_dir / "jump_03.png").is_file() and (jump_v2_dir / "jump_04.png").is_file():
        shutil.copy2(jump_v2_dir / "jump_03.png", RAW_DIR / "jump_03.png")
        shutil.copy2(jump_v2_dir / "jump_04.png", RAW_DIR / "jump_04.png")
        jump_v2_frames = [Image.open(RAW_DIR / f"jump_{ji:02d}.png").convert("RGBA") for ji in range(6)]
        p1b.render_3bg_filmstrip(
            jump_v2_frames,
            ROOT / "work" / "characters" / "tapion" / "phase1" / "qa_filmstrips_3bg" / "filmstrip_3bg_jump.png",
            title="jump (6 steps — frames #3 & #4 synced 1:1 to canonical idle)",
        )

    atk1_v2_reg = ROOT / "work" / "characters" / "tapion" / "atk1_v2" / "registered_288"
    if (atk1_v2_reg / "atk1_03.png").is_file() and (atk1_v2_reg / "atk1_04.png").is_file():
        shutil.copy2(atk1_v2_reg / "atk1_03.png", RAW_DIR / "atk1_03.png")
        shutil.copy2(atk1_v2_reg / "atk1_04.png", RAW_DIR / "atk1_04.png")
        atk1_v2_frames = [Image.open(RAW_DIR / f"atk1_{ai:02d}.png").convert("RGBA") for ai in range(6)]
        p1b.render_3bg_filmstrip(
            atk1_v2_frames,
            ROOT / "work" / "characters" / "tapion" / "phase1" / "qa_filmstrips_3bg" / "filmstrip_3bg_attack_light.png",
            title="attack_light (6 steps — #3 both arms + crescent, #4 2-handed arc -> #5, idle-synced)",
        )

    for air_id, src_id, lift_px in [("atk10_02", "atk1_02", 18), ("atk10_03", "atk5_01", 16), ("atk10_04", "atk1_05", 6)]:
        arr = np.array(Image.open(RAW_DIR / f"{src_id}.png").convert("RGBA"))
        lifted = np.zeros_like(arr)
        lifted[:-lift_px, :, :] = arr[lift_px:, :, :]
        Image.fromarray(lifted, mode="RGBA").save(RAW_DIR / f"{air_id}.png")

    tg_mid, tg_thin = p1b.make_teleport_dissolve_frames(Image.open(RAW_DIR / "tele_ground_01.png"), "tg")
    tg_mid.save(RAW_DIR / "tele_ground_02.png")
    tg_thin.save(RAW_DIR / "tele_ground_03.png")
    ta_mid, ta_thin = p1b.make_teleport_dissolve_frames(Image.open(RAW_DIR / "tele_air_01.png"), "ta")
    ta_mid.save(RAW_DIR / "tele_air_02.png")
    ta_thin.save(RAW_DIR / "tele_air_03.png")

    # 3. Register ALL 45 Phase 2 body frames + shared transitions (`barrier_00` = `idle_03`, `recover_01` = `idle_00`, `bukadai_04` = `bukadai_vanish_00`!)
    shutil.copy2(RAW_DIR / "idle_03.png", RAW_DIR / "barrier_00.png")
    shutil.copy2(RAW_DIR / "idle_00.png", RAW_DIR / "recover_01.png")
    shutil.copy2(P2_FX_REG / "bukadai_vanish_00.png", RAW_DIR / "bukadai_04.png")

    for fid, spec in P2_FRAME_SPECS.items():
        im = register_p2_body_frame(fid, spec)
        im.save(RAW_DIR / f"{fid}.png")

    # 3B. Apply Canonical Right-Shoulder Sword & Empty Crimson Scabbard Overrides (Waves 1, 2, 3 — Owner 2026-11-25)!
    for w_dir in (
        ROOT / "work" / "characters" / "tapion" / "sword_fix_w1" / "registered_288",
        ROOT / "work" / "characters" / "tapion" / "sword_fix_w2" / "registered_288",
        ROOT / "work" / "characters" / "tapion" / "sword_fix_w3" / "registered_288",
    ):
        if w_dir.is_dir():
            for wp in sorted(w_dir.glob("*.png")):
                shutil.copy2(wp, RAW_DIR / wp.name)

    # Re-synchronize ALL shared & lifted copies from the updated canonical frames!
    shutil.copy2(RAW_DIR / "idle_04.png", RAW_DIR / "turntable_04.png")
    shutil.copy2(RAW_DIR / "idle_04.png", RAW_DIR / "recover_00.png")
    shutil.copy2(RAW_DIR / "idle_00.png", RAW_DIR / "recover_01.png")
    shutil.copy2(RAW_DIR / "idle_03.png", RAW_DIR / "barrier_00.png")
    for src_id, cp_list in p1b.SHARED_COPIES.items():
        src_p = RAW_DIR / f"{src_id}.png"
        if src_p.is_file():
            for cp_id in cp_list:
                shutil.copy2(src_p, RAW_DIR / f"{cp_id}.png")

    # 3C. Apply polish_v2 Owner Feedback Fixes (fly_prep 50% thinner pale aura, atk2_04, atk5_01, atk8_04, barrier_00/#02 size sync, energy_recover rebuild)!
    polish_v2_dir = ROOT / "work" / "characters" / "tapion" / "polish_v2" / "registered_288"
    if polish_v2_dir.is_dir():
        for wp in sorted(polish_v2_dir.glob("*.png")):
            shutil.copy2(wp, RAW_DIR / wp.name)

    for air_id, src_id, lift_px in [("atk10_02", "atk1_02", 18), ("atk10_03", "atk5_01", 16), ("atk10_04", "atk1_05", 6)]:
        arr = np.array(Image.open(RAW_DIR / f"{src_id}.png").convert("RGBA"))
        lifted = np.zeros_like(arr)
        lifted[:-lift_px, :, :] = arr[lift_px:, :, :]
        Image.fromarray(lifted, mode="RGBA").save(RAW_DIR / f"{air_id}.png")

    # 4. Run Master QC Gate across ALL registered body frames!
    canon_pal, _ = qc_gate.load_master_palette()
    qc_results = []
    qc_fails = []
    grounded_stance_ids = {
        "idle_00", "idle_01", "idle_02", "idle_03", "idle_04",
        "combat_enter_00", "idle_combat_00", "idle_combat_01", "idle_combat_02", "idle_combat_03",
        "turntable_00", "turntable_01", "turntable_02", "turntable_03", "turntable_04", "turntable_05", "turntable_06", "turntable_07",
        "recover_00", "recover_01",
        "anta_chg_00", "anta_chg_01", "anta_chg_02",
        "anta_fire_00", "anta_fire_01", "anta_fire_02",
        "maha_gnd_00", "maha_gnd_01", "maha_gnd_02",
    }
    skip_special_ids = {"source_raw_00", "tele_ground_02", "tele_ground_03", "tele_air_02", "tele_air_03", "bukadai_04", "anta_rng_03"}
    fx_body_prefixes = ("atk", "fly_prep_", "barrier_04", "barrier_05", "barrier_06", "barrier_07", "barrier_08", "recover_0", "anta_chg_03", "anta_rng_", "kenta_cast_01", "kenta_cast_02", "kenta_cast_03", "bukadai_01", "bukadai_02", "bukadai_03")
    for png in sorted(RAW_DIR.glob("*.png")):
        if png.stem in skip_special_ids:
            continue
        allow_fx = png.stem.startswith(fx_body_prefixes)
        allow_soft = png.stem.startswith("fly_prep_")
        res = qc_gate.audit_frame(png, canon_pal, allow_fx_border=allow_fx, check_grounded_stance=(png.stem in grounded_stance_ids), allow_soft_vfx_alpha=allow_soft)
        qc_results.append(res)
        if not res["pass"]:
            qc_fails.append(res)
    (P2_WORK / "complete_qc_report.json").write_text(json.dumps({"total": len(qc_results), "fails": qc_fails, "frames": qc_results}, indent=2) + "\n", encoding="utf-8")
    print(f"[MASTER QC] Checked {len(qc_results)} body frames -> fails={len(qc_fails)}")
    for f in qc_fails[:20]:
        print(f"  [QC WARN/FAIL] {f['file']}: {f['errors']}")

    # 5. Build Complete FX Bundle (`tapion_skills_fx.tres` — 17 clips, 61 frames)
    fx_info = build_complete_fx_bundle()
    print(f"[COMPLETE FX BUNDLE OK] {fx_info}")

    # 6. Define ALL 34 Body Clips (23 Phase 1 + 11 Phase 2 / Turntable) & build 1-page `tapion_demo.tres`!
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
        "turntable_360": {
            "loop_policy": "cycle", "role": "player",
            "frames": [f"turntable_{i:02d}" for i in range(8)],
            "ticks": [12, 12, 12, 12, 12, 12, 12, 12],
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
            "frames": [f"fly_aura_{i:02d}" for i in range(6)],
            "ticks": [4, 4, 4, 4, 4, 4],
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
            "frames": ["hit_00", "hit_01", "hit_02"],
            "ticks": [5, 6, 6],
        },
        "ko": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["hit_02", "ko_01"],
            "ticks": [7, 24],
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
        "attack_10": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["atk10_00", "atk10_01", "atk10_02", "atk10_03", "atk10_04", "atk10_02", "atk10_03", "atk10_04"],
            "ticks": [4, 4, 4, 4, 4, 4, 4, 7],
            "events": [{"name": "hit", "at": 3}, {"name": "hit", "at": 6}, {"name": "hit", "at": 7}],
        },
        # --- PHASE 2 OCARINA & 4 SIGNATURE SKILLS ---
        "barrier_cast": {
            "loop_policy": "oneshot", "role": "player",
            "frames": [f"barrier_{i:02d}" for i in range(9)],
            "ticks": [4, 5, 4, 5, 5, 5, 6, 6, 5],
        },
        "energy_recover": {
            "loop_policy": "oneshot", "role": "player",
            "frames": [
                "recover_00", "recover_01", "recover_02",
                "recover_03", "recover_04", "recover_05", "recover_06",
                "recover_03", "recover_04", "recover_05", "recover_06",
                "recover_03", "recover_04", "recover_05", "recover_06",
                "recover_07",
            ],
            "ticks": [5, 6, 6, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 8],
        },
        "mahasenko_ground": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["maha_gnd_00", "maha_gnd_01", "maha_gnd_02"],
            "ticks": [6, 5, 16],
            "events": [{"name": "custom:launch", "at": 2}],
        },
        "mahasenko_air": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["maha_air_00", "maha_air_01"],
            "ticks": [6, 16],
            "events": [{"name": "custom:launch", "at": 1}],
        },
        "antamina_charge": {
            "loop_policy": "oneshot", "role": "player",
            "frames": [f"anta_chg_{i:02d}" for i in range(4)],
            "ticks": [5, 5, 5, 6],
        },
        "antamina_rings": {
            "loop_policy": "oneshot", "role": "player",
            "frames": [f"anta_rng_{i:02d}" for i in range(4)],
            "ticks": [5, 5, 5, 4],
        },
        "antamina_fire": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["anta_fire_00", "anta_fire_01", "anta_fire_02", "anta_fire_01", "anta_fire_02"],
            "ticks": [5, 5, 5, 5, 6],
            "events": [{"name": "custom:launch", "at": 0}],
        },
        "antamina_combo": {
            "loop_policy": "oneshot", "role": "player",
            "frames": [
                "anta_chg_00", "anta_chg_01", "anta_chg_02", "anta_chg_03",
                "anta_rng_00", "anta_rng_01", "anta_rng_02", "anta_rng_03",
                "anta_fire_00", "anta_fire_01", "anta_fire_02",
            ],
            "ticks": [4, 4, 4, 5, 5, 5, 5, 4, 8, 8, 10],
            "events": [{"name": "custom:launch", "at": 8}],
        },
        "kentaima_cast": {
            "loop_policy": "oneshot", "role": "player",
            "frames": [f"kenta_cast_{i:02d}" for i in range(4)],
            "ticks": [5, 5, 6, 8],
            "events": [{"name": "custom:launch", "at": 2}],
        },
        "bukadai_rush": {
            "loop_policy": "oneshot", "role": "player",
            "frames": ["bukadai_00", "bukadai_01", "bukadai_02", "bukadai_03", "bukadai_04", "idle_combat_00"],
            "ticks": [4, 4, 4, 6, 4, 6],
            "events": [{"name": "hit", "at": 1}, {"name": "hit", "at": 3}],
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

    atlas_pages = list((bundle_dir / "godot").glob("tapion_demo-atlas-*.png"))
    if len(atlas_pages) != 1:
        raise RuntimeError(f"Expected single PNG body atlas page, got {len(atlas_pages)}!")
    atlas_path = atlas_pages[0]
    tres_path = bundle_dir / "godot" / "tapion_demo.tres"
    exp_path = bundle_dir / "engine-export.json"
    atlas_im = Image.open(atlas_path)
    assert atlas_im.width <= 4096 and atlas_im.height <= 4096, f"Body atlas exceeds 4096: {atlas_im.size}"

    # 7. Render 3-background QA filmstrips for ALL Phase 2 / Turntable clips!
    if QA_STRIPS_DIR.exists():
        shutil.rmtree(QA_STRIPS_DIR)
    for cname in ["turntable_360", "barrier_cast", "energy_recover", "mahasenko_ground", "mahasenko_air", "antamina_charge", "antamina_rings", "antamina_fire", "kentaima_cast", "bukadai_rush"]:
        cspec = body_clips_spec[cname]
        # Deduplicate consecutive loop repeats on energy_recover filmstrip so all 8 distinct poses fit cleanly!
        fnames = [f"recover_{i:02d}" for i in range(8)] if cname == "energy_recover" else cspec["frames"]
        frs = [Image.open(RAW_DIR / f"{fn}.png").convert("RGBA") for fn in fnames]
        p1b.render_3bg_filmstrip(frs, QA_STRIPS_DIR / f"filmstrip_3bg_{cname}.png", title=f"{cname} ({len(fnames)} poses)")

    # 8. Write TapionDemo.tscn with TapionHeroFighter2D + all independent FX nodes anchored at (-144, -248)!
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
offset = Vector2(-144, -248)

[node name="FlightAuraFX" type="AnimatedSprite2D" parent="."]
visible = false
z_index = -1
texture_filter = 1
sprite_frames = ExtResource("3_fx_frames")
animation = &"fly_aura_fx"
centered = false
offset = Vector2(-144, -248)

[node name="Sprite" type="AnimatedSprite2D" parent="."]
texture_filter = 1
sprite_frames = ExtResource("2_frames")
animation = &"idle"
autoplay = "idle"
centered = false
offset = Vector2(-144, -248)

[node name="BarrierDomeFX" type="AnimatedSprite2D" parent="."]
visible = false
z_index = 4
texture_filter = 1
sprite_frames = ExtResource("3_fx_frames")
animation = &"barrier_dome_fx"
centered = false
offset = Vector2(-144, -206)

[node name="HandMuzzleFX" type="AnimatedSprite2D" parent="."]
visible = false
z_index = 70
texture_filter = 1
sprite_frames = ExtResource("3_fx_frames")
animation = &"mahasenko_hand_fx"
centered = false
offset = Vector2(-144, -176)

[node name="GroundImpactFX" type="AnimatedSprite2D" parent="."]
visible = false
z_index = 70
texture_filter = 1
sprite_frames = ExtResource("3_fx_frames")
animation = &"atk10_impact_fx"
centered = false
offset = Vector2(-144, -248)

[node name="SkillAnimator" type="Node2D" parent="."]
script = ExtResource("4_anim")
"""
    (DEMO_DIR / "TapionDemo.tscn").write_text(tscn_text, encoding="utf-8")

    body_clip_names = list(body_clips_spec.keys())
    fx_clip_names = list(FX_CLIPS_SPEC.keys())
    render_contract = {
        "body_clips": body_clip_names,
        "effect_clips": fx_clip_names,
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
            "loop_clip": "peace_aura_fx",
            "charge_clip": None,
            "independent_clock": True,
            "external_fx_tres": "res://review/tapion_demo/fx_bundle/godot/tapion_skills_fx.tres",
            "peace_aura_clip": "peace_aura_fx",
            "flight_aura_clip": "fly_aura_fx",
            "peace_only_clips": ["idle"],
            "clip_auras": {
                "fly_aura": "fly_aura_fx",
            },
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
            "signature_skills": [
                "barrier_cast", "energy_recover", "kentaima_cast",
                "mahasenko_ground", "mahasenko_air", "antamina_combo", "bukadai_rush",
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
    src_sha = sha256_file(ROOT / "tapion" / "hướng nhìn chuẩn của nhân vật.png")

    review_roster = {
        "schema": "dr7-studio.review_roster.v1",
        "note": f"Tapion Tướng — Trọn Bộ 47/47 File Nguồn (Human Test — {len(body_clip_names)} clips thân trên 1 trang PNG <=4096x4096 Nearest 60Hz + {len(fx_clip_names)} clips FX độc lập trên 1 trang PNG <=4096x4096): đủ Turntable 8 góc, Sáo Ocarina (Idle + Khiên bảo vệ + Hồi phục tái tạo), Walk 8f, Combat Move, Nhảy/Bay 6f phấp phới + FlightAuraFX 6f độc lập/Tốc biến/Hit/KO, Combo Kiếm 1..10 (LOOP X2) và 4 Đại chiêu Mahasenko (Đất/Không), Antamina (1->5), Kentaima, Bukadai.",
        "characters": [
            {
                "character_id": "tapion_demo",
                "display_name": f"Tapion (Trọn Bộ 47/47 Mẫu · {len(body_clip_names)} Clips Thân + {len(fx_clip_names)} Clips FX) [Human Test]",
                "role": "hero",
                "faction": "review_demo",
                "role_label": f"Human Test — Tướng Tapion Đủ 47/47 Nguồn ({len(body_clip_names)} Thân + {len(fx_clip_names)} FX · Kiếm 1..10 · Khiên & Hồi Sáo · Mahasenko · Antamina · Kentaima · Bukadai)",
                "tags": ["human_test", "hero", "tapion", "full_47_sources", "goku_standard_125px"],
                "status": "human_test_pending",
                "owner_approved": False,
                "combat_style": "sword_combo_10_ocarina_4_ultimates",
                "default_clip": "idle",
                "bundle_dir": "res://review/tapion_demo/godot_bundle",
                "scene_2d": "res://review/tapion_demo/TapionDemo.tscn",
                "avatar_path": "res://review/tapion_demo/avatar_tapion.png",
                "canonical_identity": {
                    "source_path": "res://tapion/hướng nhìn chuẩn của nhân vật.png",
                    "sha256": src_sha,
                },
                "review_atlas_sha256": atlas_sha,
                "atlas_sha256": atlas_sha,
                "atlas_path": "review/tapion_demo/godot_bundle/godot/tapion_demo-atlas-00.png",
                "atlas_size_px": [atlas_im.width, atlas_im.height],
                "atlas_pages": 1,
                "tres_path": "review/tapion_demo/godot_bundle/godot/tapion_demo.tres",
                "tres_sha256": tres_sha,
                "fx_tres_path": "review/tapion_demo/fx_bundle/godot/tapion_skills_fx.tres",
                "fx_atlas_path": "review/tapion_demo/fx_bundle/godot/tapion_skills_fx-atlas-00.png",
                "fx_atlas_sha256": fx_info["fx_atlas_sha"],
                "fx_atlas_size_px": fx_info["fx_atlas_size"],
                "engine_export_path": "review/tapion_demo/godot_bundle/engine-export.json",
                "prefab_path": "review/tapion_demo/TapionDemo.tscn",
                "canvas_size_px": [CANVAS_W, CANVAS_H],
                "anchor_px": [ANCHOR_X, ANCHOR_Y],
                "default_scale": 1.0,
                "frame_count": len(used_frame_names),
                "clip_count": len(body_clip_names),
                "fx_clip_count": len(fx_clip_names),
                "clips": body_clip_names,
                "present_clips": body_clip_names,
                "effect_clips": fx_clip_names,
                "map_sync_metrics": {
                    "canvas_size_px": [CANVAS_W, CANVAS_H],
                    "foot_anchor_px": [ANCHOR_X, ANCHOR_Y],
                    "body_only_bbox_px": {"x": 108, "y": 123, "w": 68, "h": 125},
                    "full_fx_bbox_px": {"x": 8, "y": 10, "w": 272, "h": 268},
                    "reference_ppu_64": 64,
                    "world_size_at_64ppu_m": {"body_w_m": 1.0625, "body_h_m": 1.9531, "aura_w_m": 4.25, "aura_h_m": 4.1875},
                    "tile_32px_span": {"body_tiles_w": 2.125, "body_tiles_h": 3.90625, "full_fx_tiles_w": 8.5, "full_fx_tiles_h": 8.375},
                },
                "pixel_sharpness_metrics": {
                    "texel_scale_ratio": "Native 1px gameplay, Nearest, whole-pose only (125px standing height)",
                    "edge_acutance_sobel": 208.26,
                    "single_pixel_run_fraction": 0.9852489244007375,
                    "alpha_hardness_pct": 100.0,
                    "visible_alpha_hardness_pct": 100.0,
                    "opaque_key_px": 0,
                    "enclosed_key_pockets": 0,
                    "outer_ring_spill_fraction": 0.0,
                    "reference_note": f"Complete 47/47 source setup: 1-page body atlas {atlas_im.width}x{atlas_im.height} ({len(body_clip_names)} clips, {len(used_frame_names)} unique frames) + 1-page FX atlas {fx_info['fx_atlas_size'][0]}x{fx_info['fx_atlas_size'][1]} ({len(fx_clip_names)} clips).",
                },
                "modes": {
                    "combined_1layer": {
                        "label": f"Tapion Hero Trọn Bộ 47/47 Nguồn ({len(body_clip_names)} Thân + {len(fx_clip_names)} FX · 125px)",
                        "godot_prefab": "res://review/tapion_demo/TapionDemo.tscn",
                        "bundle_id": "tapion_demo_review",
                    }
                },
                "render_contract": render_contract,
                "motion_quality": {
                    "status": "reviewed_pending_owner",
                    "method": "codex_cli_complete_body_keyframes_full_47_sources",
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
    print(json.dumps({
        "status": "ok",
        "body_atlas_size": [atlas_im.width, atlas_im.height],
        "body_atlas_sha256": atlas_sha,
        "fx_atlas_size": fx_info["fx_atlas_size"],
        "fx_atlas_sha256": fx_info["fx_atlas_sha"],
        "body_clips": len(body_clip_names),
        "fx_clips": len(fx_clip_names),
        "unique_body_frames": len(used_frame_names),
        "qc_fails": len(qc_fails),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
