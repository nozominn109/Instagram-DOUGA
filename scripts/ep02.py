"""11/13（金）本編「AIには話すのに、親には話さない？」を仕上げる。
※画面・表紙・キャプションには「第2話」を出さない

素材: output/ep02/clips/（1_rouka, 2_kikimimi, 3_living, 3_living_b, 4_yorumichi, 5_okaeri）, voices/（E1〜E12）

使い方:
    python3 scripts/ep02.py   # -> output/ep02/ep02.mp4
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from assemble_ai import AMBIENCE, FPS, H, ROOT, SR, W, load_loop, music_bed, sub_img, message_pop, tap
from render import FONT_B, INK, back_out, ease, font, outlined, paste, phone_screen, sparkles
from short_ai_ok import small_logo, text_block
from short_yuhan import bubble

KIT = ROOT / "output" / "ep02"
CLIPS, VOICES = KIT / "clips", KIT / "voices"
OUT = KIT / "ep02.mp4"
TEMPO = 1.3

# 顔のアップ: (中心x, 中心y, 拡大率)  ※1080x1916 の座標
FACE = {"rouka": (700, 820, 1.25), "door": (700, 700, 1.5), "papa_up": (360, 560, 1.4),
        "three": (540, 820, 1.12), "papa_aina": (420, 720, 1.4), "rina": (820, 760, 1.5), "aina": (540, 700, 1.6),
        "walk": (540, 960, 1.0), "walk_near": (520, 760, 1.35), "walk_sora": (660, 700, 1.6),
        "okaeri": (540, 960, 1.05)}

ASK = "息子が、親よりAIに相談してるみたい"
AIQ = "愛奈さんが13歳のころ、親に話せたのは、どんなときでしたか？"

# 場面: (名前, 動画, 動画の開始秒, 顔, [(声, 話す人, 字幕, 場面内の開始秒)], 最低の長さ)
SCENES = [
    ("open", "1_rouka", 0.0, "rouka", [], 2.8),
    ("nani", "2_kikimimi", 0.3, "door", [("E1_sora", "sora", "……なに？", 0.4)], 0.0),
    ("toire", "2_kikimimi", 2.2, "papa_up", [("E2_satoru", "satoru", "い、いや、トイレ……", 0.05)], 0.0),
    ("hiso", "3_living", 0.0, "papa_aina", [("E3_satoru", "satoru", "蒼、AIに相談してるっぽいぞ。\n僕たちには何も言わないのに", 0.1)], 0.0),
    ("rina", "3_living", 2.6, "rina", [("E4_rina", "rina", "AIのほうが話しやすいんじゃない？\n怒らないし", 0.05)], 0.0),
    ("phone", None, 0.0, None, [("E5_ai", "ai", None, 1.1)], 0.0),
    ("omoi", "3_living_b", 0.3, "aina", [("E6_aina", "aina", None, 0.6)], 0.0),
    ("kime", "3_living", 1.4, "aina", [("E7_aina", "aina", "聞き出すんじゃなくて、\n話したくなるまで、となりにいよう", 0.05)], 0.0),
    ("walk1", "4_yorumichi", 0.0, "walk", [("E8_aina", "aina", "コンビニ行くけど、一緒に行く？", 0.3),
                                           ("E9_sora", "sora", "…うん", 0.3)], 0.0),
    ("walk2", "4_yorumichi", 1.2, "walk_near", [("E10_sora", "sora", "……部活のこと、ずっと言えなくて", 1.1)], 0.0),
    ("walk3", "4_yorumichi", 0.4, "walk_sora", [("E11_sora", "sora", "……心配かけたくなかったんだよ", 0.4)], 0.0),
    ("walk4", "4_yorumichi", 2.6, "walk", [("E12_aina", "aina", "そっか。話してくれて、ありがとう", 0.3)], 0.0),
    ("end", "5_okaeri", 0.0, "okaeri", [], 5.2),
]


def voice(name):
    path = VOICES / f"{name}.mp3"
    if not path.exists():  # まだ届いていない声は、無音で長さだけとっておく
        return np.zeros(int(SR * 2.0))
    af = (f"silenceremove=start_periods=1:start_threshold=-40dB:stop_periods=-1:stop_duration=0.3:"
          f"stop_threshold=-40dB:stop_silence=0.2,atempo={TEMPO}")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-af", af, "-ac", "1", "-ar",
                          str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def frames(clip, start, dur, face, blur=False):
    cx, cy, z = FACE[face] if face else (540, 958, 1.0)
    cw, ch = int(1080 / z), int(1916 / z)
    x0 = min(max(int(cx - cw / 2), 0), 1080 - cw)
    y0 = min(max(int(cy - ch / 2), 0), 1916 - ch)
    vf = (f"trim=start={start},setpts=PTS-STARTPTS,fps={FPS},crop={cw}:{ch}:{x0}:{y0},"
          f"scale={W}:{H}:flags=lanczos,unsharp=5:5:0.5")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(CLIPS / f"{clip}.mp4"), "-vf", vf, "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n, last, held = W * H * 3, None, 0
    for _ in range(round(dur * FPS)):
        buf = p.stdout.read(n)
        if len(buf) == n:
            last = Image.frombytes("RGB", (W, H), buf)
            f = last.copy()
        else:  # 動画が終わったら、最後のコマをゆっくり寄せて止まって見えないようにする
            held += 1
            s = 1 + held * 0.0008
            f = last.resize((int(W * s), int(H * s)), Image.BILINEAR)
            f = f.crop(((f.width - W) // 2, (f.height - H) // 2, (f.width - W) // 2 + W, (f.height - H) // 2 + H))
        if blur:
            f = ImageEnhance.Brightness(f.filter(ImageFilter.GaussianBlur(14))).enhance(0.85)
        yield f.convert("RGBA")
    p.stdout.close()
    p.wait()


def decorate(f, sc, lt, vo):
    name = sc["name"]
    if name == "open":
        text_block(f, [("AIには話すのに、", 66, (90, 110, 170))], 1150, lt)
        text_block(f, [("親には話さない…？", 90, (236, 92, 108))], 1250, lt, 0.25)
    if name == "phone":
        st = sc["lines"][0][3]
        ln = len(vo["E5_ai"]) / SR
        msgs = [("me", ASK, int(len(ASK) * min(1, lt / 0.8)), (), 0)]
        if lt >= st - 0.1:
            msgs.append(("ai", AIQ, int(len(AIQ) * min(1, (lt - st) / max(ln * 0.8, 0.1))), (), 0))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        phone_screen(layer, lt, msgs, "こっそりAIに相談", (lt + 0.05) / 0.3)
        f.alpha_composite(layer, (0, 170))
        if lt > st + ln * 0.85:
            text_block(f, [("ハッ…", 84, (150, 110, 200))], 1630, lt, st + ln * 0.85)
    if name == "omoi":  # 心の声（吹き出し）
        st = sc["lines"][0][3]
        if lt > st - 0.2:
            bubble(f, "向かい合って聞かれると、\n言えなかった。", lt - st + 0.2, 1120, (150, 110, 200))
        if lt > st + len(vo["E6_aina"]) / SR * 0.5:
            bubble(f, "並んで歩いてるときは、\n話せたな", lt - st - len(vo["E6_aina"]) / SR * 0.5, 1400,
                   (150, 110, 200))
    if name == "end":
        f.alpha_composite(f.filter(ImageFilter.GaussianBlur(10)) if lt > 2.0 else f)
        if lt > 2.0:
            k = lt - 2.0
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            d.rounded_rectangle((60, 1000, W - 60, 1400), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150),
                                width=6)
            d.text((W / 2, 1075), "AIは、気持ちを整理する相棒。", font=font(50), fill=INK, anchor="mm")
            outlined(d, (W / 2, 1170), "最後に話せる場所は、家族。", font(62), (236, 92, 108), sw=8, anchor="mm")
            d.text((W / 2, 1262), "田中家の続きは平日20時", font=font(40, FONT_B), fill=INK, anchor="mm")
            d.rounded_rectangle((220, 1300, W - 220, 1380), 40, fill=(236, 120, 140, 245))
            d.text((W / 2, 1340), "フォローしてね", font=font(44), fill=(255, 255, 255), anchor="mm")
            paste(f, layer, 0, (1 - back_out(k / 0.4)) * 60, min(1, k / 0.25))
            sparkles(f, k, 540, 1190, 460, 8, seed=7)
            if k > 0.4:
                bubble(f, "親子で使えるAIへのお願いは\nキャプションに書いたよ！保存してね", k - 0.4, 800, (74, 170, 150))
    for v, sp, sub, st in sc["lines"]:
        ln = len(vo[v]) / SR
        if sub and st - 0.03 <= lt < st + max(ln, 0.6) + 0.1:
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
        dur = max(dur, lt + 0.35)
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
        if s["name"] == "phone":
            for i in range(8):
                sfx(tap(), s["t0"] + 0.05 + i * 0.09)
            sfx(message_pop(), s["t0"] + s["lines"][0][3] - 0.1)
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
        if s["clip"]:
            src = frames(s["clip"], s["cst"], s["dur"], s["face"])
        else:
            src = frames("3_living", 1.0, s["dur"], "three", blur=True)
        for i, f in enumerate(src):
            proc.stdin.write(decorate(f, s, i / FPS, vo).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
