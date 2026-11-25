#!/usr/bin/env python3
"""
DR7-Studio — Tapion `kentaima_impact_fx` Scale Down 30% (`0.70x`) Nearest (`polish_v3`):
Owner request: "giảm kích thước kentaima_impact_fx xuống 30%."
Idempotent: preserves an immutable 100%-scale backup under `kenta_impact_100pct_backup/`
and scales every frame `kenta_impact_00..05` by 0.70x using crisp NEAREST centered at (144, 176).
"""
from __future__ import annotations

import pathlib
import shutil
import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[2]
FX_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v2" / "fx_registered_288"
BACKUP_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v2" / "kenta_impact_100pct_backup"
QA_DIR = ROOT / "work" / "characters" / "tapion" / "polish_v2" / "qa"

CW, CH = 288, 288
CX, CY = 144, 176
SCALE = 0.70


def main() -> int:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    before_imgs, after_imgs = [], []
    for i in range(6):
        fn = f"kenta_impact_{i:02d}.png"
        src_live = FX_DIR / fn
        bkp = BACKUP_DIR / fn
        if not bkp.is_file():
            shutil.copy2(src_live, bkp)
        im_orig = Image.open(bkp).convert("RGBA")
        before_imgs.append(im_orig)
        arr = np.array(im_orig)
        ys, xs = np.where(arr[..., 3] > 0)
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        crop = im_orig.crop((x0, y0, x1 + 1, y1 + 1))
        nw = max(8, int(round(crop.width * SCALE)))
        nh = max(8, int(round(crop.height * SCALE)))
        resized = crop.resize((nw, nh), Image.Resampling.NEAREST)
        out = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        px = int(round(CX - nw / 2.0))
        py = int(round(CY - nh / 2.0))
        out.paste(resized, (px, py))
        out_arr = np.array(out)
        out_arr[out_arr[..., 3] > 0, 3] = 255
        out = Image.fromarray(out_arr, mode="RGBA")
        out.save(src_live)
        after_imgs.append(out)
        print(f"[kenta_impact_{i:02d}] {crop.width}x{crop.height} -> {nw}x{nh} (scale={SCALE:.2f}, center=({CX},{CY}))")

    # QA strip comparing 100% vs 70%
    cw, ch = 220, 220
    cbox = (34, 66, 254, 286)
    board = Image.new("RGBA", (6 * cw, 2 * (ch + 22)), (20, 24, 34, 255))
    dr = ImageDraw.Draw(board)
    for ri, (lbl, imgs) in enumerate([("BEFORE 100%", before_imgs), ("AFTER 70% (-30%)", after_imgs)]):
        for ci, im in enumerate(imgs):
            tile = Image.new("RGBA", (cw, ch), (24, 30, 44, 255))
            tile.alpha_composite(im.crop(cbox))
            x0, y0 = ci * cw, ri * (ch + 22)
            board.paste(tile, (x0, y0 + 22))
            dr.rectangle([x0, y0, x0 + cw - 1, y0 + ch + 21], outline=(80, 90, 110, 255))
            dr.text((x0 + 6, y0 + 4), f"{lbl} #{ci}", fill=(120, 235, 255, 255))
    out_qa = QA_DIR / "qa_kentaima_impact_70pct.png"
    board.save(out_qa)
    print("Saved QA:", out_qa)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
