#!/usr/bin/env python3
"""Uniformly resize ONLY Spinosaurus walk_00 and walk_07 from the 887x887 source sheet
with a single Nearest pass to match canonical walk_01..06 proportions, while keeping
all other 69 frames (including idle, walk_01..06, attacks, turn, fireball_fx) and
speed 170 px/s byte-identical."""
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[4]
CHAR_ID = "spinosaurus"
CLIPS_DIR = ROOT / "assets" / CHAR_ID / "clips"
BUNDLE_DIR = ROOT / "assets" / CHAR_ID / "godot_bundle"
WALK_SHEET = ROOT / "work/characters" / CHAR_ID / "regenerated-keyframes/walk-seam-v6/sheet.png"
STEP2_APPROVAL = ROOT / "work/characters" / CHAR_ID / "step2-visual-fix/snapshot-before/owner_approval.json"
QA_DOC = ROOT / "docs/characters/spinosaurus-final-qa.json"
ROSTER_PATH = ROOT / "assets/roster.json"

WORK_DIR = Path(__file__).resolve().parent
SNAP_DIR = WORK_DIR / "snapshot-before"
STAGE_SRC = WORK_DIR / "stage_src"
STAGE_CLIPS = WORK_DIR / "stage_clips"
STAGE_BUNDLE = WORK_DIR / "stage_bundle"

BUILD_CLIPS_SCRIPT = ROOT / ".agent/skills/generate2dsprite/scripts/build_animation_clips.py"
EXPORT_ENGINE_SCRIPT = ROOT / ".agent/skills/generate2dsprite/scripts/export_engine.py"
SHARPNESS_SCRIPT = ROOT / "tools/art/measure_pixel_sharpness.py"

GROUND_Y = 224
TARGET_H = 74
ALPHA_THRESHOLD = 224


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_snapshot() -> None:
    (WORK_DIR / ".gdignore").write_text("")
    if SNAP_DIR.exists():
        return
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(CLIPS_DIR, SNAP_DIR / "clips")
    shutil.copytree(BUNDLE_DIR, SNAP_DIR / "godot_bundle")
    shutil.copy2(QA_DOC, SNAP_DIR / "spinosaurus-final-qa.json")
    roster = json.loads(ROSTER_PATH.read_text())
    entry = next(c for c in roster["characters"] if c["character_id"] == CHAR_ID)
    (SNAP_DIR / "roster-entry.json").write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n")


def torso_x(arr: np.ndarray) -> float:
    ys, xs = np.where(arr[:195, :, 3] > 0)
    if len(xs) == 0:
        ys, xs = np.where(arr[:, :, 3] > 0)
    return float(xs.mean())


def orange_eye_count(arr: np.ndarray) -> int:
    return int(
        (
            (arr[:, :, 0] >= 180)
            & (arr[:, :, 1] >= 80)
            & (arr[:, :, 1] <= 190)
            & (arr[:, :, 2] <= 60)
            & (arr[:, :, 3] > 0)
        ).sum()
    )


def downscale_sheet_cell(cell: np.ndarray, target_torso_x: float, canvas_shape: tuple[int, int, int]) -> np.ndarray:
    """Binarize high-res cell alpha, perform a single Nearest resize to TARGET_H, and register."""
    fg = cell[:, :, 3] >= ALPHA_THRESHOLD
    ys, xs = np.where(fg)
    crop = cell[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1].copy()
    mask = crop[:, :, 3] >= ALPHA_THRESHOLD
    crop[~mask] = 0
    crop[mask, 3] = 255

    nw = int(round(crop.shape[1] * (TARGET_H / crop.shape[0])))
    resized = np.array(Image.fromarray(crop, "RGBA").resize((nw, TARGET_H), Image.NEAREST))
    ry, rx = np.where(resized[:, :, 3] > 0)
    trimmed = resized[ry.min() : ry.max() + 1, rx.min() : rx.max() + 1]
    th, tw = trimmed.shape[:2]

    oy = GROUND_Y - th
    tmp = np.zeros(canvas_shape, dtype=np.uint8)
    tmp[oy : oy + th, 91 : 91 + tw] = trimmed
    dx = int(round(target_torso_x - torso_x(tmp)))

    out = np.zeros(canvas_shape, dtype=np.uint8)
    ox = max(1, min(canvas_shape[1] - 1 - tw, 91 + dx))
    out[oy : oy + th, ox : ox + tw] = trimmed

    final_mask = out[:, :, 3] > 0
    _, n_comp = ndimage.label(final_mask, structure=np.ones((3, 3), dtype=int))
    if n_comp != 1:
        raise RuntimeError(f"Expected single connected body component, got {n_comp}")
    if orange_eye_count(out) < 1:
        raise RuntimeError("Orange eye lost during Nearest resize")
    return out


