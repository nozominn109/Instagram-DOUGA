"""11/9「夕飯で使える親子の質問」（約17秒）を仕上げる。

素材: output/short04_yuhan/clips/（1_shiin, 2_phone, 3_talk, gohan_table=金曜の時短AI①）, voices/

使い方:
    python3 scripts/short_yuhan.py   # -> output/short04_yuhan/short04_yuhan.mp4
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from assemble_ai import AMBIENCE, FPS, H, ROOT, SR, W, load_loop, music_bed, sub_img, message_pop
from render import FONT_B, INK, back_out, ease, font, outlined, paste, phone_screen, sparkles
from short_ai_ok import small_logo, text_block

KIT = ROOT / "output" / "short04_yuhan"
CLIPS, VOICES = KIT / "clips", KIT / "voices"
OUT = KIT / "short04_yuhan.mp4"
TEMPO = 1.25

# 顔のアップ: (中心x, 中心y, 拡大率)  ※1080x1916 の座標
FACE = {"wide": (540, 958, 1.0), "table": (540, 960, 1.12), "aina": (880, 820, 1.6), "sora": (420, 860, 1.5),
        "rina": (650, 860, 1.5), "satoru": (230, 860, 1.5), "chappy": (510, 1440, 1.6), "g_sora": (420, 800, 1.5),
        "g_rina": (620, 820, 1.5)}

# 場面: (名前, 動画, 動画の開始秒, 顔, [(声, 話す人, 字幕, 場面内の開始秒)], 長さ)
SCENES = [
    ("open", "1_shiin", 0.0, "table", [], 2.0),
    ("sora", "1_shiin", 2.0, "sora", [], 0.7),
    ("rina", "1_shiin", 2.6, "rina", [], 0.7),
    ("chappy", "1_shiin", 3.2, "chappy", [], 0.7),
    ("secret", "2_phone", 0.0, "aina", [], 1.8),
    ("phone", None, 0.0, None, [("Y1_ai", "ai", None, 0.3)], 0.0),
    ("hatt", "2_phone", 2.0, "aina", [], 2.8),
    ("ask", "2_phone", 3.3, "aina", [("Y2_aina", "aina", "ねえ、1日だけ大人と子どもが\n入れかわったら、何する？", 0.05)], 0.0),
    ("talk", "3_talk", 0.0, "table", [("Y3_rina", "rina", "パパの会社行って寝る！", 0.05),
                                       ("Y4_satoru", "satoru", "バレるって！", 0.0),
                                       ("Y5_sora", "sora", "…学校休んで、一日中寝る", 0.15)], 0.0),
    ("omoi", "3_talk", 3.5, "aina", [("Y6_aina", "aina", "会話がないんじゃなくて、\nきっかけがなかっただけかも", 0.05)], 0.0),
    ("end", "3_talk", 4.6, "table", [], 3.0),
]


def voice(name):
    af = (f"silenceremove=start_periods=1:start_threshold=-38dB:stop_periods=-1:stop_duration=0.2:"
          f"stop_threshold=-38dB:stop_silence=0.1,atempo={TEMPO}")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(VOICES / f"{name}.mp3"), "-af", af, "-ac", "1", "-ar",
                          str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def frames(clip, start, dur, face, blur=False):
    cx, cy, z = FACE[face] if face else (540, 958, 1.0)
    cw, ch = int(1080 / z), int(1916 / z)
    x0 = min(max(int(cx - cw / 2), 0), 1080 - cw)
    y0 = min(max(int(cy - ch / 2), 0), 1916 - ch)
    vf = (f"trim=start={start % 4.8},setpts=PTS-STARTPTS,fps={FPS},crop={cw}:{ch}:{x0}:{y0},"
          f"scale={W}:{H}:flags=lanczos,unsharp=5:5:0.5")
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


def bubble(f, text, lt, y=640, color=(150, 110, 200)):
    k = back_out(lt / 0.25)
    if k <= 0:
        return
    fnt = font(52)
    lines = text.split("\n")
    w = int(max(fnt.getlength(s) for s in lines)) + 90
    h = 76 * len(lines) + 60
    im = Image.new("RGBA", (w, h + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w, h), 40, fill=(255, 255, 255, 240), outline=color, width=5)
    d.polygon([(w / 2 - 20, h - 2), (w / 2 + 20, h - 2), (w / 2, h + 26)], fill=(255, 255, 255, 240))
    for i, s in enumerate(lines):
        d.text((w / 2, 30 + 76 * i + 38), s, font=fnt, fill=INK, anchor="mm")
    s = max(0.05, k)
    im = im.resize((max(1, int(w * s)), max(1, int((h + 30) * s))), Image.BILINEAR)
    paste(f, im, W / 2 - im.width / 2, y - im.height / 2, min(1, lt / 0.15))


def decorate(f, sc, lt, vo):
    name, dur = sc["name"], sc["dur"]
    if name == "open":
        text_block(f, [("ごはんはできた。", 60, (120, 96, 84)), ("でも、食卓がしーん…", 76, (90, 110, 170))], 360, lt)
    if name == "secret":
        text_block(f, [("こっそりAIに相談", 68, (74, 170, 150))], 380, lt)
        if lt > 0.4:
            bubble(f, "家族と話す\nきっかけがほしい", lt - 0.4, 1260)
    if name == "phone":
        st = sc["lines"][0][3]
        ln = len(vo["Y1_ai"]) / SR
        ai = "みんなが“自分の話をしたくなる”のは、どんなときですか？"
        msgs = [("me", "家族と話すきっかけがほしい", 99, (), 0)]
        if lt >= st - 0.1:
            msgs.append(("ai", ai, int(len(ai) * min(1, (lt - st) / max(ln * 0.8, 0.1))), (), 0))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        phone_screen(layer, lt, msgs, "こっそりAIに相談", (lt + 0.05) / 0.3)
        f.alpha_composite(layer, (0, 170))
    if name in ("flash", "flash2"):
        f.alpha_composite(Image.new("RGBA", (W, H), (255, 250, 230, 70)))
        text_block(f, [("肉！" if name == "flash" else "パスタ！", 110, (236, 92, 108))], 1150, lt)
        text_block(f, [("（金曜日）", 44, (120, 96, 84))], 380, 0.5)
    if name == "hatt":
        text_block(f, [("ハッ！", 90, (150, 110, 200))], 380, lt)
        if lt > 0.25:  # 愛奈が金曜の「肉！」「パスタ！」を思い出す（吹き出し）
            bubble(f, "さっき献立決めるときは\n「肉！」「パスタ！」って\nみんな言ってたな…", lt - 0.25, 1180)
        if lt > 1.5:
            bubble(f, "“したいこと”なら、\nみんな話す！", lt - 1.5, 1430, (236, 92, 108))
    if name == "end":
        f2 = f.filter(ImageFilter.GaussianBlur(10))
        f.alpha_composite(f2)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((60, 1000, W - 60, 1400), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
        d.text((W / 2, 1075), "会話がないんじゃなくて、", font=font(52), fill=INK, anchor="mm")
        outlined(d, (W / 2, 1170), "きっかけがなかっただけ。", font(66), (236, 92, 108), sw=8, anchor="mm")
        d.text((W / 2, 1262), "田中家の続きは平日20時", font=font(40, FONT_B), fill=INK, anchor="mm")
        d.rounded_rectangle((220, 1300, W - 220, 1380), 40, fill=(236, 120, 140, 245))
        d.text((W / 2, 1340), "フォローしてね", font=font(44), fill=(255, 255, 255), anchor="mm")
        paste(f, layer, 0, (1 - back_out(lt / 0.4)) * 60, min(1, lt / 0.25))
        sparkles(f, lt, 540, 1190, 460, 8, seed=7)
        if lt > 0.5:  # キャプションの告知
            bubble(f, "AIへの相談の仕方は\nキャプションに書いたよ！保存してね", lt - 0.5, 800, (74, 170, 150))
    for v, sp, sub, st in sc["lines"]:
        ln = len(vo[v]) / SR
        if sub and st - 0.03 <= lt < st + ln + 0.08:
            im = sub_img(sp, sub)
            paste(f, im, 0, 1300 - im.height / 2, ease((lt - st + 0.03) / 0.1))
    if name not in ("phone", "end"):
        paste(f, small_logo(), 30, 300)
    return f


def main():
    vo = {v: voice(v) for *_x, lines, _d in SCENES for v, *_y in lines}
    t, scenes = 0.0, []
    for name, clip, cst, face, lines, dur in SCENES:
        lt, timed = 0.0, []
        for v, sp, sub, st in lines:
            lt += st
            timed.append((v, sp, sub, lt))
            lt += len(vo[v]) / SR
        dur = max(dur, lt + 0.25)
        scenes.append(dict(name=name, clip=clip, cst=cst, face=face, lines=timed, dur=dur, t0=t))
        t += dur
    total = t
    print(f"合計 {total:.1f} 秒")
    mix = load_loop(AMBIENCE, total, 0.02) + music_bed(total, 0.06)
    voices = np.zeros_like(mix)
    duck = np.ones_like(mix)
    for s in scenes:
        for v, sp, sub, st in s["lines"]:
            x = vo[v]
            j = int((s["t0"] + st) * SR)
            voices[j:j + len(x)] += x[: len(mix) - j]
            duck[j:j + len(x)] = 0.4
        if s["name"] == "phone":
            p = message_pop()
            k = int((s["t0"] + 0.35) * SR)
            mix[k:k + len(p)] += p
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
    for s in scenes:
        if s["clip"]:
            src = frames(s["clip"], s["cst"], s["dur"], s["face"])
        else:
            src = frames("2_phone", 1.0, s["dur"], "table", blur=True)
        for i, f in enumerate(src):
            proc.stdin.write(decorate(f, s, i / FPS, vo).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
