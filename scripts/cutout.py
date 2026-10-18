"""キャラクターシート(3x2)から各キャラを切り出し、白背景を透過PNGにする。"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "assets" / "characters_sheet.webp"
OUT = ROOT / "assets" / "characters"

CELLS = {
    "satoru": (3, 3, 510, 510),
    "sora": (514, 3, 1019, 510),
    "aina": (1023, 3, 1533, 510),
    "rina": (3, 514, 510, 1021),
    "noa": (514, 514, 1019, 1021),
    "chappy": (1023, 514, 1533, 1021),
}


def cutout(img):
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    # 背景に近い白（明るく低彩度）
    light = (a.min(axis=2) > 228) & ((a.max(axis=2) - a.min(axis=2)) < 22)
    # 外周とつながっている白だけを背景とみなす（白Tシャツや靴下は残す）
    lab, _ = ndimage.label(light)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    bg = np.isin(lab, border[border > 0])
    fg = ~bg
    fg = ndimage.binary_opening(fg, iterations=1)
    # 小さなゴミを除去
    lab2, n = ndimage.label(fg)
    if n:
        sizes = ndimage.sum(fg, lab2, range(1, n + 1))
        fg = np.isin(lab2, [i + 1 for i, s in enumerate(sizes) if s > 400])
    alpha = Image.fromarray((fg * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    out = img.convert("RGBA")
    out.putalpha(alpha)
    return out.crop(out.getbbox())


def main():
    sheet = Image.open(SHEET)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, box in CELLS.items():
        c = cutout(sheet.crop(box))
        c.save(OUT / f"{name}.png")
        print(name, c.size)


if __name__ == "__main__":
    sys.exit(main())
