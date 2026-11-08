"""11/11 時短AI③「部活LINE、お礼の一文に30分」（約20秒）を仕上げる。

素材: output/jitan03_line/clips/1_line.mp4（ソファの愛奈とのぞきこむ哲）, voices/（L1〜L3）
使い回し: 蒼の回想＝output/short04_yuhan/clips/3_talk.mp4、にっこり愛奈＝output/jitan02_print/clips/2_smile.mp4

使い方:
    python3 scripts/jitan_line.py   # -> output/jitan03_line/jitan03_line.mp4
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from assemble_ai import AMBIENCE, FPS, H, ROOT, SR, W, load_loop, music_bed, sub_img, message_pop, tap
from render import FONT_B, INK, back_out, ease, font, outlined, paste, phone_screen, sparkles
from short_ai_ok import small_logo, text_block
from short_yuhan import bubble

KIT = ROOT / "output" / "jitan03_line"
VOICES = KIT / "voices"
OUT = KIT / "jitan03_line.mp4"
TEMPO = 1.25

CLIP = {"1_line": KIT / "clips" / "1_line.mp4",
        "3_talk": ROOT / "output" / "short04_yuhan" / "clips" / "3_talk.mp4",
        "2_smile": ROOT / "output" / "jitan02_print" / "clips" / "2_smile.mp4"}

# 顔のアップ: (中心x, 中心y, 拡大率)  ※1080x1916 の座標
FACE = {"all": (540, 900, 1.1), "two": (540, 760, 1.3), "aina": (720, 760, 1.5), "sora": (412, 740, 1.8),
        "smile": (540, 960, 1.0)}

ASK = "送迎のお礼の文、3行で"
DRAFT = "本日は送迎を代わっていただき、ありがとうございました。おかげさまで本当に助かりました。今後ともよろしくお願いいたします。"
AIQ = "最後に、愛奈さんの言葉でひとこと足すなら？"
ADD = "蒼が「車の中、楽しかった」って言ってました。"

# 場面: (名前, 動画, 動画の開始秒, 顔, [(声, 話す人, 字幕, 場面内の開始秒)], 最低の長さ)
SCENES = [
    ("open", "1_line", 0.0, "all", [], 2.4),
    ("papa", "1_line", 1.6, "two", [("L1_satoru", "satoru", "スタンプだけでよくない？", 0.05)], 0.0),
    ("dame", "1_line", 3.0, "aina", [("L2_aina", "aina", "ダメ！", 0.05)], 1.0),
    ("draft", None, 0.0, None, [], 3.6),
    ("aiq", None, 0.0, None, [], 2.6),
    ("sora", "3_talk", 0.5, "sora", [("L3_sora", "sora", "…車の中、楽しかった", 0.35)], 0.0),
    ("send", None, 0.0, None, [], 3.4),
    ("end", "2_smile", 0.0, "smile", [], 4.4),
]


def voice(name):
    af = (f"silenceremove=start_periods=1:start_threshold=-38dB:stop_periods=-1:stop_duration=0.2:"
          f"stop_threshold=-38dB:stop_silence=0.1,atempo={TEMPO}")
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
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(CLIP[clip]), "-vf", vf, "-f", "rawvideo",
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


def sepia(f):
    """回想：セピア色にして、ふちをぼかす。"""
    g = ImageOps.grayscale(f.convert("RGB"))
    sp = ImageOps.colorize(g, (70, 50, 35), (255, 240, 215)).convert("RGBA")
    sp = Image.blend(sp, f, 0.15)
    soft = sp.filter(ImageFilter.GaussianBlur(10))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse((-60, 200, W + 60, H - 200), fill=255)
    return Image.composite(sp, soft, mask.filter(ImageFilter.GaussianBlur(120)))


def decorate(f, sc, lt, vo):
    name = sc["name"]
    if name == "sora":
        f = sepia(f)
        text_block(f, [("（このあいだ、蒼が…）", 50, (120, 96, 84))], 380, lt)
    if name == "open":
        text_block(f, [("部活の保護者LINE、", 62, (90, 110, 170))], 1180, lt)
        text_block(f, [("お礼の一文に30分…", 84, (236, 92, 108))], 1270, lt, 0.2)
    if name in ("draft", "aiq", "send"):
        msgs = [("me", ASK, 99, (), 0)]
        if name == "draft":
            if lt > 0.8:
                msgs.append(("ai", DRAFT, int(len(DRAFT) * min(1, (lt - 0.8) / 1.6)), (), 0))
        elif name == "aiq":
            msgs.append(("ai", DRAFT, 999, (), 0))
            if lt > 0.3:
                msgs.append(("ai", AIQ, int(len(AIQ) * min(1, (lt - 0.3) / 0.8)), (), 0))
        else:
            # 下書き＋自分の言葉を打ち足して送信（打ち足した部分にマーカー）
            body = DRAFT + ADD
            shown = len(DRAFT) + int(len(ADD) * min(1, max(0, lt - 0.2) / 1.4))
            msgs = [("me", body, shown, (ADD[:-1],), ease((lt - 1.7) / 0.5))]
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        note = {"draft": "下書きはAIに", "aiq": "AIからの質問", "send": "自分の言葉をひとこと足す"}[name]
        phone_screen(layer, lt, msgs, note, (lt + 0.05) / 0.3 if name == "draft" else 1.0)
        f.alpha_composite(layer, (0, 170))
        if name == "aiq" and lt > 1.3:
            text_block(f, [("ハッ！", 90, (150, 110, 200))], 1630, lt, 1.3)
        if name == "send" and lt > 2.3:
            text_block(f, [("送信！", 80, (74, 170, 150))], 1630, lt, 2.3)
    if name == "end":
        if lt < 2.0:
            text_block(f, [("ピコン♪", 60, (74, 170, 150))], 380, lt, 0.1)
            if lt > 0.2:
                bubble(f, "蒼くん、そう言って\nくれてたんですね", lt - 0.2, 1080, (74, 170, 150))
        else:
            k = lt - 2.0
            f.alpha_composite(f.filter(ImageFilter.GaussianBlur(10)))
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            d.rounded_rectangle((60, 1000, W - 60, 1400), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150),
                                width=6)
            d.text((W / 2, 1075), "決まり文句の3行より、", font=font(50), fill=INK, anchor="mm")
            outlined(d, (W / 2, 1170), "自分の言葉のひと言。", font(66), (236, 92, 108), sw=8, anchor="mm")
            d.text((W / 2, 1262), "田中家の続きは平日20時", font=font(40, FONT_B), fill=INK, anchor="mm")
            d.rounded_rectangle((220, 1300, W - 220, 1380), 40, fill=(236, 120, 140, 245))
            d.text((W / 2, 1340), "フォローしてね", font=font(44), fill=(255, 255, 255), anchor="mm")
            paste(f, layer, 0, (1 - back_out(k / 0.4)) * 60, min(1, k / 0.25))
            sparkles(f, k, 540, 1190, 460, 8, seed=7)
            if k > 0.5:
                bubble(f, "AIへのお願いの文は\nキャプションに書いたよ！保存してね", k - 0.5, 800, (74, 170, 150))
    for v, sp, sub, st in sc["lines"]:
        ln = len(vo[v]) / SR
        if sub and st - 0.03 <= lt < st + max(ln, 0.6) + 0.1:
            im = sub_img(sp, sub)
            paste(f, im, 0, 1300 - im.height / 2, ease((lt - st + 0.03) / 0.1))
    if name not in ("draft", "aiq", "send", "end"):
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
        if s["name"] == "draft":
            for i in range(5):
                sfx(tap(), s["t0"] + 0.1 + i * 0.07)
            sfx(message_pop(), s["t0"] + 0.8)
        if s["name"] == "aiq":
            sfx(message_pop(), s["t0"] + 0.3)
        if s["name"] == "send":
            for i in range(10):
                sfx(tap(), s["t0"] + 0.2 + i * 0.13)
            sfx(message_pop(), s["t0"] + 2.3)
        if s["name"] == "end":
            sfx(message_pop(), s["t0"] + 0.1)
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
            src = frames("1_line", 1.0, s["dur"], "all", blur=True)
        for i, f in enumerate(src):
            proc.stdin.write(decorate(f, s, i / FPS, vo).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
