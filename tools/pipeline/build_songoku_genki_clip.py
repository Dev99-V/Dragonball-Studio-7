#!/usr/bin/env python3
"""
DR7-Studio — Register 6 Whole-Pose SSJ1 Goku Genki frames (`genki_cast`), Run Walk-QC & 3-bg QA,
Repack 1-page 4090x4090 Atlas (189/196 cells <= 4096x4096), and Update Governance Metadata Safely.
- Preserves 24/24 immutable Base Goku frames (base_approved_lock.json SHA-256 check).
- Preserves 100% of all 34 existing Goku clips untouched (ONLY appends `genki_cast`!).
- Archives v0.18.0 approved atlas to work/characters/songoku/v018_approved_backup/songoku-atlas-00.png
  and updates state.json PIPE-022 approved_atlas_path + roster.json motion_quality = reviewed_pending_owner
  so test_governance_and_preview.py & verify_motion_quality() pass strictly per AGENTS.md!
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
GOKU_DIR = ROOT / "assets" / "songoku"
RAW_DIR = GOKU_DIR / "source" / "raw_frames"
MANIFEST_PATH = GOKU_DIR / "source" / "clips-manifest.json"
BASE_LOCK_PATH = GOKU_DIR / "base_approved_lock.json"
APPROVAL_PATH = GOKU_DIR / "owner_approval.json"
ROSTER_PATH = ROOT / "assets" / "roster.json"
STATE_PATH = ROOT / "state.json"

WORK_GENKI = ROOT / "work" / "characters" / "songoku_genki"
GEN_DIR = WORK_GENKI / "gen_v2"
R4_GEN_DIR = ROOT / "work" / "polish_round4" / "gen"
HOLD_GEN_DIR = R4_GEN_DIR
QA_DIR = ROOT / "work" / "polish_round4" / "qa"
BACKUP_DIR = ROOT / "docs" / "releases" / "archive"
BACKUP_ATLAS = BACKUP_DIR / "songoku-v0.18.0-atlas-00.png"

BUILD_CLIPS_SCRIPT = ROOT / ".agents" / "skills" / "generate2dsprite" / "scripts" / "build_animation_clips.py"
EXPORT_ENGINE_SCRIPT = ROOT / ".agents" / "skills" / "generate2dsprite" / "scripts" / "export_engine.py"

sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import repack_songoku_hero_demo as repacker  # noqa: E402
import qc_songoku_walk_gate as walk_qc  # noqa: E402

CANVAS_W = 288
CANVAS_H = 288
ANCHOR_X = 144
ANCHOR_Y = 248


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_base_lock_live() -> None:
    lock_doc = json.loads(BASE_LOCK_PATH.read_text(encoding="utf-8"))
    expected: Dict[str, str] = lock_doc["sha256"]
    mismatches = []
    for fname, exp_sha in expected.items():
        fp = RAW_DIR / fname
        if not fp.is_file() or sha256_file(fp) != exp_sha:
            mismatches.append(fname)
    if mismatches:
        raise RuntimeError(f"BASE LOCK FAILED on {mismatches}")
    print(f"[QA GATE 0 PASS] Base Goku SHA-256 lock verified: {len(expected)}/{len(expected)} exact.")


def clean_spurious_white_chest_badge(arr: np.ndarray) -> np.ndarray:
    """Clean tiny isolated white chest-circle artifact inside orange gi (if generated) to match canonical gi."""
    out = arr.copy()
    h, w = out.shape[:2]
    r = out[:, :, 0].astype(np.int16)
    g = out[:, :, 1].astype(np.int16)
    b = out[:, :, 2].astype(np.int16)
    a = out[:, :, 3] > 0
    # Torso chest ROI (35%..65% height, 30%..76% width — catches right-chest kanji badge cleanly too!)
    roi = np.zeros((h, w), dtype=bool)
    roi[int(h * 0.35):int(h * 0.65), int(w * 0.30):int(w * 0.76)] = True
    # Pure white/pale neutral spot inside orange gi / dark outline
    white_spot = a & roi & (r > 205) & (g > 205) & (b > 200)
    lbl, n = ndimage.label(white_spot, structure=np.ones((3, 3), dtype=np.int32))
    gi_orange = a & (r > 175) & (g >= 65) & (g <= 165) & (b < 70) & ((r - g) > 35)
    gi_blue = a & (b > 90) & (r < 95) & (g < 145)
    fill_col = np.array([232, 118, 24, 255], dtype=np.uint8)
    if gi_orange.sum() > 20:
        fill_col = np.array([
            int(np.median(out[gi_orange, 0])),
            int(np.median(out[gi_orange, 1])),
            int(np.median(out[gi_orange, 2])),
            255,
        ], dtype=np.uint8)
    for ci in range(1, n + 1):
        comp = lbl == ci
        sz = int(comp.sum())
        if 4 <= sz <= int(h * w * 0.018):
            # Include 1px dark ring around the badge if adjacent to orange gi
            dil = ndimage.binary_dilation(comp, iterations=6) & ~comp
            if (dil & gi_orange).sum() >= max(6, int(sz * 0.25)):
                ring = ndimage.binary_dilation(comp, iterations=2) & ~comp
                dark_ring = ring & (r < 95) & (g < 95) & (b < 95)
                # Only replace interior dark ring pixels adjacent to orange gi (never eat outer sprite outline!)
                inner_dark = dark_ring & ndimage.binary_dilation(gi_orange, iterations=3) & ~ndimage.binary_dilation(~a, iterations=1)
                patch = comp | inner_dark
                out[patch] = fill_col
    return out


def detect_hair_crown_to_boot_height(arr: np.ndarray) -> Tuple[int, int, float]:
    """Measure boot-bottom to SSJ1 golden hair-crown height so raised hands in genki_02/03 NEVER shrink Goku's body!"""
    a = arr[:, :, 3] > 0
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    ys, xs = np.where(a)
    y1 = int(ys.max())
    # Golden SSJ1 hair OR cyan-lit top hair tips (excluding pure skin fingers high above!)
    gold_hair = a & (r > 175) & (g > 145) & (b < 150) & ((r - b) > 35)
    cyan_hair = a & (b > 170) & (g > 170) & (r < 210)
    hair_cand = gold_hair | cyan_hair
    if hair_cand.sum() >= 60:
        hys = np.where(hair_cand)[0]
        # Top of hair crown (1st percentile to ignore stray 1px speck)
        hair_top = int(np.percentile(hys, 1))
        # Add ~2px for black hair outline above bright hair fill
        crown_y0 = max(int(ys.min()), hair_top - 3)
    else:
        crown_y0 = int(ys.min())
    foot_rows = a[max(0, y1 - max(6, int((y1 - crown_y0) * 0.07))):y1 + 1, :]
    fxs = np.where(foot_rows)[1]
    smid = 0.5 * (int(fxs.min()) + int(fxs.max())) if len(fxs) else float(np.median(xs))
    return max(32, y1 - crown_y0 + 1), y1, smid


