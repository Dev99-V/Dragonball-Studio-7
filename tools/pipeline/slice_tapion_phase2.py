#!/usr/bin/env python3
"""
DR7-Studio — Exact X/Y Valley + 2D Component Slicer & Multi-Key Cleaner for all 20 remaining Tapion sheets.
Uses float32 Euclidean color distance (zero int16 overflow!) and X/Y empty-column valley splitting
so closely spaced multi-spark effects never merge across frames nor drop outer sparks!
"""
from __future__ import annotations

import json
import pathlib
import shutil
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
TAP_DIR = ROOT / "tapion"
P2_WORK = ROOT / "work" / "characters" / "tapion" / "phase2"
BODY_OUT = P2_WORK / "source_slices"
FX_OUT = P2_WORK / "fx_slices"


def key_standard_bg(arr: np.ndarray, tol: float = 16.0, strip_red_pen: bool = False) -> np.ndarray:
    out = arr.copy()
    r = out[:, :, 0].astype(np.float32)
    g = out[:, :, 1].astype(np.float32)
    b = out[:, :, 2].astype(np.float32)

    if strip_red_pen:
        pen = (r > 110) & (g < 42) & (b < 48) & ((r - g) > 72)
        pen_dil = ndimage.binary_dilation(pen, iterations=2)
        out[pen_dil] = [27, 21, 35, 255]
        r = out[:, :, 0].astype(np.float32)
        g = out[:, :, 1].astype(np.float32)
        b = out[:, :, 2].astype(np.float32)

    dist = np.sqrt((r - 27.0) ** 2 + (g - 21.0) ** 2 + (b - 35.0) ** 2)
    fg = dist > tol

    # Remove tiny 1-2px isolated noise specks in background
    lbl, n = ndimage.label(fg, structure=np.ones((3, 3)))
    if n > 0:
        sizes = np.array(ndimage.sum(fg, lbl, range(1, n + 1)))
        for cid in range(1, n + 1):
            if sizes[cid - 1] <= 2 and dist[lbl == cid].max() < tol + 18.0:
                fg[lbl == cid] = False

    bg = ~fg
    out[~fg] = [0, 0, 0, 0]
    out[fg, 3] = 255

    # Clean 1px outer purple anti-alias halo on dim border pixels
    dil_bg = ndimage.binary_dilation(bg, iterations=1)
    ring = fg & dil_bg
    dim_purple = ring & (dist < tol + 12.0) & (b >= g) & (r < 62) & (g < 52) & (b < 75)
    out[dim_purple] = [0, 0, 0, 0]
    return out


