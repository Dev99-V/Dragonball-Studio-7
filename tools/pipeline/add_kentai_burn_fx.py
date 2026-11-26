#!/usr/bin/env python3
"""Add 6-frame pixel-art `kentai_burn_fx` (green burning flames & dark forest-green smoke
referenced from `tapion/hit impact kentaima.png`) into `review/tapion_demo/fx_bundle/` (1 PNG page, 60Hz Nearest).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
GEN_DIR = ROOT / "work" / "polish_round2" / "gen"
QA_DIR = ROOT / "work" / "polish_round2" / "qa"
DEMO_DIR = ROOT / "review" / "tapion_demo"
FX_SRC_DIR = DEMO_DIR / "fx_source"
FX_RAW_DIR = FX_SRC_DIR / "raw_frames"
FX_MANIFEST_PATH = FX_SRC_DIR / "clips-manifest.json"
FX_CLIPS_DIR = DEMO_DIR / "fx_clips"
FX_BUNDLE_DIR = DEMO_DIR / "fx_bundle"
BUILD_CLIPS = ROOT / ".agents" / "skills" / "generate2dsprite" / "scripts" / "build_animation_clips.py"
EXPORT_ENGINE = ROOT / ".agents" / "skills" / "generate2dsprite" / "scripts" / "export_engine.py"

sys.path.insert(0, str(ROOT / "tools" / "pipeline"))
import repack_songoku_hero_demo as repacker  # noqa: E402

CANVAS_W = 288
CANVAS_H = 288


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def process_kentai_burn_frame(src: pathlib.Path) -> Image.Image:
    raw = Image.open(src).convert("RGBA")
    keyed, kmeta = repacker.key_magenta_2stage(raw)
    assert kmeta["opaque_key_px"] == 0, f"{src.name}: opaque_key_px={kmeta['opaque_key_px']}"
    vis = keyed[:, :, 3] > 0
    ys, xs = np.where(vis)
    crop = keyed[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    # Fit into crisp pixel-art 224x240 bounding area inside 288x288 canvas centered cleanly
    scale = min(224.0 / float(crop.shape[1]), 240.0 / float(crop.shape[0]))
    nw = max(16, int(round(crop.shape[1] * scale)))
    nh = max(16, int(round(crop.shape[0] * scale)))
    resized = Image.fromarray(crop, "RGBA").resize((nw, nh), Image.Resampling.NEAREST)
    arr = np.array(resized, dtype=np.uint8)
    mask = arr[:, :, 3] >= 128
    r, g, b = arr[:, :, 0].astype(np.int16), arr[:, :, 1].astype(np.int16), arr[:, :, 2].astype(np.int16)
    pink = mask & ((r - g) > 35) & ((b - g) > 35) & (g < 165)
    mask = mask & ~pink
    arr[~mask] = [0, 0, 0, 0]
    arr[mask, 3] = 255
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    px = (CANVAS_W - nw) // 2
    py = (CANVAS_H - nh) // 2
    canvas.paste(Image.fromarray(arr, "RGBA"), (px, py))
    return canvas


def render_3bg_strip(imgs: List[Tuple[str, Image.Image]], out_path: pathlib.Path) -> None:
    tw, th, hdr = 192, 192, 22
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
    strip_items: List[Tuple[str, Image.Image]] = []
    frame_ids: List[str] = []
    for i in range(6):
        fid = f"kentai_burn_{i:02d}"
        src = GEN_DIR / fid / "generated.png"
        assert src.is_file(), f"Missing {src}"
        im = process_kentai_burn_frame(src)
        im.save(FX_RAW_DIR / f"{fid}.png")
        strip_items.append((fid, im))
        frame_ids.append(fid)

    render_3bg_strip(strip_items, QA_DIR / "qa_kentai_burn_6f_3bg.png")

    manifest = json.loads(FX_MANIFEST_PATH.read_text(encoding="utf-8"))
    # Append/update raw frame definitions cleanly using Tapion FX manifest schema (`name` + `file`)
    existing_ids = {f["name"]: idx for idx, f in enumerate(manifest["frames"])}
    for fid in frame_ids:
        rec = {
            "name": fid,
            "file": f"raw_frames/{fid}.png",
        }
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

    # Sync review/review-roster.json & review/tapion_demo/godot_bundle/engine-export.json so 1:1 parity checks pass!
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
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
