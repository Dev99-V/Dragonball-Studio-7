#!/usr/bin/env python3
"""Stage T-rex turn-v1 clips + Godot/Aseprite bundle and render visual motion reviews."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[4]
TURN_DIR = ROOT / "work/characters/t_rex/turn-v1"
SNAP_DIR = TURN_DIR / "snapshot-before"
STAGE_DIR = TURN_DIR / "stage"
RAW_DIR = STAGE_DIR / "raw_frames"
CLIPS_OUT = STAGE_DIR / "clips"
BUNDLE_OUT = STAGE_DIR / "godot_bundle"
REVIEW_DIR = TURN_DIR / "review"

BUILD_CLIPS_PY = ROOT / ".agents/skills/generate2dsprite/scripts/build_animation_clips.py"
EXPORT_ENGINE_PY = ROOT / ".agents/skills/generate2dsprite/scripts/export_engine.py"

TURN_TICKS = [6, 3, 3, 3, 6]


def verify_baseline_frames() -> dict[str, dict]:
    manifest = json.loads((SNAP_DIR / "baseline-manifest.json").read_text(encoding="utf-8"))
    frames_meta = manifest["trex_frames"]
    assert len(frames_meta) == 73
    expected = {}
    for item in frames_meta:
        rel = item["file"]  # frames/frame-00.png
        p = ROOT / "assets/t_rex/clips" / rel
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        if got != item["file_sha256"]:
            raise RuntimeError(f"Baseline hash mismatch for {rel}: got {got} != {item['file_sha256']}")
        expected[rel] = item
    return expected


def prepare_stage_manifest() -> Path:
    if RAW_DIR.exists():
        shutil.rmtree(RAW_DIR)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    orig_sm = json.loads((ROOT / "assets/t_rex/clips/source-manifest.json").read_text(encoding="utf-8"))
    # Keep script idempotent across re-runs by stripping any prior staged turn entries first
    orig_sm["frames"] = [f for f in orig_sm["frames"] if not f["name"].startswith("turn_")]
    orig_sm["clips"].pop("turn", None)
    frames_list = orig_sm["frames"]
    assert len(frames_list) == 73
    for i, entry in enumerate(frames_list):
        src = ROOT / "assets/t_rex/clips/frames" / f"frame-{i:02d}.png"
        dst_rel = entry["file"]  # e.g. raw_frames/idle_00.png
        dst = STAGE_DIR / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # Append turn_00..04
    turn_names = [f"turn_0{i}" for i in range(5)]
    for tname in turn_names:
        src = TURN_DIR / "source" / f"{tname}.png"
        shutil.copy2(src, RAW_DIR / f"{tname}.png")
        frames_list.append({"name": tname, "file": f"raw_frames/{tname}.png"})

    orig_sm["clips"]["turn"] = {
        "role": "player",
        "frames": turn_names,
        "ticks": TURN_TICKS,
        "loop_policy": "oneshot",
        "keys": {
            "wind_start": 0,
            "wind_peak": 2,
            "strike": 2,
            "recover": 3,
            "end": 4,
        },
        "events": [
            {"at": 0, "name": "in"},
            {"at": 4, "name": "end"},
        ],
    }

    manifest_path = STAGE_DIR / "clips_manifest.json"
    manifest_path.write_text(json.dumps(orig_sm, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest_path


def run_pipeline(manifest_path: Path) -> None:
    if CLIPS_OUT.exists():
        shutil.rmtree(CLIPS_OUT)
    if BUNDLE_OUT.exists():
        shutil.rmtree(BUNDLE_OUT)

    subprocess.run(
        [
            "python3", str(BUILD_CLIPS_PY),
            "--manifest", str(manifest_path),
            "--output-dir", str(CLIPS_OUT),
            "--preview-background", "all",
            "--strict",
        ],
        check=True,
    )
    subprocess.run(
        [
            "python3", str(EXPORT_ENGINE_PY),
            "--clips", str(CLIPS_OUT / "animation-clips.json"),
            "--target", "all",
            "--output-dir", str(BUNDLE_OUT),
            "--name", "t_rex",
            "--sampling", "nearest",
            "--godot-fps", "auto",
        ],
        check=True,
    )


def inject_render_contract() -> None:
    orig_export = json.loads((SNAP_DIR / "engine-export.json").read_text(encoding="utf-8"))
    rc = json.loads(json.dumps(orig_export["render_contract"]))
    body_clips = list(rc["body_clips"])
    if "turn" not in body_clips:
        run_idx = body_clips.index("run") if "run" in body_clips else len(body_clips) - 1
        body_clips.insert(run_idx + 1, "turn")
    rc["body_clips"] = body_clips
    rc["locomotion"]["patrol"] = {
        "enabled": True,
        "clip": "walk",
        "speed_px_per_second": 55,
        "min_x": 80,
        "max_x": 880,
        "endpoint_turn_clip": "turn",
    }
    rc["turning"] = {
        "clip": "turn",
        "from": "right",
        "to": "left",
        "duration_ms": 350,
        "duration_ticks": sum(TURN_TICKS),
        "ticks": TURN_TICKS,
        "method": "complete_perspective_poses",
        "mirror_sequence_for_reverse": True,
        "whole_body_rotation": True,
    }

    export_path = BUNDLE_OUT / "engine-export.json"
    new_export = json.loads(export_path.read_text(encoding="utf-8"))
    new_export["render_contract"] = rc
    export_path.write_text(json.dumps(new_export, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def render_transition_webps() -> None:
    """Render walk->turn->walk and run->turn->run WebPs (R2L and L2R) across 3 backgrounds."""
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    clips_meta = json.loads((CLIPS_OUT / "animation-clips.json").read_text(encoding="utf-8"))
    all_frames = [
        Image.open(CLIPS_OUT / "frames" / f"frame-{i:02d}.png").convert("RGBA")
        for i in range(len(clips_meta["frames"]))
    ]
    turn_clip = clips_meta["clips"]["turn"]
    turn_imgs = [all_frames[idx] for idx in turn_clip["frames"]]
    turn_ms = turn_clip["duration_ms"]

    def make_bg(w: int, h: int, kind: str) -> Image.Image:
        if kind == "light":
            return Image.new("RGBA", (w, h), (242, 244, 248, 255))
        if kind == "dark":
            return Image.new("RGBA", (w, h), (22, 26, 36, 255))
        arr = np.zeros((h, w, 4), dtype=np.uint8)
        yy, xx = np.indices((h, w))
        c = ((yy // 12 + xx // 12) % 2) == 0
        arr[c] = [196, 202, 210, 255]
        arr[~c] = [148, 154, 166, 255]
        return Image.fromarray(arr, mode="RGBA")

    def mirror_anchor(im: Image.Image, ax: int = 176) -> Image.Image:
        # Mirror cleanly around x = anchor_x so Godot scale.x = -1 matches 1:1
        w, h = im.size
        src = im.crop((0, 0, min(w, ax * 2), h))
        flipped = src.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        out.paste(flipped, (0, 0))
        return out

    # Also build turn-test.png filmstrip + copy filmstrip-turn.png from clips/review
    for bg_name in ["light", "dark", "checker"]:
        for clip_name in ["walk", "run"]:
            c_info = clips_meta["clips"][clip_name]
            c_imgs = [all_frames[i] for i in c_info["frames"]]
            c_ms = c_info["duration_ms"]
            for direction in ["r2l", "l2r"]:
                seq_imgs = []
                seq_ms = []
                # Right/Left arrival -> Turn -> opposite departure
                if direction == "r2l":
                    # stride right -> R->L turn -> mirrored stride left
                    for im, d in zip(c_imgs, c_ms):
                        seq_imgs.append(im)
                        seq_ms.append(d)
                    for im, d in zip(turn_imgs, turn_ms):
                        seq_imgs.append(im)
                        seq_ms.append(d)
                    for im, d in zip(c_imgs, c_ms):
                        seq_imgs.append(mirror_anchor(im))
                        seq_ms.append(d)
                else:
                    # mirrored stride left -> reverse turn -> stride right
                    for im, d in zip(c_imgs, c_ms):
                        seq_imgs.append(mirror_anchor(im))
                        seq_ms.append(d)
                    for im, d in zip(reversed(turn_imgs), reversed(turn_ms)):
                        seq_imgs.append(im)
                        seq_ms.append(d)
                    for im, d in zip(c_imgs, c_ms):
                        seq_imgs.append(im)
                        seq_ms.append(d)

                w, h = 280, 176
                bg = make_bg(w, h, bg_name)
                rendered = []
                for im in seq_imgs:
                    canvas = bg.copy()
                    cropped = im.crop((46, 76, 326, 252))
                    canvas.alpha_composite(cropped, (0, 0))
                    rendered.append(canvas)
                out_p = REVIEW_DIR / f"{clip_name}-turn-{clip_name}-{direction}-{bg_name}.webp"
                rendered[0].save(
                    out_p,
                    save_all=True,
                    append_images=rendered[1:],
                    duration=seq_ms,
                    loop=0,
                    lossless=True,
                )

    # Copy filmstrip for turn clip if generated
    rev_files = sorted((CLIPS_OUT / "review").glob("filmstrip-*.png"))
    if rev_files:
        shutil.copy2(rev_files[-1], REVIEW_DIR / "filmstrip-turn.png")

    # Also build turn-test.png showing R->L (top), L->R reverse (mid), with frame index & tick markers
    cols = 5
    tw, th = 220, 160
    sheet = Image.new("RGBA", (tw * cols, th * 2), (242, 244, 248, 255))
    draw = ImageDraw.Draw(sheet)
    for row_idx, seq in enumerate([
        list(zip(range(5), turn_imgs, turn_ms)),
        list(reversed(list(zip(range(5), turn_imgs, turn_ms)))),
    ]):
        bg = make_bg(tw * cols, th, "light" if row_idx == 0 else "checker")
        sheet.paste(bg, (0, row_idx * th))
        for col_idx, (f_i, im, ms) in enumerate(seq):
            sub = im.crop((66, 80, 286, 240))
            sheet.alpha_composite(sub, (col_idx * tw, row_idx * th))
            dir_lbl = "R->L" if row_idx == 0 else "L->R"
            draw.text((col_idx * tw + 6, row_idx * th + 6), f"{dir_lbl} turn_{f_i} ({ms}ms)", fill=(20, 20, 20, 255))
    sheet.save(REVIEW_DIR / "turn-test.png")


def check_frame_preservation(expected_hashes: dict[str, dict]) -> dict:
    same_bytes = 0
    same_rgba = 0
    for i in range(73):
        rel = f"frames/frame-{i:02d}.png"
        item = expected_hashes[rel]
        new_p = CLIPS_OUT / rel
        if hashlib.sha256(new_p.read_bytes()).hexdigest() == item["file_sha256"]:
            same_bytes += 1
        a2 = np.array(Image.open(new_p).convert("RGBA"))
        if hashlib.sha256(a2.tobytes()).hexdigest() == item["rgba_sha256"]:
            same_rgba += 1
    return {"non_turn_same_sha256": same_bytes, "non_turn_same_rgba": same_rgba, "total": 73}


def main() -> None:
    expected = verify_baseline_frames()
    manifest_path = prepare_stage_manifest()
    run_pipeline(manifest_path)
    inject_render_contract()
    render_transition_webps()
    pres = check_frame_preservation(expected)
    print("Preservation:", json.dumps(pres, indent=2))


if __name__ == "__main__":
    main()
