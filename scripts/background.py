"""ジブリ風の水彩タッチ背景（2026年・東京都内マンションのリビング）を手続き的に描く。"""
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H = 1080, 1920
FLOOR_Y = 1330
ROOT = Path(__file__).resolve().parent.parent


def vgrad(w, h, top, bottom):
    t = np.linspace(0, 1, h)[:, None, None]
    a = np.array(top, float)[None, None, :] * (1 - t) + np.array(bottom, float)[None, None, :] * t
    return Image.fromarray(np.repeat(a, w, axis=1).astype(np.uint8), "RGB")


def soft_layer(size, draw_fn, blur=0):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    return layer.filter(ImageFilter.GaussianBlur(blur)) if blur else layer


def paper_texture(img, strength=10, seed=1):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, 1, (img.height // 4, img.width // 4))
    n = Image.fromarray(((n - n.min()) / (n.max() - n.min()) * 255).astype(np.uint8)).resize(img.size, Image.BICUBIC)
    n = np.asarray(n.filter(ImageFilter.GaussianBlur(2)), float) / 255 - 0.5
    fine = rng.normal(0, 0.5, (img.height, img.width))
    a = np.asarray(img.convert("RGB"), float)
    a += (n * strength * 2 + fine * strength * 0.4)[:, :, None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def cumulus(d, cx, cy, s, rng):
    """入道雲っぽいもくもく雲（影→本体→ハイライトの順で重ねる）。"""
    blobs = []
    for i in range(14):
        ang = rng.uniform(math.pi, 2 * math.pi)
        r = s * rng.uniform(0.28, 0.55)
        dx = math.cos(ang) * s * rng.uniform(0.2, 0.9)
        dy = math.sin(ang) * s * rng.uniform(0.1, 0.6)
        blobs.append((cx + dx, cy + dy, r))
    for i in range(7):
        blobs.append((cx + rng.uniform(-1, 1) * s, cy + rng.uniform(0, 0.15) * s, s * rng.uniform(0.25, 0.4)))
    for x, y, r in blobs:
        d.ellipse((x - r, y - r + r * 0.18, x + r, y + r + r * 0.18), fill=(190, 205, 228, 255))
    for x, y, r in blobs:
        d.ellipse((x - r * 0.95, y - r * 0.95, x + r * 0.95, y + r * 0.85), fill=(250, 250, 252, 255))
    for x, y, r in blobs:
        if y < cy:
            d.ellipse((x - r * 0.6, y - r * 0.85, x + r * 0.5, y - r * 0.1), fill=(255, 255, 255, 255))


def sky_view(w, h, seed=3):
    rng = random.Random(seed)
    sky = vgrad(w, h, (92, 160, 222), (196, 226, 246)).convert("RGBA")
    clouds = soft_layer((w, h), lambda d: [
        cumulus(d, w * 0.25, h * 0.42, 150, rng),
        cumulus(d, w * 0.78, h * 0.30, 120, rng),
        cumulus(d, w * 0.55, h * 0.62, 90, rng),
    ], blur=3)
    sky.alpha_composite(clouds)
    # 遠景の東京の街並み（スカイツリー入り）
    city = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(city)
    base = h
    rng2 = random.Random(seed + 7)
    for layer, (col, hmin, hmax) in enumerate([((158, 182, 206, 255), 60, 170), ((128, 152, 178, 255), 40, 120)]):
        x = -10
        while x < w:
            bw = rng2.randint(30, 80)
            bh = rng2.randint(hmin, hmax)
            d.rectangle((x, base - bh, x + bw, base), fill=col)
            if layer == 1:
                for wy in range(base - bh + 10, base - 6, 16):
                    for wx in range(x + 6, x + bw - 6, 12):
                        if rng2.random() < 0.35:
                            d.rectangle((wx, wy, wx + 4, wy + 6), fill=(236, 230, 205, 255))
            x += bw + rng2.randint(-6, 6)
    tx = int(w * 0.70)
    tc = (140, 162, 188, 255)
    d.polygon([(tx - 26, base), (tx - 7, base - 330), (tx + 7, base - 330), (tx + 26, base)], fill=tc)
    d.ellipse((tx - 20, base - 300, tx + 20, base - 280), fill=tc)
    d.ellipse((tx - 15, base - 365, tx + 15, base - 350), fill=tc)
    d.rectangle((tx - 3, base - 430, tx + 3, base - 330), fill=tc)
    sky.alpha_composite(city.filter(ImageFilter.GaussianBlur(1.2)))
    haze = vgrad(w, h, (255, 255, 255), (255, 244, 225)).convert("RGBA")
    haze.putalpha(Image.fromarray(np.linspace(0, 90, h).astype(np.uint8)[:, None].repeat(w, 1)))
    sky.alpha_composite(haze)
    return sky


def monstera(d, cx, base, s):
    d.polygon([(cx - 70 * s, base - 150 * s), (cx + 70 * s, base - 150 * s), (cx + 55 * s, base), (cx - 55 * s, base)],
              fill=(214, 196, 170, 255))
    d.rectangle((cx - 75 * s, base - 165 * s, cx + 75 * s, base - 145 * s), fill=(196, 176, 150, 255))
    leaves = [(-120, -420, 110), (90, -470, 120), (-20, -560, 105), (150, -330, 95), (-160, -300, 90), (20, -380, 100)]
    for dx, dy, r in leaves:
        x, y = cx + dx * s, base + dy * s
        d.line((cx, base - 160 * s, x, y), fill=(74, 118, 70, 255), width=int(8 * s))
    for i, (dx, dy, r) in enumerate(leaves):
        x, y, r = cx + dx * s, base + dy * s, r * s
        col = [(96, 150, 84, 255), (82, 136, 76, 255), (110, 162, 92, 255)][i % 3]
        d.ellipse((x - r, y - r * 0.75, x + r, y + r * 0.75), fill=col)
        d.ellipse((x - r * 0.55, y - r * 0.5, x + r * 0.1, y - r * 0.05), fill=(140, 186, 112, 255))


def draw_sofa(w=760, h=420):
    """ソファ（前景にも使えるよう単体レイヤー）。"""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    body, dark, light = (226, 206, 176, 255), (196, 172, 140, 255), (240, 226, 202, 255)
    d.rounded_rectangle((40, 30, w - 40, 250), 50, fill=dark)
    d.rounded_rectangle((60, 40, w - 60, 230), 46, fill=body)
    d.rounded_rectangle((0, 150, w, h - 50), 46, fill=dark)
    d.rounded_rectangle((90, 190, w // 2 - 4, 300), 30, fill=light)
    d.rounded_rectangle((w // 2 + 4, 190, w - 90, 300), 30, fill=light)
    d.rounded_rectangle((0, 110, 110, h - 50), 50, fill=body)
    d.rounded_rectangle((w - 110, 110, w, h - 50), 50, fill=body)
    for x in (60, w - 80):
        d.rectangle((x, h - 55, x + 20, h), fill=(130, 100, 70, 255))
    # クッション
    d.rounded_rectangle((130, 80, 300, 210), 40, fill=(186, 200, 226, 255))
    d.rounded_rectangle((w - 300, 85, w - 140, 210), 40, fill=(238, 196, 196, 255))
    return img.filter(ImageFilter.GaussianBlur(0.8))


def living_room(seed=11):
    rng = random.Random(seed)
    img = vgrad(W, H, (247, 236, 214), (236, 220, 192)).convert("RGBA")
    d = ImageDraw.Draw(img)
    # 窓
    wx0, wy0, wx1, wy1 = 150, 210, 930, 1010
    sky = sky_view(wx1 - wx0, wy1 - wy0)
    img.alpha_composite(sky, (wx0, wy0))
    frame = (250, 248, 242, 255)
    d.rectangle((wx0 - 22, wy0 - 22, wx1 + 22, wy0), fill=frame)
    d.rectangle((wx0 - 22, wy1, wx1 + 22, wy1 + 34), fill=frame)
    d.rectangle((wx0 - 22, wy0, wx0, wy1), fill=frame)
    d.rectangle((wx1, wy0, wx1 + 22, wy1), fill=frame)
    d.rectangle(((wx0 + wx1) // 2 - 8, wy0, (wx0 + wx1) // 2 + 8, wy1), fill=frame)
    # カーテン
    curtain = soft_layer((W, H), lambda dd: [
        dd.polygon([(wx0 - 90, wy0 - 60), (wx0 + 70, wy0 - 60), (wx0 + 10, wy1 + 120), (wx0 - 110, wy1 + 140)],
                   fill=(250, 246, 236, 235)),
        dd.polygon([(wx1 - 70, wy0 - 60), (wx1 + 90, wy0 - 60), (wx1 + 110, wy1 + 140), (wx1 - 10, wy1 + 120)],
                   fill=(250, 246, 236, 235)),
    ] + [dd.line((x, wy0 - 50, x - 18, wy1 + 130), fill=(232, 224, 206, 200), width=5)
         for x in list(range(wx0 - 70, wx0 + 60, 32)) + list(range(wx1 - 50, wx1 + 90, 32))], blur=2)
    img.alpha_composite(curtain)
    d.rectangle((wx0 - 120, wy0 - 75, wx1 + 120, wy0 - 58), fill=(178, 150, 116, 255))
    # 床（フローリング）
    floor = vgrad(W, H - FLOOR_Y, (214, 172, 124), (188, 142, 96)).convert("RGBA")
    fd = ImageDraw.Draw(floor)
    for i in range(-14, 15):
        x0 = W / 2 + i * 70
        x1 = W / 2 + i * 190
        fd.line((x0, 0, x1, H - FLOOR_Y), fill=(170, 126, 84, 120), width=3)
    for y in (60, 150, 270, 420):
        fd.line((0, y, W, y), fill=(176, 132, 88, 70), width=2)
    img.alpha_composite(floor, (0, FLOOR_Y))
    d.rectangle((0, FLOOR_Y - 26, W, FLOOR_Y), fill=(244, 238, 226, 255))  # 幅木
    # ラグ
    rug = soft_layer((W, H), lambda dd: [
        dd.ellipse((60, FLOOR_Y + 120, W - 60, FLOOR_Y + 470), fill=(238, 222, 228, 255)),
        dd.ellipse((110, FLOOR_Y + 150, W - 110, FLOOR_Y + 440), outline=(222, 196, 210, 255), width=10),
    ], blur=2)
    img.alpha_composite(rug)
    # 棚と観葉植物、フロアランプ
    shelf = soft_layer((W, H), lambda dd: [
        dd.rounded_rectangle((-40, FLOOR_Y - 330, 150, FLOOR_Y - 10), 14, fill=(206, 170, 128, 255)),
        dd.rectangle((-30, FLOOR_Y - 230, 140, FLOOR_Y - 222), fill=(178, 140, 100, 255)),
        dd.rectangle((-30, FLOOR_Y - 130, 140, FLOOR_Y - 122), fill=(178, 140, 100, 255)),
    ] + [dd.rectangle((x, FLOOR_Y - 225 - hh, x + 18, FLOOR_Y - 232),
                      fill=c) for x, hh, c in [(0, 70, (120, 150, 190, 255)), (20, 80, (220, 160, 150, 255)),
                                               (42, 60, (150, 180, 130, 255)), (64, 76, (236, 206, 140, 255)),
                                               (88, 66, (180, 150, 200, 255))]], blur=1)
    img.alpha_composite(shelf)
    plant = soft_layer((W, H), lambda dd: monstera(dd, W - 110, FLOOR_Y + 30, 0.95), blur=1.2)
    img.alpha_composite(plant)
    lamp = soft_layer((W, H), lambda dd: [
        dd.line((90, FLOOR_Y - 340, 90, FLOOR_Y - 900), fill=(120, 100, 80, 255), width=6),
        dd.polygon([(30, FLOOR_Y - 900), (150, FLOOR_Y - 900), (125, FLOOR_Y - 1010), (55, FLOOR_Y - 1010)],
                   fill=(250, 236, 200, 255)),
    ], blur=1)
    img.alpha_composite(lamp)
    # 差し込む光
    light = soft_layer((W, H), lambda dd: [
        dd.polygon([(wx0 + 40, wy0), (wx0 + 260, wy0), (wx0 + 620, H), (wx0 - 160, H)], fill=(255, 246, 214, 46)),
        dd.polygon([(wx1 - 260, wy0), (wx1 - 60, wy0), (wx1 + 220, H), (wx1 - 520, H)], fill=(255, 246, 214, 36)),
    ], blur=40)
    img.alpha_composite(light)
    # 周辺減光
    yy, xx = np.mgrid[0:H, 0:W]
    v = ((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H * 0.45) / (H * 0.75)) ** 2
    vig = Image.fromarray(np.clip(v * 120, 0, 110).astype(np.uint8))
    shade = Image.new("RGBA", (W, H), (120, 80, 50, 255))
    shade.putalpha(vig)
    img.alpha_composite(shade)
    return paper_texture(img, 7)


def build(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    living_room().save(out_dir / "bg_living.png")
    draw_sofa().save(out_dir / "sofa.png")


if __name__ == "__main__":
    build(ROOT / "build")
