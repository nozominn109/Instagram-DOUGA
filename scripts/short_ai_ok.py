"""ショート②「子どもにAI、使わせて大丈夫？」（約30秒）を仕上げる。

素材: output/short02_ai_ok/clips/（Klingの動画3本＋第1話のC06）、voices/（ElevenLabsの声）

使い方:
    python3 scripts/short_ai_ok.py   # -> output/short02_ai_ok/short02_ai_ok.mp4
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from assemble_ai import FPS, H, ROOT, SR, W, load_loop, logo, music_bed, sub_img, tap, message_pop, AMBIENCE
from render import FONT_B, INK, back_out, ease, font, outlined, paste, phone_screen, sparkles

KIT = ROOT / "output" / "short02_ai_ok"
CLIPS, VOICES = KIT / "clips", KIT / "voices"
OUT = KIT / "short02_ai_ok.mp4"
RULES = ["① 名前・学校・住所は入れない", "② 答えをもらうより、質問してもらう", "③ 困ったら家族に見せる"]

# 場面: (名前, 動画, 開始秒, 再生の速さ, 長さ)
SCENES = [
    ("ask", "1_ask", 0.0, 1.0, 5.8),
    ("think", "2_think", 0.0, 0.73, 9.6),
    ("together", "ep01_C06", 0.0, 1.0, 2.6),
    ("rules", "ep01_C06", 2.6, 0.6, 4.6),
    ("point", "3_point", 0.0, 1.0, 5.2),
    ("end", "3_point", 4.9, 1.0, 3.6),
]
# 声: (場面, ファイル, 場面の中で始まる秒, 速さ, 話す人, 字幕)
VOICE = [
    ("ask", "R1_rina", 0.2, 1.1, "rina", "ねえ、AI使っていい？\n友だちみんな使ってる"),
    ("ask", "A1_aina", 4.25, 1.0, "aina", "うーん…"),
    ("think", "A2_aina", 0.2, 1.15, "aina", None),
    ("together", "A3_aina", 0.15, 1.1, "aina", "じゃあ、まず\n一緒に使ってみよう！"),
    ("point", "R2_rina", 0.15, 1.1, "rina", "じゃあ、ママも\nスマホ見すぎない！"),
    ("point", "A4_aina", 3.4, 1.0, "aina", "…はい"),
]
THINK_SUBS = [(0.0, "怖いニュースもあるし、\n隠れて使われるのも不安だな……"), (4.2, "でも、\n使えないと困るだろうな……"),
              (6.6, "そっか、\n私も一緒に覚えればいいじゃん")]


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
    if scene == "ask" and lt < 2.4:  # 1コマ目から問い
        text_block(f, [("子どもにAI、", 70, (120, 96, 84)), ("使わせて大丈夫？", 96, (236, 92, 108))], 960, lt)
    elif scene == "think":
        st = [x for x in VOICE if x[0] == "think"][0][2]
        vend = st + VLEN["A2_aina"]
        for i, (t0, text) in enumerate(THINK_SUBS):
            t1 = THINK_SUBS[i + 1][0] if i + 1 < len(THINK_SUBS) else vend - st
            if st + t0 * 1.0 <= lt < st + t1 + (0.1 if i + 1 == len(THINK_SUBS) else 0):
                im = sub_img("aina", text)
                paste(f, im, 0, 1300 - im.height / 2, ease((lt - st - t0 + 0.05) / 0.15))
    elif scene == "rules":
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((60, 520, W - 60, 1400), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
        outlined(d, (W / 2, 630), "田中家のAIの約束", font(72), (236, 92, 108), sw=8, anchor="mm")
        paste(f, layer, 0, (1 - back_out(lt / 0.4)) * 60, min(1, lt / 0.25))
        for i, r in enumerate(RULES):
            t0 = 0.5 + i * 0.9
            if lt >= t0:
                im = Image.new("RGBA", (W, 140), (0, 0, 0, 0))
                ImageDraw.Draw(im).text((110, 70), r, font=font(50), fill=INK, anchor="lm")
                paste(im if False else f, im, (1 - ease((lt - t0) / 0.3)) * 60, 760 + i * 190, min(1, (lt - t0) / 0.25))
        sparkles(f, lt, 540, 960, 460, 8, seed=3)
    elif scene == "end":
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((60, 960, W - 60, 1420), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
        d.text((W / 2, 1040), "禁止でも、おまかせでもなく。", font=font(56), fill=INK, anchor="mm")
        outlined(d, (W / 2, 1150), "一緒に使って、一緒に決める。", font(66), (236, 92, 108), sw=8, anchor="mm")
        d.text((W / 2, 1258), "田中家の続きは平日20時", font=font(44, FONT_B), fill=INK, anchor="mm")
        d.rounded_rectangle((220, 1308, W - 220, 1393), 42, fill=(236, 120, 140, 245))
        d.text((W / 2, 1350), "フォローしてね", font=font(46), fill=(255, 255, 255), anchor="mm")
        paste(f, layer, 0, (1 - back_out(lt / 0.5)) * 80, min(1, lt / 0.3))
        sparkles(f, lt, 540, 1190, 480, 10, seed=7)
        if lt > dur - 0.4:
            f = Image.blend(f, Image.new("RGBA", (W, H), (255, 250, 240, 255)), ease((lt - dur + 0.4) / 0.4) * 0.5)
    for sc, name, st, tempo, sp, text in VOICE:
        if sc == scene and text:
            vlen = VLEN[name]
            if st - 0.05 <= lt < st + vlen + 0.05:
                im = sub_img(sp, text)
                paste(f, im, 0, 1300 - im.height / 2, ease((lt - st + 0.05) / 0.15))
    if scene not in ("think", "rules", "end"):
        paste(f, small_logo(), 30, 300)
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
    fade = int(SR * 0.6)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    wav = KIT / "_mix.wav"
    wavfile.write(wav, SR, (mix * 32767).astype(np.int16))

    vstart = {}
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for name, clip, start, speed, dur in SCENES:
        src = clip_frames(clip, start, speed, dur, blur=(name in ("rules", "end")))
        for i, f in enumerate(src):
            proc.stdin.write(decorate(f, name, i / FPS, dur, vstart).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
