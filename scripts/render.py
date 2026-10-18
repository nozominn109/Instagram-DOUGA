"""田中家リール 第1話「読書感想文編」を 1080x1920 / 30fps の MP4 に書き出す。

家族全員がこたつを囲むリビングの1シーンを2倍解像度で組み、カメラ（パン・ズーム）で
話者を追いかける。口パクは VOICEVOX のモーラタイミング、まばたきはランダム。

使い方:
    python3 scripts/cutout.py      # キャラ切り出し（初回のみ）
    python3 scripts/hires.py       # キャラ超解像（初回のみ）
    python3 scripts/voices.py      # セリフ音声とタイムライン（VOICEVOX ENGINE 起動が必要）
    python3 scripts/render.py      # 動画書き出し -> output/
"""
import json
import math
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

import background
import faces
from story import NAMES, PROMPT

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
FONT_XB = str(ROOT / "assets" / "fonts" / "MPLUSRounded1c-ExtraBold.ttf")
FONT_B = str(ROOT / "assets" / "fonts" / "MPLUSRounded1c-Bold.ttf")
W, H, FPS = 1080, 1920, 30
CS = background.CS
SR = 48000
END_CARD = 2.6
FADE = 0.2

INK = (78, 56, 46)
COLORS = {
    "rina": (240, 128, 160), "aina": (164, 132, 206), "satoru": (104, 132, 170),
    "ai": (74, 186, 168), "sora": (60, 70, 96), "noa": (246, 150, 170), "chappy": (214, 168, 106),
}

TL = json.loads((BUILD / "timeline.json").read_text())
LINE = {x["id"]: x for x in TL}
END_T = TL[-1]["end"]
TOTAL = END_T + END_CARD


# ---------------------------------------------------------------- helpers
def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def back_out(x):
    x = min(max(x, 0.0), 1.0)
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


@lru_cache(None)
def font(size, path=FONT_XB):
    return ImageFont.truetype(path, size)


def paste(frame, im, x, y, alpha=1.0):
    if alpha <= 0:
        return
    if alpha < 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    frame.alpha_composite(im, (int(round(x)), int(round(y))))


# ------------------------------------------------------------- scene setup
# 出力座標でのキャラ配置: (中心x, 画像上端y, 高さ, 左右反転)
CAST = {
    "sora": (965, 600, 900, False),
    "satoru": (215, 420, 1010, False),
    "aina": (700, 690, 980, False),
    "rina": (420, 740, 880, False),
    "chappy": (905, 1200, 330, True),
}
RINA_HAND = (0.10, 0.22)   # スマホを持つ手（キャラ画像内の相対位置）
AINA_HAND = (0.88, 0.47)
FACE = {"rina": (0.5, 0.12), "aina": (0.45, 0.10), "satoru": (0.6, 0.11), "sora": (0.55, 0.10),
        "noa": (0.38, 0.27), "chappy": (0.33, 0.25)}


def anchor(name, rel):
    key = "aina" if name == "noa" else name
    cx, top, h, flip = CAST[key]
    im = faces.base(key)
    w = im.width * h / im.height
    rx = 1 - rel[0] if flip else rel[0]
    return cx - w / 2 + rx * w, top + rel[1] * h


@lru_cache(None)
def bg_scene():
    return Image.open(BUILD / "bg_living.png").convert("RGBA").resize((W * CS, H * CS), Image.LANCZOS)


@lru_cache(None)
def layers():
    k, kpos = background.kotatsu()
    sb, sf, spos = background.sofa_layers()
    return k, kpos, sb, sf, spos


@lru_cache(maxsize=96)
def char_img(name, mouth, eyes, baby, height):
    im = faces.variant(name, mouth, eyes, baby)
    w = round(im.width * height / im.height)
    out = im.resize((w, height), Image.LANCZOS)
    return out.transpose(Image.FLIP_LEFT_RIGHT) if CAST[name][3] else out


# ------------------------------------------------------------- lip sync
def openness(speaker, t):
    for ln in TL:
        if ln["speaker"] == speaker and ln["audio"] and ln["start"] <= t < ln["start"] + ln["dur"]:
            lt = t - ln["start"]
            vals = []
            for dt in (-1 / FPS / 2, 0, 1 / FPS / 2):
                v = 0.0
                for a, b, o in ln["mouth"]:
                    if a <= lt + dt < b:
                        v = o
                        break
                vals.append(v)
            return sum(vals) / 3
    return 0.0


def mouth_state(speaker, t):
    o = openness(speaker, t)
    return "closed" if o < 0.2 else ("half" if o < 0.6 else "open")


