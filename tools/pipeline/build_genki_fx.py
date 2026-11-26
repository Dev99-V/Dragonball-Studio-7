#!/usr/bin/env python3
"""
DR7-Studio — Extract & Pack 16 Genki (Spirit Bomb) FX frames from /workspaces/Dragonball-Studio-7/Genki/1..16.png.
- Exact Sheet Fidelity (Zero AI Redraw): 2-stage pocket-first keying on exact slate-purple RGB(101,101,129).
- 100% hard binary alpha (alpha_hardness_pct = 100.0%, enclosed_key_pockets = 0, opaque_key_px = 0).
- Dedicated 1-page PNG atlas <= 4096x4096 (384x384 cells -> 1554x1554) at assets/fx/genki_fx/ (Nearest, 60Hz).
  Does NOT mutate existing assets/fx/songoku_skills_fx/ (zero regression!).
- Produces 3-background QA filmstrips (light / dark / checkerboard) for visual verification.
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
SRC_DIR = ROOT / "Genki"
WORK_DIR = ROOT / "work" / "characters" / "songoku_genki" / "fx_extract"
QA_DIR = ROOT / "work" / "characters" / "songoku_genki" / "qa"
OUT_FX_DIR = ROOT / "assets" / "fx" / "genki_fx"
BUILD_CLIPS_SCRIPT = ROOT / ".agents" / "skills" / "generate2dsprite" / "scripts" / "build_animation_clips.py"
EXPORT_ENGINE_SCRIPT = ROOT / ".agents" / "skills" / "generate2dsprite" / "scripts" / "export_engine.py"

CANVAS_W = 384
CANVAS_H = 384
ORB_CENTER = (192, 192)
EXPLODE_GROUND_Y = 352

KEY_RGB = np.array([101, 101, 129], dtype=np.int16)


def key_genki_slate_2stage(im: Image.Image) -> Tuple[Image.Image, Dict[str, int]]:
    """2-stage pocket-first keying on uniform slate-purple RGB(101,101,129) preserving 100% of blue/cyan/white/black/fire FX."""
    arr = np.array(im.convert("RGBA"), dtype=np.uint8)
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    a = arr[:, :, 3]

    dist_inf = np.maximum(np.maximum(np.abs(r - KEY_RGB[0]), np.abs(g - KEY_RGB[1])), np.abs(b - KEY_RGB[2]))
    # Stage 1: Exact key color + transparent pixels (cleans both exterior AND all enclosed pockets!)
    is_key = (a < 128) | (dist_inf <= 22)
    fg = ~is_key

    # Stage 2: 1px outer ring slate-purple spill cleanup (blended fringe only)
    for _ in range(2):
        border = fg & ndimage.binary_dilation(~fg, iterations=1)
        slate_fringe = border & (dist_inf <= 38) & (np.abs(r - g) <= 20) & ((b - r) >= 8) & ((b - r) <= 46)
        if not slate_fringe.any():
            break
        fg = fg & ~slate_fringe

    # Remove tiny 1-2px isolated stray speckles far from foreground components
    labeled, n_comp = ndimage.label(fg, structure=np.ones((3, 3), dtype=np.int32))
    if n_comp > 1:
        sizes = ndimage.sum(fg, labeled, range(1, n_comp + 1))
        for lbl_i, sz in enumerate(sizes, start=1):
            if sz <= 2:
                fg[labeled == lbl_i] = False

    out = arr.copy()
    out[~fg] = [0, 0, 0, 0]
    out[fg, 3] = 255

    opaque_key_px = int((fg & (dist_inf <= 22)).sum())
    semi_alpha_px = int(((out[:, :, 3] > 0) & (out[:, :, 3] < 255)).sum())
    return Image.fromarray(out, "RGBA"), {
        "fg_px": int(fg.sum()),
        "opaque_key_px": opaque_key_px,
        "semi_alpha_px": semi_alpha_px,
    }


def bbox_of_rgba(im: Image.Image) -> Tuple[int, int, int, int]:
    arr = np.array(im)
    ys, xs = np.where(arr[:, :, 3] > 0)
    if len(xs) == 0:
        return (0, 0, 1, 1)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def place_scaled_nearest(cropped: Image.Image, scale: float, anchor_mode: str) -> Image.Image:
    nw = max(1, int(round(cropped.width * scale)))
    nh = max(1, int(round(cropped.height * scale)))
    if nw > CANVAS_W - 8 or nh > CANVAS_H - 8:
        clamp_sc = min((CANVAS_W - 8) / cropped.width, (CANVAS_H - 8) / cropped.height)
        nw = max(1, int(round(cropped.width * clamp_sc)))
        nh = max(1, int(round(cropped.height * clamp_sc)))
    scaled = cropped.resize((nw, nh), Image.Resampling.NEAREST)
    # Enforce binary alpha after NEAREST
    arr = np.array(scaled)
    arr[:, :, 3] = np.where(arr[:, :, 3] >= 128, 255, 0).astype(np.uint8)
    arr[arr[:, :, 3] == 0] = [0, 0, 0, 0]
    scaled = Image.fromarray(arr, "RGBA")

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    if anchor_mode == "center":
        px = ORB_CENTER[0] - nw // 2
        py = ORB_CENTER[1] - nh // 2
    else:
        px = ORB_CENTER[0] - nw // 2
        py = EXPLODE_GROUND_Y - nh
    px = max(2, min(CANVAS_W - nw - 2, px))
    py = max(2, min(CANVAS_H - nh - 2, py))
    canvas.paste(scaled, (px, py), scaled)
    return canvas


def render_3bg_strip(frames: List[Tuple[str, Image.Image]], out_path: pathlib.Path, thumb: int = 192) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = len(frames)
    hdr = 22
    sheet = Image.new("RGBA", (n * thumb, hdr + 3 * thumb), (24, 28, 36, 255))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, im) in enumerate(frames):
        x0 = idx * thumb
        draw.rectangle([x0, 0, x0 + thumb - 1, hdr - 1], fill=(18, 22, 30, 255))
        draw.text((x0 + 6, 4), label, fill=(255, 240, 128, 255))
        small = im.resize((thumb, thumb), Image.Resampling.NEAREST)
        for row_i, mode in enumerate(("light", "dark", "checker")):
            y0 = hdr + row_i * thumb
            if mode == "light":
                bg = Image.new("RGBA", (thumb, thumb), (236, 240, 246, 255))
            elif mode == "dark":
                bg = Image.new("RGBA", (thumb, thumb), (20, 24, 34, 255))
            else:
                bg = Image.new("RGBA", (thumb, thumb), (52, 58, 72, 255))
                bd = ImageDraw.Draw(bg)
                for yy in range(0, thumb, 16):
                    for xx in range(0, thumb, 16):
                        if ((xx // 16) + (yy // 16)) % 2 == 0:
                            bd.rectangle([xx, yy, xx + 15, yy + 15], fill=(74, 82, 98, 255))
            bg.alpha_composite(small, (0, 0))
            sheet.paste(bg, (x0, y0))
            draw.rectangle([x0, y0, x0 + thumb - 1, y0 + thumb - 1], outline=(100, 118, 145, 255))
    sheet.save(out_path)


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    frames_dir = WORK_DIR / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    # 1. Key all 16 source images & measure tight foreground bboxes
    keyed: Dict[int, Image.Image] = {}
    crops: Dict[int, Image.Image] = {}
    stats: Dict[int, Dict[str, object]] = {}
    for i in range(1, 17):
        src = SRC_DIR / f"{i}.png"
        if not src.is_file():
            raise FileNotFoundError(f"Missing Genki source frame: {src}")
        raw_im = Image.open(src).convert("RGBA")
        kim, st = key_genki_slate_2stage(raw_im)
        bb = bbox_of_rgba(kim)
        crop = kim.crop(bb)
        keyed[i] = kim
        crops[i] = crop
        stats[i] = {**st, "src_size": list(raw_im.size), "crop_size": list(crop.size)}
        assert st["opaque_key_px"] == 0, f"Genki/{i}.png still has opaque_key_px={st['opaque_key_px']}"
        assert st["semi_alpha_px"] == 0, f"Genki/{i}.png has semi_alpha_px={st['semi_alpha_px']}"

    # 2. Choose single consistent scale per group so growth (1..8) and ground blast (9..16) preserve exact native proportions!
    max_orb_dim = max(max(crops[i].width, crops[i].height) for i in range(1, 9))
    orb_scale = 356.0 / float(max_orb_dim)  # ~0.55x -> #8 fits cleanly at ~356px inside 384x384!

    max_exp_w = max(crops[i].width for i in range(9, 17))
    max_exp_h = max(crops[i].height for i in range(9, 17))
    exp_scale = min(364.0 / float(max_exp_w), 336.0 / float(max_exp_h))  # ~0.53x -> sits solidly on ground_y=352!

    registered: Dict[int, Image.Image] = {}
    for i in range(1, 9):
        reg = place_scaled_nearest(crops[i], orb_scale, "center")
        reg.save(frames_dir / f"genki_orb_{i:02d}.png")
        registered[i] = reg
    for i in range(9, 17):
        reg = place_scaled_nearest(crops[i], exp_scale, "ground")
        reg.save(frames_dir / f"genki_exp_{i:02d}.png")
        registered[i] = reg

    # 3. Render 3-bg QA filmstrips for visual inspection
    render_3bg_strip([(f"#{i} orb ({crops[i].width}x{crops[i].height})", registered[i]) for i in range(1, 9)], QA_DIR / "qa_genki_fx_charge_3bg.png")
    render_3bg_strip([(f"#{i} exp ({crops[i].width}x{crops[i].height})", registered[i]) for i in range(9, 17)], QA_DIR / "qa_genki_fx_explode_3bg.png")

    # 4. Build clips manifest & pack 1-page atlas via generate2dsprite scripts
    manifest = {
        "schema": "generate2dsprite.animation_clips.v2",
        "art_source": "host_image",
        "pixel_art": True,
        "sampling": "nearest",
        "body_height_px": 125,
        "anchor_px": [ORB_CENTER[0], ORB_CENTER[1]],
        "frames": (
            [{"name": f"genki_orb_{i:02d}", "file": f"frames/genki_orb_{i:02d}.png"} for i in range(1, 9)]
            + [{"name": f"genki_exp_{i:02d}", "file": f"frames/genki_exp_{i:02d}.png"} for i in range(9, 17)]
        ),
        "clips": {
            "genki_charge_fx": {
                "loop_policy": "oneshot",
                "role": "fx",
                "frames": [f"genki_orb_{i:02d}" for i in range(1, 9)],
                "duration_ms": [120, 120, 120, 120, 120, 100, 100, 100],
            },
            "genki_orb_loop_fx": {
                "loop_policy": "cycle",
                "role": "fx",
                "frames": ["genki_orb_06", "genki_orb_07", "genki_orb_08"],
                "duration_ms": [80, 80, 80],
            },
            "genki_explode_fx": {
                "loop_policy": "oneshot",
                "role": "fx",
                "frames": [f"genki_exp_{i:02d}" for i in range(9, 17)],
                "duration_ms": [70, 75, 80, 85, 95, 105, 115, 125],
            },
        },
    }
    manifest_path = WORK_DIR / "clips-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    clips_out = WORK_DIR / "clips_out"
    bundle_out = WORK_DIR / "bundle_out"
    for d in (clips_out, bundle_out):
        if d.exists():
            shutil.rmtree(d)

    subprocess.run(
        [sys.executable, str(BUILD_CLIPS_SCRIPT), "--manifest", str(manifest_path), "--output-dir", str(clips_out)],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(EXPORT_ENGINE_SCRIPT),
            "--clips",
            str(clips_out / "animation-clips.json"),
            "--output-dir",
            str(bundle_out),
            "--target",
            "godot-spriteframes",
            "--name",
            "genki_fx",
            "--sampling",
            "nearest",
            "--godot-fps",
            "60",
            "--subject-height-px",
            "125",
        ],
        check=True,
    )

    atlas_src = bundle_out / "godot" / "genki_fx-atlas-00.png"
    tres_src = bundle_out / "godot" / "genki_fx.tres"
    export_src = bundle_out / "engine-export.json"
    assert atlas_src.is_file() and tres_src.is_file()
    assert not (bundle_out / "godot" / "genki_fx-atlas-01.png").exists(), "genki_fx must fit on 1 PNG page!"

    aim = Image.open(atlas_src)
    assert aim.width <= 4096 and aim.height <= 4096

    OUT_FX_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(atlas_src, OUT_FX_DIR / "genki_fx-atlas-00.png")
    shutil.copy2(tres_src, OUT_FX_DIR / "genki_fx.tres")
    # Save metadata as fx-export.json (matching assets/fx/songoku_skills_fx/fx-export.json — NOT engine-export.json!)
    exp_doc = json.loads(export_src.read_text(encoding="utf-8"))
    exp_doc["orb_scale"] = round(orb_scale, 4)
    exp_doc["explode_scale"] = round(exp_scale, 4)
    exp_doc["explode_ground_y_px"] = EXPLODE_GROUND_Y
    (OUT_FX_DIR / "fx-export.json").write_text(json.dumps(exp_doc, indent=2) + "\n", encoding="utf-8")

    summary = {
        "status": "ok",
        "atlas_size": [aim.width, aim.height],
        "atlas_sha256": sha256_file(OUT_FX_DIR / "genki_fx-atlas-00.png"),
        "tres_sha256": sha256_file(OUT_FX_DIR / "genki_fx.tres"),
        "orb_scale": round(orb_scale, 4),
        "explode_scale": round(exp_scale, 4),
        "frames": stats,
    }
    (QA_DIR / "genki_fx_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "frames"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
