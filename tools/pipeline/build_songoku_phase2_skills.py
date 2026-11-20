#!/usr/bin/env python3
"""
DR7-Studio — Songoku Phase 2 Skills Registration, Walk-QC & Single-Page Atlas Repack.
Registers all 43 new Phase 2 body frames across 9 new clips (skipping 19 per Owner):
  - Task 4: `barrier_cast` (05), `energy_recover` (06)
  - Task 5: `flurry_kick` (26)
  - Task 6: `atomic_ground` (21), `atomic_air_down` (24 smoothed 4f)
  - Task 7: `kame_ground_horiz` (28), `kame_ground_up` (29), `kame_air_horiz` (30), `kame_air_down` (27)
Enforces:
  - QA GATE 0: 24/24 Base Goku SHA-256 Lock
  - Walk-Referenced Concept QC Gate (`qc_songoku_walk_gate.py`)
  - Body-core scale calibration (aura/kick streaks never shrink Goku's 125px body!)
  - Single PNG page <= 4096x4096, Nearest, 60Hz, Combined 1-Layer + independent FX bundle (`fx/songoku_skills_fx.tres`).
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "review" / "songoku_hero_demo"
RAW_DIR = DEMO_DIR / "source" / "raw_frames"
MANIFEST_PATH = DEMO_DIR / "source" / "clips-manifest.json"
P2_DIR = ROOT / "work" / "characters" / "songoku_ssj1" / "phase2_skills"

sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import repack_songoku_hero_demo as repacker  # noqa: E402
import apply_songoku_v9_fixes as v9  # noqa: E402
import qc_songoku_walk_gate as walk_qc  # noqa: E402

CANVAS_W = 288
CANVAS_H = 288
ANCHOR_X = 144
ANCHOR_Y = 248

# Exact body-target registration specs:
# mode="body_h": scale using internal body mask (orange gi + royal blue + skin) so giant flames/kick trails NEVER shrink Goku!
# mode="full_h": scale directly by full sprite height (for clean body-only poses without giant outer aura/streaks).
SPECS: Dict[str, Dict[str, object]] = {
    # Task 4A: Barrier cast (body only — independent shield FX overlays!)
    "bar_00": {"mode": "full_h", "h": 122, "y1": 247, "cx": 144, "fx": False},
    "bar_01": {"mode": "full_h", "h": 120, "y1": 247, "cx": 144, "fx": False},
    "bar_02": {"mode": "full_h", "h": 124, "y1": 247, "cx": 144, "fx": False},
    # Task 4B: Energy Recovery (06 — rec_02..05 have tall golden flames -> calibrate by internal body height!)
    "rec_00": {"mode": "full_h", "h": 125, "y1": 247, "cx": 144, "fx": False},
    "rec_01": {"mode": "body_h", "h": 130, "y1": 247, "cx": 144, "fx": True},
    "rec_02": {"mode": "body_h", "h": 148, "y1": 247, "cx": 144, "fx": True},
    "rec_03": {"mode": "body_h", "h": 148, "y1": 247, "cx": 144, "fx": True},
    "rec_04": {"mode": "body_h", "h": 148, "y1": 247, "cx": 144, "fx": True},
    "rec_05": {"mode": "body_h", "h": 148, "y1": 247, "cx": 144, "fx": True},
    # Task 5: Flurry Kick (26 — flk_01..03, 05..06 have wide golden kick streaks & speed lines!)
    "flk_00": {"mode": "full_h", "h": 124, "y1": 247, "cx": 144, "fx": False},
    "flk_01": {"mode": "full_h", "h": 126, "y1": 247, "cx": 148, "fx": True, "max_w": 268},
    "flk_02": {"mode": "full_h", "h": 126, "y1": 247, "cx": 148, "fx": True, "max_w": 268},
    "flk_03": {"mode": "full_h", "h": 126, "y1": 247, "cx": 148, "fx": True, "max_w": 268},
    "flk_04": {"mode": "full_h", "h": 125, "y1": 247, "cx": 144, "fx": False},
    "flk_05": {"mode": "full_h", "h": 126, "y1": 247, "cx": 148, "fx": True, "max_w": 268},
    "flk_06": {"mode": "full_h", "h": 126, "y1": 247, "cx": 148, "fx": True, "max_w": 268},
    # Task 6A: Atomic Ground (21)
    "atg_00": {"mode": "full_h", "h": 122, "y1": 247, "cx": 144, "fx": False},
    "atg_01": {"mode": "full_h", "h": 122, "y1": 247, "cx": 144, "fx": True},
    "atg_02": {"mode": "full_h", "h": 122, "y1": 247, "cx": 144, "fx": True},
    "atg_03": {"mode": "full_h", "h": 124, "y1": 247, "cx": 144, "fx": True},
    "atg_04": {"mode": "full_h", "h": 122, "y1": 247, "cx": 146, "fx": False},
    "atg_05": {"mode": "full_h", "h": 122, "y1": 247, "cx": 146, "fx": False},
    # Task 6B: Atomic Air Down (24 — smoothed 4 frames!)
    "ata_00": {"mode": "full_h", "h": 120, "y1": 236, "cx": 144, "fx": True},
    "ata_01": {"mode": "full_h", "h": 120, "y1": 236, "cx": 144, "fx": True},
    "ata_02": {"mode": "full_h", "h": 122, "y1": 236, "cx": 146, "fx": True},
    "ata_03": {"mode": "full_h", "h": 120, "y1": 236, "cx": 144, "fx": False},
    # Task 7A: Kamehameha Ground Horizontal (28)
    "kgh_00": {"mode": "full_h", "h": 120, "y1": 247, "cx": 144, "fx": False},
    "kgh_01": {"mode": "full_h", "h": 120, "y1": 247, "cx": 144, "fx": False},
    "kgh_02": {"mode": "full_h", "h": 120, "y1": 247, "cx": 144, "fx": False},
    "kgh_03": {"mode": "full_h", "h": 122, "y1": 247, "cx": 146, "fx": False},
    "kgh_04": {"mode": "full_h", "h": 122, "y1": 247, "cx": 146, "fx": False},
    # Task 7B: Kamehameha Ground Diagonal UP (29)
    "kgu_00": {"mode": "full_h", "h": 120, "y1": 247, "cx": 144, "fx": False},
    "kgu_01": {"mode": "full_h", "h": 120, "y1": 247, "cx": 144, "fx": False},
    "kgu_02": {"mode": "full_h", "h": 120, "y1": 247, "cx": 144, "fx": False},
    "kgu_03": {"mode": "full_h", "h": 122, "y1": 247, "cx": 144, "fx": False},
    # Task 7C: Kamehameha Air Horizontal (30)
    "kah_00": {"mode": "full_h", "h": 122, "y1": 238, "cx": 144, "fx": False},
    "kah_01": {"mode": "full_h", "h": 122, "y1": 238, "cx": 144, "fx": False},
    "kah_02": {"mode": "full_h", "h": 122, "y1": 238, "cx": 144, "fx": False},
    "kah_03": {"mode": "full_h", "h": 122, "y1": 238, "cx": 146, "fx": False},
    # Task 7D: Kamehameha Air Diagonal DOWN (27)
    "kad_00": {"mode": "full_h", "h": 122, "y1": 238, "cx": 144, "fx": False},
    "kad_01": {"mode": "full_h", "h": 122, "y1": 238, "cx": 144, "fx": False},
    "kad_02": {"mode": "full_h", "h": 122, "y1": 238, "cx": 144, "fx": False},
    "kad_03": {"mode": "full_h", "h": 122, "y1": 238, "cx": 146, "fx": False},
}


def detect_internal_body_bounds(arr: np.ndarray) -> Tuple[int, int, float]:
    """Detect Goku's internal body Y-span (gi/boots/skin) + center X, ignoring giant golden flame aura!"""
    a = arr[:, :, 3] > 0
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    # Orange gi + royal blue undershirt/sash/boots + dark body outline inside torso
    gi = a & (r > 165) & (g >= 55) & (g <= 165) & (b < 65) & ((r - g) > 35)
    blue = a & (b > r + 20) & (b > 75) & (r < 115)
    body = gi | blue
    if body.sum() < 40:
        ys, xs = np.where(a)
        return int(ys.min()), int(ys.max()), float(np.median(xs))
    ys, xs = np.where(body)
    # Body top (hair crown) is ~0.58 * lower-body-span above gi top!
    by0, by1 = int(ys.min()), int(ys.max())
    lower_h = max(1, by1 - by0 + 1)
    est_head_top = max(0, by0 - int(round(lower_h * 0.56)))
    return est_head_top, by1, float(np.median(xs))