def is_speaking(speaker, t):
    return any(ln["speaker"] == speaker and ln["start"] <= t < ln["start"] + ln["dur"] for ln in TL)


def blinking(name, t):
    rng = np.random.default_rng(sum(map(ord, name)))
    times = np.cumsum(rng.uniform(2.2, 4.5, 20)) - rng.uniform(0, 2)
    return any(0 <= t - bt < 0.12 for bt in times)


def char_state(name, t):
    if name == "chappy":
        barking = is_speaking("chappy", t)
        return ("closed" if barking and mouth_state("chappy", t) == "closed" else "open"), "open", "closed"
    baby = mouth_state("noa", t) if name == "aina" else "closed"
    eyes = "closed" if blinking(name, t) else "open"
    return mouth_state(name, t), eyes, baby


# ----------------------------------------------------------------- scene render
def papa_x(t):
    t2 = LINE["l02"]["start"]
    k = back_out((t - t2 + 0.45) / 0.5)
    return -260 + (CAST["satoru"][0] + 260) * k


def phone_pos(t):
    """スマホの位置（出力座標）。ママが取り上げるまでは莉奈の手、その後はママの手。"""
    t0 = LINE["l04"]["start"] + 0.5
    rx, ry = anchor("rina", RINA_HAND)
    ax, ay = anchor("aina", AINA_HAND)
    g = ease((t - t0) / 0.4)
    return rx + (ax - rx) * g, ry + (ay - ry) * g - math.sin(g * math.pi) * 120 + math.sin(t * 3) * 4


def sparkle(d, x, y, r, col=(255, 236, 140, 255)):
    pts = []
    for i in range(8):
        a = i * math.pi / 4
        rr = r if i % 2 == 0 else r * 0.28
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    d.polygon(pts, fill=col)


@lru_cache(None)
def phone_small():
    im = Image.new("RGBA", (92 * CS, 160 * CS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, 92 * CS - 1, 160 * CS - 1), 18 * CS, fill=(52, 58, 80, 255))
    d.rounded_rectangle((7 * CS, 10 * CS, 85 * CS, 150 * CS), 12 * CS, fill=(200, 236, 248, 255))
    d.rounded_rectangle((14 * CS, 30 * CS, 70 * CS, 50 * CS), 8 * CS, fill=(255, 190, 205, 255))
    d.rounded_rectangle((20 * CS, 62 * CS, 78 * CS, 84 * CS), 8 * CS, fill=(255, 255, 255, 255))
    sparkle(d, 46 * CS, 115 * CS, 16 * CS, (120, 200, 190, 255))
    im = im.resize((int(im.width * 0.72), int(im.height * 0.72)), Image.LANCZOS)
    return im.rotate(-12, Image.BICUBIC, expand=True)


