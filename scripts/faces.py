"""口パク（閉じ/半開き/開き）とまばたきの差分をキャラ画像から作る。

座標はすべて assets/characters/*.png（等倍）上のピクセル。超解像版(x4)に合わせて拡大して使う。
"""
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
HIRES = ROOT / "assets" / "characters_hires"
K = 4  # 超解像倍率

# 口: (x0, y0, x1, y1, 元画像の口が開いているか)
MOUTHS = {
    "satoru": (105, 73, 122, 88, True),
    "rina": (65, 94, 86, 107, True),
    "aina": (68, 71, 81, 76, False),
    "sora": (75, 78, 85, 82, False),
    "noa_in_aina": (54, 143, 69, 153, True),
    "chappy": (64, 102, 96, 125, True),
}
# 目: [(x0, y0, x1, y1), ...]
EYES = {
    "satoru": [(104, 51, 117, 61), (129, 57, 140, 65)],
    "rina": [(50, 70, 62, 86), (83, 70, 96, 86)],
    "aina": [(49, 54, 62, 65), (76, 45, 90, 57)],
    "sora": [(69, 54, 85, 61), (94, 59, 106, 67)],
}
LINE = (96, 54, 46, 255)


@lru_cache(None)
def base(name):
    return Image.open(HIRES / f"{name}.png").convert("RGBA")


def skin_near(img, box, below=False):
    a = np.asarray(img).astype(int)
    x0, y0, x1, y1 = box
    m = 3 * K
    if below:
        region = a[y1 + K:y1 + m * 2, x0:x1]
    else:
        region = np.concatenate([a[y0 - m:y0, x0:x1].reshape(-1, 4), a[y1:y1 + m, x0:x1].reshape(-1, 4),
                                 a[y0:y1, x0 - m:x0].reshape(-1, 4), a[y0:y1, x1:x1 + m].reshape(-1, 4)])
    px = region.reshape(-1, 4)
    px = px[(px[:, 3] > 200) & (px[:, :3].sum(1) > 560) & (px[:, 0] >= px[:, 2])]
    if len(px) == 0:
        return (250, 222, 205, 255)
    return tuple(int(v) for v in np.median(px[:, :3], axis=0)) + (255,)


def patch(img, box, color, pad=1.2, blur=1.6):
    """box を楕円状に塗りつぶす（ふち をぼかして馴染ませる）。"""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse((x0 - w * (pad - 1), y0 - h * (pad - 1), x1 + w * (pad - 1), y1 + h * (pad - 1)),
                                 fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(blur * K))
    fill = Image.new("RGBA", img.size, color)
    img.paste(fill, (0, 0), mask)


def kbox(b):
    return tuple(v * K for v in b[:4])


def closed_line(d, box, smile=0.25, width=1.3):
    x0, y0, x1, y1 = box
    w = x1 - x0
    cx = (x0 + x1) / 2
    y = y0 + (y1 - y0) * 0.38
    d.arc((cx - w * 0.32, y - w * smile, cx + w * 0.32, y + w * smile), 20, 160, fill=LINE, width=int(width * K))


def draw_open(d, box, amount):
    x0, y0, x1, y1 = box
    w = (x1 - x0) * (0.85 if amount < 0.7 else 1.0)
    cx = (x0 + x1) / 2
    top = (y0 + y1) / 2 - K
    h = w * 0.75 * amount
    d.chord((cx - w / 2, top - h * 0.35, cx + w / 2, top + h), 0, 180, fill=(150, 62, 64, 255),
            outline=LINE, width=int(K * 0.9))
    if amount > 0.6:
        d.chord((cx - w * 0.3, top + h * 0.35, cx + w * 0.3, top + h * 0.95), 180, 360, fill=(236, 140, 140, 255))


def set_mouth(img, key, state):
    x0, y0, x1, y1, is_open = MOUTHS[key]
    box = kbox((x0, y0, x1, y1))
    d = ImageDraw.Draw(img)
    if is_open:
        if state == "open":
            return
        src = base("aina" if key == "noa_in_aina" else key).crop(box)
        patch(img, box, skin_near(img, box))
        if state == "closed":
            if key == "chappy":
                cx, y = (box[0] + box[2]) / 2, box[1] + (box[3] - box[1]) * 0.25
                r = (box[2] - box[0]) * 0.18
                d.arc((cx - 2 * r, y - r, cx, y + r), 0, 180, fill=LINE, width=int(K * 1.2))
                d.arc((cx, y - r, cx + 2 * r, y + r), 0, 180, fill=LINE, width=int(K * 1.2))
            else:
                closed_line(d, box)
        else:  # half: 元の口を縦につぶして貼る
            w, h = src.size
            small = src.resize((int(w * 0.88), max(1, int(h * 0.5))), Image.LANCZOS)
            m = Image.new("L", small.size, 0)
            ImageDraw.Draw(m).ellipse((0, 0, small.width - 1, small.height - 1), fill=255)
            img.paste(small, (int(box[0] + (w - small.width) / 2), int(box[1] + h * 0.12)),
                      m.filter(ImageFilter.GaussianBlur(K * 0.6)))
    else:
        if state == "closed":
            return
        patch(img, box, skin_near(img, box), pad=1.1, blur=0.8)
        draw_open(d, box, 1.0 if state == "open" else 0.5)


def close_eyes(img, name):
    d = ImageDraw.Draw(img)
    for b in EYES[name]:
        box = kbox(b)
        patch(img, box, skin_near(img, box, below=True), pad=1.05, blur=0.9)
        x0, y0, x1, y1 = box
        y = y0 + (y1 - y0) * 0.55
        w = x1 - x0
        d.arc((x0, y - w * 0.25, x1, y + w * 0.25), 15, 165, fill=LINE, width=int(K * 1.3))


@lru_cache(maxsize=64)
def variant(name, mouth="closed", eyes="open", baby="closed"):
    """name の差分画像（超解像サイズ）。"""
    img = base(name).copy()
    if name in MOUTHS:
        set_mouth(img, name, mouth)
    if name == "aina":
        set_mouth(img, "noa_in_aina", baby)
    if eyes == "closed" and name in EYES:
        close_eyes(img, name)
    return img