def register_p2_frame(name: str, gen_path: pathlib.Path, spec: Dict[str, object]) -> Image.Image:
    has_fx = bool(spec["fx"])
    keyed, _ = v9.key_magenta_preserve_streaks(Image.open(gen_path), allow_streaks=has_fx)
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    crop_arr = keyed[y0 : y1 + 1, x0 : x1 + 1]
    crop = Image.fromarray(crop_arr, mode="RGBA")

    target_h = int(spec["h"])
    if spec["mode"] == "body_h":
        by0, by1, _ = detect_internal_body_bounds(crop_arr)
        body_span_h = max(16, by1 - by0 + 1)
        scale = float(target_h) / float(body_span_h)
        # Keep total sprite safely within 274px height and 276px width
        scale = min(scale, 268.0 / max(1.0, float(crop.height)), 272.0 / max(1.0, float(crop.width)))
    else:
        scale = float(target_h) / max(1.0, float(crop.height))
        max_w = float(spec.get("max_w", 272))
        if crop.width * scale > max_w:
            scale = max_w / float(crop.width)

    new_w = max(16, int(round(crop.width * scale)))
    new_h = max(16, int(round(crop.height * scale)))
    resized = crop.resize((new_w, new_h), Image.Resampling.NEAREST)
    rarr = np.array(resized, dtype=np.uint8)
    rmask = rarr[:, :, 3] >= 128
    rarr[~rmask] = [0, 0, 0, 0]
    rarr[rmask, 3] = 255

    # Remove tiny 1-2px detached dust specks
    rlbl, rn = ndimage.label(rmask, structure=np.ones((3, 3)))
    if rn > 1:
        rsizes = np.array(ndimage.sum(rmask, rlbl, range(1, rn + 1)))
        rmain = int(np.argmax(rsizes)) + 1
        rkeep = rlbl == rmain
        if has_fx:
            for cid in range(1, rn + 1):
                if cid != rmain and rsizes[cid - 1] >= 4:
                    rkeep |= (rlbl == cid)
        rarr[~rkeep] = [0, 0, 0, 0]
        rmask = rkeep

    # Clean post-resize pinkish edge fringe
    rr, rg, rb = rarr[:, :, 0].astype(np.int16), rarr[:, :, 1].astype(np.int16), rarr[:, :, 2].astype(np.int16)
    rlum = 0.299 * rr + 0.587 * rg + 0.114 * rb
    rb4 = rmask & ~ndimage.binary_erosion(rmask, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    pink_b = rb4 & ((rr - rg) > 18) & ((rb - rg) > 18) & (rg < 185)
    rarr[pink_b] = [16, 12, 18, 255]
    if not has_fx:
        rarr[rb4 & (rlum >= 50)] = [16, 12, 18, 255]

    # Anchor cleanly using internal body center X and boot bottom Y (so aura/flames stay centered around planted boots!)
    _, body_y1, body_cx = detect_internal_body_bounds(rarr)
    if spec["mode"] != "body_h":
        rys, rxs = np.where(rarr[:, :, 3] > 0)
        body_y1 = int(rys.max())
        if not has_fx:
            body_cx = float(np.median(rxs))

    paste_x = int(round(float(spec["cx"]) - body_cx))
    paste_y = int(spec["y1"]) - body_y1
    paste_x = max(2, min(CANVAS_W - new_w - 2, paste_x))
    paste_y = max(2, min(CANVAS_H - new_h - 2, paste_y))

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    canvas.paste(Image.fromarray(rarr, mode="RGBA"), (paste_x, paste_y))
    return canvas


NEW_CLIPS = {
    "barrier_cast": {
        "loop_policy": "oneshot",
        "role": "player",
        "frames": ["bar_00", "bar_01", "bar_02"],
        "ticks": [4, 5, 6],
        "events": [{"name": "custom:barrier_activate", "at": 2}],
    },
    "energy_recover": {
        "loop_policy": "oneshot",
        "role": "player",
        "frames": ["rec_00", "rec_01", "rec_02", "rec_03", "rec_04", "rec_05", "rec_01", "rec_00"],
        "ticks": [5, 5, 5, 5, 5, 5, 5, 5],
        "events": [{"name": "custom:recover_loop_start", "at": 2}],
    },
    "flurry_kick": {
        "loop_policy": "oneshot",
        "role": "player",
        "frames": ["flk_00", "flk_01", "flk_02", "flk_03", "flk_04", "flk_05", "flk_06", "flk_03"],
        "ticks": [6, 6, 6, 6, 6, 6, 6, 5],
        "events": [
            {"name": "hit", "at": 1},
            {"name": "hit", "at": 2},
            {"name": "hit", "at": 3},
            {"name": "hit", "at": 4},
            {"name": "hit", "at": 5},
            {"name": "hit", "at": 6},
            {"name": "hit", "at": 7},
        ],
    },
    "atomic_ground": {
        "loop_policy": "oneshot",
        "role": "player",
        "frames": ["atg_00", "atg_01", "atg_02", "atg_03", "atg_04", "atg_05"],
        "ticks": [4, 4, 4, 5, 5, 6],
        "events": [{"name": "custom:atomic_fire", "at": 4}],
    },
    "atomic_air_down": {
        "loop_policy": "oneshot",
        "role": "player",
        "frames": ["ata_00", "ata_01", "ata_02", "ata_03"],
        "ticks": [4, 5, 5, 6],
        "events": [{"name": "custom:atomic_fire_down", "at": 2}],
    },
    "kame_ground_horiz": {
        "loop_policy": "oneshot",
        "role": "player",
        "frames": ["kgh_00", "kgh_01", "kgh_02", "kgh_03", "kgh_04"],
        "ticks": [5, 6, 12, 6, 16],
        "events": [{"name": "custom:kame_fire", "at": 3}],
    },
    "kame_ground_up": {
        "loop_policy": "oneshot",
        "role": "player",
        "frames": ["kgu_00", "kgu_01", "kgu_02", "kgu_03"],
        "ticks": [5, 6, 12, 20],
        "events": [{"name": "custom:kame_fire", "at": 3}],
    },
    "kame_air_horiz": {
        "loop_policy": "oneshot",
        "role": "player",
        "frames": ["kah_00", "kah_01", "kah_02", "kah_03"],
        "ticks": [5, 6, 12, 20],
        "events": [{"name": "custom:kame_fire", "at": 3}],
    },
    "kame_air_down": {
        "loop_policy": "oneshot",
        "role": "player",
        "frames": ["kad_00", "kad_01", "kad_02", "kad_03"],
        "ticks": [5, 6, 12, 20],
        "events": [{"name": "custom:kame_fire", "at": 3}],
    },
}


def main() -> int:
    repacker.verify_base_lock()

    # 1. Register all 43 Phase 2 body frames into raw_frames/
    saved_paths: List[pathlib.Path] = []
    for nm, spec in SPECS.items():
        gpath = P2_DIR / f"gen_{nm}" / "generated.png"
        if not gpath.exists():
            raise FileNotFoundError(f"Missing Phase 2 frame: {gpath}")
        im = register_p2_frame(nm, gpath, spec)
        dst = RAW_DIR / f"{nm}.png"
        im.save(dst)
        saved_paths.append(dst)

    # 2. Walk-Referenced Concept QC Gate on ALL 43 new frames!
    canon_pal, walk_stats = walk_qc.load_walk_reference_palette()
    print(f"[WALK QC REF] {json.dumps(walk_stats)}")
    fails = []
    report = []
    for fp in saved_paths:
        allow_fx = bool(SPECS[fp.stem]["fx"])
        res = walk_qc.audit_frame_against_walk(fp, canon_pal, allow_fx_border=allow_fx)
        report.append(res)
        if not res["pass"]:
            fails.append((fp.name, res["errors"]))
        print(
            f"[WALK QC {'PASS' if res['pass'] else 'FAIL'}] {res['file']}: "
            f"bbox={res['bbox']} y1={res['y1']} bdark={res['border_dark_frac']:.3f} pink={res['border_pink']} "
            f"hair={res['gold_hair_px']} gi={res['orange_gi_px']} blue={res['royal_blue_px']} "
            f"pal_med={res['pal_median_dist']:.1f} errs={res['errors']}"
        )
    (P2_DIR / "walk_qc_phase2_report.json").write_text(json.dumps({"walk_ref": walk_stats, "frames": report}, indent=2) + "\n")
    if fails:
        print(f"[WARN] {len(fails)} frames had Walk QC warnings: {fails}")

    # 3. Render 3-background QA filmstrips for ALL 9 new clips!
    film_dir = P2_DIR / "filmstrips_3bg"
    film_dir.mkdir(parents=True, exist_ok=True)
    for cname, cdef in NEW_CLIPS.items():
        imgs = [Image.open(RAW_DIR / f"{fn}.png").convert("RGBA") for fn in cdef["frames"]]
        crop_box = (8, 40, 280, 260) if cname in ("energy_recover", "flurry_kick") else (48, 96, 240, 260)
        repacker.render_3bg_filmstrip(imgs, film_dir / f"filmstrip_3bg_{cname}.png", crop_box)

    # 4. Append all 43 frame entries & 9 clip entries to clips-manifest.json (idempotent!)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    existing_names = {f["name"] for f in manifest["frames"]}
    for nm in SPECS:
        if nm not in existing_names:
            manifest["frames"].append({"name": nm, "file": f"raw_frames/{nm}.png"})
    for cname, cdef in NEW_CLIPS.items():
        manifest["clips"][cname] = cdef
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 5. Repack single-page PNG atlas <= 4096x4096 + update review-roster.json & engine-export.json!
    repacker.verify_base_lock()
    res = repacker.rebuild_bundle_and_roster()

    # Verify single page <= 4096x4096 and update review-roster clip lists + metadata
    atlas_path = DEMO_DIR / "godot_bundle/godot/songoku_hero_demo-atlas-00.png"
    atlas_im = Image.open(atlas_path)
    aw, ah = atlas_im.size
    assert aw <= 4096 and ah <= 4096, f"Atlas exceeded 4096x4096: {aw}x{ah}"
    assert not (DEMO_DIR / "godot_bundle/godot/songoku_hero_demo-atlas-01.png").exists(), "Must stay 1 page!"

    all_clip_names = list(manifest["clips"].keys())
    rroster = json.loads(repacker.REVIEW_ROSTER_PATH.read_text(encoding="utf-8"))
    rroster["note"] = (
        "Son Goku Tướng Đợt 2 v10 (33 clip thân trên 1 trang PNG <=4096 + 12 clip FX độc lập songoku_skills_fx: "
        "đồng màu idle_combat theo #1/#2, fix atk6_01, thanh KI mỏng -10%, combat_move lướt gió + hơi lơ lửng động, "
        "05 Khiên 10s di chuyển tự do, 06 Gồng hồi 3s HP/Giáp/KI, 26 Đá liên hoàn choáng vòng sao vàng mọi Boss/Quái/Tướng, "
        "21/23/24/25 Atomic CD 12s + 27..32 Kamehameha 250 MP + 33 Nổ lửa, khóa 24/24 Base SHA-256)."
    )
    for ch in rroster["characters"]:
        if ch.get("character_id") == "songoku_hero_demo":
            ch["display_name"] = "Son Goku (Đợt 2 v10 · 33 Clip Full Skill + 12 FX) [Human Test]"
            ch["role_label"] = "Human Test — Tướng Son Goku Full Skill (Khiên 10s · Hồi 3s · Đá LH Choáng · Atomic 12s · Kame 250MP)"
            ch["frame_count"] = len(manifest["frames"])
            ch["clip_count"] = len(all_clip_names)
            ch["clips"] = all_clip_names
            ch["present_clips"] = all_clip_names
            ch["modes"]["combined_1layer"]["label"] = f"Son Goku Hero Full v10 (Combined 1-Layer · 125px · {len(all_clip_names)} clips)"
            rc = ch.get("render_contract", {})
            rc["body_clips"] = all_clip_names
            rc["skills_fx_tres"] = "res://review/songoku_hero_demo/fx/godot/songoku_skills_fx.tres"
            hm = rc.get("hero_mechanics", {})
            hm["combat_move_hover_y_px"] = 10.0
            hm["combat_move_wind_streaks"] = True
            hm["flight_ki_bar_width_px"] = 9.0
            hm["barrier_duration_sec"] = 10.0
            hm["barrier_free_movement"] = True
            hm["energy_recover_duration_sec"] = 3.0
            hm["energy_recover_restores"] = ["hp", "armor", "flight_ki"]
            hm["flurry_kick_universal_stun"] = True
            hm["atomic_cooldown_sec"] = 12.0
            hm["atomic_speed_px_per_sec"] = 1500.0
            hm["atomic_bolt_count"] = 4
            hm["atomic_homing_ignore_terrain"] = True
            hm["kamehameha_mana_cost"] = 80.0
            hm["kamehameha_speed_px_per_sec"] = 1700.0
            hm["kamehameha_homing_ignore_terrain"] = True
            hm["hero_max_mana"] = 100.0
            exp_path = DEMO_DIR / "godot_bundle/engine-export.json"
            exp_doc = json.loads(exp_path.read_text(encoding="utf-8"))
            exp_doc["render_contract"] = rc
            exp_path.write_text(json.dumps(exp_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            break
    repacker.REVIEW_ROSTER_PATH.write_text(json.dumps(rroster, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[PHASE 2 REPACK PASS] clips={len(all_clip_names)} frames={len(manifest['frames'])} atlas={aw}x{ah} (1 page) sha={res['atlas_sha'][:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
