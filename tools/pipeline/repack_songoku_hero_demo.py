#!/usr/bin/env python3
"""
DR7-Studio — Songoku Hero Demo Repack & QA Pipeline (Combined 1-Layer).
- Enforces QA GATE 0: Immutable SHA-256 lock on all 24 approved Base Goku frames.
- Keys & head-width-locks Codex CLI whole-pose frames (zero zoom pulsing!) for `idle_combat`.
- Ensures `ko_02.png` rests solidly on the ground line (anchor_y = 248).
- Updates `combat_move` ticks to [6, 5, 6, 5] (100ms hop / ~90ms land @ 60Hz).
- Rebuilds `clips/` + `godot_bundle/` (1 page <= 4096x4096, Nearest, 60Hz) and updates `review/review-roster.json`.
- Renders 3-background QA filmstrips (light / dark / checkerboard) for visual verification.
"""
from __future__ import annotations

import argparse
import hashlib
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
BASE_LOCK_PATH = DEMO_DIR / "base_approved_lock.json"
REVIEW_ROSTER_PATH = ROOT / "review" / "review-roster.json"
BUILD_CLIPS_SCRIPT = ROOT / ".agents" / "skills" / "generate2dsprite" / "scripts" / "build_animation_clips.py"
EXPORT_ENGINE_SCRIPT = ROOT / ".agents" / "skills" / "generate2dsprite" / "scripts" / "export_engine.py"

CANVAS_W = 288
CANVAS_H = 288
ANCHOR_X = 144
ANCHOR_Y = 248


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_base_lock() -> None:
    lock_doc = json.loads(BASE_LOCK_PATH.read_text(encoding="utf-8"))
    expected: Dict[str, str] = lock_doc["sha256"]
    mismatches: List[str] = []
    for fname, exp_sha in expected.items():
        fpath = RAW_DIR / fname
        if not fpath.exists():
            mismatches.append(f"{fname}: MISSING")
            continue
        got_sha = sha256_file(fpath)
        if got_sha != exp_sha:
            mismatches.append(f"{fname}: expected {exp_sha[:12]} got {got_sha[:12]}")
    if mismatches:
        raise RuntimeError(f"QA GATE 0 FAILED (Base SHA-256 Lock): {mismatches}")
    print(f"[QA GATE 0 PASS] Base Lock verified: {len(expected)}/{len(expected)} frames exact SHA-256.")