@lru_cache(None)
def phone_glow():
    g = Image.new("RGBA", (240 * CS, 280 * CS), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse((20 * CS, 20 * CS, 220 * CS, 260 * CS), fill=(255, 250, 210, 90))
    return g.filter(ImageFilter.GaussianBlur(26 * CS))


def draw_char(scene, name, t, x=None):
    cx, top, h, _ = CAST[name]
    cx = cx if x is None else x
    mouth, eyes, baby = char_state(name, t)
    speaker = "noa" if (name == "aina" and is_speaking("noa", t)) else name
    amt = openness(speaker, t)
    breath = math.sin(t * 2.2 + len(name)) * 0.004
    hop = amt * h * 0.006
    if name == "chappy" and is_speaking("chappy", t):
        hop += abs(math.sin((t - LINE["l16"]["start"]) * 9)) * 40
    im = char_img(name, mouth, eyes, baby, int(h * CS))
    sy = 1 + breath + amt * 0.008
    if abs(sy - 1) > 0.0015:
        im = im.resize((im.width, int(im.height * sy)), Image.BILINEAR)
    bottom = (top + h) * CS
    scene.alpha_composite(im, (int(cx * CS - im.width / 2), int(bottom - im.height - hop * CS)))


def render_scene(t):
    """全員そろったリビング（出力の2倍解像度）。"""
    scene = bg_scene().copy()
    k, kpos, sb, sf, spos = layers()
    scene.alpha_composite(sb, (spos[0] * CS, spos[1] * CS))
    draw_char(scene, "sora", t)
    scene.alpha_composite(sf, (spos[0] * CS, spos[1] * CS))
    if t >= LINE["l02"]["start"] - 0.45:
        draw_char(scene, "satoru", t, papa_x(t))
    draw_char(scene, "aina", t)
    draw_char(scene, "rina", t)
    scene.alpha_composite(k, (kpos[0] * CS, kpos[1] * CS))
    px, py = phone_pos(t)
    g = phone_glow()
    scene.alpha_composite(g, (int(px * CS - g.width / 2), int(py * CS - g.height / 2)))
    ph = phone_small()
    scene.alpha_composite(ph, (int(px * CS - ph.width / 2), int(py * CS - ph.height / 2)))
    draw_char(scene, "chappy", t)
    return scene


# ----------------------------------------------------------------- camera
MASTER = (540, 960, 1.0)


def face_cam(name, zoom, dy=0.0):
    x, y = anchor(name, FACE[name])
    return (x, y + 1920 / zoom * (0.18 + dy), zoom)


def cam_keys():
    L = LINE
    rina_papa = ((anchor("rina", FACE["rina"])[0] + CAST["satoru"][0]) / 2, 900, 1.35)
    duo = (560, 960, 1.38)
    return [
        (0.0, MASTER),
        (1.0, face_cam("rina", 1.6)),
        (L["l02"]["start"] - 0.25, rina_papa),
        (L["l04"]["start"] - 0.1, duo),
        (L["l09"]["start"], face_cam("aina", 1.6)),
        (L["l10"]["start"] - 0.1, face_cam("rina", 1.65)),
        (L["l12"]["start"] - 0.05, face_cam("rina", 2.1, -0.04)),
        (L["l13"]["start"] - 0.05, face_cam("satoru", 1.9)),
        (L["l14"]["start"] - 0.05, face_cam("sora", 1.95)),
        (L["l15"]["start"] - 0.1, face_cam("noa", 2.4, -0.05)),
        (L["l16"]["start"] - 0.1, face_cam("chappy", 2.0, 0.08)),
        (END_T, MASTER),
    ]


CAM = cam_keys()
PAN = 0.4


def camera(t):
    cur = CAM[0][1]
    for i, (kt, target) in enumerate(CAM):
        if t < kt:
            break
        prev = CAM[i - 1][1] if i else target
        k = ease((t - kt) / PAN)
        cur = tuple(p + (q - p) * k for p, q in zip(prev, target))
    return cur


def view_box(cam):
    cx, cy, z = cam
    cw, ch = W / z, H / z
    x0 = min(max(cx - cw / 2, 0), W - cw)
    y0 = min(max(cy - ch / 2, 0), H - ch)
    return x0, y0, cw, ch


def shoot(scene, cam):
    x0, y0, cw, ch = view_box(cam)
    return scene.resize((W, H), Image.BICUBIC, box=(x0 * CS, y0 * CS, (x0 + cw) * CS, (y0 + ch) * CS))


def to_screen(pt, cam):
    """シーン座標（出力単位）→ 画面座標。"""
    x0, y0, _, _ = view_box(cam)
    return (pt[0] - x0) * cam[2], (pt[1] - y0) * cam[2]


# ----------------------------------------------------------------- text & fx
def wrap(text, fnt, max_w):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for ch in para:
            if fnt.getlength(cur + ch) > max_w and cur:
                if ch in "、。！？」』…）ー〜":
                    cur += ch
                    continue
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        lines.append(cur)
    return lines


def outlined(d, xy, text, fnt, fill, stroke=(255, 255, 255), sw=8, anchor="la"):
    d.text(xy, text, font=fnt, fill=fill, stroke_width=sw, stroke_fill=stroke, anchor=anchor)


@lru_cache(None)
def subtitle_img(lid):
    ln = LINE[lid]
    sp = ln["speaker"]
    fnt = font(54)
    lines = wrap(ln["text"], fnt, 900)
    lh = 74
    bw, bh = 980, 60 + lh * len(lines)
    im = Image.new("RGBA", (bw, bh + 46), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((6, 52, bw - 6, bh + 40), 36, fill=(120, 90, 70, 60))
    d.rounded_rectangle((0, 40, bw - 8, bh + 32), 36, fill=(255, 252, 245, 245), outline=COLORS[sp], width=6)
    name = NAMES[sp]
    nf = font(36)
    nw = nf.getlength(name) + 48
    d.rounded_rectangle((34, 8, 34 + nw, 64), 28, fill=COLORS[sp])
    d.text((34 + nw / 2, 36), name, font=nf, fill=(255, 255, 255), anchor="mm")
    for i, s in enumerate(lines):
        d.text((bw / 2 - 4, 76 + i * lh + lh / 2), s, font=fnt, fill=INK, anchor="mm")
    return im


def draw_subtitle(frame, lid, t):
    ln = LINE[lid]
    if not ln["text"] or not (ln["start"] - 0.05 <= t < ln["end"]):
        return
    im = subtitle_img(lid)
    k = back_out((t - ln["start"] + 0.05) / 0.22)
    s = 0.85 + 0.15 * k
    im2 = im.resize((int(im.width * s), int(im.height * s)), Image.BILINEAR)
    paste(frame, im2, W / 2 - im2.width / 2, 1620 - im2.height / 2, min(1, k + 0.2))


@lru_cache(None)
def title_band():
    im = Image.new("RGBA", (W, 130), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((150, 18, W - 150, 112), 47, fill=(255, 250, 240, 230), outline=(240, 170, 150), width=4)
    d.text((W / 2, 50), "田中家のAIじかん", font=font(38), fill=(220, 110, 110), anchor="mm")
    d.text((W / 2, 90), "第1話　読書感想文編", font=font(28, FONT_B), fill=INK, anchor="mm")
    return im


@lru_cache(None)
def hook_img():
    im = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    outlined(d, (W / 2, 95), "宿題をAIに", font(84), (90, 70, 60), sw=12, anchor="mm")
    outlined(d, (W / 2, 205), "丸投げ！？", font(118), (236, 92, 108), sw=14, anchor="mm")
    return im


def pop_text(frame, text, x, y, t0, t, size=90, color=(236, 92, 108), rot=0, dur=None):
    if t < t0 or (dur and t > t0 + dur):
        return
    k = back_out((t - t0) / 0.25)
    fnt = font(size)
    w = int(fnt.getlength(text)) + 60
    im = Image.new("RGBA", (w, size + 60), (0, 0, 0, 0))
    outlined(ImageDraw.Draw(im), (w / 2, (size + 60) / 2), text, fnt, color, sw=10, anchor="mm")
    if rot:
        im = im.rotate(rot, Image.BICUBIC, expand=True)
    s = max(0.05, k)
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
    paste(frame, im, x - im.width / 2, y - im.height / 2)


def sparkles(frame, t, cx, cy, spread, n=10, seed=0, col=(255, 230, 120, 255)):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rng = np.random.default_rng(seed)
    for i in range(n):
        ph = rng.uniform(0, 6.28)
        sp = rng.uniform(1.5, 3.0)
        x = cx + rng.uniform(-1, 1) * spread
        y = cy + rng.uniform(-1, 1) * spread * 0.7
        r = (0.5 + 0.5 * math.sin(t * sp * 3 + ph)) * rng.uniform(14, 30)
        if r > 3:
            sparkle(d, x, y, r, col)
    frame.alpha_composite(layer)


def speed_lines(frame, t, col=(255, 255, 255), alpha=110, cx=W / 2, cy=H * 0.45, seed=3):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rng = np.random.default_rng(seed + int(t * 12))
    for _ in range(60):
        a = rng.uniform(0, 2 * math.pi)
        r0 = rng.uniform(560, 700)
        w = rng.uniform(0.008, 0.02)
        p = [(cx + math.cos(a - w) * 1600, cy + math.sin(a - w) * 1600),
             (cx + math.cos(a) * r0, cy + math.sin(a) * r0),
             (cx + math.cos(a + w) * 1600, cy + math.sin(a + w) * 1600)]
        d.polygon(p, fill=col + (alpha,))
    frame.alpha_composite(layer)


def hearts(frame, t, x0, x1, y_base):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(6):
        ph = (t * 0.6 + i / 6) % 1
        x = x0 + (x1 - x0) * i / 5 + math.sin(t * 2 + i) * 20
        y = y_base - ph * 600
        r = 18 + (i % 3) * 6
        a = int(200 * math.sin(ph * math.pi))
        c = (246, 140, 170, a)
        d.ellipse((x - r, y - r, x, y), fill=c)
        d.ellipse((x, y - r, x + r, y), fill=c)
        d.polygon([(x - r, y - r / 2), (x + r, y - r / 2), (x, y + r)], fill=c)
    frame.alpha_composite(layer)


# ------------------------------------------------------------- phone UI
PX0, PY0, PX1, PY1 = 150, 300, 930, 1430


@lru_cache(None)
def ai_avatar(size=84):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, size - 1, size - 1), fill=(120, 214, 196, 255))
    sparkle(d, size * 0.5, size * 0.5, size * 0.36, (255, 255, 255, 255))
    sparkle(d, size * 0.76, size * 0.26, size * 0.12, (255, 246, 180, 255))
    return im


def bubble(d, x, y, text, fnt, max_w, fill, me, lh, highlights=(), hl_k=0.0):
    lines = wrap(text, fnt, max_w - 56)
    bw = min(max_w, max(fnt.getlength(s) for s in lines) + 56) if lines else 80
    bh = 36 + lh * len(lines)
    x0 = x - bw if me else x
    d.rounded_rectangle((x0, y, x0 + bw, y + bh), 34, fill=fill)
    if hl_k > 0:
        joined = "".join(lines)
        for word in highlights:
            pos = joined.find(word)
            if pos < 0:
                continue
            idx = 0
            for li, s in enumerate(lines):
                a, b = max(pos - idx, 0), min(pos + len(word) - idx, len(s))
                if a < b:
                    xa = x0 + 28 + fnt.getlength(s[:a])
                    xb = x0 + 28 + fnt.getlength(s[:b])
                    xb = xa + (xb - xa) * ease(hl_k)
                    yy = y + 18 + li * lh
                    d.rectangle((xa, yy + lh * 0.52, xb, yy + lh * 0.92), fill=(255, 226, 92, 255))
                idx += len(s)
    for i, s in enumerate(lines):
        d.text((x0 + 28, y + 18 + i * lh), s, font=fnt, fill=INK)
    return bh


def phone_screen(frame, t, msgs, header_note, rot_k=1.0):
    """msgs: [(who, text, chars_shown, highlights, hl_k)]"""
    k = back_out(rot_k)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((PX0 - 4, PY0 + 16, PX1 + 12, PY1 + 24), 80, fill=(60, 40, 30, 70))
    d.rounded_rectangle((PX0, PY0, PX1, PY1), 76, fill=(46, 52, 72, 255))
    d.rounded_rectangle((PX0 + 22, PY0 + 22, PX1 - 22, PY1 - 22), 58, fill=(246, 250, 252, 255))
    d.rounded_rectangle((W / 2 - 70, PY0 + 34, W / 2 + 70, PY0 + 64), 15, fill=(46, 52, 72, 255))
    d.rectangle((PX0 + 22, PY0 + 86, PX1 - 22, PY0 + 190), fill=(232, 247, 244, 255))
    layer.alpha_composite(ai_avatar(), (PX0 + 50, PY0 + 96))
    d.text((PX0 + 152, PY0 + 118), "AIくん", font=font(42), fill=INK, anchor="lm")
    d.text((PX0 + 152, PY0 + 166), "オンライン", font=font(24, FONT_B), fill=(74, 170, 150), anchor="lm")
    y = PY0 + 220
    fnt = font(40, FONT_B)
    for who, text, shown, hls, hlk in msgs:
        txt = text[:shown]
        if not txt:
            continue
        if who == "me":
            y += bubble(d, PX1 - 50, y, txt, fnt, 640, (255, 222, 230, 255), True, 50, hls, hlk) + 26
        else:
            layer.alpha_composite(ai_avatar(64), (PX0 + 44, y))
            y += bubble(d, PX0 + 120, y, txt, fnt, 620, (226, 246, 240, 255), False, 50) + 26
    if header_note:
        hb = font(44)
        tw = hb.getlength(header_note) + 70
        d.rounded_rectangle((W / 2 - tw / 2, PY0 - 120, W / 2 + tw / 2, PY0 - 34), 43, fill=(255, 250, 240, 245),
                            outline=(236, 130, 150), width=5)
        d.text((W / 2, PY0 - 77), header_note, font=hb, fill=(220, 90, 110), anchor="mm")
    s = 0.6 + 0.4 * k
    if s < 0.999:
        layer = layer.resize((int(W * s), int(H * s)), Image.BILINEAR)
        paste(frame, layer, W / 2 - layer.width / 2, H * 0.45 - layer.height * 0.45, min(1, rot_k * 2))
    else:
        frame.alpha_composite(layer)


def progress(lid, t):
    ln = LINE[lid]
    return min(max((t - ln["start"]) / max(ln["dur"], 0.1), 0), 1)


def head_icon(name, t, size=190):
    """丸窓のしゃべる顔アイコン（口パク付き）。"""
    mouth, eyes, baby = char_state(name, t)
    im = faces.variant(name, mouth, eyes, baby)
    fx, fy = FACE[name]
    r = im.width * (0.36 if name == "rina" else 0.32)
    cx, cy = im.width * fx, im.height * fy + r * 0.25
    crop = im.crop((int(cx - r), int(cy - r), int(cx + r), int(cy + r)))
    sq = Image.new("RGBA", crop.size, (255, 250, 240, 255))
    sq.alpha_composite(crop)
    sq = sq.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size + 12, size + 12), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse((0, 0, size + 11, size + 11), fill=(255, 255, 255, 255))
    out.paste(sq, (6, 6), mask)
    return out


