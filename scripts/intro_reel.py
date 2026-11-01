"""紹介リール「はじめまして、田中家です」（約20秒）を第1話の素材から作る。

ママ（愛奈）の声は output/ep01_kit/voices_eleven/INTRO_aina.mp3 があれば入れる（なければ字幕だけの仮の版）。

使い方:
    python3 scripts/intro_reel.py   # -> output/tanakake_intro.mp4
"""
import math
import subprocess
from functools import lru_cache

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageFilter

from assemble_ai import (AMBIENCE, CLIPS, FPS, H, MUSIC, ROOT, SR, VOICES, W, load_loop, load_voice, logo,
                         music_bed, sub_img)
from render import FONT_B, INK, back_out, ease, font, outlined, paste, sparkles

OUT = ROOT / "output" / "tanakake_intro.mp4"
VOICE = VOICES / "INTRO_aina.mp3"
LINE = "AIに聞いて\n答えを教えてもらうんじゃなくて、\n一緒に考える相棒に。\n田中家の“どう使う？”、\nはじまります"

# (場面, 動画, 開始秒, 長さ, 再生の速さ)
SCENES = [
    ("hello", "END", 0.0, 3.0, 1.0),
    ("哲", None, 0, 1.15, 1.0),
    ("愛奈", None, 0, 1.15, 1.0),
    ("蒼", None, 0, 1.15, 1.0),
    ("莉奈", None, 0, 1.15, 1.0),
    ("希亜", None, 0, 1.15, 1.0),
    ("チャッピー", None, 0, 1.25, 1.0),
    ("line", "C09", 0.0, 6.0, 0.85),
    ("outro", "END", 1.0, 4.0, 1.0),
]
CHAR_FILE = {"哲": "satoru", "愛奈": "aina", "蒼": "sora", "莉奈": "rina", "希亜": "noa", "チャッピー": "chappy"}
# 名前の横に添える言葉（"left" は名前の左、"right" は右）
LABEL = {"哲": ("パパ", "left"), "愛奈": ("ママ", "left"), "蒼": ("中1", "right"), "莉奈": ("小5", "right"),
         "希亜": ("0歳", "right")}
RUBY = {"哲": "さとる", "愛奈": "あいな", "蒼": "そら", "莉奈": "りな", "希亜": "のあ", "チャッピー": ""}
# 名前を言う声（なければ鳴き声などの既存の声、それもなければ声なし）
NAME_VOICE = {"哲": ["INTRO_satoru"], "愛奈": ["INTRO_aina_name"], "蒼": ["INTRO_sora"], "莉奈": ["INTRO_rina"],
              "希亜": ["INTRO_noa", "C15_noa"], "チャッピー": ["INTRO_chappy", "C16_chappy"]}
CHAR_COLOR = {"哲": (104, 132, 170), "愛奈": (164, 132, 206), "蒼": (60, 70, 96), "莉奈": (240, 128, 160),
              "希亜": (246, 150, 170), "チャッピー": (214, 168, 106)}


def clip_frames(clip, start, dur, speed):
    vf = (f"trim=start={start}:duration={dur * speed},setpts=(PTS-STARTPTS)/{speed},fps={FPS},"
          f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(CLIPS / f"{clip}.mp4"), "-vf", vf, "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n, last = W * H * 3, None
    for _ in range(round(dur * FPS)):
        buf = p.stdout.read(n)
        if len(buf) == n:
            last = Image.frombytes("RGB", (W, H), buf)
        yield last.copy().convert("RGBA")
    p.stdout.close()
    p.wait()


@lru_cache(None)
def card_bg():
    """名前紹介の背景：リビングをぼかして、やわらかい色をかぶせたもの。"""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "1.0", "-i", str(CLIPS / "END.mp4"), "-frames:v", "1", "-vf",
                          f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    bg = Image.frombytes("RGB", (W, H), raw).filter(ImageFilter.GaussianBlur(18)).convert("RGBA")
    bg.alpha_composite(Image.new("RGBA", (W, H), (255, 248, 240, 120)))
    return bg


@lru_cache(None)
def char_img(name):
    im = Image.open(ROOT / "assets" / "characters_hires" / f"{CHAR_FILE[name]}.png").convert("RGBA")
    h = 1150 if name not in ("希亜", "チャッピー") else 820
    return im.resize((int(im.width * h / im.height), h), Image.LANCZOS)


def card_frames(name, dur):
    for i in range(round(dur * FPS)):
        lt = i / FPS
        f = card_bg().copy()
        im = char_img(name)
        k = back_out(lt / 0.3)
        s = 0.6 + 0.4 * k
        im2 = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR) if s < 0.999 else im
        bottom = 1380
        paste(f, im2, W / 2 - im2.width / 2, bottom - im2.height + math.sin(lt * 5) * 6, min(1, lt / 0.12))
        yield f