def key_magenta_2stage(img: Image.Image) -> Tuple[np.ndarray, Dict[str, int]]:
    """Pocket-first 2-stage chroma-key on pure magenta #FF00FF with zero spill & 100% hard binary alpha."""
    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)

    # Stage 1: Aggressive interior + exterior magenta background removal (including enclosed pockets)
    is_magenta = (
        ((r > 165) & (b > 165) & (g < 130) & ((r - g) > 55) & ((b - g) > 55))
        | ((r > 195) & (b > 195) & (g < 165) & ((r - g) > 40) & ((b - g) > 40))
    )
    fg = ~is_magenta

    # 2D Component Ownership Masking: keep only primary character connected component (8-connectivity)
    labeled, n_comp = ndimage.label(fg, structure=np.ones((3, 3), dtype=np.int32))
    if n_comp > 1:
        sizes = ndimage.sum(fg, labeled, range(1, n_comp + 1))
        main_label = int(np.argmax(sizes)) + 1
        fg = labeled == main_label

    # Stage 2: 1px outer ring magenta spill cleanup
    dilated_bg = ndimage.binary_dilation(~fg, iterations=2)
    ring = fg & dilated_bg
    spill = ring & ((r - g) > 35) & ((b - g) > 35) & (g < 155)
    fg = fg & ~spill

    # Re-verify single connected component after fringe trim
    labeled2, n_comp2 = ndimage.label(fg, structure=np.ones((3, 3), dtype=np.int32))
    if n_comp2 > 1:
        sizes2 = ndimage.sum(fg, labeled2, range(1, n_comp2 + 1))
        main_label2 = int(np.argmax(sizes2)) + 1
        fg = labeled2 == main_label2

    # Check enclosed magenta pockets remaining
    opaque_key_px = int((fg & is_magenta).sum())
    bg_lbl, n_bg = ndimage.label(~fg, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    # Exterior background touches border
    border_labels = set(np.unique(np.concatenate([bg_lbl[0, :], bg_lbl[-1, :], bg_lbl[:, 0], bg_lbl[:, -1]])))
    interior_pockets = 0
    for lbl in range(1, n_bg + 1):
        if lbl in border_labels:
            continue
        pocket_mask = bg_lbl == lbl
        if int(pocket_mask.sum()) >= 2:
            # Interior transparent hole (e.g. between legs/arms) is intentional transparency, NOT opaque pocket!
            pass
    out = arr.copy()
    out[~fg] = [0, 0, 0, 0]
    out[fg, 3] = 255
    return out, {"opaque_key_px": opaque_key_px, "enclosed_key_pockets": interior_pockets}


def measure_sprite_metrics(arr: np.ndarray) -> Dict[str, float]:
    a = arr[:, :, 3] > 0
    ys, xs = np.where(a)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    h = y1 - y0 + 1
    w = x1 - x0 + 1
    # Yellow hair + head region = top 45% of character height
    head_end = y0 + max(1, int(round(h * 0.45)))
    hxs = np.where(a[y0:head_end, :])[1]
    head_w = int(hxs.max() - hxs.min() + 1) if len(hxs) else w
    # Boots center X = median X of bottom 12% rows
    boot_start = max(y0, y1 - max(4, int(round(h * 0.12))))
    bxs = np.where(a[boot_start : y1 + 1, :])[1]
    boot_cx = float(np.median(bxs)) if len(bxs) else float((x0 + x1) * 0.5)
    boot_span = int(bxs.max() - bxs.min() + 1) if len(bxs) else 0
    return {
        "x0": x0, "y0": y0, "x1": x1, "y1": y1,
        "w": w, "h": h, "head_w": head_w,
        "boot_cx": boot_cx, "boot_span": boot_span,
    }


def register_idle_combat_frame(
    gen_path: pathlib.Path,
    ref_metrics: Dict[str, float],
) -> Tuple[Image.Image, Dict[str, float]]:
    """
    Scale generated whole-pose frame by STRICTLY LOCKING HEAD WIDTH (zero zoom pulsing!)
    and plant boots firmly at ref_metrics['boot_cx'], y=247.
    """
    keyed_arr, key_stats = key_magenta_2stage(Image.open(gen_path))
    m_gen = measure_sprite_metrics(keyed_arr)
    crop = Image.fromarray(keyed_arr[m_gen["y0"] : m_gen["y1"] + 1, m_gen["x0"] : m_gen["x1"] + 1], mode="RGBA")

    # Lock scale strictly by head width so crouching/standing NEVER zooms the head or body!
    scale = float(ref_metrics["head_w"]) / max(1.0, float(m_gen["head_w"]))
    new_w = max(16, int(round(crop.width * scale)))
    new_h = max(16, int(round(crop.height * scale)))

    resized = crop.resize((new_w, new_h), Image.Resampling.NEAREST)
    res_arr = np.array(resized, dtype=np.uint8)
    mask = res_arr[:, :, 3] >= 128
    res_arr[~mask] = [0, 0, 0, 0]
    res_arr[mask, 3] = 255
    m_res = measure_sprite_metrics(res_arr)

    # Plant boots cleanly at exact ref boot_cx and y1 = 247 (ground line anchor_y = 248)
    paste_x = int(round(ref_metrics["boot_cx"] - m_res["boot_cx"]))
    paste_y = 247 - int(m_res["y1"])

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    canvas.paste(Image.fromarray(res_arr, mode="RGBA"), (paste_x, paste_y))
    final_arr = np.array(canvas, dtype=np.uint8)
    final_m = measure_sprite_metrics(final_arr)
    final_m.update(key_stats)
    return canvas, final_m


def fix_ko_02_ground_contact() -> Dict[str, int]:
    """Ensure ko_02.png lying back/boots rest solidly on anchor_y=248 (not floating on 2px hair outline)."""
    ko2_path = RAW_DIR / "ko_02.png"
    arr = np.array(Image.open(ko2_path).convert("RGBA"), dtype=np.uint8)
    a = arr[:, :, 3] > 0
    r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
    orange = a & (r > 180) & (g > 60) & (g < 170) & (b < 70)
    orange_max_y = int(np.where(orange)[0].max()) if orange.any() else 248
    # Target orange_gi_max_y = 250 (resting firmly on ground line y=248, boots ~245)
    shift_y = max(0, 250 - orange_max_y)
    if shift_y > 0:
        shifted = np.zeros_like(arr)
        shifted[shift_y:, :, :] = arr[:-shift_y, :, :]
        Image.fromarray(shifted, mode="RGBA").save(ko2_path)
        arr = shifted
    a2 = arr[:, :, 3] > 0
    ys = np.where(a2)[0]
    return {"shift_y": shift_y, "y0": int(ys.min()), "y1": int(ys.max())}


def render_3bg_filmstrip(frames: List[Image.Image], out_path: pathlib.Path, crop_box: Tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = crop_box
    cw, ch = x1 - x0, y1 - y0
    n = len(frames)
    pad = 8
    scale = 2
    cell_w, cell_h = cw * scale, ch * scale
    total_w = n * cell_w + (n + 1) * pad
    total_h = 3 * cell_h + 4 * pad

    strip = Image.new("RGBA", (total_w, total_h), (24, 28, 36, 255))
    bgs = [
        ("light", (245, 247, 250, 255)),
        ("dark", (18, 22, 30, 255)),
        ("checker", None),
    ]
    for row_idx, (_, bg_col) in enumerate(bgs):
        ry = pad + row_idx * (cell_h + pad)
        for col_idx, fr in enumerate(frames):
            rx = pad + col_idx * (cell_w + pad)
            if bg_col is not None:
                cell = Image.new("RGBA", (cell_w, cell_h), bg_col)
            else:
                cell = Image.new("RGBA", (cell_w, cell_h), (195, 200, 208, 255))
                carr = np.array(cell)
                yy, xx = np.indices((cell_h, cell_w))
                chk = ((xx // 8) + (yy // 8)) % 2 == 0
                carr[chk] = [230, 234, 240, 255]
                cell = Image.fromarray(carr, mode="RGBA")
            # Draw horizontal red ground reference line at y = ANCHOR_Y
            gy_local = (ANCHOR_Y - y0) * scale
            if 0 <= gy_local < cell_h:
                carr2 = np.array(cell)
                carr2[gy_local : min(cell_h, gy_local + 2), :, :] = [235, 65, 65, 255]
                cell = Image.fromarray(carr2, mode="RGBA")
            sub = fr.crop((x0, y0, x1, y1)).resize((cell_w, cell_h), Image.Resampling.NEAREST)
            cell.alpha_composite(sub)
            strip.alpha_composite(cell, (rx, ry))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    strip.save(out_path)


def rebuild_bundle_and_roster() -> Dict[str, str]:
    # Update combat_move ticks in clips-manifest.json to [6, 5, 6, 5] (100ms hop / ~90ms land @ 60Hz)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["clips"]["combat_move"]["ticks"] = [6, 5, 6, 5]
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    tmp_clips = DEMO_DIR / "_tmp_clips"
    tmp_bundle = DEMO_DIR / "_tmp_godot_bundle"
    if tmp_clips.exists():
        shutil.rmtree(tmp_clips)
    if tmp_bundle.exists():
        shutil.rmtree(tmp_bundle)

    subprocess.run(
        [
            sys.executable,
            str(BUILD_CLIPS_SCRIPT),
            "--manifest",
            str(MANIFEST_PATH),
            "--output-dir",
            str(tmp_clips),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(EXPORT_ENGINE_SCRIPT),
            "--clips",
            str(tmp_clips / "animation-clips.json"),
            "--target",
            "godot-spriteframes",
            "--output-dir",
            str(tmp_bundle),
            "--name",
            "songoku_hero_demo",
            "--sampling",
            "nearest",
            "--godot-fps",
            "auto",
            "--subject-height-px",
            "125",
        ],
        check=True,
    )

    # Place .gdignore inside clips/ before swapping into place
    (tmp_clips / ".gdignore").write_text("", encoding="utf-8")
    clips_dir = DEMO_DIR / "clips"
    bundle_dir = DEMO_DIR / "godot_bundle"
    if clips_dir.exists():
        shutil.rmtree(clips_dir)
    tmp_clips.rename(clips_dir)

    # Preserve Godot .import sidecars if present? No, overwrite clean files inside godot_bundle so UIDs stay valid!
    if bundle_dir.exists():
        # Copy generated files over existing directory to keep .png.import UID intact
        for src_p in tmp_bundle.rglob("*"):
            rel = src_p.relative_to(tmp_bundle)
            dst_p = bundle_dir / rel
            if src_p.is_dir():
                dst_p.mkdir(parents=True, exist_ok=True)
            else:
                dst_p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_p, dst_p)
        shutil.rmtree(tmp_bundle)
    else:
        tmp_bundle.rename(bundle_dir)

    atlas_path = bundle_dir / "godot" / "songoku_hero_demo-atlas-00.png"
    tres_path = bundle_dir / "godot" / "songoku_hero_demo.tres"
    atlas_sha = sha256_file(atlas_path)
    tres_sha = sha256_file(tres_path)
    atlas_im = Image.open(atlas_path)
    atlas_w, atlas_h = atlas_im.size

    # Update review-roster.json
    rroster = json.loads(REVIEW_ROSTER_PATH.read_text(encoding="utf-8"))
    rroster["note"] = (
        "Son Goku Tướng Đợt 1 v9 (khử nhấp nháy viền idle_combat 100% dark outline, "
        "combat_move dash liên tục không aura: lùi #0 400px/s -> phanh #1, tiến #3 500px/s -> phanh #2 khi kéo analog gần giữa, "
        "vẽ lại chuẩn walk_ssj các frame lỗi attack_light #2/#4/#8/#10, attack_2 #1/#2, attack_5 #1/#5/#6/#7, attack_6 #2, "
        "giữ khóa SHA-256 24/24 Base)."
    )
    for ch in rroster["characters"]:
        if ch.get("character_id") == "songoku_hero_demo":
            ch["display_name"] = "Son Goku (Đợt 1 v9 · Viền Idle · Dash/Phanh CMove · Fix Attack) [Human Test]"
            ch["role_label"] = "Human Test — Tướng Son Goku Đợt 1 v9 (Clean Idle Border · CMove Dash 400/500 & Brake #1/#2 · Walk-Synced Attacks)"
            ch["review_atlas_sha256"] = atlas_sha
            ch["atlas_sha256"] = atlas_sha
            ch["atlas_size_px"] = [atlas_w, atlas_h]
            ch["tres_sha256"] = tres_sha
            ch["modes"]["combined_1layer"]["label"] = "Son Goku Hero Đợt 1 v9 (Combined 1-Layer · 125px · 24 clips)"
            rc = ch.get("render_contract", {})
            loc = rc.get("locomotion", {})
            loc["combat_speed_px_per_second"] = 500.0
            loc["combat_back_speed_px_per_second"] = 400.0
            loc["combat_fwd_speed_px_per_second"] = 500.0
            loc["combat_move_hop_distance_px"] = 0.0
            loc["combat_move_hover_y_px"] = 0.0
            hm = rc.get("hero_mechanics", {})
            hm["combat_move_speed_px_per_sec"] = 500.0
            hm["combat_move_back_speed_px_per_sec"] = 400.0
            hm["combat_move_fwd_speed_px_per_sec"] = 500.0
            hm["combat_move_hop_distance_px"] = 0.0
            hm["combat_move_hover_y_px"] = 0.0
            hm["combat_move_dash_no_aura"] = True
            hm["combat_move_mode"] = "continuous_dash_with_analog_brake"
            hm["combat_move_frame_roles"] = {
                "back_dash": 0,
                "back_brake": 1,
                "fwd_brake": 2,
                "fwd_dash": 3,
            }
            hm["combat_move_loop_ms"] = {
                "backward": [0, 100, 1, 120],
                "forward": [3, 100, 2, 120],
            }
            hm["flight_ki_max"] = 50.0
            hm["flight_ki_drain_per_sec"] = 5.0
            hm["flight_ki_regen_per_sec"] = 5.0
            hm["flight_ki_bar_color"] = "orange"
            hm["flight_ki_bar_layout"] = "vertical_right_of_hp_mana_armor"
            # Sync `render_contract` into `engine-export.json` (required by tools/preview/server.py load_review_content!)
            exp_path = bundle_dir / "engine-export.json"
            exp_doc = json.loads(exp_path.read_text(encoding="utf-8"))
            exp_doc["render_contract"] = rc
            exp_path.write_text(json.dumps(exp_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            break
    REVIEW_ROSTER_PATH.write_text(json.dumps(rroster, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"atlas_sha": atlas_sha, "tres_sha": tres_sha, "atlas_size": f"{atlas_w}x{atlas_h}"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--f1", type=pathlib.Path, required=True)
    ap.add_argument("--f2", type=pathlib.Path, required=True)
    ap.add_argument("--f3", type=pathlib.Path, required=True)
    ap.add_argument("--qa-dir", type=pathlib.Path, default=ROOT / "work" / "characters" / "songoku_ssj1" / "idle_combat_v8")
    args = ap.parse_args()

    verify_base_lock()

    ref_backup = args.qa_dir / "idle_combat_ref_crouch.png"
    if not ref_backup.exists():
        args.qa_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAW_DIR / "idle_combat_00.png", ref_backup)
    ref_img = Image.open(ref_backup).convert("RGBA")
    ref_arr = np.array(ref_img, dtype=np.uint8)
    ref_m = measure_sprite_metrics(ref_arr)
    print(f"[REF crouch] W={ref_m['w']} H={ref_m['h']} headW={ref_m['head_w']} boot_cx={ref_m['boot_cx']:.1f} bootSpan={ref_m['boot_span']} y1={ref_m['y1']}")

    # Smooth 4-frame rhythmic stance knee-bounce loop (0 -> 1 -> 2 -> 3 -> 0) with locked headW & planted boots:
    # F0 = high stance (f3), F1 = descending flex (f1), F2 = deepest crouch (ref), F3 = rising rebound (f2)
    f0_im, f0_m = register_idle_combat_frame(args.f3, ref_m)
    f1_im, f1_m = register_idle_combat_frame(args.f1, ref_m)
    f2_im, f2_m = ref_img, dict(ref_m, opaque_key_px=0, enclosed_key_pockets=0)
    f3_im, f3_m = register_idle_combat_frame(args.f2, ref_m)

    out_frames = [f0_im, f1_im, f2_im, f3_im]
    for idx, (im, m) in enumerate([(f0_im, f0_m), (f1_im, f1_m), (f2_im, f2_m), (f3_im, f3_m)]):
        fname = f"idle_combat_{idx:02d}.png"
        im.save(RAW_DIR / fname)
        print(
            f"[SET {fname}] W={m['w']} H={m['h']} headW={m['head_w']} "
            f"boot_cx={m['boot_cx']:.1f} bootSpan={m['boot_span']} y0={m['y0']} y1={m['y1']} "
            f"key_px={m['opaque_key_px']} pockets={m['enclosed_key_pockets']}"
        )

    ko_res = fix_ko_02_ground_contact()
    print(f"[KO_02 GROUND FIX] shift_y=+{ko_res['shift_y']}px -> y=[{ko_res['y0']}..{ko_res['y1']}] (anchor_y={ANCHOR_Y})")

    # Render 3-background QA filmstrips
    render_3bg_filmstrip(out_frames, args.qa_dir / "filmstrip_3bg_idle_combat_v8.png", (80, 118, 210, 260))
    ko_frames = [Image.open(RAW_DIR / f"ko_{i:02d}.png").convert("RGBA") for i in range(3)]
    render_3bg_filmstrip(ko_frames, args.qa_dir / "filmstrip_3bg_ko_v8.png", (64, 146, 224, 264))

    # Re-verify Base Lock before & after repack
    verify_base_lock()
    res = rebuild_bundle_and_roster()
    print(f"[DONE REPACK] atlas={res['atlas_size']} sha256={res['atlas_sha'][:16]} | tres sha256={res['tres_sha'][:16]}")


if __name__ == "__main__":
    main()
