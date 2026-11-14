#!/usr/bin/env python3
"""Finalize Owner approval (PIPE-010) for T-rex turn-v1 and freeze runtime files."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
LIVE_TREX = ROOT / "assets/t_rex"
WORK_TURN = ROOT / "work/characters/t_rex/turn-v1"
FROZEN_DIR = ROOT / "work/characters/t_rex/approved-final-frames"
ROSTER_PATH = ROOT / "assets/roster.json"
STATE_PATH = ROOT / "state.json"
QA_PATH = ROOT / "docs/characters/t-rex-turn-v1-qa.json"
REVIEW_PATH = WORK_TURN / "review/keyframe-review.json"
RELEASE_LOG_PATH = ROOT / "docs/releases/v0.11.2-t_rex-turn-finalization.json"

APPROVED_AT = "2026-11-14T07:12:14+00:00"
OWNER_MESSAGE = "ok anh duyệt t-rex bắt đàu với nhân vật tiếp theo"
WORKFLOW_ID = "PIPE-010"
PREV_WORKFLOW_ID = "PIPE-001"
PREV_ATLAS_SHA = "d78b3b750c51793de4eafe3532c2350fff52bce9d54ecd40b879fc6e44c1d1b7"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_final_frames() -> None:
    if FROZEN_DIR.exists():
        shutil.rmtree(FROZEN_DIR)
    shutil.copytree(LIVE_TREX / "clips", FROZEN_DIR)
    proof: dict[str, str] = {}
    for p in sorted(FROZEN_DIR.rglob("*")):
        if p.is_file():
            proof[str(p.relative_to(ROOT))] = sha256_file(p)
    (FROZEN_DIR / "freeze-proof.json").write_text(
        json.dumps(
            {
                "workflow_id": WORKFLOW_ID,
                "character_id": "t_rex",
                "revision": "turn-v1",
                "approved_at": APPROVED_AT,
                "files_sha256": proof,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def collect_runtime_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for sub in ("clips", "godot_bundle"):
        for p in sorted((LIVE_TREX / sub).rglob("*")):
            if p.is_file() and p.name != ".gdignore":
                hashes[str(p.relative_to(ROOT))] = sha256_file(p)
    for extra in (ROOT / "scenes/TRex.tscn", ROOT / "scenes/TRexFighter2D.gd"):
        hashes[str(extra.relative_to(ROOT))] = sha256_file(extra)
    return hashes


def main() -> None:
    freeze_final_frames()
    runtime_hashes = collect_runtime_hashes()

    roster = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    trex = next(c for c in roster["characters"] if c["character_id"] == "t_rex")
    engine_export = json.loads((LIVE_TREX / "godot_bundle/engine-export.json").read_text(encoding="utf-8"))
    clips_manifest = json.loads((LIVE_TREX / "clips/animation-clips.json").read_text(encoding="utf-8"))

    atlas_path = LIVE_TREX / "godot_bundle/godot/t_rex-atlas-00.png"
    tres_path = LIVE_TREX / "godot_bundle/godot/t_rex.tres"
    prefab_path = ROOT / "scenes/TRex.tscn"
    clips_path = LIVE_TREX / "clips/animation-clips.json"
    export_path = LIVE_TREX / "godot_bundle/engine-export.json"

    atlas_sha = sha256_file(atlas_path)
    tres_sha = sha256_file(tres_path)
    prefab_sha = sha256_file(prefab_path)
    clips_sha = sha256_file(clips_path)
    export_sha = sha256_file(export_path)

    approval_receipt = {
        "schema": "dr7-studio.owner_approval_receipt.v1",
        "status": "owner_approved",
        "workflow_id": WORKFLOW_ID,
        "character_id": "t_rex",
        "display_name": "T-rex",
        "approved_at": APPROVED_AT,
        "owner_message": OWNER_MESSAGE,
        "approval_basis": "Owner verified T-rex turn-v1 (5 whole-body perspective turn poses, ticks [6,3,3,3,6], --godot-fps auto resolving ISS-TREX-TICK-LEGACY, 73/73 original non-turn frames preserved) on localhost:8080 and approved advancing to #3 Pteranodon.",
        "approved_revision": "turn-v1 / v0.11.2",
        "release_version": "0.11.2",
        "previous_workflow_id": PREV_WORKFLOW_ID,
        "previous_revision": "walk-style-v4 / v0.6.0",
        "previous_approval_archive": [
            "work/characters/t_rex/turn-v1/snapshot-before/owner_approval.json",
            "docs/releases/t_rex-v0.6.0-approval.json",
        ],
        "previous_atlas_sha256": PREV_ATLAS_SHA,
        "atlas_path": str(atlas_path.relative_to(ROOT)),
        "atlas_sha256": atlas_sha,
        "tres_path": str(tres_path.relative_to(ROOT)),
        "tres_sha256": tres_sha,
        "prefab_path": str(prefab_path.relative_to(ROOT)),
        "prefab_sha256": prefab_sha,
        "clips_manifest_path": str(clips_path.relative_to(ROOT)),
        "clips_manifest_sha256": clips_sha,
        "engine_export_path": str(export_path.relative_to(ROOT)),
        "engine_export_sha256": export_sha,
        "canvas_size_px": trex["map_sync_metrics"]["canvas_size_px"],
        "foot_anchor_px": trex["map_sync_metrics"]["foot_anchor_px"],
        "body_only_bbox_px": trex["map_sync_metrics"]["body_only_bbox_px"],
        "full_fx_bbox_px": trex["map_sync_metrics"]["full_fx_bbox_px"],
        "present_clips": sorted(clips_manifest["clips"].keys()),
        "effect_clips": trex["effect_clips"],
        "excluded_clips": trex["missing_provisional_clips"],
        "canonical_identity": trex["canonical_identity"],
        "render_contract": engine_export["render_contract"],
        "qa_report": "docs/characters/t-rex-turn-v1-qa.json",
        "frozen_source": "work/characters/t_rex/approved-final-frames/animation-clips.json",
        "approved_runtime_files_sha256": runtime_hashes,
        "approval_scope": "Final turn-v1 revision adding 5 whole-body perspective turn poses (21 ticks / 350 ms), bidirectional + two-endpoint patrol runtime, and Owner-approved --godot-fps auto tick fix while preserving all 73 pre-existing v0.6.0 body/FX frames, clip order, events, and canonical walk0 identity.",
        "known_technical_limits": "Owner Human Test acceptance certifies delivered turn-v1 artwork/timing in Godot 4 & localhost:8080; it does not replace measured mobile hardware 60FPS profiling.",
    }
    (LIVE_TREX / "owner_approval.json").write_text(
        json.dumps(approval_receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Update QA report to 100/100 Owner-approved
    qa = json.loads(QA_PATH.read_text(encoding="utf-8"))
    qa["status"] = "owner_approved"
    qa["owner_approved"] = True
    qa["owner_score"] = 100
    qa.pop("score_provisional", None)
    qa["gates_completed"] = 10
    qa["gates_total"] = 10
    qa["note_score"] = "10/10 evidence gates verified (10 pts each) + explicit Owner Human Test approval."
    qa["gates"]["10_owner_human_test_approved"] = True
    qa["approved_at"] = APPROVED_AT
    qa["owner_message"] = OWNER_MESSAGE
    qa["workflow_id"] = WORKFLOW_ID
    qa["owner_approval_file"] = "assets/t_rex/owner_approval.json"
    QA_PATH.write_text(json.dumps(qa, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Update keyframe-review.json
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    review["status"] = "owner_approved"
    review["owner_approved"] = True
    review["approved_at"] = APPROVED_AT
    review["owner_message"] = OWNER_MESSAGE
    review["workflow_id"] = WORKFLOW_ID
    REVIEW_PATH.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Update roster.json
    trex["atlas_stage"] = "finalized_owner_approved"
    trex["owner_animation_approval"] = {
        "status": "owner_approved",
        "approved_at": APPROVED_AT,
        "workflow_id": WORKFLOW_ID,
        "revision": "turn-v1 / v0.11.2",
        "approval_file": "assets/t_rex/owner_approval.json",
        "atlas_sha256": atlas_sha,
        "previous_revision": "walk-style-v4 / v0.6.0",
        "previous_approval_file": "docs/releases/t_rex-v0.6.0-approval.json",
        "previous_atlas_sha256": PREV_ATLAS_SHA,
    }
    mq = trex["motion_quality"]
    mq["status"] = "owner_approved"
    mq["owner_approved"] = True
    mq["owner_accepted_motion"] = True
    mq["naturalness_verdict"] = "owner_approved"
    mq["approved_at"] = APPROVED_AT
    mq["workflow_id"] = WORKFLOW_ID
    mq["owner_message"] = OWNER_MESSAGE
    ROSTER_PATH.write_text(json.dumps(roster, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Clean duplicate PNG copies under work/characters/t_rex/turn-v1/stage/
    retained_by_sha: dict[str, str] = {}
    for p in sorted(LIVE_TREX.rglob("*.png")):
        retained_by_sha[sha256_file(p)] = str(p.relative_to(ROOT))
    removed_list = []
    removed_bytes = 0
    for sp in sorted((WORK_TURN / "stage").rglob("*.png")):
        sh = sha256_file(sp)
        if sh in retained_by_sha:
            sz = sp.stat().st_size
            removed_bytes += sz
            removed_list.append(
                {
                    "removed": str(sp.relative_to(ROOT)),
                    "retained": retained_by_sha[sh],
                    "sha256": sh,
                    "bytes": sz,
                }
            )
            sp.unlink()

    RELEASE_LOG_PATH.write_text(
        json.dumps(
            {
                "approved_at": APPROVED_AT,
                "workflow_id": WORKFLOW_ID,
                "supersedes": PREV_WORKFLOW_ID,
                "owner_approval_file": "assets/t_rex/owner_approval.json",
                "archived_previous_receipt": "docs/releases/t_rex-v0.6.0-approval.json",
                "atlas_sha256": atlas_sha,
                "tres_sha256": tres_sha,
                "runtime_files_frozen": len(runtime_hashes),
                "cleanup": {
                    "removed_count": len(removed_list),
                    "removed_bytes": removed_bytes,
                    "scope": "Only byte-identical stage PNG copies inside work/characters/t_rex/turn-v1/stage/.",
                    "files": removed_list,
                },
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    # Update state.json approved_workflows, PIPE-001 superseded_by, TURN-002 task, turn_policy
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    for wf in state["approved_workflows"]:
        if wf["id"] == PREV_WORKFLOW_ID:
            wf["superseded_by"] = WORKFLOW_ID
    state["approved_workflows"] = [w for w in state["approved_workflows"] if w["id"] != WORKFLOW_ID]
    state["approved_workflows"].append(
        {
            "id": WORKFLOW_ID,
            "character_id": "t_rex",
            "display_name": "T-rex",
            "approved_at": APPROVED_AT,
            "approval_file": "assets/t_rex/owner_approval.json",
            "atlas_sha256": atlas_sha,
            "revision": "turn-v1 / v0.11.2",
        }
    )
    for t in state["task_history"]:
        if t.get("id") == "TURN-002":
            t["status"] = "completed"
            t["timestamp"] = APPROVED_AT
            t["summary"] = (
                "T-rex turn-v1 Owner-approved (PIPE-010 / v0.11.2, 100/100): archived PIPE-001/v0.6.0 "
                "receipt+frozen snapshot, froze runtime files & 78 clips, cleaned duplicate stage PNGs, "
                "resolved ISS-TREX-TICK-LEGACY via --godot-fps auto; verified Godot/Rust/WASM/Chromium/HTTP "
                "before advancing to #3 Pteranodon."
            )
    state["current_focus"]["active_task_id"] = "TURN-003"
    state["current_focus"]["status"] = "in_progress"
    state["current_focus"]["character_id"] = "pteranodon"
    state["current_focus"]["master_image"] = "work/characters/pteranodon/master-match-v9/reference.png"
    state["current_focus"]["summary"] = (
        "T-rex turn-v1 Owner-approved (PIPE-010 / v0.11.2, 100/100); starting TODO #3 Pteranodon (TURN-003): "
        "snapshot-before, audit aerial flight/wingbeat/near-far wings/anchor, design whole-body perspective turn."
    )
    state["turn_policy"]["retrofit_gate"] = (
        "Bat (PIPE-009) & T-rex (PIPE-010) turn-v1 Owner-approved (2/4 TODO done); starting #3 Pteranodon (TURN-003)."
    )
    state["session_resume"]["next_action"] = "Continue turn-retrofit TODO #3 Pteranodon (TURN-003): snapshot-before, audit flight/wingbeat/near-far wings/anchor, design aerial whole-body turn."
    state["session_resume"]["asset_status"] = "8 nhân vật Owner-approved (Bat & T-rex turn-v1 / v0.11.2); starting TURN-003 Pteranodon."
    state["session_resume"]["approval_file"] = "assets/t_rex/owner_approval.json"
    state["session_resume"]["cleanup_report"] = "docs/releases/v0.11.2-t_rex-turn-finalization.json"
    state["session_resume"]["verification"] = "docs/characters/t-rex-turn-v1-qa.json"
    state["session_resume"]["review_evidence"] = "work/characters/t_rex/turn-v1/review/keyframe-review.json"
    state["session_resume"]["latest_delivery"] = "assets/t_rex/godot_bundle"
    state["session_resume"]["preview_url"] = "http://localhost:8080/?character=t_rex&clip=turn&frame=0&paused=1"
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({"workflow": WORKFLOW_ID, "atlas_sha256": atlas_sha, "runtime_files_frozen": len(runtime_hashes), "removed_stage_pngs": len(removed_list), "removed_bytes": removed_bytes}, indent=2))


if __name__ == "__main__":
    main()