def big_text(f, lines, y, lt, size=96, color=(240, 110, 150), t0=0.0):
    k = back_out((lt - t0) / 0.35)
    if k <= 0:
        return
    for i, (txt, sz, col) in enumerate(lines):
        im = Image.new("RGBA", (W, sz + 70), (0, 0, 0, 0))
        outlined(ImageDraw.Draw(im), (W / 2, (sz + 70) / 2), txt, font(sz), col, sw=12, anchor="mm")
        s = max(0.05, k)
        im2 = im.resize((max(1, int(W * s)), max(1, int(im.height * s))), Image.BILINEAR) if s < 0.999 else im
        paste(f, im2, W / 2 - im2.width / 2, y + i * (sz + 30) + (im.height - im2.height) / 2, min(1, (lt - t0) / 0.2))


def name_tag(f, name, lt):
    x, y = W / 2, 1500
    k = back_out((lt - 0.12) / 0.25)
    fnt, rf, lf = font(120), font(48), font(60)
    nw = fnt.getlength(name)
    label, side = LABEL.get(name, ("", ""))
    lw = lf.getlength(label) + 24 if label else 0
    w = int(nw + lw * 2) + 100
    im = Image.new("RGBA", (w, 280), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = w / 2
    if RUBY[name]:
        outlined(d, (cx, 52), RUBY[name], rf, CHAR_COLOR[name], sw=8, anchor="mm")
    outlined(d, (cx, 170), name, fnt, (255, 255, 255), stroke=CHAR_COLOR[name], sw=14, anchor="mm")
    if label:
        lx = cx - nw / 2 - 16 if side == "left" else cx + nw / 2 + 16
        outlined(d, (lx, 190), label, lf, CHAR_COLOR[name], sw=9, anchor="rm" if side == "left" else "lm")
    s = max(0.05, k)
    im = im.resize((max(1, int(w * s)), max(1, int(280 * s))), Image.BILINEAR)
    paste(f, im, x - im.width / 2, y - im.height / 2, min(1, lt / 0.12))


def decorate(f, scene, lt, dur, voice_len):
    if scene == "hello":
        big_text(f, [("はじめまして、", 84, (120, 96, 84)), ("田中家です", 120, (240, 110, 150))], 1150, lt, t0=0.2)
        sparkles(f, lt, 540, 1250, 420, 10, seed=2)
    elif scene == "line":
        if lt > 0.2 and (voice_len is None or lt < 0.25 + voice_len + 0.2):
            paste(f, sub_img("aina", LINE), 0, 1360 - sub_img("aina", LINE).height / 2, ease((lt - 0.2) / 0.15))
    elif scene == "outro":
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((60, 1080, W - 60, 1580), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
        outlined(d, (W / 2 - 40, 1180), "AIは、", font(70), (120, 96, 84), sw=8, anchor="rm")
        outlined(d, (W / 2 - 40, 1172), "相棒。", font(100), (240, 110, 150), sw=9, anchor="lm")
        d.text((W / 2, 1290), "〜田中家の「どう使う？」〜", font=font(48, FONT_B), fill=INK, anchor="mm")
        d.text((W / 2, 1400), "平日20時に更新", font=font(64), fill=(236, 120, 140), anchor="mm")
        d.rounded_rectangle((200, 1640, W - 200, 1750), 55, fill=(236, 120, 140, 245))
        d.text((W / 2, 1695), "フォローしてね", font=font(56), fill=(255, 255, 255), anchor="mm")
        paste(f, layer, 0, (1 - back_out(lt / 0.5)) * 80, min(1, lt / 0.3))
        sparkles(f, lt, 540, 1320, 480, 10, seed=12)
        if lt > dur - 0.4:
            f = Image.blend(f, Image.new("RGBA", (W, H), (255, 250, 240, 255)), ease((lt - dur + 0.4) / 0.4) * 0.5)
    else:
        name_tag(f, scene, lt)
    if scene not in ("hello", "outro"):
        paste(f, logo(), 28, 64)
    return f


def main():
    voice = load_voice("INTRO_aina", 1.1) if VOICE.exists() else None
    vlen = len(voice) / SR if voice is not None else None
    scenes = list(SCENES)
    if vlen:  # 声の長さに合わせてセリフの場面の長さを決める
        i = next(i for i, s in enumerate(scenes) if s[0] == "line")
        n, c, st, _, sp = scenes[i]
        scenes[i] = (n, c, st, min(max(4.5, vlen + 0.5), 6.0 / sp), sp)
    name_voice = {}
    for i, (n, c, st, d, sp) in enumerate(scenes):
        for cand in NAME_VOICE.get(n, []):
            if (VOICES / f"{cand}.mp3").exists():
                v = load_voice(cand, 1.1)
                name_voice[n] = v
                scenes[i] = (n, c, st, max(d, 0.15 + len(v) / SR + 0.25), sp)
                break
    total = sum(s[3] for s in scenes)
    print(f"合計 {total:.1f} 秒", "（声あり）" if voice is not None else "（声なしの仮の版）")

    mix = load_loop(AMBIENCE, total, 0.02) + music_bed(total, 0.06)
    t0 = sum(s[3] for s in scenes[: next(i for i, s in enumerate(scenes) if s[0] == "line")])
    if voice is not None:
        j = int((t0 + 0.25) * SR)
        mix[j:j + len(voice)] *= 0.55
        mix[j:j + len(voice)] += voice[: len(mix) - j]
    # 最初のあいさつと最後のお知らせも愛奈の声で
    for scene_name, cand in (("hello", "INTRO_aina_hello"), ("outro", "INTRO_aina_outro")):
        if (VOICES / f"{cand}.mp3").exists():
            v = load_voice(cand, 1.1)
            i = next(i for i, sc in enumerate(scenes) if sc[0] == scene_name)
            n, c, st, d, sp = scenes[i]
            scenes[i] = (n, c, st, max(d, 0.3 + len(v) / SR + 0.4), sp)
            name_voice[scene_name] = v
    total = sum(sc[3] for sc in scenes)
    mix = load_loop(AMBIENCE, total, 0.02) + music_bed(total, 0.06)
    t0 = sum(sc[3] for sc in scenes[: next(i for i, sc in enumerate(scenes) if sc[0] == "line")])
    if voice is not None:
        j = int((t0 + 0.25) * SR)
        mix[j:j + len(voice)] *= 0.55
        mix[j:j + len(voice)] += voice[: len(mix) - j]
    t = 0.0
    for n, c, st, d, sp in scenes:
        if n in name_voice:
            v = name_voice[n]
            j = int((t + (0.3 if n in ("hello", "outro") else 0.15)) * SR)
            mix[j:j + len(v)] = mix[j:j + len(v)] * 0.55 + v[: len(mix) - j]
        t += d
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    wav = ROOT / "output" / "_intro_mix.wav"
    wavfile.write(wav, SR, (mix * 32767).astype(np.int16))

    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for scene, clip, start, dur, speed in scenes:
        src = clip_frames(clip, start, dur, speed) if clip else card_frames(scene, dur)
        for i, f in enumerate(src):
            proc.stdin.write(decorate(f, scene, i / FPS, dur, vlen).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