def phone_insert(t, lid):
    ln = LINE[lid]
    f = shoot(render_scene(t), (560, 960, 1.3)).filter(ImageFilter.GaussianBlur(12))
    f = ImageEnhance.Brightness(f).enhance(0.85)
    rk = (t - ln["start"] + 0.25) / 0.35
    if lid == "l05":
        shown = int(len(PROMPT) * min(1, progress("l05", t) * 1.7))
        hl = ease((t - ln["start"] - ln["dur"] * 0.62) / 0.6)
        phone_screen(f, t, [("me", PROMPT, shown, ("優しいインタビュアー", "質問を3つ", "1個ずつ順番に"), hl)],
                     "丸投げNG → こうお願いする！", rk)
        paste(f, head_icon("aina", t), 50, 1290)
        d = ImageDraw.Draw(f)
        d.rounded_rectangle((270, 1320, 1010, 1430), 40, fill=(255, 252, 245, 240), outline=COLORS["aina"], width=5)
        d.text((300, 1375), "役割 ＋ 目的 ＋ 1つずつ質問", font=font(44), fill=INK, anchor="lm")
        if hl > 0:
            sparkles(f, t, 540, 900, 380, 8, seed=5)
    else:
        ai_text = ln["text"].replace("\n", "")
        shown = int(len(ai_text) * min(1, progress(lid, t) * 1.05))
        phone_screen(f, t, [("me", "AI、質問して〜！", 99, (), 0), ("ai", ai_text, shown, (), 0)],
                     "AIがインタビュアーに！", rk)
        paste(f, head_icon("rina", t), 40, 1250 + math.sin(t * 8) * 6)
        pop_text(f, "わくわく", 330, 1270, ln["start"] + 0.5, t, 60, (240, 110, 150))
    return f


