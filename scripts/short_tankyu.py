"""ショート②（差し替え）「子どもにAI、使わせて大丈夫？」探究心版を仕上げる。

素材: output/short02b_tankyu/clips/（Klingの動画＋使い回し）、voices/（ElevenLabsの声）
声の長い間（ま）は短くつめ、場面の長さは声に合わせて自動で決める。

使い方:
    python3 scripts/short_tankyu.py   # -> output/short02b_tankyu/short02b_tankyu.mp4
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from assemble_ai import AMBIENCE, FPS, H, ROOT, SR, W, load_loop, music_bed, sub_img, message_pop
from render import FONT_B, INK, back_out, ease, font, outlined, paste, phone_screen, sparkles
from short_ai_ok import small_logo, text_block

KIT = ROOT / "output" / "short02b_tankyu"
CLIPS, VOICES = KIT / "clips", KIT / "voices"
OUT = KIT / "short02b_tankyu.mp4"
TEMPO = 1.1 * 1.15 * 1.1  # 決まったテンポ（声1.1倍×全体1.15倍）をさらに1.1倍（11/4 希さん）
GAP = 0.06  # セリフとセリフの間

# 場面: (名前, 動画, 動画の開始秒, [(声, 話す人, 字幕), ...], 前の余白, 後ろの余白)
SCENES = [
    ("ask", "1_ask", 0.0, [("T1_rina", "rina", "ねえ、AI使っていい？")], 0.5, 0.1),
    ("think", "2_think", 0.0, [("A2_aina", "aina", None)], 0.1, 0.15),
    ("start", "ep01_C06", 0.0, [("T2_aina", "aina", "じゃあ一緒に使ってみよう。\n莉奈がいま一番知りたいことは？"),
                                ("T3_rina", "rina", "チャッピーって、\nなんでボールが好きなの？")], 0.1, 0.15),
    ("phone", None, 0.0, [("T4_ai", "ai", None), ("T5_rina", "rina", None), ("T6_ai", "ai", None)], 0.35, 0.2),
    ("ball", "ball", 0.0, [("T7_rina", "rina", "やっぱり！\n動くものが好きなんだ！"),
                           ("T8_aina", "aina", "すごい、\n自分で確かめたね")], 0.6, 0.1),
    ("omoi", "ep01_C09", 0.0, [("T11_aina", "aina", "答えを教えてもらうより、\n自分で見つけたほうが、\nずっと楽しいよね")], 0.1, 0.25),
    ("end", "ball", 4.0, [], 3.4, 0.0),
]
THINK_SUBS = [(0.0, "怖いニュースもあるし、\n隠れて使われるのも不安だな……"), (0.4, "でも、\n使えないと困るだろうな……"),
              (0.62, "そっか、\n私も一緒に覚えればいいじゃん")]  # 声の長さに対する割合
CHAT = {"T3": ("me", "チャッピーって、なんでボールが好きなの？"), "T4_ai": ("ai", "莉奈さんは、どうしてだと思いますか？"),
        "T5_rina": ("me", "えっと…動くものを追いかけたいから？"),
        "T6_ai": ("ai", "止まっているボールと転がるボール、チャッピーはどっちに飛びつくかな？")}


def voice(name):
    """声を読み込み、決まったテンポにして、長い間（ま）を短くつめる。"""
    af = (f"silenceremove=start_periods=1:start_threshold=-35dB:stop_periods=-1:stop_duration=0.2:"
          f"stop_threshold=-35dB:stop_silence=0.12,atempo={TEMPO}")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(VOICES / f"{name}.mp3"), "-af", af, "-ac", "1", "-ar",
                          str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def probe(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(path)], capture_output=True, text=True, check=True).stdout)


def clip_frames(clip, start, dur, blur=False):
    """動画を場面の長さに合わせて流す（足りなければ少しゆっくり、それでも足りなければ最後のコマで止める）。"""
    avail = probe(CLIPS / f"{clip}.mp4") - start
    speed = min(1.15, max(0.6, avail / dur))
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


def plan():
    vo, t, out = {}, 0.0, []
    for name, clip, cst, lines, pre, post in SCENES:
        lt, timed = pre, []
        for v, sp, sub in lines:
            vo[v] = voice(v)
            timed.append((v, sp, sub, lt, len(vo[v]) / SR))
            lt += len(vo[v]) / SR + GAP
        dur = (lt - GAP if lines else lt) + post
        out.append(dict(name=name, clip=clip, cst=cst, t0=t, dur=dur, lines=timed))
        t += dur
    return out, vo, t


def decorate(f, sc, lt):
    name, dur = sc["name"], sc["dur"]
    if name == "ask":
        text_block(f, [("子どもにAI、", 70, (120, 96, 84)), ("使わせて大丈夫…？", 92, (236, 92, 108))], 960, lt)
    if name == "think":
        v, sp, sub, st, ln = sc["lines"][0]
        for i, (r, text) in enumerate(THINK_SUBS):
            a = st + r * ln
            b = st + THINK_SUBS[i + 1][0] * ln if i + 1 < len(THINK_SUBS) else st + ln + 0.1
            if a - 0.05 <= lt < b:
                im = sub_img("aina", text)
                paste(f, im, 0, 1300 - im.height / 2, ease((lt - a + 0.05) / 0.15))
    if name == "phone":
        msgs = [("me", CHAT["T3"][1], 99, (), 0)]
        for v, sp, sub, st, ln in sc["lines"]:
            who, text = CHAT[v]
            if lt >= st - 0.1:
                k = 1 if who == "me" else min(1, (lt - st) / max(ln * 0.8, 0.1))
                msgs.append((who, text, int(len(text) * k) if who == "ai" else 99, (), 0))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        phone_screen(layer, lt, msgs, "AIに聞いてみた", (lt + 0.05) / 0.35)
        f.alpha_composite(layer, (0, 170))
    if name == "ball" and lt < 0.7:
        text_block(f, [("ためしてみよう！", 80, (74, 170, 150))], 940, lt, 0.05)
    if name == "end":
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((60, 960, W - 60, 1420), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150), width=6)
        d.text((W / 2, 1040), "答えより、", font=font(60), fill=INK, anchor="mm")
        outlined(d, (W / 2, 1148), "“知りたい”を育てる。", font(78), (236, 92, 108), sw=8, anchor="mm")
        d.text((W / 2, 1250), "明日、莉奈の“なんで？”はまだ続く…", font=font(44, FONT_B), fill=INK, anchor="mm")
        d.rounded_rectangle((150, 1308, W - 150, 1393), 42, fill=(236, 120, 140, 245))
        d.text((W / 2, 1350), "続きは明日20時。フォローしてね", font=font(40), fill=(255, 255, 255), anchor="mm")
        paste(f, layer, 0, (1 - back_out(lt / 0.5)) * 80, min(1, lt / 0.3))
        sparkles(f, lt, 540, 1190, 480, 10, seed=7)
        if lt > dur - 0.4:
            f = Image.blend(f, Image.new("RGBA", (W, H), (255, 250, 240, 255)), ease((lt - dur + 0.4) / 0.4) * 0.5)
    for v, sp, sub, st, ln in sc["lines"]:
        if sub and st - 0.05 <= lt < st + ln + 0.05:
            im = sub_img(sp, sub)
            paste(f, im, 0, 1300 - im.height / 2, ease((lt - st + 0.05) / 0.15))
    if name not in ("think", "phone", "end"):
        paste(f, small_logo(), 30, 300)
    return f


def main():
    scenes, vo, total = plan()
    for s in scenes:
        print(f"{s['name']:6s} {s['t0']:5.1f}s 長さ {s['dur']:.1f}s")
    print(f"合計 {total:.1f} 秒")
    mix = load_loop(AMBIENCE, total, 0.02) + music_bed(total, 0.05)
    voices = np.zeros_like(mix)
    duck = np.ones_like(mix)
    for s in scenes:
        for v, sp, sub, st, ln in s["lines"]:
            x = vo[v]
            j = int((s["t0"] + st) * SR)
            voices[j:j + len(x)] += x[: len(mix) - j]
            duck[j:j + len(x)] = 0.35
            if v in ("T4_ai", "T6_ai"):
                p = message_pop()
                k = int((s["t0"] + st - 0.15) * SR)
                mix[k:k + len(p)] += p[: len(mix) - k]
    duck = np.convolve(duck, np.ones(4800) / 4800, "same")
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
            src = clip_frames(s["clip"], s["cst"], s["dur"], blur=(s["name"] == "end"))
        else:
            src = clip_frames("ep01_C10", 2.0, s["dur"], blur=True)
        for i, f in enumerate(src):
            proc.stdin.write(decorate(f, s, i / FPS).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
