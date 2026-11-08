"""11/10 時短AI②「これ明日まで」プリント（約16〜20秒）を仕上げる。

素材: output/jitan02_print/clips/（1_print, 2_smile）, voices/（P1〜P4）

使い方:
    python3 scripts/jitan_print.py   # -> output/jitan02_print/jitan02_print.mp4
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageFilter

from assemble_ai import AMBIENCE, FPS, H, ROOT, SR, W, load_loop, music_bed, sub_img, message_pop, tap
from render import FONT_B, INK, back_out, ease, font, outlined, paste, phone_screen, sparkles
from short_ai_ok import small_logo, text_block
from short_yuhan import bubble, frames as _frames

KIT = ROOT / "output" / "jitan02_print"
CLIPS, VOICES = KIT / "clips", KIT / "voices"
OUT = KIT / "jitan02_print.mp4"
TEMPO = 1.25

# 顔のアップ: (中心x, 中心y, 拡大率)  ※1080x1916 の座標
FACE = {"wide": (540, 958, 1.0), "all": (540, 900, 1.15), "sora": (860, 720, 1.6), "satoru": (420, 560, 1.7),
        "aina": (280, 900, 1.6), "two": (560, 820, 1.3), "smile": (540, 960, 1.0)}

ASK = "締め切りと持ち物だけ教えて"
AI = "締め切り：明日\n持ち物：上ばき・のり\n親がやること：参加の◯をつけて署名"

# 場面: (名前, 動画, 動画の開始秒, 顔, [(声, 話す人, 字幕, 場面内の開始秒)], 最低の長さ)
SCENES = [
    ("open", "1_print", 0.0, "all", [], 1.8),
    ("give", "1_print", 1.0, "two", [("P1_sora", "sora", "……これ、明日まで", 0.1)], 1.6),
    ("papa", "1_print", 2.3, "satoru", [("P2_satoru", "satoru", "…あ、俺も会社の書類、\n明日までだった", 0.05)], 0.0),
    ("phone", None, 0.0, None, [], 3.4),
    ("ask", "1_print", 3.0, "aina", [("P3_aina", "aina", "どうしたら、\n明日までにならないかな？", 0.05)], 0.0),
    ("answer", "1_print", 3.8, "sora", [("P4_sora", "sora", "……もらったら、写真送る", 0.05)], 0.0),
    ("next", "2_smile", 0.0, "smile", [], 3.2),
    ("end", "2_smile", 3.2, "smile", [], 3.0),
]


def voice(name):
    af = (f"silenceremove=start_periods=1:start_threshold=-38dB:stop_periods=-1:stop_duration=0.2:"
          f"stop_threshold=-38dB:stop_silence=0.1,atempo={TEMPO}")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(VOICES / f"{name}.mp3"), "-af", af, "-ac", "1", "-ar",
                          str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def frames(clip, start, dur, face, blur=False):
    import short_yuhan
    short_yuhan.FACE.update(FACE)
    short_yuhan.CLIPS = CLIPS
    return _frames(clip, start, dur, face, blur)


def decorate(f, sc, lt, vo):
    name, dur = sc["name"], sc["dur"]
    if name == "open":
        text_block(f, [("夜10時。", 64, (90, 110, 170)), ("「これ明日まで」", 90, (236, 92, 108))], 380, lt)
    if name == "phone":
        msgs = [("me", ASK, 99, (), 0)]
        if lt > 0.9:
            k = min(1, (lt - 0.9) / 1.4)
            msgs.append(("ai", AI.replace("\n", "　"), int(len(AI) * k), (), 0))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        phone_screen(layer, lt, msgs, "プリントを撮ってAIに", (lt + 0.05) / 0.3)
        f.alpha_composite(layer, (0, 170))
    if name == "next":
        text_block(f, [("次の日", 64, (74, 170, 150))], 380, lt)
        if lt > 0.5:
            bubble(f, "蒼：（プリントの写真）", lt - 0.5, 760, (74, 170, 150))
        if lt > 1.3:
            bubble(f, "自分で決めたことは、\nちゃんと続くんだね", lt - 1.3, 1330)
    if name == "end":
        f.alpha_composite(f.filter(ImageFilter.GaussianBlur(10)))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((60, 1000, W - 60, 1400), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
        d.text((W / 2, 1075), "プリントの管理は、本人の課題。", font=font(48), fill=INK, anchor="mm")
        outlined(d, (W / 2, 1170), "親は問いかけて、任せるだけ。", font(60), (236, 92, 108), sw=8, anchor="mm")
        d.text((W / 2, 1262), "田中家の続きは平日20時", font=font(40, FONT_B), fill=INK, anchor="mm")
        d.rounded_rectangle((220, 1300, W - 220, 1380), 40, fill=(236, 120, 140, 245))
        d.text((W / 2, 1340), "フォローしてね", font=font(44), fill=(255, 255, 255), anchor="mm")
        paste(f, layer, 0, (1 - back_out(lt / 0.4)) * 60, min(1, lt / 0.25))
        sparkles(f, lt, 540, 1190, 460, 8, seed=7)
        if lt > 0.5:
            bubble(f, "AIへのお願いの文は\nキャプションに書いたよ！保存してね", lt - 0.5, 800, (74, 170, 150))
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
        dur = max(dur, lt + 0.3)
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
            for i in range(6):
                x = tap()
                j = int((s["t0"] + 0.1 + i * 0.07) * SR)
                mix[j:j + len(x)] += x
            p = message_pop()
            k = int((s["t0"] + 0.9) * SR)
            mix[k:k + len(p)] += p
        if s["name"] == "next":
            p = message_pop()
            k = int((s["t0"] + 0.5) * SR)
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
            src = frames("1_print", 1.0, s["dur"], "all", blur=True)
        for i, f in enumerate(src):
            proc.stdin.write(decorate(f, s, i / FPS, vo).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
