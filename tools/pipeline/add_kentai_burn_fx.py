#!/usr/bin/env python3
"""Update `review/tapion_demo/fx_bundle/` (1 PNG page <= 4096x4096, 60Hz Nearest):
  1. Re-extract `maha_beam_air_00..02` directly from original high-res `tapion/chiêu mahasenko từ trên không trung.png`
     at exact parity scale (`0.62 * 0.70 * 0.865`) so air Mahasenko bolt matches ground `maha_beam_h_00..02` 1:1 in size!
  2. Replace `kentai_burn_fx` (6f) with refined crisp micro green flame+smoke sprites (`work/polish_round3/gen/kentai_micro_00..05`)
     using shared relative proportions inside 64x64 pixel-art frames for ~10-14px point-burns directly on the victim's body!
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
import shutil
import subprocess
import sys
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
GEN_DIR = ROOT / "work" / "polish_round3" / "gen"
QA_DIR = ROOT / "work" / "polish_round3" / "qa"
TAP_DIR = ROOT / "tapion"
DEMO_DIR = ROOT / "review" / "tapion_demo"
FX_SRC_DIR = DEMO_DIR / "fx_source"
FX_RAW_DIR = FX_SRC_DIR / "raw_frames"
FX_MANIFEST_PATH = FX_SRC_DIR / "clips-manifest.json"
FX_CLIPS_DIR = DEMO_DIR / "fx_clips"
FX_BUNDLE_DIR = DEMO_DIR / "fx_bundle"
BUILD_CLIPS = ROOT / ".agents" / "skills" / "generate2dsprite" / "scripts" / "build_animation_clips.py"
EXPORT_ENGINE = ROOT / ".agents" / "skills" / "generate2dsprite" / "scripts" / "export_engine.py"

sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import slice_tapion_phase2 as slp2  # noqa: E402
import sharpen_tapion_9fx_v2 as sh9  # noqa: E402

MICRO_CANVAS = 288
MAHA_AIR_PARITY_SCALE = 0.62 * 0.70 * 0.865


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def key_micro_magenta(src: pathlib.Path) -> np.ndarray:
    """Multi-component magenta keying preserving ALL crisp sparks, embers & smoke puffs."""
    arr = np.array(Image.open(src).convert("RGBA"), dtype=np.uint8)
    r, g, b = arr[:, :, 0].astype(np.int16), arr[:, :, 1].astype(np.int16), arr[:, :, 2].astype(np.int16)
    a = arr[:, :, 3] > 0
    is_mag = a & ((r - g) > 42) & ((b - g) > 42) & (g < 178)
    dil = ndimage.binary_dilation(is_mag, iterations=1) & ~is_mag
    fringe = dil & ((r - g) > 25) & ((b - g) > 25) & (g < 198)
    bg = is_mag | fringe
    out = arr.copy()
    out[bg] = [0, 0, 0, 0]
    fg = out[:, :, 3] >= 128
    out[~fg] = [0, 0, 0, 0]
    out[fg, 3] = 255
    return out


def split_3_vertical_clean(rgba: np.ndarray) -> List[Tuple[int, int, int, int, np.ndarray]]:
    """Split a 3-row vertical FX sheet cleanly into exactly 3 boxes (splitting widest span at min row density if 2 touch)."""
    vis = rgba[:, :, 3] > 0
    row_counts = vis.sum(axis=1)
    non_empty = row_counts > 0
    closed = ndimage.binary_closing(non_empty, structure=np.ones(4, dtype=bool))
    lbl, n = ndimage.label(closed)
    spans = []
    for cid in range(1, n + 1):
        ys = np.where((lbl == cid) & non_empty)[0]
        if len(ys) == 0:
            continue
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        if int(vis[y0:y1, :].sum()) >= 40:
            spans.append((y0, y1))
    while len(spans) > 3:
        best_i = min(range(len(spans) - 1), key=lambda i: spans[i + 1][0] - spans[i][1])
        spans[best_i:best_i + 2] = [(spans[best_i][0], spans[best_i + 1][1])]
    while len(spans) < 3:
        widest_i = max(range(len(spans)), key=lambda i: spans[i][1] - spans[i][0])
        sy0, sy1 = spans[widest_i]
        margin = max(20, (sy1 - sy0) // 5)
        cut = sy0 + margin + int(np.argmin(row_counts[sy0 + margin:sy1 - margin]))
        spans[widest_i:widest_i + 1] = [(sy0, cut), (cut, sy1)]
    boxes = []
    for (sy0, sy1) in spans:
        cm = np.zeros_like(vis)
        cm[sy0:sy1, :] = vis[sy0:sy1, :]
        ys, xs = np.where(cm)
        boxes.append((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1, cm))
    return boxes


def rebuild_maha_beam_air_parity() -> Tuple[List[Tuple[str, Image.Image]], float]:
    """Re-extract maha_beam_air_00..02 from original high-res `tapion/chiêu mahasenko từ trên không trung.png`
    at 0.865x parity with `maha_beam_h_00..02`!
    """
    src_sheet = TAP_DIR / "chiêu mahasenko từ trên không trung.png"
    assert src_sheet.is_file(), f"Missing {src_sheet}"
    arr_ma = np.array(Image.open(src_sheet).convert("RGBA"))
    arr_ma[:, 438:, :] = [27, 21, 35, 255]
    keyed_ma = slp2.key_standard_bg(arr_ma, tol=16.0, strip_red_pen=True)
    boxes_ma = split_3_vertical_clean(keyed_ma)
    assert len(boxes_ma) == 3, f"Expected 3 maha_beam_air slices from {src_sheet.name}, got {len(boxes_ma)}"

    tmp_dir = ROOT / "work" / "polish_round3" / "maha_air_slices"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    qa_pairs: List[Tuple[str, Image.Image]] = []
    pca_rad = 0.587
    for idx, b in enumerate(boxes_ma):
        fid = f"maha_beam_air_{idx:02d}"
        slice_p = tmp_dir / f"{fid}.png"
        slp2.save_crop(keyed_ma, b, slice_p)
        crisp = sh9.deblur_and_quantize_fx(
            slice_p,
            MAHA_AIR_PARITY_SCALE,
            sh9.PAL_YELLOW_BEAM,
            bg_trim_lum=60.0,
            unsharp_pct=220,
            unsharp_rad=1.8,
            add_dark_outline=True,
            outline_rgb=(112, 50, 12),
            erode_blur_rim=1,
        )
        reg = sh9.place_on_288(crisp, mode="center", ref_y=176, left_x=20)
        reg.save(FX_RAW_DIR / f"{fid}.png")
        # Measure PCA major/minor extents vs ground maha_beam_h!
        for label, im_chk in [(f"gnd_{idx:02d}", Image.open(FX_RAW_DIR / f"maha_beam_h_{idx:02d}.png").convert("RGBA")), (f"air_{idx:02d}", reg)]:
            a_c = np.array(im_chk)[:, :, 3] > 0
            ys, xs = np.where(a_c)
            pts = np.stack([xs - xs.mean(), ys - ys.mean()], axis=1).astype(np.float64)
            _, _, vt = np.linalg.svd(pts, full_matrices=False)
            proj0 = pts @ vt[0]
            proj1 = pts @ vt[1]
            maj = float(proj0.max() - proj0.min() + 1)
            mn = float(proj1.max() - proj1.min() + 1)
            if label == "air_00":
                vx, vy = vt[0]
                if vx < 0:
                    vx, vy = -vx, -vy
                pca_rad = math.atan2(vy, vx)
            print(f"  [MAHA PARITY {label}] major={maj:.1f}px minor={mn:.1f}px area={int(a_c.sum())}")
            qa_pairs.append((label, im_chk))
    print(f"  [PCA maha_beam_air_00] rad={pca_rad:.4f} deg={math.degrees(pca_rad):.2f}")
    return qa_pairs, pca_rad


def build_micro_kentai_burn_frames() -> Tuple[List[str], List[Tuple[str, Image.Image]]]:
    """Process 6 micro Kentai burn frames with SHARED relative pixel scale into crisp 64x64 canvases."""
    keyed_list: List[np.ndarray] = []
    # Measure raw sprite spans relative to their source image sizes so relative flame growth (00 small -> 01/02/03 full -> 04/05 fade) is preserved 100%!
    crops: List[Tuple[np.ndarray, float]] = []
    for i in range(6):
        src = GEN_DIR / f"kentai_micro_{i:02d}" / "generated.png"
        assert src.is_file(), f"Missing {src}"
        keyed = key_micro_magenta(src)
        vis = keyed[:, :, 3] > 0
        ys, xs = np.where(vis)
        crop = keyed[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        # Relative span against source image min side (invariant to 1024x1024 vs 1536x1024 aspect!)
        rel_h = float(crop.shape[0]) / float(min(keyed.shape[0], keyed.shape[1]))
        rel_w = float(crop.shape[1]) / float(min(keyed.shape[0], keyed.shape[1]))
        crops.append((crop, max(rel_h, rel_w)))
        keyed_list.append(keyed)

    # Peak frame (frames 1..3) fills ~224px of the 288x288 native canvas; smaller frames (00, 04, 05) preserve natural smaller scale!
    max_rel = max(c[1] for c in crops)
    frame_ids: List[str] = []
    strip_items: List[Tuple[str, Image.Image]] = []
    for i, (crop, rel_span) in enumerate(crops):
        fid = f"kentai_burn_{i:02d}"
        frac = rel_span / max(0.05, max_rel)
        target_span = max(92.0 if i in (0, 5) else 128.0, min(224.0, 224.0 * frac))
        sc = target_span / float(max(crop.shape[0], crop.shape[1]))
        nw = max(16, int(round(crop.shape[1] * sc)))
        nh = max(16, int(round(crop.shape[0] * sc)))
        resized = Image.fromarray(crop, "RGBA").resize((nw, nh), Image.Resampling.NEAREST)
        rarr = np.array(resized, dtype=np.uint8)
        m = rarr[:, :, 3] >= 128
        r, g, b = rarr[:, :, 0].astype(np.int16), rarr[:, :, 1].astype(np.int16), rarr[:, :, 2].astype(np.int16)
        pink = m & ((r - g) > 35) & ((b - g) > 35) & (g < 175)
        m = m & ~pink
        rarr[~m] = [0, 0, 0, 0]
        rarr[m, 3] = 255
        canvas = Image.new("RGBA", (MICRO_CANVAS, MICRO_CANVAS), (0, 0, 0, 0))
        px = (MICRO_CANVAS - nw) // 2
        # Bottom-weighted anchor so flame rises organically from the burn point on the victim's body!
        py = max(8, min(MICRO_CANVAS - nh - 8, 252 - nh)) if i <= 3 else (MICRO_CANVAS - nh) // 2
        canvas.paste(Image.fromarray(rarr, "RGBA"), (px, py))
        canvas.save(FX_RAW_DIR / f"{fid}.png")
        print(f"  [MICRO {fid}] placed={nw}x{nh} inside {MICRO_CANVAS}x{MICRO_CANVAS} fg_px={int(m.sum())}")
        frame_ids.append(fid)
        strip_items.append((fid, canvas))
    return frame_ids, strip_items


def render_3bg_strip(imgs: List[Tuple[str, Image.Image]], out_path: pathlib.Path, tw: int = 160, th: int = 160) -> None:
    hdr = 22
    sheet = Image.new("RGBA", (len(imgs) * tw, hdr + 3 * th), (24, 28, 36, 255))
    draw = ImageDraw.Draw(sheet)
    for i, (lbl, im) in enumerate(imgs):
        x0 = i * tw
        draw.rectangle([x0, 0, x0 + tw - 1, hdr - 1], fill=(18, 22, 30, 255))
        draw.text((x0 + 6, 4), lbl, fill=(255, 240, 128, 255))
        thumb = im.resize((tw, th), Image.Resampling.NEAREST)
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
            bg.alpha_composite(thumb)
            sheet.paste(bg, (x0, y0))
            draw.rectangle([x0, y0, x0 + tw - 1, y0 + th - 1], outline=(100, 118, 145, 255))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def main() -> int:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    maha_pairs, pca_rad = rebuild_maha_beam_air_parity()
    render_3bg_strip(maha_pairs, QA_DIR / "qa_maha_beam_ground_vs_air_3bg.png", tw=192, th=192)

    frame_ids, strip_items = build_micro_kentai_burn_frames()
    render_3bg_strip(strip_items, QA_DIR / "qa_kentai_micro_burn_6f_3bg.png", tw=144, th=144)

    manifest = json.loads(FX_MANIFEST_PATH.read_text(encoding="utf-8"))
    existing_ids = {f["name"]: idx for idx, f in enumerate(manifest["frames"])}
    for fid in frame_ids:
        rec = {"name": fid, "file": f"raw_frames/{fid}.png"}
        if fid in existing_ids:
            manifest["frames"][existing_ids[fid]] = rec
        else:
            manifest["frames"].append(rec)

    manifest["clips"]["kentai_burn_fx"] = {
        "loop_policy": "cycle",
        "role": "fx",
        "frames": frame_ids,
        "ticks": [5] * 6,
    }
    FX_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for d in (FX_CLIPS_DIR, FX_BUNDLE_DIR):
        if d.exists():
            shutil.rmtree(d)

    subprocess.run(
        [sys.executable, str(BUILD_CLIPS), "--manifest", str(FX_MANIFEST_PATH), "--output-dir", str(FX_CLIPS_DIR)],
        check=True,
    )
    (FX_CLIPS_DIR / ".gdignore").write_text("", encoding="utf-8")

    subprocess.run(
        [
            sys.executable, str(EXPORT_ENGINE),
            "--clips", str(FX_CLIPS_DIR / "animation-clips.json"),
            "--target", "godot-spriteframes",
            "--output-dir", str(FX_BUNDLE_DIR),
            "--name", "tapion_skills_fx",
            "--sampling", "nearest",
            "--godot-fps", "60",
            "--max-atlas-size", "4096",
            "--padding", "2",
            "--extrude", "1",
        ],
        check=True,
    )
    atlas_p = FX_BUNDLE_DIR / "godot" / "tapion_skills_fx-atlas-00.png"
    tres_p = FX_BUNDLE_DIR / "godot" / "tapion_skills_fx.tres"
    im_a = Image.open(atlas_p)
    assert max(im_a.size) <= 4096, f"Tapion FX atlas exceeded 4096: {im_a.size}"
    new_fx_sha = sha256_file(atlas_p)
    new_fx_tres_sha = sha256_file(tres_p)

    fx_clip_names = list(manifest["clips"].keys())
    rr_path = ROOT / "review" / "review-roster.json"
    if rr_path.is_file():
        rr = json.loads(rr_path.read_text(encoding="utf-8"))
        for ch in rr.get("characters", []):
            if ch.get("character_id") == "tapion_demo":
                ch["fx_atlas_sha256"] = new_fx_sha
                ch["fx_atlas_size_px"] = [im_a.width, im_a.height]
                ch["fx_clip_count"] = len(fx_clip_names)
                ch["effect_clips"] = fx_clip_names
                if isinstance(ch.get("render_contract"), dict):
                    ch["render_contract"]["effect_clips"] = fx_clip_names
                break
        rr_path.write_text(json.dumps(rr, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    body_exp_p = DEMO_DIR / "godot_bundle" / "engine-export.json"
    if body_exp_p.is_file():
        bexp = json.loads(body_exp_p.read_text(encoding="utf-8"))
        if isinstance(bexp.get("render_contract"), dict):
            bexp["render_contract"]["effect_clips"] = fx_clip_names
            body_exp_p.write_text(json.dumps(bexp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "clips": len(manifest["clips"]),
        "frames": len(manifest["frames"]),
        "atlas_size": [im_a.width, im_a.height],
        "atlas_sha256": new_fx_sha,
        "tres_sha256": new_fx_tres_sha,
        "maha_beam_air_pca_rad": round(pca_rad, 4),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
