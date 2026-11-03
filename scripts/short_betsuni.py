"""ショート①「『別に』しか返ってこない」（約26秒）を仕上げる。

素材: output/short01_betsuni/clips/（Klingの動画3本）、voices/（ElevenLabsの声 S1〜S6）

使い方:
    python3 scripts/short_betsuni.py   # -> output/short01_betsuni/short01_betsuni.mp4
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from assemble_ai import FPS, H, ROOT, SR, W, load_loop, logo, music_bed, sub_img, tap, message_pop, AMBIENCE
from render import FONT_B, INK, back_out, ease, font, outlined, paste, phone_screen, sparkles

KIT = ROOT / "output" / "short01_betsuni"
CLIPS, VOICES = KIT / "clips", KIT / "voices"
OUT = KIT / "short01_betsuni.mp4"
ASK = "中学生の息子が『別に』しか言わない。どうしたら話してくれる？"
AI_REPLY = "愛奈さんが中学生のころ、親にどう話しかけてほしかったですか？"

# 場面: (名前, 動画, 開始秒, 再生の速さ, 長さ)
SCENES = [
    ("door", "1_door", 0.0, 1.0, 5.0),
    ("phone", None, 0, 1.0, 5.6),
    ("think", "2_phone", 1.0, 0.6, 6.9),
    ("cookie", "3_cookie", 0.0, 1.0, 5.7),
    ("end", "3_cookie", 4.9, 1.0, 3.6),
]
# 声: (場面, ファイル, 場面の中で始まる秒, 速さ, 字幕)
VOICE = [
    ("door", "S1_aina", 0.25, 1.1, "aina", "今日どうだった？"),
    ("door", "S2_sora", 1.9, 1.0, "sora", "…別に。"),
    ("phone", "S3_ai", 0.9, 1.1, "ai", None),
    ("think", "S4_aina", 0.5, 1.12, "aina", "そうだ、私、子どもの頃そうだった。\n聞かれると、\n信用されてないみたいで嫌だった"),
    ("cookie", "S5_aina", 0.15, 1.1, "aina", "おかえり。\nこれ好きだったよね"),
    ("cookie", "S6_sora", 2.6, 1.0, "sora", "…ありがと。\nあのさ、今日さ…"),
]


def voice(name, tempo):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(VOICES / f"{name}.mp3"), "-af", f"atempo={tempo}",
                          "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def clip_frames(clip, start, speed, dur, blur=False):
    vf = (f"trim=start={start},setpts=(PTS-STARTPTS)/{speed},fps={FPS},"
          f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(CLIPS / f"{clip}.mp4"), "-vf", vf, "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n, last = W * H * 3, None
    for _ in range(round(dur * FPS)):
        buf = p.stdout.read(n)
        if len(buf) == n:
            last = Image.frombytes("RGB", (W, H), buf)
        f = last.copy()
        if blur:
            f = ImageEnhance.Brightness(f.filter(ImageFilter.GaussianBlur(14))).enhance(0.85)
        yield f.convert("RGBA")
    p.stdout.close()
    p.wait()


def text_block(f, lines, y, lt, t0=0.0, cx=W / 2):
    """白ふちの大きな文字（何行か）をポンと出す。"""
    k = back_out((lt - t0) / 0.3)
    if k <= 0:
        return
    for i, (txt, size, col) in enumerate(lines):
        im = Image.new("RGBA", (W, size + 60), (0, 0, 0, 0))
        outlined(ImageDraw.Draw(im), (W / 2, (size + 60) / 2), txt, font(size), col, sw=12, anchor="mm")
        s = max(0.05, k)
        im2 = im.resize((max(1, int(W * s)), max(1, int(im.height * s))), Image.BILINEAR) if s < 0.999 else im
        paste(f, im2, cx - im2.width / 2, y + i * (size + 24) + (im.height - im2.height) / 2,
              min(1, (lt - t0) / 0.2))


def decorate(f, scene, lt, dur, vstart):
    if scene == "door":
        if lt < 2.0:  # 1コマ目から悩みの問い
            text_block(f, [("「今日どうだった？」", 54, (120, 96, 84)), ("→「別に」…", 80, (236, 92, 108))], 780, lt, cx=740)
        if lt > 3.4:  # 愛奈の心の声
            text_block(f, [("（なんでそんな返事しか", 52, (150, 110, 200)), ("できないの…）", 52, (150, 110, 200))],
                       800, lt, 3.4, cx=740)
    elif scene == "phone":
        ai_t = lt - vstart["phone"]
        shown_me = int(len(ASK) * min(1, lt / 0.8))
        shown_ai = int(len(AI_REPLY) * min(1, max(0, ai_t) / 3.6)) if ai_t > 0 else 0
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        phone_screen(layer, lt, [("me", ASK, shown_me, (), 0), ("ai", AI_REPLY, shown_ai, (), 0)], "AIに相談してみた",
                     (lt + 0.05) / 0.35)
        f.alpha_composite(layer, (0, 170))  # 上18%（インスタの表示）を避けて少し下げる
    elif scene == "think":
        if lt < 0.6:
            text_block(f, [("はっ…！", 84, (150, 110, 200))], 520, lt, 0.05, cx=840)
    elif scene == "end":
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((60, 980, W - 60, 1420), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
        d.text((W / 2, 1060), "聞き出すより、", font=font(64), fill=INK, anchor="mm")
        outlined(d, (W / 2, 1160), "話したくなる時間を。", font(80), (236, 92, 108), sw=8, anchor="mm")
        d.text((W / 2, 1262), "田中家の続きは平日20時", font=font(44, FONT_B), fill=INK, anchor="mm")
        d.rounded_rectangle((220, 1310, W - 220, 1395), 42, fill=(236, 120, 140, 245))
        d.text((W / 2, 1352), "フォローしてね", font=font(46), fill=(255, 255, 255), anchor="mm")
        paste(f, layer, 0, (1 - back_out(lt / 0.5)) * 80, min(1, lt / 0.3))
        sparkles(f, lt, 540, 1200, 480, 10, seed=7)
        if lt > dur - 0.4:
            f = Image.blend(f, Image.new("RGBA", (W, H), (255, 250, 240, 255)), ease((lt - dur + 0.4) / 0.4) * 0.5)
    for sc, name, st, tempo, sp, text in VOICE:
        if sc == scene and text:
            vlen = VLEN[name]
            if st - 0.05 <= lt < st + vlen + 0.05:
                im = sub_img(sp, text)
                paste(f, im, 0, 1300 - im.height / 2, ease((lt - st + 0.05) / 0.15))
    if scene not in ("phone", "end"):  # ロゴは人物の顔にかからない側に（上18%より下）
        lg = small_logo()
        paste(f, lg, 30, 300)
    return f


VLEN = {}


def small_logo():
    lg = logo()
    return lg.resize((int(lg.width * 0.62), int(lg.height * 0.62)), Image.LANCZOS)


def main():
    voices = {}
    for sc, name, st, tempo, sp, text in VOICE:
        voices[name] = voice(name, tempo)
        VLEN[name] = len(voices[name]) / SR
    t0, starts = 0.0, {}
    for name, *_rest in SCENES:
        starts[name] = t0
        t0 += _rest[-1]
    total = t0
    print(f"合計 {total:.1f} 秒")

    mix = load_loop(AMBIENCE, total, 0.02) + music_bed(total, 0.05)
    vo = np.zeros_like(mix)
    duck = np.ones_like(mix)
    for sc, name, st, tempo, sp, text in VOICE:
        v = voices[name]
        j = int((starts[sc] + st) * SR)
        vo[j:j + len(v)] += v[: len(mix) - j]
        duck[j:j + len(v)] = 0.35
    duck = np.convolve(duck, np.ones(4800) / 4800, "same")
    mix = mix * duck + vo
    for i in range(14):  # スマホに打ち込む音
        j = int((starts["phone"] + 0.1 + i * 0.055) * SR)
        x = tap()
        mix[j:j + len(x)] += x
    x = message_pop()
    j = int((starts["phone"] + 0.9) * SR)
    mix[j:j + len(x)] += x
    fade = int(SR * 0.6)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    wav = KIT / "_mix.wav"
    wavfile.write(wav, SR, (mix * 32767).astype(np.int16))

    vstart = {sc: st for sc, name, st, *_ in VOICE if sc == "phone"}
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for name, clip, start, speed, dur in SCENES:
        if name == "phone":
            src = clip_frames("2_phone", 0.3, 0.2, dur, blur=True)
        else:
            src = clip_frames(clip, start, speed, dur, blur=(name == "end"))
        for i, f in enumerate(src):
            proc.stdin.write(decorate(f, name, i / FPS, dur, vstart).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