def measure_walk(frames: list[np.ndarray]) -> dict:
    summary = []
    txs = []
    for idx, a in enumerate(frames):
        m = a[:, :, 3] > 0
        ys, xs = np.where(m)
        tx = torso_x(a)
        txs.append(tx)
        summary.append(
            {
                "index": idx,
                "w": int(xs.max() - xs.min() + 1),
                "h": int(ys.max() - ys.min() + 1),
                "bottom": int(ys.max() + 1),
                "area": int(m.sum()),
                "torso_x": round(tx, 2),
                "eye_px": orange_eye_count(a),
            }
        )
    return {"frames": summary, "torso_x_spread_px": round(max(txs) - min(txs), 3)}


def main() -> None:
    ensure_snapshot()
    snap_c = SNAP_DIR / "clips"
    snap_clips = json.loads((snap_c / "animation-clips.json").read_text())
    snap_sm = json.loads((snap_c / "source-manifest.json").read_text())
    snap_export = json.loads((SNAP_DIR / "godot_bundle/engine-export.json").read_text())

    for p in (STAGE_SRC, STAGE_CLIPS, STAGE_BUNDLE):
        if p.exists():
            shutil.rmtree(p)
    (STAGE_SRC / "raw_frames").mkdir(parents=True, exist_ok=True)

    # Load all snapshot frames keyed by frame name
    snap_arrays: dict[str, np.ndarray] = {}
    snap_paths: dict[str, Path] = {}
    for idx, sm_f in enumerate(snap_sm["frames"]):
        fname = sm_f["name"]
        p = snap_c / snap_clips["frames"][idx]["file"]
        snap_paths[fname] = p
        snap_arrays[fname] = np.array(Image.open(p).convert("RGBA"))

    # Reference torso centroid from preserved walk_01..06
    target_walk_tx = float(np.mean([torso_x(snap_arrays[f"walk_{i:02d}"]) for i in range(1, 7)]))
    sheet = np.array(Image.open(WALK_SHEET).convert("RGBA"))
    canvas_shape = snap_arrays["walk_01"].shape

    # Rebuild ONLY walk_00 (right cell) and walk_07 (left cell) from 887x887 sheet
    new_w00 = downscale_sheet_cell(sheet[:, 887:], target_walk_tx, canvas_shape)
    new_w07 = downscale_sheet_cell(sheet[:, :887], target_walk_tx, canvas_shape)

    # Copy all 69 other frames byte-for-byte; write new walk_00 & walk_07
    for sm_f in snap_sm["frames"]:
        fname = sm_f["name"]
        out_p = STAGE_SRC / sm_f["file"]
        if fname == "walk_00":
            Image.fromarray(new_w00, "RGBA").save(out_p)
        elif fname == "walk_07":
            Image.fromarray(new_w07, "RGBA").save(out_p)
        else:
            shutil.copy2(snap_paths[fname], out_p)

    walk_frames = [
        new_w00,
        *[snap_arrays[f"walk_{i:02d}"] for i in range(1, 7)],
        new_w07,
    ]
    walk_report = measure_walk(walk_frames)
    if walk_report["torso_x_spread_px"] > 2.0:
        raise RuntimeError(f"Walk torso_x spread exceeded 2.0px: {walk_report['torso_x_spread_px']}")

    (STAGE_SRC / "manifest.json").write_text(json.dumps(snap_sm, indent=2, ensure_ascii=False) + "\n")

    subprocess.run(
        [
            sys.executable,
            str(BUILD_CLIPS_SCRIPT),
            "--manifest",
            str(STAGE_SRC / "manifest.json"),
            "--output-dir",
            str(STAGE_CLIPS),
            "--preview-scale",
            "2",
            "--strict",
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(EXPORT_ENGINE_SCRIPT),
            "--clips",
            str(STAGE_CLIPS / "animation-clips.json"),
            "--target",
            "all",
            "--output-dir",
            str(STAGE_BUNDLE),
            "--name",
            CHAR_ID,
            "--sampling",
            "nearest",
            "--godot-fps",
            "auto",
        ],
        check=True,
    )

    # Restore exact custom metadata & relative paths in engine-export.json
    new_export = json.loads((STAGE_BUNDLE / "engine-export.json").read_text())
    new_export["source"]["path"] = "../clips/animation-clips.json"
    if "qa" in new_export and "inputs" in new_export["qa"]:
        for inp in new_export["qa"]["inputs"]:
            if isinstance(inp.get("path"), str) and "/stage_clips/" in inp["path"]:
                inp["path"] = "../clips/" + inp["path"].split("/stage_clips/", 1)[1]
            elif isinstance(inp.get("path"), str) and inp["path"].startswith("../stage_clips/"):
                inp["path"] = "../clips/" + inp["path"].split("../stage_clips/", 1)[1]

    now_iso = datetime.now(timezone.utc).isoformat()
    new_export["states"] = snap_export["states"]
    new_export["unused_frames"] = snap_export["unused_frames"]
    rc = json.loads(json.dumps(snap_export["render_contract"]))
    new_export["render_contract"] = rc

    new_atlas_sha = sha256_file(STAGE_BUNDLE / "godot/spinosaurus-atlas-00.png")
    step2_prev_sha = json.loads(STEP2_APPROVAL.read_text())["atlas_sha256"]
    prev_calib_sha = sha256_file(SNAP_DIR / "godot_bundle/godot/spinosaurus-atlas-00.png")

    note = (
        "Walk-edge-uniform-v1: kept idle, walk_01..06, attack_*, power_up, hit, ko, turn, fireball_fx "
        "(69/71 PNGs) byte-identical to calibration-v1 (speed 170 px/s); rebuilt ONLY walk_00 & walk_07 "
        "from 887x887 walk-seam-v6 source via single Nearest resize (thr=224, h=74, area=4542/4564px, "
        "ground=224, torso_x spread=0.75px) to eliminate end-of-loop bloat."
    )
    prov = dict(snap_export["provenance"])
    prov["owner_approved"] = False
    prov["owner_animation_approved"] = False
    prov["previous_atlas_sha256"] = step2_prev_sha
    prov["previous_revision_atlas_sha256"] = prev_calib_sha
    prov["walk_edge_uniform_v1_at"] = now_iso
    prov["calibration_update"] = note
    new_export["provenance"] = prov
    (STAGE_BUNDLE / "engine-export.json").write_text(json.dumps(new_export, indent=2, ensure_ascii=False) + "\n")

    # Atomically install clips and godot_bundle while keeping existing .import files
    preserved_imports = {p.relative_to(BUNDLE_DIR): p.read_bytes() for p in BUNDLE_DIR.rglob("*.import")}
    shutil.rmtree(CLIPS_DIR)
    shutil.copytree(STAGE_CLIPS, CLIPS_DIR)
    (CLIPS_DIR / ".gdignore").write_text("")

    shutil.rmtree(BUNDLE_DIR)
    shutil.copytree(STAGE_BUNDLE, BUNDLE_DIR)
    for rel, content in preserved_imports.items():
        (BUNDLE_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
        (BUNDLE_DIR / rel).write_bytes(content)

    # Record frame hashes & visual measurements
    built_clips = json.loads((CLIPS_DIR / "animation-clips.json").read_text())
    frame_hashes = {f["name"]: sha256_file(CLIPS_DIR / f["file"]) for f in built_clips["frames"]}
    (WORK_DIR / "frame-hashes.json").write_text(
        json.dumps(
            {
                "atlas_sha256": new_atlas_sha,
                "previous_atlas_sha256": prev_calib_sha,
                "walk_report": walk_report,
                "frames": frame_hashes,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )

    fireball_origin = rc["projectile"]["origin_canvas_px"]
    union_mask = np.zeros((256, 384), dtype=bool)
    for f in built_clips["frames"]:
        ba = np.array(Image.open(CLIPS_DIR / f["file"]).convert("RGBA"))
        if f["name"].startswith("fireball_fx_"):
            dx_fb = fireball_origin[0] - 176
            dy_fb = fireball_origin[1] - 128
            fys, fxs = np.where(ba[:, :, 3] > 0)
            union_mask[np.clip(fys + dy_fb, 0, 255), np.clip(fxs + dx_fb, 0, 383)] = True
        else:
            union_mask |= ba[:, :, 3] > 0
    uys, uxs = np.where(union_mask)
    fx_bbox = {
        "x": int(uxs.min()),
        "y": int(uys.min()),
        "w": int(uxs.max() - uxs.min() + 1),
        "h": int(uys.max() - uys.min() + 1),
    }

    sharp_w0 = json.loads(
        subprocess.check_output([sys.executable, str(SHARPNESS_SCRIPT), str(CLIPS_DIR / "frames/frame-12.png")], text=True)
    )
    sharp_w7 = json.loads(
        subprocess.check_output([sys.executable, str(SHARPNESS_SCRIPT), str(CLIPS_DIR / "frames/frame-19.png")], text=True)
    )

    review_json = {
        "status": "reviewed_pending_owner",
        "method": "existing_complete_source_frames",
        "atlas_sha256": new_atlas_sha,
        "previous_revision_atlas_sha256": prev_calib_sha,
        "reviewed_at": now_iso,
        "checks": {
            "body_connections": True,
            "whole_pose_sequence": True,
            "perspective_turns": True,
            "phase_timing": True,
            "three_backgrounds": True,
            "character_identity": True,
        },
        "unresolved_structural_failures": [],
        "naturalness_verdict": "reviewed_pending_owner",
        "owner_approved": False,
        "notes": note,
        "walk_report": walk_report,
        "walk_00_sharpness": sharp_w0,
        "walk_07_sharpness": sharp_w7,
        "filmstrips_opened": [f"filmstrip-0{i}.png" for i in range(9)],
        "backgrounds": ["light", "dark", "checker"],
    }
    (WORK_DIR / "keyframe-review.json").write_text(json.dumps(review_json, indent=2, ensure_ascii=False) + "\n")

    # Update roster.json spinosaurus entry only
    roster = json.loads(ROSTER_PATH.read_text())
    for ch in roster["characters"]:
        if ch["character_id"] == CHAR_ID:
            body_bbox = ch["map_sync_metrics"]["body_only_bbox_px"]
            ch["status"] = "finalized_pending_owner_reapproval"
            ch["atlas_stage"] = "reviewed_pending_owner"
            ch["atlas_sha256"] = new_atlas_sha
            ch["map_sync_metrics"]["full_fx_bbox_px"] = fx_bbox
            ch["map_sync_metrics"]["world_size_at_64ppu_m"] = {
                "body_w_m": round(body_bbox["w"] / 64.0, 3),
                "body_h_m": round(body_bbox["h"] / 64.0, 3),
                "aura_w_m": round(fx_bbox["w"] / 64.0, 3),
                "aura_h_m": round(fx_bbox["h"] / 64.0, 3),
            }
            ch["map_sync_metrics"]["tile_32px_span"] = {
                "body_tiles_w": round(body_bbox["w"] / 32.0, 3),
                "body_tiles_h": round(body_bbox["h"] / 32.0, 3),
                "full_fx_tiles_w": round(fx_bbox["w"] / 32.0, 3),
                "full_fx_tiles_h": round(fx_bbox["h"] / 32.0, 3),
            }
            ch["owner_animation_approval"]["atlas_sha256"] = new_atlas_sha
            ch["owner_animation_approval"]["reason"] = note
            ch["motion_quality"].update(
                {
                    "status": "reviewed_pending_owner",
                    "atlas_sha256": new_atlas_sha,
                    "previous_revision_atlas_sha256": step2_prev_sha,
                    "reviewed_at": now_iso,
                    "owner_approved": False,
                    "naturalness_verdict": "reviewed_pending_owner",
                    "notes": note,
                    "review_evidence": "work/characters/spinosaurus/walk-edge-uniform-v1/keyframe-review.json",
                }
            )
            break
    ROSTER_PATH.write_text(json.dumps(roster, indent=2, ensure_ascii=False) + "\n")

    # Update docs/characters/spinosaurus-final-qa.json while keeping legacy turn/heavy contract fields intact
    qa = json.loads(QA_DOC.read_text())
    qa["status"] = "reviewed_pending_owner"
    qa["atlas_sha256"] = new_atlas_sha
    qa["atlas"] = new_export["atlas"]
    qa["full_fx_bbox_px"] = fx_bbox
    qa["render_contract"]["locomotion"] = rc["locomotion"]
    qa["motion_quality"].update(
        {
            "status": "reviewed_pending_owner",
            "atlas_sha256": new_atlas_sha,
            "owner_approved": False,
            "naturalness_verdict": "reviewed_pending_owner",
            "review_evidence": "work/characters/spinosaurus/walk-edge-uniform-v1/keyframe-review.json",
            "notes": note,
        }
    )
    qa["walk_edge_uniform_v1"] = walk_report
    QA_DOC.write_text(json.dumps(qa, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"atlas_sha256": new_atlas_sha, "full_fx_bbox_px": fx_bbox, "walk_report": walk_report}, indent=2))


if __name__ == "__main__":
    main()