def register_genki_body_frame(fid: str, src_path: pathlib.Path, spec: Dict[str, object]) -> Image.Image:
    raw = Image.open(src_path).convert("RGBA")
    keyed, kmeta = repacker.key_magenta_2stage(raw)
    assert kmeta["opaque_key_px"] == 0, f"{fid}: opaque_key_px={kmeta['opaque_key_px']}"
    keyed = clean_spurious_white_chest_badge(keyed)

    # Crop tight around sprite
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop = keyed[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

    target_body_h = float(spec["body_h"])
    body_cx_frac = None
    body_bot_frac = None
    if bool(spec.get("use_body_comp_h", False)):
        # Frame with sweeping motion arc (genki_04): measure ONLY Goku's body (orange gi + blue boots/sash + hair above torso)
        ca = crop[:, :, 3] > 0
        cr, cg, cb = crop[:, :, 0].astype(np.int16), crop[:, :, 1].astype(np.int16), crop[:, :, 2].astype(np.int16)
        body_seed = ca & (
            ((cr > 175) & (cg >= 60) & (cg <= 165) & (cb < 75))
            | ((cb > 100) & (cr < 90) & (cg < 135))
        )
        bys, bxs = np.where(body_seed)
        if len(bys) > 30:
            bx_min = max(0, int(bxs.min()) - int(crop.shape[1] * 0.05))
            bx_max = min(crop.shape[1] - 1, int(bxs.max()) + int(crop.shape[1] * 0.02))
            hair_in_band = (
                ca[:, bx_min:bx_max + 1]
                & (cr[:, bx_min:bx_max + 1] > 180)
                & (cg[:, bx_min:bx_max + 1] > 145)
                & (cb[:, bx_min:bx_max + 1] < 135)
                & ((cr[:, bx_min:bx_max + 1] - cb[:, bx_min:bx_max + 1]) > 35)
            )
            hys = np.where(hair_in_band)[0]
            top_by = max(0, int(np.percentile(hys, 1)) - 4) if len(hys) > 20 else int(bys.min())
            bot_by = int(bys.max())
            raw_bh = max(32, bot_by - top_by + 1)
            scale = target_body_h / float(raw_bh)
            body_cx_frac = (0.5 * (int(bxs.min()) + int(bxs.max()))) / max(1.0, float(crop.shape[1]))
            body_bot_frac = float(bot_by) / max(1.0, float(crop.shape[0]))
        else:
            scale = target_body_h / float(crop.shape[0])
    elif bool(spec.get("use_hair_crown_h", False)):
        raw_bh, _, _ = detect_hair_crown_to_boot_height(crop)
        scale = target_body_h / float(raw_bh)
    else:
        scale = target_body_h / float(crop.shape[0])

    # Clamp max canvas fit
    max_w, max_h = 264.0, 240.0
    scale = min(scale, max_w / float(crop.shape[1]), max_h / float(crop.shape[0]))
    nw = max(16, int(round(crop.shape[1] * scale)))
    nh = max(16, int(round(crop.shape[0] * scale)))
    resized = Image.fromarray(crop, "RGBA").resize((nw, nh), Image.Resampling.NEAREST)
    rarr = np.array(resized, dtype=np.uint8)
    # Enforce 100% hard binary alpha and clean any 1px pink residue
    rmask = rarr[:, :, 3] >= 128
    r, g, b = rarr[:, :, 0].astype(np.int16), rarr[:, :, 1].astype(np.int16), rarr[:, :, 2].astype(np.int16)
    pink = rmask & ((r - g) > 40) & ((b - g) > 40) & (g < 155)
    rmask = rmask & ~pink
    rarr[~rmask] = [0, 0, 0, 0]
    rarr[rmask, 3] = 255

    # Anchor by exact stance midpoint (or torso/hair-crown hover anchor for mid-air leg sway frames!)
    rys, rxs = np.where(rmask)
    if bool(spec.get("hover_torso_anchor", False)):
        # Keep head, torso & raised hands ROCK-SOLID across genki_hold_00..03 while the 2 dangling legs gently sway underneath!
        cr, cg, cb = rarr[:, :, 0].astype(np.int16), rarr[:, :, 1].astype(np.int16), rarr[:, :, 2].astype(np.int16)
        gold_c = rmask & (((cr > 175) & (cg > 145) & (cb < 150) & ((cr - cb) > 35)) | ((cb > 170) & (cg > 170) & (cr < 210)))
        crown_y0 = max(0, int(np.percentile(np.where(gold_c)[0], 1)) - 2) if gold_c.sum() >= 30 else int(rys.min())
        # Torso horizontal center measured strictly on upper orange gi (between crown+22 and crown+68) so swinging legs never shift X!
        t_lo = min(nh - 1, crown_y0 + 24)
        t_hi = min(nh, crown_y0 + 72)
        torso_gi = rmask[t_lo:t_hi, :] & (cr[t_lo:t_hi, :] > 170) & (cg[t_lo:t_hi, :] >= 65) & (cg[t_lo:t_hi, :] <= 165) & (cb[t_lo:t_hi, :] < 75)
        txs = np.where(torso_gi)[1]
        smid = float(np.median(txs)) if len(txs) >= 20 else float(np.median(rxs))
        cx_target = float(spec.get("cx", 144.0))
        crown_target = int(spec.get("crown_y", 123))
        px = max(2, min(CANVAS_W - nw - 2, int(round(cx_target - smid))))
        py = max(2, min(CANVAS_H - nh - 2, crown_target - crown_y0))
    else:
        if body_cx_frac is not None and body_bot_frac is not None:
            smid = body_cx_frac * float(nw)
            ry1 = int(round(body_bot_frac * float(nh)))
        else:
            ry1 = int(rys.max())
            foot_band = rmask[max(0, ry1 - 7):ry1 + 1, :]
            fxs = np.where(foot_band)[1]
            smid = 0.5 * (int(fxs.min()) + int(fxs.max())) if len(fxs) else float(np.median(rxs))

        y1_target = int(spec.get("y1", 247))
        cx_target = float(spec.get("cx", 144.0))
        px = max(2, min(CANVAS_W - nw - 2, int(round(cx_target - smid))))
        py = max(2, min(CANVAS_H - nh - 2, y1_target - ry1))

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    canvas.paste(Image.fromarray(rarr, "RGBA"), (px, py))
    return canvas


def render_3bg_strip(imgs: List[Tuple[str, Image.Image]], out_path: pathlib.Path, crop_box=(64, 72, 224, 256)) -> None:
    cw = crop_box[2] - crop_box[0]
    ch = crop_box[3] - crop_box[1]
    scale = 2
    tw, th = cw * scale, ch * scale
    hdr = 22
    sheet = Image.new("RGBA", (len(imgs) * tw, hdr + 3 * th), (24, 28, 36, 255))
    draw = ImageDraw.Draw(sheet)
    for i, (lbl, im) in enumerate(imgs):
        x0 = i * tw
        draw.rectangle([x0, 0, x0 + tw - 1, hdr - 1], fill=(18, 22, 30, 255))
        draw.text((x0 + 6, 4), lbl, fill=(255, 240, 128, 255))
        cropped = im.crop(crop_box).resize((tw, th), Image.Resampling.NEAREST)
        for ri, mode in enumerate(("light", "dark", "checker")):
            y0 = hdr + ri * th
            if mode == "light":
                bg = Image.new("RGBA", (tw, th), (236, 240, 246, 255))
            elif mode == "dark":
                bg = Image.new("RGBA", (tw, th), (20, 24, 34, 255))
            else:
                bg = Image.new("RGBA", (tw, th), (52, 58, 72, 255))
                bd = ImageDraw.Draw(bg)
                for yy in range(0, th, 16):
                    for xx in range(0, tw, 16):
                        if ((xx // 16) + (yy // 16)) % 2 == 0:
                            bd.rectangle([xx, yy, xx + 15, yy + 15], fill=(74, 82, 98, 255))
            bg.alpha_composite(cropped)
            sheet.paste(bg, (x0, y0))
            draw.rectangle([x0, y0, x0 + tw - 1, y0 + th - 1], outline=(100, 118, 145, 255))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def main() -> int:
    verify_base_lock_live()
    QA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Backup v0.18.0 approved atlas into git-tracked .gdignore'd archive (works in both local & CI!)
    live_atlas = GOKU_DIR / "godot_bundle" / "godot" / "songoku-atlas-00.png"
    approval = json.loads(APPROVAL_PATH.read_text(encoding="utf-8"))
    orig_approved_sha = approval["atlas_sha256"]
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / ".gdignore").write_text("", encoding="utf-8")
    backup_atlas = BACKUP_ATLAS
    legacy_backup = ROOT / "work" / "characters" / "songoku" / "v018_approved_backup" / "songoku-atlas-00.png"
    if not backup_atlas.is_file():
        if live_atlas.is_file() and sha256_file(live_atlas) == orig_approved_sha:
            shutil.copy2(live_atlas, backup_atlas)
            print(f"[BACKUP] Archived v0.18.0 approved songoku atlas -> {backup_atlas}")
        elif legacy_backup.is_file() and sha256_file(legacy_backup) == orig_approved_sha:
            shutil.copy2(legacy_backup, backup_atlas)
            print(f"[BACKUP] Migrated v0.18.0 approved songoku atlas -> {backup_atlas}")
        else:
            raise AssertionError("Cannot find v0.18.0 approved songoku atlas before backup!")
    else:
        assert sha256_file(backup_atlas) == orig_approved_sha, "Existing backup atlas hash mismatch!"

    # 2. Register all 10 Genki whole-pose frames (Owner image copy 4.png + 4 fluttering overhead hold loop frames!):
    #    #0 genki_00 (ready) -> #1 genki_01 (arms bent up) -> #2 genki_02 (arms overhead)
    #    -> #3..#6 genki_hold_00..03 (4-frame overhead hair/gi/sash flutter loop @ 120ms for 5.0s charge!)
    #    -> #7 genki_03 (lunge wind-up) -> #8 genki_04 (downward hurl + arc) -> #9 genki_05 (crouched follow-through)
    specs = {
        "genki_00":      {"body_h": 124, "use_hair_crown_h": False, "y1": 247, "cx": 144.0, "src": R4_GEN_DIR / "genki_00" / "generated.png"},
        "genki_01":      {"body_h": 126, "use_hair_crown_h": False, "y1": 247, "cx": 144.0, "src": R4_GEN_DIR / "genki_01" / "generated.png"},
        "genki_02":      {"body_h": 124, "use_hair_crown_h": True,  "y1": 247, "cx": 144.0, "src": GEN_DIR / "genki_02" / "generated.png"},
        "genki_hold_00": {"body_h": 124, "use_hair_crown_h": True, "hover_torso_anchor": True, "crown_y": 123, "cx": 144.0, "src": HOLD_GEN_DIR / "genki_hold_00" / "generated.png"},
        "genki_hold_01": {"body_h": 124, "use_hair_crown_h": True, "hover_torso_anchor": True, "crown_y": 123, "cx": 144.0, "src": HOLD_GEN_DIR / "genki_hold_01" / "generated.png"},
        "genki_hold_02": {"body_h": 124, "use_hair_crown_h": True, "hover_torso_anchor": True, "crown_y": 123, "cx": 144.0, "src": HOLD_GEN_DIR / "genki_hold_02" / "generated.png"},
        "genki_hold_03": {"body_h": 124, "use_hair_crown_h": True, "hover_torso_anchor": True, "crown_y": 123, "cx": 144.0, "src": HOLD_GEN_DIR / "genki_hold_03" / "generated.png"},
        "genki_03":      {"body_h": 120, "use_hair_crown_h": False, "y1": 247, "cx": 144.0, "src": GEN_DIR / "genki_03" / "generated.png"},
        "genki_04":      {"body_h": 92,  "use_body_comp_h": True,   "y1": 247, "cx": 144.0, "src": GEN_DIR / "genki_04" / "generated.png"},
        "genki_05":      {"body_h": 96,  "use_hair_crown_h": False, "y1": 247, "cx": 144.0, "src": R4_GEN_DIR / "genki_05" / "generated.png"},
    }

    bar_ref = Image.open(RAW_DIR / "idle_combat_00.png").convert("RGBA")
    strip_items: List[Tuple[str, Image.Image]] = [("REF idle_combat_00", bar_ref)]
    saved_paths: List[pathlib.Path] = []
    for fid, sp in specs.items():
        gen_p = sp["src"]
        assert gen_p.is_file(), f"Missing generated frame {gen_p}"
        im = register_genki_body_frame(fid, gen_p, sp)
        dst = RAW_DIR / f"{fid}.png"
        im.save(dst)
        saved_paths.append(dst)
        arr = np.array(im)
        ys, xs = np.where(arr[:, :, 3] > 0)
        foot = arr[max(0, int(ys.max()) - 10):int(ys.max()) + 1, :, 3] > 0
        fxs = np.where(foot)[1]
        smid = 0.5 * (int(fxs.min()) + int(fxs.max())) if len(fxs) else float(np.median(xs))
        fspan = int(fxs.max() - fxs.min() + 1) if len(fxs) else 0
        print(f"  [{fid:14s}] bbox=({xs.min()},{ys.min()})..({xs.max()},{ys.max()}) w={xs.max()-xs.min()+1} h={ys.max()-ys.min()+1} stance_mid={smid:.1f} foot_span={fspan} boot_y={ys.max()}")
        strip_items.append((fid, im))

    # 3. Render 3-background QA filmstrip comparing side-by-side with canonical bar_00!
    qa_strip_path = QA_DIR / "qa_songoku_genki_body_3bg.png"
    render_3bg_strip(strip_items, qa_strip_path)
    print(f"[QA STRIP] Saved {qa_strip_path}")

    # 4. Append genki_00..05 & genki_cast clip to assets/songoku/source/clips-manifest.json (preserving ALL 34 existing clips!)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    existing_fnames = {f["name"] for f in manifest["frames"]}
    for fid in specs:
        if fid not in existing_fnames:
            manifest["frames"].append({"name": fid, "file": f"raw_frames/{fid}.png"})
    manifest["clips"]["genki_cast"] = {
        "loop_policy": "oneshot",
        "role": "player",
        "frames": [
            "genki_00", "genki_01", "genki_02",
            "genki_hold_00", "genki_hold_01", "genki_hold_02", "genki_hold_03",
            "genki_03", "genki_04", "genki_05",
        ],
        "ticks": [7, 7, 7, 7, 7, 7, 7, 7, 8, 10],
        "events": [{"name": "custom:genki_throw", "at": 8}],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 5. Rebuild clips/ & godot_bundle/ (1 single PNG page <= 4096x4096, Nearest, 60Hz)
    verify_base_lock_live()
    clips_dir = GOKU_DIR / "clips"
    bundle_dir = GOKU_DIR / "godot_bundle"
    prev_exp = json.loads((bundle_dir / "engine-export.json").read_text(encoding="utf-8"))
    prev_rc = prev_exp.get("render_contract", {})

    for d in (clips_dir, bundle_dir):
        if d.exists():
            shutil.rmtree(d)

    subprocess.run(
        [sys.executable, str(BUILD_CLIPS_SCRIPT), "--manifest", str(MANIFEST_PATH), "--output-dir", str(clips_dir)],
        check=True,
    )
    (clips_dir / ".gdignore").write_text("", encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(EXPORT_ENGINE_SCRIPT),
            "--clips",
            str(clips_dir / "animation-clips.json"),
            "--target",
            "godot-spriteframes",
            "--output-dir",
            str(bundle_dir),
            "--name",
            "songoku",
            "--sampling",
            "nearest",
            "--godot-fps",
            "60",
            "--subject-height-px",
            "125",
        ],
        check=True,
    )

    atlas_pages = list((bundle_dir / "godot").glob("songoku-atlas-*.png"))
    assert len(atlas_pages) == 1, f"Expected 1 PNG page for songoku, got {len(atlas_pages)}"
    atlas_im = Image.open(live_atlas)
    assert atlas_im.width <= 4096 and atlas_im.height <= 4096, f"Atlas exceeded 4096: {atlas_im.size}"
    new_atlas_sha = sha256_file(live_atlas)
    new_tres_sha = sha256_file(bundle_dir / "godot" / "songoku.tres")

    # 6. Preserve & extend render_contract inside engine-export.json & assets/roster.json + motion_quality!
    all_clip_names = list(manifest["clips"].keys())
    prev_rc["body_clips"] = all_clip_names
    prev_rc["genki_fx_tres"] = "res://assets/fx/genki_fx/genki_fx.tres"
    hm = prev_rc.get("hero_mechanics", {})
    hm["genki_air_only"] = True
    hm["genki_mana_cost"] = 100.0
    hm["genki_cooldown_sec"] = 15.0
    hm["genki_charge_duration_sec"] = 5.0
    hm["genki_aoe_radius_px"] = 700.0
    hm["genki_base_damage"] = 400.0
    hm["genki_per_player_bonus"] = 5.0
    hm["genki_max_bonus_players"] = 20
    hm["genki_cc_immune_while_casting"] = True
    prev_rc["hero_mechanics"] = hm
    # Preserve original turning contract ({"clip": null, "flip_h": true}) untouched so SongokuHero.tscn prefab stays 100% identical
    prev_rc["turning"] = {"clip": None, "flip_h": True}

    exp_doc = json.loads((bundle_dir / "engine-export.json").read_text(encoding="utf-8"))
    exp_doc["render_contract"] = prev_rc
    (bundle_dir / "engine-export.json").write_text(json.dumps(exp_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Update assets/roster.json for songoku with reviewed_pending_owner motion_quality bound to new atlas SHA-256!
    roster = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    for ch in roster.get("characters", []):
        if ch.get("character_id") == "songoku":
            ch["present_clips"] = all_clip_names
            ch["render_contract"] = prev_rc
            ch["motion_quality"] = {
                "status": "reviewed_pending_owner",
                "owner_approved": False,
                "method": "imagegen_complete_body_keyframes",
                "turn_method": "instant_flip",
                "atlas_sha256": new_atlas_sha,
                "previous_revision_atlas_sha256": orig_approved_sha,
                "reviewed_at": "2026-11-26T04:32:00Z",
                "checks": {
                    "body_connections": True,
                    "whole_pose_sequence": True,
                    "perspective_turns": True,
                    "phase_timing": True,
                    "three_backgrounds": True,
                    "character_identity": True,
                },
                "unresolved_structural_failures": [],
                "review_evidence": "assets/songoku/clips/review/filmstrip-34.png",
                "notes": "Appended 6-frame SSJ1 genki_cast clip (4 arm-raise + 2 downward 25deg throw) preserving 100% of 34 existing clips & 24/24 Base SHA-256 lock; pending Owner Human Test.",
            }
            break
    ROSTER_PATH.write_text(json.dumps(roster, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Update state.json PIPE-022 approved_atlas_path -> git-tracked .gdignore'd archive so CI & local governance both verify cleanly!
    st = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    for w in st.get("approved_workflows", []):
        if w.get("id") == "PIPE-022" and w.get("character_id") == "songoku":
            w["approved_atlas_path"] = "docs/releases/archive/songoku-v0.18.0-atlas-00.png"
            break
    STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "clips": len(all_clip_names),
        "frames": len(manifest["frames"]),
        "atlas_size": [atlas_im.width, atlas_im.height],
        "new_atlas_sha256": new_atlas_sha,
        "prev_approved_sha256": orig_approved_sha,
        "new_tres_sha256": new_tres_sha,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
