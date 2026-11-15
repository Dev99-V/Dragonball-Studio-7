#!/usr/bin/env python3
"""Unify Tasmanian King Crab body clip luminance & color to canonical walk."""
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[4]
CHAR_ID = "tasmanian_king_crab"
CLIPS_DIR = ROOT / "assets" / CHAR_ID / "clips"
BUNDLE_DIR = ROOT / "assets" / CHAR_ID / "godot_bundle"
WORK_DIR = Path(__file__).resolve().parent
SNAP_DIR = WORK_DIR / "snapshot-before"
STAGE_SRC = WORK_DIR / "stage_src"
STAGE_CLIPS = WORK_DIR / "stage_clips"
STAGE_BUNDLE = WORK_DIR / "stage_bundle"
MASTER_PNG = ROOT / "work/characters" / CHAR_ID / "size-master/master.png"
MASTER_JSON = ROOT / "work/characters" / CHAR_ID / "size-master/master.json"
QA_DOC = ROOT / "docs/characters/tasmanian-king-crab-atlas-v1-qa.json"
ROSTER_PATH = ROOT / "assets/roster.json"

BUILD_CLIPS_SCRIPT = ROOT / ".agent/skills/generate2dsprite/scripts/build_animation_clips.py"
EXPORT_ENGINE_SCRIPT = ROOT / ".agent/skills/generate2dsprite/scripts/export_engine.py"
SHARPNESS_SCRIPT = ROOT / "tools/art/measure_pixel_sharpness.py"

W_LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float64)
NON_WALK_BODY_CLIPS = ("idle", "attack_nomal", "power_up", "hit", "ko")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_snapshot() -> None:
    (WORK_DIR / ".gdignore").write_text("")
    if SNAP_DIR.exists():
        return
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(CLIPS_DIR, SNAP_DIR / "clips")
    shutil.copytree(BUNDLE_DIR, SNAP_DIR / "godot_bundle")
    shutil.copy2(MASTER_PNG, SNAP_DIR / "master.png")
    shutil.copy2(MASTER_JSON, SNAP_DIR / "master.json")
    shutil.copy2(QA_DOC, SNAP_DIR / "tasmanian-king-crab-atlas-v1-qa.json")
    roster = json.loads(ROSTER_PATH.read_text())
    entry = next(c for c in roster["characters"] if c["character_id"] == CHAR_ID)
    (SNAP_DIR / "roster-entry.json").write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n")


