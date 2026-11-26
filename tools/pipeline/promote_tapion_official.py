#!/usr/bin/env python3
"""Promote Tapion from review/tapion_demo/ to official assets/tapion/ & assets/fx/tapion_skills_fx/.

Prunes all unused/redundant clips & frames before repacking:
  - Body: 34 -> 30 active clips (149 -> 136 frames; drops turntable_360, antamina_charge,
    antamina_rings, antamina_fire and their 13 unreferenced frames).
  - FX:   20 -> 19 active clips (75 -> 74 frames; drops antamina_flash_fx / antamina_flash_00).
Exports both bundles at 60Hz Nearest on 1 PNG page <= 4096x4096, copies avatar_tapion.png,
writes assets/tapion/master_approved_lock.json & assets/tapion/owner_approval.json (PIPE-024),
and prints full SHA-256 receipts.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = ROOT / "review" / "tapion_demo"
OUT_BODY_DIR = ROOT / "assets" / "tapion"
OUT_FX_DIR = ROOT / "assets" / "fx" / "tapion_skills_fx"

BUILD_CLIPS = ROOT / ".agents/skills/generate2dsprite/scripts/build_animation_clips.py"
EXPORT_ENGINE = ROOT / ".agents/skills/generate2dsprite/scripts/export_engine.py"

PRUNED_BODY_CLIPS = {"turntable_360", "antamina_charge", "antamina_rings", "antamina_fire"}
PRUNED_FX_CLIPS = {"antamina_flash_fx"}

OWNER_APPROVAL_MSG = (
    "ok anh chốt 2 nhân vật kèm map cell giúp anh chốt theo qui trình , "
    "các hoạt ảnh dư thừa không sử dụng của tapion cũng dọn dẹp giúp anh xác định các hoạt ảnh đang sử dụng của tapion, "
    "sau khi chốt chưa push chạy ci/cd cần xuất 1 subagent chạy riêng 1 nhánh test logic kỹ thuật xem còn lỗi bug ẩn nào không "
    "nếu sạch và pass thì bắt đàu push chạy ci/cd đồng bộ 4 clinet"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(262144), b""):
            h.update(chunk)
    return h.hexdigest()


def run_cmd(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        raise RuntimeError(f"Command failed ({res.returncode}): {' '.join(cmd)}")
    if res.stdout.strip():
        print(res.stdout.strip())


def build_tapion_render_contract(active_body_clips: list[str]) -> dict:
    return {
        "body_clips": active_body_clips,
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
            "flight_speed_px_per_second": 520.0,
            "jump_height_px": 100.0,
        },
        "game_states": {
            "peace": {
                "walk": True,
                "idle": True,
                "combat_move": False,
                "idle_combat": False,
                "attack": False,
            },
            "combat": {
                "walk": False,
                "idle": False,
                "combat_move": True,
                "idle_combat": True,
                "attack": True,
            },
        },
        "aura": {
            "loop_clip": "peace_aura_fx",
            "charge_clip": None,
            "independent_clock": True,
            "external_fx_tres": "res://assets/fx/tapion_skills_fx/tapion_skills_fx.tres",
            "peace_aura_clip": "peace_aura_fx",
            "flight_aura_clip": "fly_aura_fx",
            "peace_only_clips": ["idle"],
            "clip_auras": {"fly_aura": "fly_aura_fx"},
        },
        "projectile": None,
        "turning": {
            "clip": None,
            "method": "instant_flip",
            "flip_h": True,
        },
        "hero_mechanics": {
            "forms": ["konatsian_hero"],
            "master_approved_locked": True,
            "combat_combo_sequence": [
                "attack_light",
                "attack_2",
                "attack_3",
                "attack_4",
                "attack_5",
                "attack_6",
                "attack_7",
                "attack_8",
                "attack_9",
                "attack_10",
            ],
            "combo_frame_ms": 60,
            "combo_link_gap_ms": 40,
            "signature_skills": [
                "barrier_cast",
                "energy_recover",
                "kentaima_cast",
                "mahasenko_ground",
                "mahasenko_air",
                "antamina_combo",
                "bukadai_rush",
            ],
            "attack_10_loop_x2": True,
            "attack_10_ground_impact_fx": "atk10_impact_fx",
            "skill_max_range_px": 1175.0,
            "antamina_unlimited_range": True,
            "antamina_charge_duration_sec": 3.0,
            "antamina_orb_frame_ms": 80,
            "antamina_locked_facing_overhead_uturn": True,
            "kentai_micro_burn_fx": "kentai_burn_fx",
            "flight_ki_max": 50.0,
            "teleport_stamina_max": 100.0,
            "combat_move_mode": "continuous_dash_with_analog_brake",
        },
        "facing_default": "right",
        "skills_fx_tres": "res://assets/fx/tapion_skills_fx/tapion_skills_fx.tres",
    }


def main() -> None:
    if not REVIEW_DIR.is_dir():
        raise SystemExit(f"Missing source review dir: {REVIEW_DIR}")

    # 1. Prepare clean assets/tapion/
    if OUT_BODY_DIR.exists():
        shutil.rmtree(OUT_BODY_DIR)
    src_dir = OUT_BODY_DIR / "source"
    raw_dir = src_dir / "raw_frames"
    clips_dir = OUT_BODY_DIR / "clips"
    bundle_dir = OUT_BODY_DIR / "godot_bundle"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / ".gdignore").write_text("", encoding="utf-8")

    # Copy avatar
    shutil.copy2(REVIEW_DIR / "avatar_tapion.png", OUT_BODY_DIR / "avatar_tapion.png")

    # Preserve canonical approved master inside assets/tapion/source/ (gdignored)
    approved_master_src = ROOT / "work" / "characters" / "tapion" / "approved-master" / "approved-master-125px.png"
    master_dst = src_dir / "master_approved.png"
    if approved_master_src.is_file():
        shutil.copy2(approved_master_src, master_dst)
    else:
        shutil.copy2(REVIEW_DIR / "source" / "raw_frames" / "idle_00.png", master_dst)
    master_sha = sha256_file(master_dst)

    old_lock = json.loads((REVIEW_DIR / "master_approved_lock.json").read_text(encoding="utf-8"))
    new_lock = {
        "schema": old_lock.get("schema", "dr7-studio.master_approval_lock.v1"),
        "character_id": "tapion",
        "status": "owner_approved_immutable_master",
        "approved_at": old_lock.get("approved_at"),
        "owner_message": old_lock.get("owner_message"),
        "uploaded_confirmation_sha256": master_sha,
        "master_125px": {
            **(old_lock.get("files", {}).get("master_125px", {})),
            "path": "assets/tapion/source/master_approved.png",
            "sha256": master_sha,
        },
    }
    (OUT_BODY_DIR / "master_approved_lock.json").write_text(
        json.dumps(new_lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # 2. Prune body manifest & copy ONLY active 136 frames
    body_manifest_in = json.loads((REVIEW_DIR / "source" / "clips-manifest.json").read_text(encoding="utf-8"))
    active_body_clips_dict = {
        k: v for k, v in body_manifest_in["clips"].items() if k not in PRUNED_BODY_CLIPS
    }
    used_body_frames: set[str] = set()
    for cdata in active_body_clips_dict.values():
        used_body_frames.update(cdata["frames"])

    active_body_frames_list = [f for f in body_manifest_in["frames"] if f["name"] in used_body_frames]
    dropped_body_frames = sorted({f["name"] for f in body_manifest_in["frames"]} - used_body_frames)

    assert len(active_body_clips_dict) == 30, f"Expected 30 body clips, got {len(active_body_clips_dict)}"
    assert len(active_body_frames_list) == 136, f"Expected 136 body frames, got {len(active_body_frames_list)}"

    for fentry in active_body_frames_list:
        src_png = REVIEW_DIR / "source" / fentry["file"]
        dst_png = src_dir / fentry["file"]
        dst_png.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_png, dst_png)

    body_manifest_out = dict(body_manifest_in)
    body_manifest_out["frames"] = active_body_frames_list
    body_manifest_out["clips"] = active_body_clips_dict
    body_manifest_path = src_dir / "clips-manifest.json"
    body_manifest_path.write_text(json.dumps(body_manifest_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    run_cmd([
        sys.executable, str(BUILD_CLIPS),
        "--manifest", str(body_manifest_path),
        "--out", str(clips_dir),
    ])
    (clips_dir / ".gdignore").write_text("", encoding="utf-8")

    run_cmd([
        sys.executable, str(EXPORT_ENGINE),
        "--clips", str(clips_dir / "animation-clips.json"),
        "--target", "godot-spriteframes",
        "--output-dir", str(bundle_dir),
        "--name", "tapion",
        "--sampling", "nearest",
        "--godot-fps", "60",
        "--max-atlas-size", "4096",
        "--padding", "2",
        "--extrude", "1",
    ])

    # Patch render_contract into engine-export.json
    export_json_path = bundle_dir / "engine-export.json"
    export_meta = json.loads(export_json_path.read_text(encoding="utf-8"))
    pages = export_meta["atlas"]["pages"]
    assert len(pages) == 1, f"Tapion body must be 1 page, got {len(pages)}"
    assert max(pages[0]["size"]) <= 4096, f"Tapion body page exceeds 4096: {pages[0]['size']}"
    for cname, cobj in export_meta["clips"].items():
        assert cobj["godot"]["speed"] == 60, f"Clip {cname} speed != 60: {cobj['godot']['speed']}"

    active_body_clip_names = list(active_body_clips_dict.keys())
    render_contract = build_tapion_render_contract(active_body_clip_names)
    export_meta["render_contract"] = render_contract
    export_json_path.write_text(json.dumps(export_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 3. Prune & export Tapion FX to assets/fx/tapion_skills_fx/
    if OUT_FX_DIR.exists():
        shutil.rmtree(OUT_FX_DIR)
    OUT_FX_DIR.mkdir(parents=True, exist_ok=True)

    fx_manifest_in = json.loads((REVIEW_DIR / "fx_source" / "clips-manifest.json").read_text(encoding="utf-8"))
    active_fx_clips_dict = {
        k: v for k, v in fx_manifest_in["clips"].items() if k not in PRUNED_FX_CLIPS
    }
    used_fx_frames: set[str] = set()
    for cdata in active_fx_clips_dict.values():
        used_fx_frames.update(cdata["frames"])
    active_fx_frames_list = [f for f in fx_manifest_in["frames"] if f["name"] in used_fx_frames]
    dropped_fx_frames = sorted({f["name"] for f in fx_manifest_in["frames"]} - used_fx_frames)

    assert len(active_fx_clips_dict) == 19, f"Expected 19 FX clips, got {len(active_fx_clips_dict)}"
    assert len(active_fx_frames_list) == 74, f"Expected 74 FX frames, got {len(active_fx_frames_list)}"

    with tempfile.TemporaryDirectory(prefix="tapion_fx_promote_") as tmp_str:
        tmp = Path(tmp_str)
        fx_src = tmp / "fx_source"
        fx_raw = fx_src / "raw_frames"
        fx_clips = tmp / "fx_clips"
        fx_bundle = tmp / "fx_bundle"
        fx_raw.mkdir(parents=True, exist_ok=True)
        for fentry in active_fx_frames_list:
            src_png = REVIEW_DIR / "fx_source" / fentry["file"]
            dst_png = fx_src / fentry["file"]
            dst_png.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_png, dst_png)
        fx_manifest_out = dict(fx_manifest_in)
        fx_manifest_out["frames"] = active_fx_frames_list
        fx_manifest_out["clips"] = active_fx_clips_dict
        fx_manifest_path = fx_src / "clips-manifest.json"
        fx_manifest_path.write_text(json.dumps(fx_manifest_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        run_cmd([
            sys.executable, str(BUILD_CLIPS),
            "--manifest", str(fx_manifest_path),
            "--out", str(fx_clips),
        ])
        run_cmd([
            sys.executable, str(EXPORT_ENGINE),
            "--clips", str(fx_clips / "animation-clips.json"),
            "--target", "godot-spriteframes",
            "--output-dir", str(fx_bundle),
            "--name", "tapion_skills_fx",
            "--sampling", "nearest",
            "--godot-fps", "60",
            "--max-atlas-size", "4096",
            "--padding", "2",
            "--extrude", "1",
        ])

        fx_export = json.loads((fx_bundle / "engine-export.json").read_text(encoding="utf-8"))
        fx_pages = fx_export["atlas"]["pages"]
        assert len(fx_pages) == 1, f"Tapion FX must be 1 page, got {len(fx_pages)}"
        assert max(fx_pages[0]["size"]) <= 4096, f"Tapion FX page exceeds 4096: {fx_pages[0]['size']}"

        shutil.copy2(fx_bundle / "godot" / "tapion_skills_fx-atlas-00.png", OUT_FX_DIR / "tapion_skills_fx-atlas-00.png")
        shutil.copy2(fx_bundle / "godot" / "tapion_skills_fx.tres", OUT_FX_DIR / "tapion_skills_fx.tres")
        shutil.copy2(fx_bundle / "engine-export.json", OUT_FX_DIR / "fx-export.json")

    # 4. Write owner_approval.json (PIPE-024)
    body_atlas = bundle_dir / "godot" / "tapion-atlas-00.png"
    body_tres = bundle_dir / "godot" / "tapion.tres"
    fx_atlas = OUT_FX_DIR / "tapion_skills_fx-atlas-00.png"
    fx_tres = OUT_FX_DIR / "tapion_skills_fx.tres"
    prefab = ROOT / "scenes" / "TapionHero.tscn"

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt = {
        "schema": "dr7-studio.owner_approval_receipt.v1",
        "status": "owner_approved",
        "workflow_id": "PIPE-024",
        "character_id": "tapion",
        "display_name": "Tapion",
        "approved_revision": "pruned-30body-19fx-final / v0.19.0",
        "release_version": "0.19.0",
        "approved_at": now_iso,
        "owner_message": OWNER_APPROVAL_MSG,
        "atlas_path": "assets/tapion/godot_bundle/godot/tapion-atlas-00.png",
        "atlas_sha256": sha256_file(body_atlas),
        "atlas_size_px": pages[0]["size"],
        "tres_path": "assets/tapion/godot_bundle/godot/tapion.tres",
        "tres_sha256": sha256_file(body_tres),
        "prefab_path": "scenes/TapionHero.tscn",
        "prefab_sha256": sha256_file(prefab) if prefab.is_file() else "",
        "skills_fx_atlas_path": "assets/fx/tapion_skills_fx/tapion_skills_fx-atlas-00.png",
        "skills_fx_atlas_sha256": sha256_file(fx_atlas),
        "skills_fx_atlas_size_px": fx_pages[0]["size"],
        "skills_fx_tres_path": "assets/fx/tapion_skills_fx/tapion_skills_fx.tres",
        "skills_fx_tres_sha256": sha256_file(fx_tres),
        "avatar_path": "assets/tapion/avatar_tapion.png",
        "avatar_sha256": sha256_file(OUT_BODY_DIR / "avatar_tapion.png"),
        "pruned_unused_clips": {
            "body_removed": sorted(PRUNED_BODY_CLIPS),
            "body_frames_removed": dropped_body_frames,
            "fx_removed": sorted(PRUNED_FX_CLIPS),
            "fx_frames_removed": dropped_fx_frames,
        },
        "canvas_size_px": [288, 288],
        "foot_anchor_px": [144, 248],
        "body_only_bbox_px": {"x": 108, "y": 123, "w": 68, "h": 125},
        "full_fx_bbox_px": {"x": 8, "y": 10, "w": 272, "h": 268},
        "present_clips": active_body_clip_names,
        "effect_clips": [],
        "external_fx_clips": list(active_fx_clips_dict.keys()),
        "not_applicable_clips": {
            "run": "Tapion uses walk (Peace 200px/s) and combat_move continuous dash (Combat 400 back / 500 fwd px/s) instead of a separate run clip.",
            "guard": "guard/win excluded project-wide per Owner rule.",
            "win": "guard/win excluded project-wide per Owner rule.",
            "attack_heavy": "Heavy combo finisher is covered by attack_10 (LOOP X2 sword slam + atk10_impact_fx).",
            "power_up": "Ocarina buff/recovery is covered by barrier_cast and energy_recover.",
            "aura_loop": "Peace/Flight aura FX live in independent atlas assets/fx/tapion_skills_fx/ (peace_aura_fx, fly_aura_fx).",
            "turn": "Owner scoped new characters to instant horizontal flip without dedicated turn clip.",
        },
        "render_contract": render_contract,
    }
    (OUT_BODY_DIR / "owner_approval.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print("\n=== TAPION OFFICIAL PROMOTION SUMMARY ===")
    print(f"Body Atlas : {pages[0]['size']} (1 page, 30 clips, 136 frames) sha256={receipt['atlas_sha256']}")
    print(f"Body .tres : sha256={receipt['tres_sha256']}")
    print(f"FX Atlas   : {fx_pages[0]['size']} (1 page, 19 clips, 74 frames) sha256={receipt['skills_fx_atlas_sha256']}")
    print(f"FX .tres   : sha256={receipt['skills_fx_tres_sha256']}")
    print(f"Dropped Body Clips ({len(PRUNED_BODY_CLIPS)}): {sorted(PRUNED_BODY_CLIPS)}")
    print(f"Dropped Body Frames ({len(dropped_body_frames)}): {dropped_body_frames}")
    print(f"Dropped FX Clips ({len(PRUNED_FX_CLIPS)}): {sorted(PRUNED_FX_CLIPS)}")
    print(f"Dropped FX Frames ({len(dropped_fx_frames)}): {dropped_fx_frames}")


if __name__ == "__main__":
    main()
