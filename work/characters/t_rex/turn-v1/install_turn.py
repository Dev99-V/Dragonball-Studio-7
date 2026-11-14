#!/usr/bin/env python3
"""Install staged T-rex turn-v1 clips/bundle, archive PIPE-001 receipt, and update roster/QA metadata."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[4]
TURN_DIR = ROOT / "work/characters/t_rex/turn-v1"
STAGE_DIR = TURN_DIR / "stage"
LIVE_TREX = ROOT / "assets/t_rex"
LIVE_CLIPS = LIVE_TREX / "clips"
LIVE_BUNDLE = LIVE_TREX / "godot_bundle"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_tree_preserving_special(src: Path, dst: Path, keep_names: set[str]) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    # Remove stale files/dirs except preserved files like .gdignore / *.import
    for item in list(dst.iterdir()):
        if item.name in keep_names or any(item.name.endswith(s) for s in keep_names if s.startswith(".")):
            continue
        if item.is_dir():
            # Preserve any .import files inside subdirectories cleanly
            preserved = {}
            for p in item.rglob("*.import"):
                preserved[p.relative_to(item)] = p.read_bytes()
            shutil.rmtree(item)
            for rel, data in preserved.items():
                (item / rel).parent.mkdir(parents=True, exist_ok=True)
                (item / rel).write_bytes(data)
        else:
            item.unlink()

    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            for sub in item.rglob("*"):
                if sub.is_dir():
                    continue
                rel = sub.relative_to(src)
                out = dst / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sub, out)
        else:
            shutil.copy2(item, target)


def archive_pipe001_receipt() -> None:
    live_app = LIVE_TREX / "owner_approval.json"
    archive_app = ROOT / "docs/releases/t_rex-v0.6.0-approval.json"
    archive_app.parent.mkdir(parents=True, exist_ok=True)
    snap_app = TURN_DIR / "snapshot-before/owner_approval.json"
    if snap_app.exists() and not archive_app.exists():
        shutil.copy2(snap_app, archive_app)
    if live_app.exists():
        if not archive_app.exists():
            shutil.copy2(live_app, archive_app)
        live_app.unlink()


def install_assets() -> tuple[str, dict]:
    copy_tree_preserving_special(STAGE_DIR / "clips", LIVE_CLIPS, {".gdignore"})
    # Also install staged clips_manifest.json as assets/t_rex/clips/source-manifest.json
    shutil.copy2(STAGE_DIR / "clips_manifest.json", LIVE_CLIPS / "source-manifest.json")
    copy_tree_preserving_special(STAGE_DIR / "godot_bundle", LIVE_BUNDLE, {".import"})

    # Keep .gdignore inside source and clips
    (LIVE_CLIPS / ".gdignore").write_text("", encoding="utf-8")

    atlas_path = LIVE_BUNDLE / "godot/t_rex-atlas-00.png"
    atlas_sha = sha256_file(atlas_path)
    export_meta = json.loads((LIVE_BUNDLE / "engine-export.json").read_text(encoding="utf-8"))
    return atlas_sha, export_meta


def compute_full_fx_union_bbox(num_frames: int) -> dict:
    xs_min, ys_min, xs_max, ys_max = 9999, 9999, -1, -1
    for i in range(num_frames):
        im = np.array(Image.open(LIVE_CLIPS / f"frames/frame-{i:02d}.png").convert("RGBA"))
        ys, xs = np.where(im[..., 3] > 0)
        if len(xs):
            xs_min = min(xs_min, int(xs.min()))
            ys_min = min(ys_min, int(ys.min()))
            xs_max = max(xs_max, int(xs.max()))
            ys_max = max(ys_max, int(ys.max()))
    return {"x": xs_min, "y": ys_min, "w": xs_max - xs_min + 1, "h": ys_max - ys_min + 1}


def update_reviews_and_qa(atlas_sha: str, export_meta: dict) -> list[float]:
    sharp = json.loads((TURN_DIR / "turn-sharpness.json").read_text(encoding="utf-8"))
    sobel_vals = [float(item["edge_acutance_sobel"]) for item in sharp["frames"]]
    tres_sha = sha256_file(LIVE_BUNDLE / "godot/t_rex.tres")
    scene_sha = sha256_file(ROOT / "scenes/TRex.tscn")
    ctrl_sha = sha256_file(ROOT / "scenes/TRexFighter2D.gd")
    export_sha = sha256_file(LIVE_BUNDLE / "engine-export.json")

    keyframe_review = {
        "schema": "dr7-studio.keyframe_review.v1",
        "character_id": "t_rex",
        "revision": "turn-v1",
        "status": "reviewed_pending_owner",
        "method": "imagegen_complete_body_keyframes",
        "turn_method": "complete_perspective_poses",
        "atlas_sha256": atlas_sha,
        "previous_revision_atlas_sha256": "d78b3b750c51793de4eafe3532c2350fff52bce9d54ecd40b879fc6e44c1d1b7",
        "canonical_master_sha256": "d4dc74e198774a0af2097962967492e3d2f909831b40b7c811ea7b5aa3208e69",
        "front_proportion_guide": "assets/t_rex/clips/frames/frame-38.png",
        "turn_poses": [
            {"index": i, "file": f"work/characters/t_rex/turn-v1/source/turn_0{i}.png", **sharp["frames"][i]}
            for i in range(5)
        ],
        "ticks": [6, 3, 3, 3, 6],
        "duration_ms": [100, 50, 50, 50, 100],
        "total_duration_ms": 350,
        "total_duration_ticks": 21,
        "visual_checks": {
            "turn_lineup_1x": "work/characters/t_rex/turn-v1/review/turn-lineup-1x.png",
            "turn_rim_4x": "work/characters/t_rex/turn-v1/review/turn-rim-4x.png",
            "turn_test": "work/characters/t_rex/turn-v1/review/turn-test.png",
            "filmstrip_turn": "work/characters/t_rex/turn-v1/review/filmstrip-turn.png",
            "transition_continuity": "work/characters/t_rex/turn-v1/review/transition-continuity.png",
            "walk_turn_walk_webps": [
                f"work/characters/t_rex/turn-v1/review/walk-turn-walk-{d}-{bg}.webp"
                for d in ("r2l", "l2r")
                for bg in ("light", "dark", "checker")
            ],
            "run_turn_run_webps": [
                f"work/characters/t_rex/turn-v1/review/run-turn-run-{d}-{bg}.webp"
                for d in ("r2l", "l2r")
                for bg in ("light", "dark", "checker")
            ],
            "body_connections": True,
            "whole_pose_sequence": True,
            "perspective_turns": True,
            "phase_timing": True,
            "three_backgrounds": True,
            "character_identity": True,
            "zero_alpha_halo_or_pockets": True,
            "non_turn_73_frames_preserved": True,
        },
        "iss_trex_tick_legacy": {
            "status": "resolved_by_owner_decision_exact_ticks",
            "owner_decision": "Re-export T-rex turn-v1 with --godot-fps auto so godot.relative_durations equals exact authored 60Hz ticks (fixing attack_heavy frame 5 0.96 -> 1.0 tick) while keeping all 73 original PNGs, clip order, duration_ms, events, and keys intact.",
        },
    }
    (TURN_DIR / "review/keyframe-review.json").write_text(
        json.dumps(keyframe_review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    qa_doc = {
        "schema": "dr7-studio.turn_qa_report.v1",
        "character_id": "t_rex",
        "revision": "turn-v1",
        "status": "reviewed_pending_owner",
        "owner_approved": False,
        "score_provisional": 90,
        "score_max": 100,
        "gates_completed": 9,
        "gates_total": 10,
        "note_score": "100/100 only allowed after Owner Human Test approval; gate 10 pending.",
        "bundles": {
            "atlas_path": "assets/t_rex/godot_bundle/godot/t_rex-atlas-00.png",
            "atlas_sha256": atlas_sha,
            "tres_path": "assets/t_rex/godot_bundle/godot/t_rex.tres",
            "tres_sha256": tres_sha,
            "engine_export_path": "assets/t_rex/godot_bundle/engine-export.json",
            "engine_export_sha256": export_sha,
            "prefab_path": "scenes/TRex.tscn",
            "prefab_sha256": scene_sha,
            "controller_path": "scenes/TRexFighter2D.gd",
            "controller_sha256": ctrl_sha,
        },
        "turn_contract": export_meta["render_contract"]["turning"],
        "patrol_contract": export_meta["render_contract"]["locomotion"]["patrol"],
        "turn_sharpness_sobel": sobel_vals,
        "non_turn_preservation": {
            "preserved_frame_count": 73,
            "preserved_clip_names": [
                "idle", "walk", "run", "attack_light", "attack_heavy", "power_up", "hit", "ko", "fireball_fx"
            ],
            "legacy_approval_archive": "docs/releases/t_rex-v0.6.0-approval.json",
            "previous_atlas_sha256": "d78b3b750c51793de4eafe3532c2350fff52bce9d54ecd40b879fc6e44c1d1b7",
        },
        "iss_trex_tick_legacy": keyframe_review["iss_trex_tick_legacy"],
        "gates": {
            "1_canonical_identity_preserved": True,
            "2_no_cut_warp_or_card_flip": True,
            "3_grounded_weight_shift_and_tail_followthrough": True,
            "4_sharpness_binary_alpha_no_rim_pockets": True,
            "5_60hz_phase_timing_and_ticks": True,
            "6_non_turn_73_frames_and_events_unchanged": True,
            "7_bidirectional_turn_and_input_lock_wired": True,
            "8_two_endpoint_patrol_walk_and_run_wired": True,
            "9_godot_wasm_localhost_parity_and_tests": True,
            "10_owner_human_test_approved": "pending_owner_human_test",
        },
    }
    (ROOT / "docs/characters/t-rex-turn-v1-qa.json").write_text(
        json.dumps(qa_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return sobel_vals


def update_roster_and_state(atlas_sha: str, export_meta: dict, sobel_vals: list[float]) -> None:
    roster_path = ROOT / "assets/roster.json"
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    trex = next(c for c in roster["characters"] if c["character_id"] == "t_rex")

    full_fx = compute_full_fx_union_bbox(78)
    trex["present_clips"] = ["idle", "walk", "run", "turn", "attack_light", "attack_heavy", "power_up", "hit", "ko"]
    trex["effect_clips"] = ["fireball_fx"]
    trex["render_contract"] = export_meta["render_contract"]
    trex["facing_contract"] = {
        "camera_view": "side_view_2d",
        "default_atlas_facing": "right (+X)",
        "left_facing_rule": "Two-way turn clip plays 5 whole-body perspective poses (right -> front -> left) before committing horizontal flip around foot_anchor_x = 176; left -> right plays reverse mirrored sequence while holding -X orientation until the final pose settles.",
        "locomotion_vector_rule": "Bipedal walk/run unchanged; endpoint and manual direction reversals execute perspective turn with mid-turn lock; attack_heavy retains 360-degree planted tail whip.",
    }
    trex["map_sync_metrics"]["full_fx_bbox_px"] = full_fx
    trex["map_sync_metrics"]["world_size_at_64ppu_m"]["aura_w_m"] = round(full_fx["w"] / 64.0, 3)
    trex["map_sync_metrics"]["world_size_at_64ppu_m"]["aura_h_m"] = round(full_fx["h"] / 64.0, 3)
    trex["map_sync_metrics"]["tile_32px_span"]["full_fx_tiles_w"] = round(full_fx["w"] / 32.0, 4)
    trex["map_sync_metrics"]["tile_32px_span"]["full_fx_tiles_h"] = round(full_fx["h"] / 32.0, 4)

    trex["pixel_sharpness_metrics"]["turn_edge_acutance_sobel"] = sobel_vals
    trex["atlas_stage"] = "demo_pending_owner"
    trex["qa_report"] = "docs/characters/t-rex-turn-v1-qa.json"
    trex["owner_animation_approval"] = {
        "status": "pending_owner",
        "revision": "turn-v1",
        "previous_revision": "walk-style-v4 / v0.6.0",
        "previous_approval_file": "docs/releases/t_rex-v0.6.0-approval.json",
        "previous_atlas_sha256": "d78b3b750c51793de4eafe3532c2350fff52bce9d54ecd40b879fc6e44c1d1b7",
    }
    trex["motion_quality"] = {
        "status": "reviewed_pending_owner",
        "revision": "turn-v1",
        "method": "imagegen_complete_body_keyframes",
        "turn_method": "complete_perspective_poses",
        "atlas_sha256": atlas_sha,
        "previous_revision_atlas_sha256": "d78b3b750c51793de4eafe3532c2350fff52bce9d54ecd40b879fc6e44c1d1b7",
        "prior_demo_atlas_sha256": "7cdc28601c3f8ac7867409d4bd6c036e78c5091ffd3d45751a7db1f12798d7e7",
        "canonical_identity_sha256": "d4dc74e198774a0af2097962967492e3d2f909831b40b7c811ea7b5aa3208e69",
        "review_evidence": "work/characters/t_rex/turn-v1/review/keyframe-review.json",
        "turn_sharpness_sobel": sobel_vals,
        "checks": {
            "body_connections": True,
            "whole_pose_sequence": True,
            "perspective_turns": True,
            "phase_timing": True,
            "three_backgrounds": True,
            "character_identity": True,
            "bidirectional_runtime_wired": True,
            "two_endpoint_patrol_wired": True,
        },
        "unresolved_structural_failures": [],
        "owner_approved": False,
        "owner_accepted_motion": False,
        "naturalness_verdict": "reviewed_pending_owner",
    }
    roster_path.write_text(json.dumps(roster, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    st_path = ROOT / "state.json"
    st = json.loads(st_path.read_text(encoding="utf-8"))
    for wf in st.get("approved_workflows", []):
        if wf.get("id") == "PIPE-001":
            wf["approval_file"] = "docs/releases/t_rex-v0.6.0-approval.json"
            wf["approved_atlas_path"] = "work/characters/t_rex/turn-v1/snapshot-before/t_rex-atlas-00.png"
            wf["revision"] = "walk-style-v4 / v0.6.0"
    st_path.write_text(json.dumps(st, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    archive_pipe001_receipt()
    atlas_sha, export_meta = install_assets()
    sobel_vals = update_reviews_and_qa(atlas_sha, export_meta)
    update_roster_and_state(atlas_sha, export_meta, sobel_vals)
    print(json.dumps({"atlas_sha256": atlas_sha, "turn_sobel": sobel_vals}, indent=2))


if __name__ == "__main__":
    main()