# ----------------------------------------------------------------- frame
INSERTS = [("l05", LINE["l05"]["start"] - 0.1, LINE["l06"]["start"] - 0.1),
           ("l11", LINE["l11"]["start"] - 0.1, LINE["l12"]["start"] - 0.05)]


def thought_cloud(f, t, t0):
    a = int(235 * ease((t - t0 - 0.4) / 0.4))
    if a <= 0:
        return
    cloud = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(cloud)
    for (x, y, r) in [(640, 640, 26), (700, 560, 38)]:
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, a))
    for (x, y, r) in [(780, 360, 120), (900, 340, 110), (850, 440, 110), (720, 440, 90), (960, 440, 80)]:
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, a))
    d.rounded_rectangle((770, 290, 920, 480), 10, fill=(250, 250, 240, a), outline=(150, 150, 170, a), width=4)
    d.text((845, 330), "企画書", font=font(36), fill=(90, 90, 120, a), anchor="mm")
    for yy in range(370, 460, 22):
        d.line((795, yy, 895, yy), fill=(180, 180, 200, a), width=5)
    f.alpha_composite(cloud)


def live_frame(t):
    cam = camera(t)
    f = shoot(render_scene(t), cam)
    L = LINE
    if t < 2.6:
        a = 1 - ease((t - 2.2) / 0.4)
        h = hook_img()
        k = max(back_out(t / 0.35), 0.05)
        hs = h.resize((int(W * k), int(300 * k)), Image.BILINEAR) if k < 0.999 else h
        paste(f, hs, W / 2 - hs.width / 2, 180 + (300 - hs.height) / 2, a)
    if L["l02"]["start"] <= t < L["l02"]["end"]:
        x, y = to_screen(anchor("satoru", FACE["satoru"]), cam)
        pop_text(f, "えぇぇ！？", min(max(x + 150, 260), 820), max(y - 200, 330), L["l02"]["start"], t, 96,
                 (90, 110, 170), rot=8)
    if L["l04"]["start"] <= t < L["l04"]["end"]:
        pop_text(f, "丸投げは", 720, 380, L["l04"]["start"] + 0.1, t, 76, (150, 110, 200), rot=4)
        pop_text(f, "ダメ！", 800, 480, L["l04"]["start"] + 0.3, t, 104, (236, 92, 108), rot=4)
        pop_text(f, "スッ", 560, 760, L["l04"]["start"] + 0.5, t, 70, (150, 120, 200), dur=0.8)
    t9 = L["l09"]["start"] + L["l09"]["dur"] * 0.55
    if t9 <= t < L["l09"]["end"]:
        sparkles(f, t, 540, 800, 480, 14, seed=9)
        pop_text(f, "AIは相棒", 540, 380, t9, t, 96, (74, 170, 150))
    if L["l06"]["start"] <= t < L["l06"]["end"]:
        pop_text(f, "ほんとだ！", 330, 420, L["l06"]["start"], t, 80, (240, 110, 150), rot=-5)
    if L["l10"]["start"] <= t < L["l10"]["end"]:
        pop_text(f, "質問して〜！", 560, 380, L["l10"]["start"], t, 80, (240, 110, 150), rot=-5)
    if L["l12"]["start"] <= t < L["l12"]["end"]:
        speed_lines(f, t, (255, 236, 200), 110)
        sparkles(f, t, 540, 700, 460, 16, seed=4)
        pop_text(f, "やばっ！", 540, 330, L["l12"]["start"], t, 130, (240, 100, 140), rot=-5)
    if L["l13"]["start"] <= t < L["l13"]["end"]:
        tint = Image.new("RGBA", (W, H), (110, 140, 200, int(70 * ease((t - L["l13"]["start"]) / 0.4))))
        f.alpha_composite(tint)
        thought_cloud(f, t, L["l13"]["start"])
        pop_text(f, "（遠い目）", 280, 1300, L["l13"]["start"] + 0.6, t, 64, (90, 110, 170))
    if L["l14"]["start"] <= t < L["l14"]["end"]:
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for i, x in enumerate(range(380, 760, 38)):
            d.line((x, 260, x, 260 + 160 + (i % 3) * 40), fill=(80, 90, 140, 120), width=6)
        f.alpha_composite(layer)
        pop_text(f, "じー……", 300, 560, L["l14"]["start"] + 0.1, t, 92, (70, 80, 120), rot=-3)
        d = ImageDraw.Draw(f)
        d.rounded_rectangle((90, 1330, 520, 1410), 40, fill=(60, 70, 96, 220))
        d.text((305, 1370), "中1・反抗期の蒼", font=font(40), fill=(255, 255, 255), anchor="mm")
    if L["l15"]["start"] <= t < L["l15"]["end"]:
        pop_text(f, "あーあー！", 540, 380, L["l15"]["start"], t, 100, (240, 120, 150), rot=-6)
        hearts(f, t, 200, 880, 1300)
    if L["l16"]["start"] - 0.1 <= t < END_T:
        pop_text(f, "ワン！", 640, 420, L["l16"]["start"], t, 120, (200, 140, 70), rot=6)
        hearts(f, t, 200, 880, 1300)
    return f


