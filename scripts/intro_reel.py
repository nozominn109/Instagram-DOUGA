"""紹介リール「はじめまして、田中家です」（約20秒）を第1話の素材から作る。

ママ（愛奈）の声は output/ep01_kit/voices_eleven/INTRO_aina.mp3 があれば入れる（なければ字幕だけの仮の版）。

使い方:
    python3 scripts/intro_reel.py   # -> output/tanakake_intro.mp4
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw

from assemble_ai import (AMBIENCE, CLIPS, FPS, H, MUSIC, ROOT, SR, VOICES, W, load_loop, load_voice, logo,
                         music_bed, sub_img)
from render import FONT_B, INK, back_out, ease, font, outlined, paste, sparkles

OUT = ROOT / "output" / "tanakake_intro.mp4"
VOICE = VOICES / "INTRO_aina.mp3"
LINE = "AIに聞いて\n答えを教えてもらうんじゃなくて、\n一緒に考える相棒に。\n田中家の“どう使う？”、\nはじまります"

# (場面, 動画, 開始秒, 長さ, 再生の速さ)
SCENES = [
    ("hello", "END", 0.0, 3.0, 1.0),
    ("哲", "C02", 0.4, 1.15, 1.0),
    ("愛奈", "C07", 0.2, 1.15, 1.0),
    ("蒼", "C14", 3.0, 1.15, 1.0),
    ("莉奈", "C12", 0.6, 1.15, 1.0),
    ("希亜", "C15_C16", 0.2, 1.15, 1.0),
    ("チャッピー", "C15_C16", 2.6, 1.25, 1.0),
    ("line", "C09", 0.0, 6.0, 0.85),
    ("outro", "END", 1.0, 4.0, 1.0),
]
NAME_POS = {"哲": (300, 1150), "愛奈": (300, 1150), "蒼": (760, 1180), "莉奈": (780, 1150), "希亜": (300, 1120),
            "チャッピー": (760, 1120)}


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
    x, y = NAME_POS[name]
    k = back_out(lt / 0.25)
    fnt = font(110)
    w = int(fnt.getlength(name)) + 80
    im = Image.new("RGBA", (w, 200), (0, 0, 0, 0))
    outlined(ImageDraw.Draw(im), (w / 2, 100), name, fnt, (255, 255, 255), stroke=(240, 110, 150), sw=12, anchor="mm")
    s = max(0.05, k)
    im = im.resize((max(1, int(w * s)), max(1, int(200 * s))), Image.BILINEAR)
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
    total = sum(s[3] for s in scenes)
    print(f"合計 {total:.1f} 秒", "（声あり）" if voice is not None else "（声なしの仮の版）")

    mix = load_loop(AMBIENCE, total, 0.02) + music_bed(total, 0.06)
    t0 = sum(s[3] for s in scenes[: next(i for i, s in enumerate(scenes) if s[0] == "line")])
    if voice is not None:
        j = int((t0 + 0.25) * SR)
        mix[j:j + len(voice)] *= 0.55
        mix[j:j + len(voice)] += voice[: len(mix) - j]
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    wav = ROOT / "output" / "_intro_mix.wav"
    wavfile.write(wav, SR, (mix * 32767).astype(np.int16))

    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for scene, clip, start, dur, speed in scenes:
        for i, f in enumerate(clip_frames(clip, start, dur, speed)):
            proc.stdin.write(decorate(f, scene, i / FPS, dur, vlen).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