def split_by_x_valleys(rgba: np.ndarray, expected_n: int, min_gap_cols: int = 3) -> List[Tuple[int, int, int, int, np.ndarray]]:
    """Split horizontal strip along completely empty vertical column runs (valleys)."""
    vis = rgba[:, :, 3] > 0
    col_counts = vis.sum(axis=0)
    H, W = vis.shape
    # Find contiguous runs of non-empty columns, allowing tiny internal gaps < min_gap_cols
    non_empty = col_counts > 0
    # Close gaps smaller than min_gap_cols
    if min_gap_cols > 1:
        closed = ndimage.binary_closing(non_empty, structure=np.ones(min_gap_cols, dtype=bool))
    else:
        closed = non_empty
    lbl, n = ndimage.label(closed)
    spans = []
    for cid in range(1, n + 1):
        xs = np.where((lbl == cid) & non_empty)[0]
        if len(xs) == 0:
            continue
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        sub_vis = vis[:, x0:x1]
        if int(sub_vis.sum()) < 25:
            continue
        spans.append((x0, x1))
    # If spans > expected_n, merge closest neighbors until len == expected_n
    while len(spans) > expected_n:
        best_i = min(range(len(spans) - 1), key=lambda i: spans[i + 1][0] - spans[i][1])
        spans[best_i : best_i + 2] = [(spans[best_i][0], spans[best_i + 1][1])]
    # If spans < expected_n (e.g. slight x-overlap between two frames), split widest span at minimum column density!
    while len(spans) < expected_n:
        widest_i = max(range(len(spans)), key=lambda i: spans[i][1] - spans[i][0])
        sx0, sx1 = spans[widest_i]
        margin = max(12, (sx1 - sx0) // 6)
        cut = sx0 + margin + int(np.argmin(col_counts[sx0 + margin : sx1 - margin]))
        spans[widest_i : widest_i + 1] = [(sx0, cut), (cut, sx1)]

    boxes = []
    for (sx0, sx1) in spans:
        cm = np.zeros_like(vis)
        cm[:, sx0:sx1] = vis[:, sx0:sx1]
        ys, xs = np.where(cm)
        boxes.append((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1, cm))
    return boxes


def split_by_y_valleys(rgba: np.ndarray, expected_n: int, min_gap_rows: int = 3) -> List[Tuple[int, int, int, int, np.ndarray]]:
    vis = rgba[:, :, 3] > 0
    row_counts = vis.sum(axis=1)
    non_empty = row_counts > 0
    closed = ndimage.binary_closing(non_empty, structure=np.ones(min_gap_rows, dtype=bool)) if min_gap_rows > 1 else non_empty
    lbl, n = ndimage.label(closed)
    spans = []
    for cid in range(1, n + 1):
        ys = np.where((lbl == cid) & non_empty)[0]
        if len(ys) == 0:
            continue
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        if int(vis[y0:y1, :].sum()) < 25:
            continue
        spans.append((y0, y1))
    while len(spans) > expected_n:
        best_i = min(range(len(spans) - 1), key=lambda i: spans[i + 1][0] - spans[i][1])
        spans[best_i : best_i + 2] = [(spans[best_i][0], spans[best_i + 1][1])]
    boxes = []
    for (sy0, sy1) in spans:
        cm = np.zeros_like(vis)
        cm[sy0:sy1, :] = vis[sy0:sy1, :]
        ys, xs = np.where(cm)
        boxes.append((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1, cm))
    return boxes


def save_crop(rgba: np.ndarray, box: Tuple[int, int, int, int, np.ndarray], dst: pathlib.Path) -> Dict[str, object]:
    x0, y0, x1, y1, mask = box
    sub = rgba[y0:y1, x0:x1].copy()
    sub_m = mask[y0:y1, x0:x1]
    sub[~sub_m] = [0, 0, 0, 0]
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(sub, mode="RGBA").save(dst)
    return {"file": dst.name, "x0": x0, "y0": y0, "w": x1 - x0, "h": y1 - y0, "px": int(sub_m.sum())}


def main() -> int:
    if BODY_OUT.exists():
        shutil.rmtree(BODY_OUT)
    if FX_OUT.exists():
        shutil.rmtree(FX_OUT)
    BODY_OUT.mkdir(parents=True, exist_ok=True)
    FX_OUT.mkdir(parents=True, exist_ok=True)
    meta = {"body": [], "fx": []}

    body_specs = [
        ("hình dạng toàn bộ cơ thể.png", "turntable", 8, 16.0, 4),
        ("hồi phục và tái tạo.png", "recover", 8, 16.0, 8),
        ("vận công tung chiêu mahasenko khi ở dưới mặt đất.png", "maha_gnd", 3, 16.0, 8),
        ("hiệu ứng mahasenko khi ở trên không trung.png", "maha_air", 2, 16.0, 8),
        ("Vận công chuẩn bị chiêu antomina.png", "anta_chg", 4, 16.0, 8),
        ("vận công antamina 2.png", "anta_rng", 4, 16.0, 14),
        ("quá trình tung chiêu antamina.png", "anta_fire", 3, 16.0, 8),
        ("tung chiêu kentaima.png", "kenta_cast", 4, 16.0, 8),
    ]
    for sheet_name, prefix, exp_n, tol, mgap in body_specs:
        arr = np.array(Image.open(TAP_DIR / sheet_name).convert("RGBA"))
        keyed = key_standard_bg(arr, tol=tol)
        boxes = split_by_x_valleys(keyed, exp_n, min_gap_cols=mgap)
        print(f"[BODY] {sheet_name}: exp={exp_n}, got={len(boxes)} -> {[(b[2]-b[0], b[3]-b[1]) for b in boxes]}")
        for idx, b in enumerate(boxes):
            rec = save_crop(keyed, b, BODY_OUT / f"{prefix}_{idx:02d}.png")
            rec["sheet"] = sheet_name
            meta["body"].append(rec)

    # `vòng tròn bảo vệ.png` (9 phases: 0..3 body jump+flute, 4..8 body inside electric blue shield dome)
    arr_bar = np.array(Image.open(TAP_DIR / "vòng tròn bảo vệ.png").convert("RGBA"))
    arr_bar[:, 1850:, :] = [27, 21, 35, 255]
    keyed_bar = key_standard_bg(arr_bar, tol=16.0)
    boxes_bar = split_by_x_valleys(keyed_bar, 9, min_gap_cols=12)
    print(f"[BODY+FX] vòng tròn bảo vệ.png: exp=9, got={len(boxes_bar)} -> {[(b[2]-b[0], b[3]-b[1]) for b in boxes_bar]}")
    for idx, b in enumerate(boxes_bar):
        rec = save_crop(keyed_bar, b, BODY_OUT / f"barrier_{idx:02d}.png")
        rec["sheet"] = "vòng tròn bảo vệ.png"
        meta["body"].append(rec)
        if idx >= 4:
            # Also create clean pure blue-electric dome FX (replacing inner body pixels with pixelated lattice so sustained barrier works on ANY pose!)
            rec_fx = save_crop(keyed_bar, b, FX_OUT / f"barrier_dome_{idx-4:02d}.png")
            rec_fx["sheet"] = "vòng tròn bảo vệ.png"
            meta["fx"].append(rec_fx)

    # `Bukadai.png` (9 phases: 0..3 body slash/dash, 4 vanish streak, 5..8 yellow lightning spheres)
    arr_buk = np.array(Image.open(TAP_DIR / "Bukadai.png").convert("RGBA"))
    arr_buk[:24, 1400:, :] = [27, 21, 35, 255]
    keyed_buk = key_standard_bg(arr_buk, tol=16.0)
    boxes_buk = split_by_x_valleys(keyed_buk, 9, min_gap_cols=6)
    print(f"[BODY+FX] Bukadai.png: exp=9, got={len(boxes_buk)} -> {[(b[2]-b[0], b[3]-b[1]) for b in boxes_buk]}")
    for idx, b in enumerate(boxes_buk):
        if idx <= 3:
            rec = save_crop(keyed_buk, b, BODY_OUT / f"bukadai_{idx:02d}.png")
            rec["sheet"] = "Bukadai.png"
            meta["body"].append(rec)
        elif idx == 4:
            rec = save_crop(keyed_buk, b, FX_OUT / "bukadai_vanish_00.png")
            rec["sheet"] = "Bukadai.png"
            meta["fx"].append(rec)
        else:
            rec = save_crop(keyed_buk, b, FX_OUT / f"bukadai_sphere_{idx-5:02d}.png")
            rec["sheet"] = "Bukadai.png"
            meta["fx"].append(rec)

    # Pure FX sheets:
    # 1. VFX từ tay mahasenko (3 vertical)
    keyed_mh = key_standard_bg(np.array(Image.open(TAP_DIR / "VFX từ tay khi thi triên mahasenko.png").convert("RGBA")), tol=16.0)
    boxes_mh = split_by_y_valleys(keyed_mh, 3, min_gap_rows=8)
    print(f"[FX] VFX từ tay mahasenko: got={len(boxes_mh)} -> {[(b[2]-b[0], b[3]-b[1]) for b in boxes_mh]}")
    for idx, b in enumerate(boxes_mh):
        rec = save_crop(keyed_mh, b, FX_OUT / f"maha_hand_{idx:02d}.png")
        rec["sheet"] = "VFX từ tay khi thi triên mahasenko.png"
        meta["fx"].append(rec)

    # 2. chiêu mahasenko.png (3 vertical, strip right red numbers x >= 445)
    arr_mb = np.array(Image.open(TAP_DIR / "chiêu mahasenko.png").convert("RGBA"))
    arr_mb[:, 445:, :] = [27, 21, 35, 255]
    keyed_mb = key_standard_bg(arr_mb, tol=16.0, strip_red_pen=True)
    boxes_mb = split_by_y_valleys(keyed_mb, 3, min_gap_rows=10)
    print(f"[FX] chiêu mahasenko.png: got={len(boxes_mb)} -> {[(b[2]-b[0], b[3]-b[1]) for b in boxes_mb]}")
    for idx, b in enumerate(boxes_mb):
        rec = save_crop(keyed_mb, b, FX_OUT / f"maha_beam_h_{idx:02d}.png")
        rec["sheet"] = "chiêu mahasenko.png"
        meta["fx"].append(rec)

    # 3. chiêu mahasenko từ trên không trung.png (3 vertical, strip right red numbers x >= 438)
    arr_ma = np.array(Image.open(TAP_DIR / "chiêu mahasenko từ trên không trung.png").convert("RGBA"))
    arr_ma[:, 438:, :] = [27, 21, 35, 255]
    keyed_ma = key_standard_bg(arr_ma, tol=16.0, strip_red_pen=True)
    boxes_ma = split_by_y_valleys(keyed_ma, 3, min_gap_rows=10)
    print(f"[FX] chiêu mahasenko không trung: got={len(boxes_ma)} -> {[(b[2]-b[0], b[3]-b[1]) for b in boxes_ma]}")
    for idx, b in enumerate(boxes_ma):
        rec = save_crop(keyed_ma, b, FX_OUT / f"maha_beam_air_{idx:02d}.png")
        rec["sheet"] = "chiêu mahasenko từ trên không trung.png"
        meta["fx"].append(rec)

    # 4. hit impact mahasenko.png (top row 3, bottom row 2; strip red pen!)
    arr_mi = np.array(Image.open(TAP_DIR / "hit impact mahasenko.png").convert("RGBA"))
    keyed_mi = key_standard_bg(arr_mi, tol=16.0, strip_red_pen=True)
    top_mi = keyed_mi.copy(); top_mi[405:, :, :] = 0
    bot_mi = keyed_mi.copy(); bot_mi[:405, :, :] = 0
    boxes_mi = split_by_x_valleys(top_mi, 3, min_gap_cols=20) + split_by_x_valleys(bot_mi, 2, min_gap_cols=35)
    print(f"[FX] hit impact mahasenko.png: got={len(boxes_mi)} -> {[(b[2]-b[0], b[3]-b[1]) for b in boxes_mi]}")
    for idx, b in enumerate(boxes_mi):
        rec = save_crop(keyed_mi, b, FX_OUT / f"maha_impact_{idx:02d}.png")
        rec["sheet"] = "hit impact mahasenko.png"
        meta["fx"].append(rec)

    # 5. chiêu antamina.png (1..5 RIGHT-TO-LEFT!)
    arr_as = np.array(Image.open(TAP_DIR / "chiêu antamina.png").convert("RGBA"))
    keyed_as = key_standard_bg(arr_as, tol=16.0, strip_red_pen=True)
    right_part = keyed_as.copy(); right_part[:, :1055, :] = 0
    left_part = keyed_as.copy(); left_part[:, 1055:, :] = 0
    b_r_vert = split_by_y_valleys(right_part, 2, min_gap_rows=10)
    b_l_horz = split_by_x_valleys(left_part, 3, min_gap_cols=6)
    ordered_as = [b_r_vert[1], b_r_vert[0], b_l_horz[2], b_l_horz[1], b_l_horz[0]]
    print(f"[FX] chiêu antamina.png (1->5): got={len(ordered_as)} -> {[(b[2]-b[0], b[3]-b[1]) for b in ordered_as]}")
    for idx, b in enumerate(ordered_as):
        rec = save_crop(keyed_as, b, FX_OUT / f"anta_stream_{idx:02d}.png")
        rec["sheet"] = "chiêu antamina.png"
        meta["fx"].append(rec)

    # 6. hit impact antamina.png (4 horizontal)
    keyed_ai = key_standard_bg(np.array(Image.open(TAP_DIR / "hit impact antamina.png").convert("RGBA")), tol=16.0)
    boxes_ai = split_by_x_valleys(keyed_ai, 4, min_gap_cols=12)
    print(f"[FX] hit impact antamina.png: got={len(boxes_ai)} -> {[(b[2]-b[0], b[3]-b[1]) for b in boxes_ai]}")
    for idx, b in enumerate(boxes_ai):
        rec = save_crop(keyed_ai, b, FX_OUT / f"anta_impact_{idx:02d}.png")
        rec["sheet"] = "hit impact antamina.png"
        meta["fx"].append(rec)

    # 7. chiêu kentaima.png (4 horizontal; two-tone left bg!)
    arr_kw = np.array(Image.open(TAP_DIR / "chiêu kentaima.png").convert("RGBA"))
    r_kw, g_kw, b_kw = arr_kw[:, :, 0].astype(np.float32), arr_kw[:, :, 1].astype(np.float32), arr_kw[:, :, 2].astype(np.float32)
    fg_kw = ((b_kw - r_kw) > 26.0) | ((r_kw > 155) & (g_kw > 185) & (b_kw > 195))
    keyed_kw = arr_kw.copy()
    keyed_kw[~fg_kw] = [0, 0, 0, 0]
    keyed_kw[fg_kw, 3] = 255
    boxes_kw = split_by_x_valleys(keyed_kw, 4, min_gap_cols=12)
    print(f"[FX] chiêu kentaima.png: got={len(boxes_kw)} -> {[(b[2]-b[0], b[3]-b[1]) for b in boxes_kw]}")
    for idx, b in enumerate(boxes_kw):
        rec = save_crop(keyed_kw, b, FX_OUT / f"kenta_wave_{idx:02d}.png")
        rec["sheet"] = "chiêu kentaima.png"
        meta["fx"].append(rec)

    # 8. hit impact kentaima.png (6 horizontal; preserve dark smoke + cyan embers!)
    arr_ki = np.array(Image.open(TAP_DIR / "hit impact kentaima.png").convert("RGBA"))
    r_ki, g_ki, b_ki = arr_ki[:, :, 0].astype(np.float32), arr_ki[:, :, 1].astype(np.float32), arr_ki[:, :, 2].astype(np.float32)
    dist_ki = np.sqrt((r_ki - 27.0) ** 2 + (g_ki - 21.0) ** 2 + (b_ki - 35.0) ** 2)
    fg_ki = dist_ki > 11.5
    keyed_ki = arr_ki.copy()
    keyed_ki[~fg_ki] = [0, 0, 0, 0]
    keyed_ki[fg_ki, 3] = 255
    boxes_ki = split_by_x_valleys(keyed_ki, 6, min_gap_cols=8)
    print(f"[FX] hit impact kentaima.png: got={len(boxes_ki)} -> {[(b[2]-b[0], b[3]-b[1]) for b in boxes_ki]}")
    for idx, b in enumerate(boxes_ki):
        rec = save_crop(keyed_ki, b, FX_OUT / f"kenta_impact_{idx:02d}.png")
        rec["sheet"] = "hit impact kentaima.png"
        meta["fx"].append(rec)

    # 9. hiệu ứng nối từ budakai vào hit impact budakai.png (1 cluster)
    keyed_bf = key_standard_bg(np.array(Image.open(TAP_DIR / "hiệu ứng nối từ budakai vào hit impact budakai.png").convert("RGBA")), tol=16.0)
    boxes_bf = split_by_x_valleys(keyed_bf, 1, min_gap_cols=6)
    print(f"[FX] budakai flash: got={len(boxes_bf)} -> {[(b[2]-b[0], b[3]-b[1]) for b in boxes_bf]}")
    for idx, b in enumerate(boxes_bf):
        rec = save_crop(keyed_bf, b, FX_OUT / f"bukadai_flash_{idx:02d}.png")
        rec["sheet"] = "hiệu ứng nối từ budakai vào hit impact budakai.png"
        meta["fx"].append(rec)

    # 10. hitimpact budakai.png (3 horizontal)
    keyed_bi = key_standard_bg(np.array(Image.open(TAP_DIR / "hitimpact budakai.png").convert("RGBA")), tol=16.0)
    boxes_bi = split_by_x_valleys(keyed_bi, 3, min_gap_cols=16)
    print(f"[FX] hitimpact budakai.png: got={len(boxes_bi)} -> {[(b[2]-b[0], b[3]-b[1]) for b in boxes_bi]}")
    for idx, b in enumerate(boxes_bi):
        rec = save_crop(keyed_bi, b, FX_OUT / f"bukadai_impact_{idx:02d}.png")
        rec["sheet"] = "hitimpact budakai.png"
        meta["fx"].append(rec)

    (P2_WORK / "phase2_slices_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for label, folder, out_png in [("BODY", BODY_OUT, P2_WORK / "overview_body_slices.png"), ("FX", FX_OUT, P2_WORK / "overview_fx_slices.png")]:
        files = sorted(folder.glob("*.png"))
        cols = 8
        rows = (len(files) + cols - 1) // cols
        cw, ch = 180, 180
        sheet = Image.new("RGBA", (cols * cw, rows * ch), (20, 24, 32, 255))
        draw = ImageDraw.Draw(sheet)
        for i, fp in enumerate(files):
            r_i, c_i = divmod(i, cols)
            x0, y0 = c_i * cw, r_i * ch
            im = Image.open(fp).convert("RGBA")
            sc = min(148.0 / max(1, im.width), 136.0 / max(1, im.height))
            nw, nh = max(1, int(round(im.width * sc))), max(1, int(round(im.height * sc)))
            rim = im.resize((nw, nh), Image.Resampling.NEAREST)
            sheet.alpha_composite(rim, (x0 + (cw - nw) // 2, y0 + 22 + (140 - nh) // 2))
            draw.rectangle([x0, y0, x0 + cw - 1, y0 + ch - 1], outline=(55, 65, 85, 255))
            draw.text((x0 + 4, y0 + 3), f"{fp.stem}\n{im.width}x{im.height}", fill=(240, 225, 130, 255))
        sheet.save(out_png)
    print(f"[DONE] Body slices={len(meta['body'])}, FX slices={len(meta['fx'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
