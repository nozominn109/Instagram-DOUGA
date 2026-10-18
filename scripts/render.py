"""田中家リール 第1話「読書感想文編」を 1080x1920 / 30fps の MP4 に書き出す。

使い方:
    python3 scripts/cutout.py      # キャラ切り出し（初回のみ）
    python3 scripts/voices.py      # セリフ音声とタイムライン
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
from story import NAMES, PROMPT

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
CHARS = ROOT / "assets" / "characters"
FONT_XB = str(ROOT / "assets" / "fonts" / "MPLUSRounded1c-ExtraBold.ttf")
FONT_B = str(ROOT / "assets" / "fonts" / "MPLUSRounded1c-Bold.ttf")
W, H, FPS = 1080, 1920, 30
SR = 48000
END_CARD = 2.8
FADE = 0.2

INK = (78, 56, 46)
COLORS = {
    "rina": (240, 128, 160), "aina": (164, 132, 206), "satoru": (104, 132, 170),
    "ai": (74, 186, 168), "sora": (60, 70, 96), "noa": (246, 150, 170), "chappy": (214, 168, 106),
}

TL = json.loads((BUILD / "timeline.json").read_text())
LINE = {x["id"]: x for x in TL}
TOTAL = TL[-1]["end"] + END_CARD


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


@lru_cache(None)
def sprite(name, height, flip=False):
    im = Image.open(CHARS / f"{name}.png").convert("RGBA")
    w = round(im.width * height / im.height)
    im = im.resize((w, height), Image.LANCZOS).filter(ImageFilter.UnsharpMask(2, 60, 2))
    return im.transpose(Image.FLIP_LEFT_RIGHT) if flip else im


@lru_cache(None)
def bg_living():
    return Image.open(BUILD / "bg_living.png").convert("RGBA")


@lru_cache(None)
def bg_blur():
    im = bg_living().filter(ImageFilter.GaussianBlur(14))
    return ImageEnhance.Brightness(im).enhance(0.82)


@lru_cache(None)
def sofa():
    return Image.open(BUILD / "sofa.png").convert("RGBA")


def zoomed(img, z, cx=0.5, cy=0.5):
    """画面中心付近を z 倍に拡大した背景（ケンバーンズ）。"""
    if z <= 1.0001:
        return img.copy()
    w, h = img.size
    cw, ch = w / z, h / z
    x0 = min(max(cx * w - cw / 2, 0), w - cw)
    y0 = min(max(cy * h - ch / 2, 0), h - ch)
    return img.resize((w, h), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def paste(frame, im, x, y, alpha=1.0):
    if alpha <= 0:
        return
    if alpha < 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    frame.alpha_composite(im, (int(round(x)), int(round(y))))


# ------------------------------------------------------------- lip "sync"
@lru_cache(None)
def envelope(lid):
    path = BUILD / "audio" / f"{lid}.wav"
    if not path.exists():
        return np.zeros(1)
    _, x = wavfile.read(path)
    x = x.astype(float) / 32768
    hop = SR // FPS
    n = len(x) // hop + 1
    env = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(n)])
    return env / (env.max() + 1e-9)


def talk(lid, t):
    """そのセリフ中のしゃべり量 0..1。"""
    ln = LINE[lid]
    i = int((t - ln["start"]) * FPS)
    env = envelope(lid)
    return float(env[i]) if 0 <= i < len(env) else 0.0


def speaking_amount(speaker, t):
    return max([talk(x["id"], t) for x in TL if x["speaker"] == speaker and x["start"] <= t < x["end"]] or [0.0])


def char(frame, name, cx, feet, height, t, flip=False, alpha=1.0, bob=1.0, speaker=None, squash=True):
    amt = speaking_amount(speaker or name, t) * bob
    im = sprite(name, height, flip)
    breath = math.sin(t * 2.4 + hash(name) % 7) * 0.006
    sy = 1 + breath + (0.025 * amt if squash else 0)
    if abs(sy - 1) > 0.002:
        im = im.resize((int(im.width * (2 - sy)), int(im.height * sy)), Image.BILINEAR)
    hop = amt * height * 0.025
    paste(frame, im, cx - im.width / 2, feet - im.height - hop, alpha)


def head(name, size):
    """丸窓用の顔アップ。"""
    boxes = {"rina": (0.12, 0.0, 0.88, 0.26), "aina": (0.20, 0.0, 0.80, 0.21), "satoru": (0.22, 0.0, 0.78, 0.2)}
    im = Image.open(CHARS / f"{name}.png").convert("RGBA")
    bx = boxes[name]
    crop = im.crop((int(bx[0] * im.width), int(bx[1] * im.height), int(bx[2] * im.width), int(bx[3] * im.height)))
    s = max(crop.size)
    sq = Image.new("RGBA", (s, s), (255, 250, 240, 255))
    sq.alpha_composite(crop, ((s - crop.width) // 2, (s - crop.height) // 2 + 6))
    sq = sq.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size + 12, size + 12), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse((0, 0, size + 11, size + 11), fill=(255, 255, 255, 255))
    out.paste(sq, (6, 6), mask)
    return out


HEADS = {}


def get_head(name, size):
    key = (name, size)
    if key not in HEADS:
        HEADS[key] = head(name, size)
    return HEADS[key]


# --------------------------------------------------------------- text
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
    if not (ln["start"] - 0.05 <= t < ln["end"]):
        return
    im = subtitle_img(lid)
    k = back_out((t - ln["start"] + 0.05) / 0.22)
    s = 0.85 + 0.15 * k
    im2 = im.resize((int(im.width * s), int(im.height * s)), Image.BILINEAR)
    paste(frame, im2, W / 2 - im2.width / 2, 1600 - im2.height / 2, min(1, k + 0.2))


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


def sparkle(d, x, y, r, col=(255, 236, 140, 255)):
    pts = []
    for i in range(8):
        a = i * math.pi / 4
        rr = r if i % 2 == 0 else r * 0.28
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    d.polygon(pts, fill=col)


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


@lru_cache(None)
def phone_small():
    im = Image.new("RGBA", (92, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, 91, 159), 18, fill=(52, 58, 80, 255))
    d.rounded_rectangle((7, 10, 84, 149), 12, fill=(200, 236, 248, 255))
    d.rounded_rectangle((14, 30, 70, 50), 8, fill=(255, 190, 205, 255))
    d.rounded_rectangle((20, 62, 78, 84), 8, fill=(255, 255, 255, 255))
    sparkle(d, 46, 115, 16, (120, 200, 190, 255))
    return im.rotate(-12, Image.BICUBIC, expand=True)


def glow_phone(frame, x, y, t):
    g = Image.new("RGBA", (220, 260), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse((10, 10, 210, 250), fill=(255, 255, 220, int(70 + 30 * math.sin(t * 6))))
    paste(frame, g.filter(ImageFilter.GaussianBlur(24)), x - 110, y - 130)
    ph = phone_small()
    paste(frame, ph, x - ph.width / 2, y - ph.height / 2)


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
    # 強調（マーカー）
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
    # ヘッダー
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


def progress(lid, t, lead=0.0):
    ln = LINE[lid]
    return min(max((t - ln["start"] + lead) / max(ln["dur"], 0.1), 0), 1)


# ----------------------------------------------------------------- shots
FEET = 1640


def shot_intro(t):
    """l01〜l03: 莉奈が丸投げ、パパがあわてる。"""
    f = zoomed(bg_living(), 1.06 - 0.03 * ease((t - 0) / 6))
    t2 = LINE["l02"]["start"]
    # パパが右からすべりこむ
    if t >= t2 - 0.3:
        k = back_out((t - t2 + 0.3) / 0.45)
        shake = math.sin(t * 60) * 6 if t2 <= t < t2 + 0.9 else 0
        char(f, "satoru", 1240 - 470 * k + shake, FEET + 20, 1080, t)
        if t2 <= t < LINE["l02"]["end"]:
            pop_text(f, "えぇぇ！？", 830, 420, t2, t, 96, (90, 110, 170), rot=8)
    char(f, "rina", 380, FEET, 960, t)
    glow_phone(f, 240, 790 - math.sin(t * 3) * 6, t)
    if t < t2:
        pop_text(f, "AIくーん！", 470, 640, LINE["l01"]["start"] + 0.1, t, 80, (240, 110, 150), rot=-6)
    if t < 2.6:
        a = 1 - ease((t - 2.2) / 0.4)
        h = hook_img()
        k = max(back_out(t / 0.35), 0.05)
        hs = h.resize((int(W * k), int(300 * k)), Image.BILINEAR) if k < 0.999 else h
        paste(f, hs, W / 2 - hs.width / 2, 180 + (300 - hs.height) / 2, a)
    return f


def shot_mama(t):
    """l04: ママ登場、スマホをスッと取り上げる。"""
    t0 = LINE["l04"]["start"]
    f = zoomed(bg_living(), 1.04)
    k = ease((t - t0 + 0.2) / 0.5)
    char(f, "rina", 760, FEET, 960, t, flip=True)
    char(f, "aina", -200 + 520 * k, FEET + 10, 1060, t)
    grab = ease((t - t0 - 0.9) / 0.4)
    px = 680 + (420 - 680) * grab
    py = 820 - math.sin(grab * math.pi) * 120
    glow_phone(f, px, py, t)
    if 0 < grab < 1:
        pop_text(f, "スッ", 560, 640, t0 + 0.9, t, 70, (150, 120, 200), dur=0.8)
    pop_text(f, "丸投げは", 300, 380, t0 + 0.2, t, 76, (150, 110, 200), rot=-4)
    pop_text(f, "ダメ！", 520, 480, t0 + 0.45, t, 104, (236, 92, 108), rot=-4)
    return f


def shot_prompt(t):
    """l05: スマホ画面アップでプロンプトを入力していく。"""
    ln = LINE["l05"]
    f = bg_blur().copy()
    p = progress("l05", t)
    shown = int(len(PROMPT) * min(1, p * 1.7))
    hl = ease((t - ln["start"] - ln["dur"] * 0.62) / 0.6)
    phone_screen(f, t, [("me", PROMPT, shown, ("優しいインタビュアー", "質問を3つ", "1個ずつ順番に"), hl)],
                 "丸投げNG → こうお願いする！", rot_k=(t - ln["start"] + 0.25) / 0.35)
    hd = get_head("aina", 190)
    bobv = talk("l05", t) * 10
    paste(f, hd, 60, 1450 - bobv)
    d = ImageDraw.Draw(f)
    d.rounded_rectangle((270, 1490, 1010, 1600), 40, fill=(255, 252, 245, 240), outline=COLORS["aina"], width=5)
    d.text((300, 1545), "役割 ＋ 目的 ＋ 1つずつ質問", font=font(44), fill=INK, anchor="lm")
    if hl > 0:
        sparkles(f, t, 540, 900, 380, 8, seed=5)
    return f


def shot_talk(t):
    """l06・l09・l10: ママと莉奈の会話。"""
    t0 = LINE["l06"]["start"]
    f = zoomed(bg_living(), 1.05 + 0.03 * ease((t - t0) / 14))
    char(f, "aina", 330, FEET + 10, 1060, t)
    char(f, "rina", 790, FEET, 960, t, flip=True)
    glow_phone(f, 420, 820, t)
    l9 = LINE["l09"]
    t9 = l9["start"] + l9["dur"] * 0.55
    if t9 <= t < l9["end"]:
        sparkles(f, t, 540, 700, 480, 14, seed=9)
        pop_text(f, "AIは相棒", 540, 360, t9, t, 96, (74, 170, 150))
    l6 = LINE["l06"]
    if l6["start"] <= t < l6["end"]:
        pop_text(f, "ほんとだ！", 790, 470, l6["start"], t, 80, (240, 110, 150), rot=5)
    l10 = LINE["l10"]
    if t >= l10["start"]:
        pop_text(f, "質問して〜！", 760, 470, l10["start"], t, 80, (240, 110, 150), rot=5)
    return f


def shot_ai(t):
    """l11: AIの返答がスマホに届く。"""
    ln = LINE["l11"]
    f = bg_blur().copy()
    ai_text = ln["text"].replace("\n", "")
    shown = int(len(ai_text) * min(1, progress("l11", t) * 1.05))
    phone_screen(f, t, [("me", "AI、質問して〜！", 99, (), 0), ("ai", ai_text, shown, (), 0)],
                 "AIがインタビュアーに！", rot_k=(t - ln["start"] + 0.25) / 0.35)
    hd = get_head("rina", 190)
    paste(f, hd, 40, 1250 + math.sin(t * 8) * 6)
    pop_text(f, "わくわく", 330, 1270, ln["start"] + 0.5, t, 60, (240, 110, 150))
    sparkles(f, t, 140, 1340, 140, 5, seed=2)
    return f


def shot_yaba(t):
    """l12: 莉奈ワクワク。"""
    ln = LINE["l12"]
    f = zoomed(bg_living(), 1.25, 0.5, 0.45)
    speed_lines(f, t, (255, 236, 200), 120)
    char(f, "rina", 540, 2200, 1700, t)
    sparkles(f, t, 540, 700, 460, 18, seed=4)
    pop_text(f, "やばっ！", 540, 330, ln["start"], t, 130, (240, 100, 140), rot=-5)
    return f


def shot_papa(t):
    """l13: パパ遠い目。"""
    ln = LINE["l13"]
    k = ease((t - ln["start"]) / ln["dur"])
    f = zoomed(bg_living(), 1.12 + 0.06 * k, 0.5, 0.4)
    tint = Image.new("RGBA", (W, H), (110, 140, 200, 70))
    f.alpha_composite(tint)
    char(f, "satoru", 470, 2050 + 0 * k, 1500, t)
    # 思い浮かべる企画書
    cloud = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(cloud)
    a = int(235 * ease((t - ln["start"] - 0.5) / 0.5))
    if a > 0:
        for (x, y, r) in [(690, 560, 28), (740, 480, 40)]:
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, a))
        for (x, y, r) in [(780, 300, 120), (900, 280, 110), (850, 380, 110), (720, 380, 90), (960, 380, 80)]:
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, a))
        d.rounded_rectangle((770, 230, 920, 420), 10, fill=(250, 250, 240, a), outline=(150, 150, 170, a), width=4)
        d.text((845, 270), "企画書", font=font(36), fill=(90, 90, 120, a), anchor="mm")
        for yy in range(310, 400, 22):
            d.line((795, yy, 895, yy), fill=(180, 180, 200, a), width=5)
        f.alpha_composite(cloud)
    pop_text(f, "（遠い目）", 300, 1230, ln["start"] + 0.8, t, 64, (90, 110, 170))
    return f


def shot_sora(t):
    """l14: 反抗期の蒼がソファの端から冷めた目で見ている。"""
    ln = LINE["l14"]
    f = zoomed(bg_living(), 1.15, 0.6, 0.55)
    char(f, "sora", 820, 1780, 1250, t, bob=0)
    sf = sofa().resize((int(sofa().width * 1.5), int(sofa().height * 1.5)), Image.LANCZOS)
    paste(f, sf, 420, 1180)
    # どよーん縦線
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, x in enumerate(range(680, 980, 34)):
        d.line((x, 300, x, 300 + 160 + (i % 3) * 40), fill=(80, 90, 140, 120), width=6)
    f.alpha_composite(layer)
    pop_text(f, "じー……", 330, 600, ln["start"] + 0.1, t, 92, (70, 80, 120), rot=-3)
    d = ImageDraw.Draw(f)
    d.rounded_rectangle((90, 760, 520, 840), 40, fill=(60, 70, 96, 220))
    d.text((305, 800), "中1・反抗期の蒼", font=font(40), fill=(255, 255, 255), anchor="mm")
    return f


def shot_pets(t):
    """l15〜l16: 希亜とチャッピーで和やかに。"""
    l15, l16 = LINE["l15"], LINE["l16"]
    f = zoomed(bg_living(), 1.18, 0.5, 0.78)
    noa_hop = abs(math.sin((t - l15["start"]) * 9)) * 30 if l15["start"] <= t < l15["end"] + 0.3 else 0
    char(f, "noa", 330, 1560 - noa_hop, 640, t, bob=0.6)
    ch_hop = abs(math.sin((t - l16["start"]) * 8)) * 60 if l16["start"] <= t < l16["start"] + 0.8 else 0
    char(f, "chappy", 770, 1560 - ch_hop, 600, t, bob=0.6, flip=True)
    pop_text(f, "あーあー！", 330, 760, l15["start"], t, 90, (240, 120, 150), rot=-6)
    pop_text(f, "ワン！", 780, 820, l16["start"], t, 110, (200, 140, 70), rot=6)
    # ハート
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(6):
        ph = (t * 0.6 + i / 6) % 1
        x = 150 + i * 160 + math.sin(t * 2 + i) * 20
        y = 1300 - ph * 700
        r = 18 + (i % 3) * 6
        a = int(200 * math.sin(ph * math.pi))
        c = (246, 140, 170, a)
        d.ellipse((x - r, y - r, x, y), fill=c)
        d.ellipse((x, y - r, x + r, y), fill=c)
        d.polygon([(x - r, y - r / 2), (x + r, y - r / 2), (x, y + r)], fill=c)
    f.alpha_composite(layer)
    return f


def shot_end(t):
    """エンドカード：家族集合＋メッセージ。"""
    t0 = TL[-1]["end"]
    k = ease((t - t0) / 0.6)
    f = zoomed(bg_living(), 1.08 - 0.04 * k)
    char(f, "sora", 830, 1500, 980, t, bob=0)
    char(f, "satoru", 250, 1500, 980, t, bob=0)
    char(f, "aina", 600, 1560, 960, t, bob=0)
    char(f, "rina", 380, 1620, 860, t, bob=0)
    char(f, "chappy", 860, 1700, 400, t, bob=0, flip=True)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((60, 220, W - 60, 700), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
    d.text((W / 2, 300), "AIは「丸投げ」じゃなく", font=font(60), fill=INK, anchor="mm")
    outlined(d, (W / 2, 410), "「相棒」に。", font(104), (236, 92, 108), sw=8, anchor="mm")
    d.text((W / 2, 530), "プロンプトは保存して", font=font(44, FONT_B), fill=INK, anchor="mm")
    d.text((W / 2, 595), "親子で試してみてね！", font=font(44, FONT_B), fill=INK, anchor="mm")
    d.rounded_rectangle((180, 1700, W - 180, 1800), 50, fill=(236, 120, 140, 245))
    d.text((W / 2, 1750), "フォローで田中家の続きを見る", font=font(44), fill=(255, 255, 255), anchor="mm")
    paste(f, layer, 0, (1 - back_out((t - t0) / 0.5)) * -80, min(1, (t - t0) / 0.3))
    sparkles(f, t, 540, 450, 520, 10, seed=12)
    return f


SHOTS = [
    (0.0, shot_intro),
    (LINE["l04"]["start"] - 0.25, shot_mama),
    (LINE["l05"]["start"] - 0.1, shot_prompt),
    (LINE["l06"]["start"] - 0.1, shot_talk),
    (LINE["l11"]["start"] - 0.1, shot_ai),
    (LINE["l12"]["start"] - 0.05, shot_yaba),
    (LINE["l13"]["start"] - 0.05, shot_papa),
    (LINE["l14"]["start"] - 0.05, shot_sora),
    (LINE["l15"]["start"] - 0.25, shot_pets),
    (TL[-1]["end"], shot_end),
]


def render_frame(i):
    t = i / FPS
    idx = max(j for j, (s, _) in enumerate(SHOTS) if s <= t)
    f = SHOTS[idx][1](t)
    # 直前のショットからのクロスフェード
    if idx > 0 and t - SHOTS[idx][0] < FADE:
        prev = SHOTS[idx - 1][1](t)
        f = Image.blend(prev, f, ease((t - SHOTS[idx][0]) / FADE))
    if t < TL[-1]["end"]:
        paste(f, title_band(), 0, 70)
        for ln in TL:
            if ln["id"] != "l05":
                draw_subtitle(f, ln["id"], t)
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
    total = TOTAL
    mix = bgm(total) * 0.9
    # セリフ中はBGMを下げる（ダッキング）
    duck = np.ones_like(mix)
    for ln in TL:
        if ln["audio"]:
            a, b = int(ln["start"] * SR), int((ln["start"] + ln["dur"]) * SR)
            duck[a:b] = 0.55
    duck = np.convolve(duck, np.ones(4800) / 4800, "same")
    mix *= duck

    def add(x, t):
        j = int(t * SR)
        mix[j:j + len(x)] += x[: max(0, len(mix) - j)]

    for ln in TL:
        if ln["audio"]:
            _, x = wavfile.read(BUILD / "audio" / f"{ln['id']}.wav")
            add(x.astype(float) / 32768, ln["start"])
    add(sfx_whoosh(), LINE["l02"]["start"] - 0.3)
    add(sfx_whoosh(), LINE["l04"]["start"] + 0.9)
    add(sfx_chime(), LINE["l05"]["start"] + LINE["l05"]["dur"] * 0.62)
    add(sfx_chime(), LINE["l09"]["start"] + LINE["l09"]["dur"] * 0.55)
    add(sfx_chime(), LINE["l12"]["start"])
    add(sfx_chime(), TL[-1]["end"])
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    wavfile.write(path, SR, (mix * 32767).astype(np.int16))


# ------------------------------------------------------------------ main
def main():
    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    if not (BUILD / "bg_living.png").exists():
        background.build(BUILD)
    audio = BUILD / "mix.wav"
    build_audio(audio)
    n = int(TOTAL * FPS)
    if len(sys.argv) > 1 and sys.argv[1] == "--stills":
        for sec in sys.argv[2:]:
            i = int(float(sec) * FPS)
            Image.frombytes("RGB", (W, H), render_frame(i)).save(BUILD / f"still_{sec}.png")
        return
    out = out_dir / "tanakake_ep01_dokusho.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool() as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(n), chunksize=8)):
            proc.stdin.write(buf)
            if k % 150 == 0:
                print(f"frame {k}/{n}", flush=True)
    proc.stdin.close()
    proc.wait()
    print("wrote", out, f"{TOTAL:.1f}s")


if __name__ == "__main__":
    main()
