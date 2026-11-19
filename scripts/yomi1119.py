"""11/19（木）20:00「音読の聞き役」（約15秒）を仕上げる。

素材: output/yomi1119/clips/（1_kitchen, 2_read, 3_smile）, voices/（X1〜X4）
使い方:
    python3 scripts/yomi1119.py
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from assemble_ai import AMBIENCE, FPS, H, ROOT, SR, W, load_loop, music_bed, sub_img, message_pop, tap
from render import FONT_B, INK, back_out, ease, font, outlined, paste, phone_screen, sparkles
from short_ai_ok import small_logo, text_block

KIT = ROOT / "output" / "yomi1119"
CLIPS, VOICES = KIT / "clips", KIT / "voices"
OUT = KIT / "yomi1119.mp4"

# 声（ファイル, 速さ）
VOICE = {"x2": ("X2_rina", 1.4), "x1": ("X1_aina", 1.45), "x4": ("X4_ai", 1.35), "x3": ("X3_rina", 1.35)}

FACE = {"wide": (540, 960, 1.0), "close": (540, 900, 1.15)}

# 場面: (名前, 動画, 動画の開始秒, 顔, [(声キー, 話す人, 字幕, 場面内の開始秒)], 最低の長さ)
SCENES = [
    ("open", "1_kitchen", 0.0, "close", [("x2", "rina", "音読聞いて！", 0.15)], 0.0),
    ("tell", "1_kitchen", 2.2, "close", [("x1", "aina", "今、手が離せないの。\nAIに聞いてもらおう", 0.1)], 0.0),
    ("read", "2_read", 0.0, "close", [], 2.4),
    ("ai", "2_read", 2.4, "close", [("x4", "ai", "「そっと」の読み方、\nやさしくて素敵でした", 0.2)], 0.0),
    ("last", "3_smile", 0.3, "wide", [("x3", "rina", "最後のとこは、ママに聞いてほしい", 0.1)], 0.0),
    ("end", "3_smile", 3.2, "wide", [], 2.2),
]


def voice(key):
    name, tempo = VOICE[key]
    af = (f"silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_duration=0.3:"
          f"stop_threshold=-45dB:stop_silence=0.2,atempo={tempo}")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(VOICES / f"{name}.mp3"), "-af", af, "-ac", "1", "-ar",
                          str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def frames(clip, start, dur, face, blur=False):
    cx, cy, z = FACE[face]
    cw, ch = int(1080 / z), int(1916 / z)
    x0 = min(max(int(cx - cw / 2), 0), 1080 - cw)
    y0 = min(max(int(cy - ch / 2), 0), 1916 - ch)
    vf = (f"trim=start={start},setpts=PTS-STARTPTS,fps={FPS},crop={cw}:{ch}:{x0}:{y0},"
          f"scale={W}:{H}:flags=lanczos,unsharp=5:5:0.5")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(CLIPS / f"{clip}.mp4"), "-vf", vf, "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n, last = W * H * 3, None
    for _ in range(round(dur * FPS)):
        buf = p.stdout.read(n)
        if len(buf) == n:
            last = Image.frombytes("RGB", (W, H), buf)
        f = last.copy()
        if clip == "3_smile":  # 昼の光のキッチンを、夕方6時の光に寄せる（暖色・少し暗く）
            r, g, b = f.split()
            f = Image.merge("RGB", (r.point(lambda v: min(255, int(v * 1.06))), g.point(lambda v: int(v * 0.88)),
                                    b.point(lambda v: int(v * 0.70))))
            f = ImageEnhance.Brightness(f).enhance(0.92)
        if blur:
            f = ImageEnhance.Brightness(f.filter(ImageFilter.GaussianBlur(14))).enhance(0.85)
        yield f.convert("RGBA")
    p.stdout.close()
    p.wait()


def caption_note(f, lt, t0, text="全文はキャプションに。保存してね"):
    if lt < t0:
        return
    fnt = font(38, FONT_B)
    w = int(fnt.getlength(text)) + 70
    im = Image.new("RGBA", (w, 84), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, 83), 42, fill=(255, 250, 240, 240), outline=(74, 170, 150), width=4)
    d.text((w / 2, 42), text, font=fnt, fill=INK, anchor="mm")
    paste(f, im, W / 2 - w / 2, 1470, ease((lt - t0) / 0.2))


def decorate(f, sc, lt, vo, gt):
    name = sc["name"]
    if gt < 3.4 and name in ("open", "tell"):  # タイトルは0秒目から全部見せる
        text_block(f, [("夕方6時", 50, (120, 96, 84))], 940, 9, instant=True)
        text_block(f, [("「音読聞いて！」でも", 56, (90, 110, 170))], 1005, 9, instant=True)
        text_block(f, [("手が離せない…どうする？", 54, (236, 92, 108))], 1090, 9, instant=True)
    if name == "ai":  # 保存バナーは中盤（AIのほめ言葉のあと）に1回
        st = sc["lines"][0][3] + len(vo["x4"]) / SR
        caption_note(f, lt, st + 0.1)
    if name == "end":
        f.alpha_composite(f.filter(ImageFilter.GaussianBlur(10)))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((60, 1000, W - 60, 1400), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
        d.text((W / 2, 1075), "手が離せない夕方は、AIを聞き役に。", font=font(44), fill=INK, anchor="mm")
        outlined(d, (W / 2, 1170), "最後は、ママに聞いてほしい。", font(58), (236, 92, 108), sw=8, anchor="mm")
        d.text((W / 2, 1262), "田中家の続きは平日20時", font=font(40, FONT_B), fill=INK, anchor="mm")
        d.rounded_rectangle((220, 1300, W - 220, 1380), 40, fill=(236, 120, 140, 245))
        d.text((W / 2, 1340), "フォローしてね", font=font(44), fill=(255, 255, 255), anchor="mm")
        paste(f, layer, 0, (1 - back_out(lt / 0.4)) * 60, min(1, lt / 0.25))
        sparkles(f, lt, 540, 1190, 460, 8, seed=7)
    for v, sp, sub, st in sc["lines"]:
        ln = len(vo[v]) / SR
        hold = 1.0 if v == "x4" else 0.1  # AIのほめ言葉は、大きな字幕で1秒長めに
        if sub and st - 0.03 <= lt < st + ln + hold:
            im = sub_img(sp, sub)
            paste(f, im, 0, 1300 - im.height / 2, ease((lt - st + 0.03) / 0.1))
    if name != "end":
        paste(f, small_logo(), 30, 300)
    return f


def main():
    vo = {k: voice(k) for k in VOICE}
    t, scenes = 0.0, []
    for name, clip, cst, face, lines, dur in SCENES:
        lt, timed = 0.0, []
        for v, sp, sub, st in lines:
            lt += st
            timed.append((v, sp, sub, lt))
            lt += len(vo[v]) / SR
        if name == "ai":
            dur = lt + 1.0  # AIのセリフのあと、字幕を1秒長めに止める
        dur = max(dur, lt + 0.2)
        scenes.append(dict(name=name, clip=clip, cst=cst, face=face, lines=timed, dur=dur, t0=t))
        t += dur
    total = t
    print(f"合計 {total:.1f} 秒")
    mix = load_loop(AMBIENCE, total, 0.02) + music_bed(total, 0.06)
    voices = np.zeros_like(mix)
    duck = np.ones_like(mix)

    def sfx(x, at):
        j = int(at * SR)
        mix[j:j + len(x)] += x[: len(mix) - j]

    for s in scenes:
        for v, sp, sub, st in s["lines"]:
            x = vo[v]
            j = int((s["t0"] + st) * SR)
            voices[j:j + len(x)] += x[: len(mix) - j]
            duck[j:j + len(x)] = 0.4
    duck = np.convolve(duck, np.ones(3000) / 3000, "same")
    mix = mix * duck + voices
    fade = int(SR * 0.5)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    wav = KIT / "_mix.wav"
    wavfile.write(wav, SR, (mix * 32767).astype(np.int16))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    gt = 0.0
    for s in scenes:
        src = frames(s["clip"], s["cst"], s["dur"], s["face"], blur=(s["name"] == "end"))
        for i, f in enumerate(src):
            proc.stdin.write(decorate(f, s, i / FPS, vo, s["t0"] + i / FPS).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