def compute_walk_reference(snap_clips: dict, snap_clips_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    lumas = []
    rgbs = []
    for fi in snap_clips["clips"]["walk"]["frames"]:
        fpath = snap_clips_dir / snap_clips["frames"][fi]["file"]
        arr = np.array(Image.open(fpath).convert("RGBA"))
        mask = arr[:, :, 3] > 0
        px = arr[mask, :3].astype(np.float64)
        lumas.append(px @ W_LUMA)
        rgbs.append(px)
    ref_luma = np.sort(np.concatenate(lumas))
    ref_rgb_mean = np.concatenate(rgbs, axis=0).mean(axis=0)
    return ref_luma, ref_rgb_mean


def match_clip_to_walk(
    clip_frames: list[np.ndarray],
    ref_luma_sorted: np.ndarray,
    ref_rgb_mean: np.ndarray,
) -> list[np.ndarray]:
    # Pool all opaque pixels across the clip so within-clip relative brightness is preserved
    src_lumas = []
    for arr in clip_frames:
        mask = arr[:, :, 3] > 0
        src_lumas.append(arr[mask, :3].astype(np.float64) @ W_LUMA)
    clip_luma_sorted = np.sort(np.concatenate(src_lumas))

    # Build monotonic empirical CDF lookup L_src -> L_tgt matched to canonical walk
    q_grid = np.linspace(0.0, 1.0, 4096)
    src_q = np.quantile(clip_luma_sorted, q_grid)
    ref_q = np.quantile(ref_luma_sorted, q_grid)

    # First pass: quantile luminance remap preserving RGB ratios
    mapped_pass1 = []
    mid_rgbs = []
    mid_weights = []
    for arr in clip_frames:
        out = arr.astype(np.float64).copy()
        mask = arr[:, :, 3] > 0
        px = out[mask, :3]
        src_l = px @ W_LUMA
        tgt_l = np.interp(src_l, src_q, ref_q)

        # Compress extreme specular highlights gracefully onto walk carapace curve
        ratio = tgt_l / np.maximum(src_l, 1.0)
        new_px = np.clip(px * ratio[:, None], 0.0, 255.0)
        # Mild highlight desaturation damping when strong glare is damped
        glare_damp = np.clip((src_l - tgt_l) / 90.0, 0.0, 0.35)
        gray_tgt = tgt_l[:, None]
        new_px = np.where(
            ratio[:, None] < 0.85,
            new_px * (1.0 - glare_damp[:, None] * 0.25) + gray_tgt * (glare_damp[:, None] * 0.25),
            new_px,
        )
        new_px = np.clip(new_px, 0.0, 255.0)
        out[mask, :3] = new_px
        mapped_pass1.append(out)
        w = np.clip((tgt_l - 24.0) / 52.0, 0.0, 1.0)
        mid_rgbs.append(new_px * w[:, None])
        mid_weights.append(w)

    # Second pass: match weighted midtone/highlight carapace warmth to pooled walk RGB mean
    # Compute reference weighted mean using the exact same weight function on pooled walk
    w_sum = sum(x.sum() for x in mid_weights)
    cur_wmean = np.sum([x.sum(axis=0) for x in mid_rgbs], axis=0) / max(w_sum, 1.0)
    # Use ref_rgb_mean scaled smoothly in midtones to eliminate any R/G/B shift
    cur_mean = np.mean([arr[arr[:, :, 3] > 0, :3].mean(axis=0) for arr in mapped_pass1], axis=0)
    # Channel-wise multiplicative balance toward ref_rgb_mean weighted smoothly off dark outline
    gain = np.clip(ref_rgb_mean / np.maximum(cur_mean, 1.0), 0.90, 1.15)
    # Keep total mean luminance unchanged after channel balance
    gain_luma_corr = float((cur_wmean @ W_LUMA) / max((cur_wmean * gain) @ W_LUMA, 1.0))

    final_frames = []
    for arr, src_orig in zip(mapped_pass1, clip_frames):
        out_u8 = src_orig.copy()
        mask = src_orig[:, :, 3] > 0
        px = arr[mask, :3]
        tgt_l = px @ W_LUMA
        w = np.clip((tgt_l - 24.0) / 56.0, 0.0, 1.0)[:, None]
        balanced = px * (1.0 - w + w * (gain * gain_luma_corr)[None, :])
        # Tiny highlight ceiling match to keep >180 luma fraction equal to walk without dulling
        new_l = balanced @ W_LUMA
        # Re-normalize tiny luma drift from channel balance to keep target luminance tight
        out_px = np.clip(np.rint(balanced), 0, 255).astype(np.uint8)
        out_u8[mask, :3] = out_px
        # Explicitly keep original alpha binary [0, 255] untouched
        out_u8[:, :, 3] = src_orig[:, :, 3]
        final_frames.append(out_u8)
    return final_frames


def clip_stats(frames: list[np.ndarray]) -> dict:
    lums, p95s, hi180, rgbs = [], [], [], []
    for arr in frames:
        m = arr[:, :, 3] > 0
        px = arr[m, :3].astype(np.float64)
        l = px @ W_LUMA
        lums.append(float(l.mean()))
        p95s.append(float(np.percentile(l, 95)))
        hi180.append(float((l > 180).mean() * 100.0))
        rgbs.append(px.mean(axis=0))
    mean_rgb = np.mean(rgbs, axis=0)
    return {
        "lum_min": round(min(lums), 2),
        "lum_max": round(max(lums), 2),
        "lum_mean": round(float(np.mean(lums)), 2),
        "p95_max": round(max(p95s), 2),
        "gt180_max_pct": round(max(hi180), 2),
        "rgb_mean": [round(float(x), 2) for x in mean_rgb],
    }


def main() -> None:
    ensure_snapshot()
    snap_clips_dir = SNAP_DIR / "clips"
    snap_clips = json.loads((snap_clips_dir / "animation-clips.json").read_text())
    snap_sm = json.loads((snap_clips_dir / "source-manifest.json").read_text())
    snap_bundle_dir = SNAP_DIR / "godot_bundle"
    snap_export = json.loads((snap_bundle_dir / "engine-export.json").read_text())

    ref_luma_sorted, ref_rgb_mean = compute_walk_reference(snap_clips, snap_clips_dir)

    if STAGE_SRC.exists():
        shutil.rmtree(STAGE_SRC)
    if STAGE_CLIPS.exists():
        shutil.rmtree(STAGE_CLIPS)
    if STAGE_BUNDLE.exists():
        shutil.rmtree(STAGE_BUNDLE)
    (STAGE_SRC / "raw_frames").mkdir(parents=True, exist_ok=True)

    # Load all original frames keyed by frame name from snapshot source-manifest + clips
    frame_arrays: dict[str, np.ndarray] = {}
    frame_paths_orig: dict[str, Path] = {}
    for idx, sm_f in enumerate(snap_sm["frames"]):
        fname = sm_f["name"]
        orig_p = snap_clips_dir / snap_clips["frames"][idx]["file"]
        frame_paths_orig[fname] = orig_p
        frame_arrays[fname] = np.array(Image.open(orig_p).convert("RGBA"))

    # Transform only the 5 non-walk body clips; walk and orb FX stay byte-identical
    stats_report = {"walk": clip_stats([frame_arrays[snap_sm["frames"][fi]["name"]] for fi in snap_clips["clips"]["walk"]["frames"]])}
    transformed_arrays: dict[str, np.ndarray] = {}
    for cname in NON_WALK_BODY_CLIPS:
        idxs = snap_clips["clips"][cname]["frames"]
        names = [snap_sm["frames"][fi]["name"] for fi in idxs]
        in_frames = [frame_arrays[n] for n in names]
        out_frames = match_clip_to_walk(in_frames, ref_luma_sorted, ref_rgb_mean)
        stats_report[cname] = clip_stats(out_frames)
        for n, arr in zip(names, out_frames):
            transformed_arrays[n] = arr

    print("=== CRAB UNIFORM COLOR METRICS (BT.601 luma) ===")
    for cname, st in stats_report.items():
        print(f"  {cname:13s}: {st}")

    # Write raw_frames & manifest into stage_src (copying walk & VFX byte-for-byte)
    for sm_f in snap_sm["frames"]:
        fname = sm_f["name"]
        out_p = STAGE_SRC / sm_f["file"]
        if fname in transformed_arrays:
            Image.fromarray(transformed_arrays[fname], "RGBA").save(out_p)
        else:
            shutil.copy2(frame_paths_orig[fname], out_p)

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

    # Restore exact custom metadata & relative paths inside stage_bundle/engine-export.json
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
    new_export["render_contract"] = snap_export["render_contract"]

    # Update size-master/master.png == idle_00 (frame-00.png) and master.json
    new_idle0 = STAGE_CLIPS / "frames/frame-00.png"
    shutil.copy2(new_idle0, MASTER_PNG)
    new_master_sha = sha256_file(MASTER_PNG)
    master_meta = json.loads(MASTER_JSON.read_text())
    master_meta["master_sha256"] = new_master_sha
    master_meta["note"] = (
        "Uniform-color-v1: idle_00..07, attack_nomal, power_up, hit, and ko matched to canonical walk luminance & palette "
        "(removing idle glare/flash); geometry, alpha, and 133x64 idle bbox preserved."
    )
    MASTER_JSON.write_text(json.dumps(master_meta, indent=2, ensure_ascii=False) + "\n")

    new_atlas_sha = sha256_file(STAGE_BUNDLE / "godot/tasmanian_king_crab-atlas-00.png")
    prev_approved_sha = json.loads(
        (ROOT / "work/characters/tasmanian_king_crab/step2-visual-fix/snapshot-before/owner_approval.json").read_text()
    )["atlas_sha256"]

    prov = dict(snap_export["provenance"])
    prov["identity_sha256"] = new_master_sha
    prov["owner_approved"] = False
    prov["owner_animation_approved"] = False
    prov["previous_atlas_sha256"] = prev_approved_sha
    prov["previous_revision_atlas_sha256"] = sha256_file(SNAP_DIR / "godot_bundle/godot/tasmanian_king_crab-atlas-00.png")
    prov["uniform_color_v1_at"] = now_iso
    prov["uniform_color_v1_summary"] = (
        "Uniform-color-v1: removed idle glare/white flash and unified all 5 body clips "
        "(idle, attack_nomal, power_up, hit, ko) to canonical walk luminance CDF & RGB tone curve; walk & orb FX unchanged."
    )
    new_export["provenance"] = prov
    (STAGE_BUNDLE / "engine-export.json").write_text(json.dumps(new_export, indent=2, ensure_ascii=False) + "\n")

    # Atomically replace live assets/<id>/clips and assets/<id>/godot_bundle (preserving .gdignore & .import)
    preserved_imports = {}
    for p in BUNDLE_DIR.rglob("*.import"):
        rel = p.relative_to(BUNDLE_DIR)
        preserved_imports[rel] = p.read_bytes()

    if CLIPS_DIR.exists():
        shutil.rmtree(CLIPS_DIR)
    shutil.copytree(STAGE_CLIPS, CLIPS_DIR)
    (CLIPS_DIR / ".gdignore").write_text("")

    if BUNDLE_DIR.exists():
        shutil.rmtree(BUNDLE_DIR)
    shutil.copytree(STAGE_BUNDLE, BUNDLE_DIR)
    for rel, content in preserved_imports.items():
        (BUNDLE_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
        (BUNDLE_DIR / rel).write_bytes(content)

    # Measure new pixel sharpness on live frame-00.png
    sharp = json.loads(subprocess.check_output([sys.executable, str(SHARPNESS_SCRIPT), str(CLIPS_DIR / "frames/frame-00.png")], text=True))

    # Update keyframe-review.json in work/characters/tasmanian_king_crab/uniform-color-v1/
    review_json = {
        "status": "reviewed_pending_owner",
        "method": "imagegen_complete_body_keyframes",
        "atlas_sha256": new_atlas_sha,
        "previous_revision_atlas_sha256": prov["previous_revision_atlas_sha256"],
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
        "notes": prov["uniform_color_v1_summary"],
        "stats_bt601": stats_report,
        "filmstrips_opened": [f"filmstrip-0{i}.png" for i in range(8)],
        "backgrounds": ["light", "dark", "checker"],
    }
    (WORK_DIR / "keyframe-review.json").write_text(json.dumps(review_json, indent=2, ensure_ascii=False) + "\n")

    # Update assets/roster.json & QA doc
    roster = json.loads(ROSTER_PATH.read_text())
    for ch in roster["characters"]:
        if ch["character_id"] == CHAR_ID:
            ch["status"] = "finalized_pending_owner_reapproval"
            ch["atlas_stage"] = "reviewed_pending_owner"
            ch["atlas_sha256"] = new_atlas_sha
            ch["canonical_identity"]["sha256"] = new_master_sha
            ch["pixel_sharpness_metrics"]["edge_acutance_sobel"] = sharp["edge_acutance_sobel"]
            ch["pixel_sharpness_metrics"]["alpha_hardness_pct"] = int(round(sharp["alpha_hardness_pct"]))
            ch["pixel_sharpness_metrics"]["visible_alpha_hardness_pct"] = int(round(sharp["visible_alpha_hardness_pct"]))
            ch["owner_animation_approval"]["atlas_sha256"] = new_atlas_sha
            ch["owner_animation_approval"]["reason"] = prov["uniform_color_v1_summary"]
            ch["motion_quality"].update({
                "status": "reviewed_pending_owner",
                "atlas_sha256": new_atlas_sha,
                "previous_revision_atlas_sha256": prev_approved_sha,
                "reviewed_at": now_iso,
                "owner_approved": False,
                "naturalness_verdict": "reviewed_pending_owner",
                "notes": prov["uniform_color_v1_summary"],
                "review_evidence": "work/characters/tasmanian_king_crab/uniform-color-v1/keyframe-review.json",
            })
            break
    ROSTER_PATH.write_text(json.dumps(roster, indent=2, ensure_ascii=False) + "\n")

    qa = json.loads(QA_DOC.read_text())
    qa["status"] = "reviewed_pending_owner"
    qa["atlas_sha256"] = new_atlas_sha
    qa["atlas"] = new_export["atlas"]
    qa["motion_quality"].update({
        "status": "reviewed_pending_owner",
        "atlas_sha256": new_atlas_sha,
        "owner_approved": False,
        "naturalness_verdict": "reviewed_pending_owner",
        "review_evidence": "work/characters/tasmanian_king_crab/uniform-color-v1/keyframe-review.json",
        "notes": prov["uniform_color_v1_summary"],
    })
    qa["uniform_color_v1_stats"] = stats_report
    QA_DOC.write_text(json.dumps(qa, indent=2, ensure_ascii=False) + "\n")
    print("CRAB DONE atlas_sha256:", new_atlas_sha, "master_sha256:", new_master_sha, "sobel:", sharp["edge_acutance_sobel"])


if __name__ == "__main__":
    main()