def end_overlay(f, t):
    k = t - END_T
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((60, 200, W - 60, 660), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
    d.text((W / 2, 280), "AIは「丸投げ」じゃなく", font=font(60), fill=INK, anchor="mm")
    outlined(d, (W / 2, 390), "「相棒」に。", font(104), (236, 92, 108), sw=8, anchor="mm")
    d.text((W / 2, 505), "プロンプトは保存して", font=font(44, FONT_B), fill=INK, anchor="mm")
    d.text((W / 2, 570), "親子で試してみてね！", font=font(44, FONT_B), fill=INK, anchor="mm")
    d.rounded_rectangle((180, 1660, W - 180, 1760), 50, fill=(236, 120, 140, 245))
    d.text((W / 2, 1710), "フォローで田中家の続きを見る", font=font(44), fill=(255, 255, 255), anchor="mm")
    paste(f, layer, 0, (1 - back_out(k / 0.5)) * -80, min(1, k / 0.3))
    sparkles(f, t, 540, 430, 520, 10, seed=12)


def compose(t):
    for lid, a, b in INSERTS:
        if a <= t < b:
            f = phone_insert(t, lid)
            if t - a < FADE:
                f = Image.blend(live_frame(t), f, ease((t - a) / FADE))
            return f
        if b <= t < b + FADE:
            return Image.blend(phone_insert(t, lid), live_frame(t), ease((t - b) / FADE))
    return live_frame(t)


def render_frame(i):
    t = i / FPS
    f = compose(t)
    if t < END_T:
        paste(f, title_band(), 0, 70)
        for ln in TL:
            draw_subtitle(f, ln["id"], t)
    else:
        end_overlay(f, t)
    if t > TOTAL - 0.4:
        f = Image.blend(f, Image.new("RGBA", (W, H), (255, 250, 240, 255)), ease((t - TOTAL + 0.4) / 0.4) * 0.5)
    return f.convert("RGB").tobytes()


# ----------------------------------------------------------------- audio
def tone(freq, dur, kind="pluck"):
    n = int(SR * dur)
    tt = np.arange(n) / SR
    if kind == "pluck":
        env = np.exp(-tt * 5.5) * np.minimum(1, tt * 200)
        x = (np.sin(2 * np.pi * freq * tt) + 0.3 * np.sin(4 * np.pi * freq * tt) + 0.1 * np.sin(6 * np.pi * freq * tt))
    else:
        env = np.minimum(1, tt * 3) * np.minimum(1, (dur - tt) * 3)
        x = np.sin(2 * np.pi * freq * tt) + 0.5 * np.sin(2 * np.pi * freq * 1.003 * tt)
    return x * env


def bgm(total):
    """ほのぼのした4和音ループ（C - Am - F - G）。"""
    out = np.zeros(int(SR * (total + 1)))
    bpm = 96
    beat = 60 / bpm
    prog = [[261.6, 329.6, 392.0], [220.0, 261.6, 329.6], [174.6, 220.0, 261.6], [196.0, 246.9, 293.7]]
    melody = [659.3, 587.3, 523.3, 587.3, 659.3, 784.0, 659.3, 587.3, 523.3, 440.0, 523.3, 587.3, 493.9, 587.3,
              659.3, 587.3]
    t = 0.0
    bar = 0
    while t < total:
        ch = prog[bar % 4]
        pad = sum(tone(f / 2, beat * 4, "pad") for f in ch) * 0.05
        i0 = int(t * SR)
        out[i0:i0 + len(pad)] += pad[: len(out) - i0]
        for b in range(4):
            ts = t + b * beat
            for k, f in enumerate(ch):
                x = tone(f, 1.2) * 0.06
                j = int((ts + k * 0.02) * SR)
                out[j:j + len(x)] += x[: max(0, len(out) - j)]
            m = melody[(bar % 4) * 4 + b]
            if b % 2 == 0 or bar % 2 == 1:
                x = tone(m * 2, 0.9) * 0.035
                j = int((ts + beat / 2) * SR)
                out[j:j + len(x)] += x[: max(0, len(out) - j)]
        t += beat * 4
        bar += 1
    return out[: int(SR * total)]


def sfx_whoosh():
    n = int(SR * 0.35)
    x = np.random.default_rng(1).normal(0, 1, n)
    x = np.convolve(x, np.ones(30) / 30, "same")
    return x * np.sin(np.linspace(0, np.pi, n)) * 0.25


def sfx_chime():
    return sum(tone(f, 1.0) * 0.12 for f in (1318.5, 1568.0, 2093.0))


def build_audio(path):
    mix = bgm(TOTAL) * 0.8
    duck = np.ones_like(mix)
    for ln in TL:
        if ln["audio"]:
            a, b = int(ln["start"] * SR), int((ln["start"] + ln["dur"]) * SR)
            duck[a:b] = 0.5
    duck = np.convolve(duck, np.ones(4800) / 4800, "same")
    mix *= duck

    def add(x, t):
        j = int(t * SR)
        mix[j:j + len(x)] += x[: max(0, len(mix) - j)]

    for ln in TL:
        if ln["audio"]:
            _, x = wavfile.read(BUILD / "audio" / f"{ln['id']}.wav")
            add(x.astype(float) / 32768, ln["start"])
    add(sfx_whoosh(), LINE["l02"]["start"] - 0.4)
    add(sfx_whoosh(), LINE["l04"]["start"] + 0.5)
    add(sfx_chime(), LINE["l05"]["start"] + LINE["l05"]["dur"] * 0.62)
    add(sfx_chime(), LINE["l09"]["start"] + LINE["l09"]["dur"] * 0.55)
    add(sfx_chime(), LINE["l12"]["start"])
    add(sfx_chime(), END_T)
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    wavfile.write(path, SR, (mix * 32767).astype(np.int16))


# ------------------------------------------------------------------ main
def main():
    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    if not (BUILD / "bg_living.png").exists():
        background.build(BUILD)
    if len(sys.argv) > 1 and sys.argv[1] == "--stills":
        for sec in sys.argv[2:]:
            i = int(float(sec) * FPS)
            Image.frombytes("RGB", (W, H), render_frame(i)).save(BUILD / f"still_{sec}.png")
        return
    audio = BUILD / "mix.wav"
    build_audio(audio)
    n = int(TOTAL * FPS)
    out = out_dir / "tanakake_ep01_dokusho.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool() as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(n), chunksize=6)):
            proc.stdin.write(buf)
            if k % 150 == 0:
                print(f"frame {k}/{n}", flush=True)
    proc.stdin.close()
    proc.wait()
    print("wrote", out, f"{TOTAL:.1f}s")


if __name__ == "__main__":
    main()
