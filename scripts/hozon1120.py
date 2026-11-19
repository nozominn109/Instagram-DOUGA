"""11/20（金）20:00 保存版「親がAIに頼むときの型、3つ」（約30秒）を仕上げる。

月〜木の完成動画から場面を切り出して使い回し、最初と最後の愛奈だけ新しく作った動画を使う。
素材: output/hozon1120/clips/（1_aina_open, 2_aina_end）, voices/（Z1, Z2）
使い回し: output/un1116/un1116.mp4（月）, output/chk1118/chk1118.mp4（水）, output/yomi1119/yomi1119.mp4（木）
使い方:
    python3 scripts/hozon1120.py   # -> output/hozon1120/hozon1120.mp4
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from assemble_ai import AMBIENCE, FPS, H, ROOT, SR, W, load_loop, music_bed, sub_img, message_pop
from render import FONT_B, INK, back_out, ease, font, outlined, paste, sparkles
from short_ai_ok import small_logo, text_block

KIT = ROOT / "output" / "hozon1120"
OUT = KIT / "hozon1120.mp4"
V = KIT / "voices"
CLIP = {"open": KIT / "clips" / "1_aina_open.mp4", "end": KIT / "clips" / "2_aina_end.mp4",
        "mon": ROOT / "output" / "un1116" / "un1116.mp4", "wed": ROOT / "output" / "chk1118" / "chk1118.mp4",
        "thu": ROOT / "output" / "yomi1119" / "yomi1119.mp4"}

# 場面: (名前, 素材, 素材の開始秒, 使う秒数, 出す長さ)  ※使う秒数より出す長さが長いときは、ゆっくり再生にする
SCENES = [
    ("open", "open", 0.0, 3.6, 3.6),
    ("t1", "thu", 7.0, 5.0, 6.8),
    ("t2", "mon", 6.5, 6.0, 7.0),
    ("t3", "wed", 3.0, 5.5, 5.8),
    ("sum", "wed", 8.6, 1.0, 1.7),
    ("end", "end", 0.0, 5.0, 6.2),
]

ZOPEN = ("Z1_aina_open", 1.3)
ZEND = ("Z2_aina_end", 1.0)


def voice(name, tempo):
    af = (f"silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_duration=0.4:"
          f"stop_threshold=-45dB:stop_silence=0.25,atempo={tempo}")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(V / f"{name}.mp3"), "-af", af, "-ac", "1", "-ar",
                          str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def frames(src, start, use, dur):
    k = dur / use  # 1より大きいとゆっくり再生
    vf = f"setpts=PTS*{k:.4f},fps={FPS},scale={W}:{H}:flags=lanczos"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(use), "-i", str(CLIP[src]), "-vf", vf,
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n, last = W * H * 3, None
    for _ in range(round(dur * FPS)):
        buf = p.stdout.read(n)
        if len(buf) == n:
            last = Image.frombytes("RGB", (W, H), buf)
        yield last.copy().convert("RGBA")
    p.stdout.close()
    p.wait()


def banner(f, lt, no, title, sub=None, color=(236, 92, 108)):
    """画面上のほう（安全な範囲）に、型の番号と題を出す。"""
    k = back_out(lt / 0.3)
    if k <= 0:
        return
    h = 215 if sub else 170
    im = Image.new("RGBA", (W - 120, h + 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 6, W - 121, h + 6), 40, fill=(70, 50, 40, 60))
    d.rounded_rectangle((0, 0, W - 121, h), 40, fill=(255, 252, 245, 245), outline=color, width=5)
    d.rounded_rectangle((26, 26, 150, h - 26), 30, fill=color)
    d.text((88, h / 2), f"型\n{no}", font=font(44, FONT_B), fill=(255, 255, 255), anchor="mm", align="center")
    d.text((180, 58 if sub else h / 2), title, font=font(46, FONT_B), fill=INK, anchor="lm")
    if sub:
        d.text((180, 138), sub, font=font(38), fill=(110, 90, 80), anchor="lm")
    s = max(0.05, k)
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
    paste(f, im, W / 2 - im.width / 2, 370, min(1, lt / 0.15))


def note(f, lt, t0, text):
    if lt < t0:
        return
    fnt = font(40, FONT_B)
    w = int(fnt.getlength(text)) + 80
    im = Image.new("RGBA", (w, 88), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, 87), 44, fill=(255, 250, 240, 245), outline=(74, 170, 150), width=4)
    d.text((w / 2, 44), text, font=fnt, fill=INK, anchor="mm")
    paste(f, im, W / 2 - w / 2, 1400, ease((lt - t0) / 0.2))


def summary(f, lt):
    """3つの型を1枚にまとめた画面（山場）。"""
    f.alpha_composite(f.filter(ImageFilter.GaussianBlur(12)))
    f.alpha_composite(Image.new("RGBA", (W, H), (255, 250, 240, 90)))
    k = back_out(lt / 0.3)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((60, 430, W - 60, 1330), 56, fill=(255, 252, 245, 244), outline=(240, 170, 150), width=6)
    d.text((W / 2, 520), "親がAIに頼むときの型、3つ", font=font(54, FONT_B), fill=INK, anchor="mm")
    rows = [("①", "「〇〇の親です」で始める"), ("②", "答えじゃなく、質問してもらう"),
            ("③", "形を決める（リスト・3行・1つだけ）")]
    cols = [(236, 92, 108), (74, 170, 150), (150, 110, 200)]
    for i, ((n, t), c) in enumerate(zip(rows, cols)):
        y = 650 + i * 190
        d.rounded_rectangle((110, y - 70, W - 110, y + 70), 36, fill=(255, 255, 255, 255), outline=c, width=5)
        d.ellipse((136, y - 46, 228, y + 46), fill=c)
        d.text((182, y), n, font=font(54, FONT_B), fill=(255, 255, 255), anchor="mm")
        fs = 40 if len(t) > 14 else 46
        d.text((260, y), t, font=font(fs, FONT_B), fill=INK, anchor="lm")
    d.text((W / 2, 1240), "保存して、明日使ってね", font=font(50, FONT_B), fill=(236, 92, 108), anchor="mm")
    paste(f, layer, 0, (1 - k) * 60, min(1, lt / 0.2))
    sparkles(f, lt, 540, 880, 420, 8, seed=3)


def decorate(f, name, lt, dur, vo):
    if name == "open":
        text_block(f, [("保存版", 70, (236, 92, 108))], 1090, lt, instant=True)
        text_block(f, [("親がAIに頼むときの型、3つ", 54, (90, 110, 170))], 1190, lt, instant=True)
    if name == "t1":
        banner(f, lt, "①", "「〇〇の親です」で始める", "例：「小学5年生の親です。」")
    if name == "t2":
        banner(f, lt, "②", "答えじゃなく、質問してもらう", "「答えは言わずに、質問して」")
        note(f, lt, 3.2, "保存して、明日使ってね")
    if name == "t3":
        banner(f, lt, "③", "形を決める", "チェックリスト・3行で・1つだけ")
    if name == "sum":
        summary(f, lt)
    if name == "end":
        k = ease((lt - 0.4) / 0.25)
        if lt < 4.2:
            im = sub_img("aina", "AIと考えるって、\nひとりで考えるより、\nちょっとだけ心強い。")
            paste(f, im, 0, 1290 - im.height / 2, k)
        else:
            e = lt - 4.2
            f.alpha_composite(f.filter(ImageFilter.GaussianBlur(10)))
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            d.rounded_rectangle((60, 1000, W - 60, 1400), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150),
                                width=6)
            outlined(d, (W / 2, 1100), "保存して、明日使ってね。", font(64), (236, 92, 108), sw=8, anchor="mm")
            d.text((W / 2, 1200), "田中家は平日20時", font=font(46, FONT_B), fill=INK, anchor="mm")
            d.rounded_rectangle((220, 1270, W - 220, 1350), 40, fill=(236, 120, 140, 245))
            d.text((W / 2, 1310), "フォローしてね", font=font(44), fill=(255, 255, 255), anchor="mm")
            paste(f, layer, 0, (1 - back_out(e / 0.4)) * 60, min(1, e / 0.25))
            sparkles(f, e, 540, 1190, 460, 8, seed=7)
    if name not in ("sum", "t1", "t2", "t3") or True:
        if name in ("open", "end") and not (name == "end" and lt >= 4.2):
            paste(f, small_logo(), 30, 300)
    return f


def main():
    vo = {"open": voice(*ZOPEN), "end": voice(*ZEND)}
    t, scenes = 0.0, []
    for name, src, st, use, dur in SCENES:
        scenes.append(dict(name=name, src=src, st=st, use=use, dur=dur, t0=t))
        t += dur
    total = t
    print(f"合計 {total:.1f} 秒")
    mix = load_loop(AMBIENCE, total, 0.02) + music_bed(total, 0.06)
    voices = np.zeros_like(mix)
    duck = np.ones_like(mix)

    def put(x, at):
        j = int(at * SR)
        voices[j:j + len(x)] += x[: len(mix) - j]
        duck[j:j + len(x)] = 0.4

    put(vo["open"], scenes[0]["t0"] + 0.2)
    put(vo["end"], scenes[-1]["t0"] + 0.5)
    for s in scenes:
        if s["name"] == "sum":
            p = message_pop()
            j = int(s["t0"] * SR)
            mix[j:j + len(p)] += p
    duck = np.convolve(duck, np.ones(3000) / 3000, "same")
    mix = mix * duck + voices
    fade = int(SR * 0.6)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    wav = KIT / "_mix.wav"
    wavfile.write(wav, SR, (mix * 32767).astype(np.int16))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for s in scenes:
        for i, f in enumerate(frames(s["src"], s["st"], s["use"], s["dur"])):
            proc.stdin.write(decorate(f, s["name"], i / FPS, s["dur"], vo).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
