"""11/23（月）20:00 ショート「上の子ばっかり怒っちゃう」（約20秒）を仕上げる。台本はウィル（Muse）。セリフは台本のまま。

素材: output/ue1123/clips/（1_scold, 2_back, 3_hatto, 4_sorry, 5_talk）, voices/（A1〜A5）
使い方:
    python3 scripts/ue1123.py   # -> output/ue1123/ue1123.mp4
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from assemble_ai import AMBIENCE, FPS, H, ROOT, SR, W, load_loop, music_bed, sub_img, message_pop, tap
from render import FONT_B, INK, back_out, ease, font, outlined, paste, phone_screen, sparkles
from short_ai_ok import small_logo, text_block

KIT = ROOT / "output" / "ue1123"
CLIPS, VOICES = KIT / "clips", KIT / "voices"
OUT = KIT / "ue1123.mp4"

# 声（ファイル, 速さ）。冒頭・後半の愛奈はゆっくり。蒼は短く小さめ
VOICE = {"a1": ("A1_aina", 1.1), "a2": ("A2_sora", 1.2), "a3": ("A3_aina", 1.1), "a4": ("A4_sora", 1.2),
         "a5": ("A5_aina", 1.0)}

ASK = "きょうだい喧嘩で、つい上の子ばかり叱ってしまいます。どう声をかけたらいい？"
ANS = "叱る前に、決めつけず、上の子の気持ちを聞いて"

# 場面: (名前, 動画, 動画の開始秒, [(声キー, 話す人, 字幕, 場面内の開始秒)], 最低の長さ)
SCENES = [
    ("scold", "1_scold", 0.0, [("a1", "aina", "蒼！お兄ちゃんなんだから、\n我慢しなさい！", 0.12)], 0.0),
    ("back", "2_back", 0.3, [("a2", "sora", "どうせ、俺だけ怒られるし。", 0.12)], 0.0),
    ("phone", "3_hatto", 0.5, [], 4.5),
    ("sorry", "4_sorry", 0.2, [("a3", "aina", "……ごめん。\nいきなり蒼だけ怒って。", 0.12)], 0.0),
    ("talk", "5_talk", 0.3, [("a4", "sora", "……莉奈が先に、\n俺のゲーム消した。", 0.12)], 0.0),
    ("nod", "4_sorry", 3.0, [("a5", "aina", "……そっか。", 0.12)], 2.2),
    ("end", "4_sorry", 4.2, [], 2.6),
]


def voice(key):
    name, tempo = VOICE[key]
    af = (f"silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_duration=0.4:"
          f"stop_threshold=-45dB:stop_silence=0.25,atempo={tempo}")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(VOICES / f"{name}.mp3"), "-af", af, "-ac", "1", "-ar",
                          str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def frames(clip, start, dur, blur=False):
    vf = f"trim=start={start},setpts=PTS-STARTPTS,fps={FPS},scale={W}:{H}:flags=lanczos"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(CLIPS / f"{clip}.mp4"), "-vf", vf, "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n, last, held = W * H * 3, None, 0
    for _ in range(round(dur * FPS)):
        buf = p.stdout.read(n)
        if len(buf) == n:
            last = Image.frombytes("RGB", (W, H), buf)
            held = 0
            f = last.copy()
        else:  # 動画が終わったあとは、止まって見えないよう、ごくゆっくり寄せる
            held += 1
            z = 1 + held * 0.0012
            f = last.resize((int(W * z), int(H * z)), Image.BILINEAR)
            f = f.crop(((f.width - W) // 2, (f.height - H) // 2, (f.width - W) // 2 + W, (f.height - H) // 2 + H))
        if blur:
            f = ImageEnhance.Brightness(f.filter(ImageFilter.GaussianBlur(14))).enhance(0.85)
        yield f.convert("RGBA")
    p.stdout.close()
    p.wait()


def note(f, lt, t0, text, y=1150):
    if lt < t0:
        return
    fnt = font(38, FONT_B)
    w = int(fnt.getlength(text)) + 70
    im = Image.new("RGBA", (w, 84), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, 83), 42, fill=(255, 250, 240, 240), outline=(74, 170, 150), width=4)
    d.text((w / 2, 42), text, font=fnt, fill=INK, anchor="mm")
    paste(f, im, W / 2 - w / 2, y, ease((lt - t0) / 0.2))


def decorate(f, sc, lt, vo, gt):
    name = sc["name"]
    if name == "scold" and gt < 3.6:  # タイトルは0秒目から全部見せる（人物の顔にかからない画面下のほう）
        text_block(f, [("上の子ばっかり", 84, (236, 92, 108))], 1160, lt, instant=True)
        text_block(f, [("怒っちゃう", 100, (236, 92, 108))], 1270, lt, instant=True)
    if name == "phone":
        if lt >= 0.9:  # 最初の約0.9秒は、はっとした愛奈をそのまま見せ、そのあと背景をぼかしてスマホ画面を出す
            f = ImageEnhance.Brightness(f.filter(ImageFilter.GaussianBlur(14))).enhance(0.85)
            t = lt - 0.9
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            msgs = [("me", ASK, int(len(ASK) * min(1, t / 1.0)), (), 0)]
            if t > 1.1:
                msgs.append(("ai", ANS, int(len(ANS) * min(1, (t - 1.1) / 0.45)), (), 0))
            phone_screen(layer, t, msgs, "", 1.0)
            f.alpha_composite(layer, (0, 170))
            if t >= 1.3:  # 答えは、大きな字幕で約2.3秒止める
                im = sub_img("ai", "叱る前に、決めつけず、\n上の子の気持ちを聞いて")
                paste(f, im, 0, 1330 - im.height / 2, ease((t - 1.3) / 0.15))
    if name == "sorry":
        note(f, lt, 0.5, "全文はキャプションに。保存してね")
    if name == "end":  # 余韻のあと、フェードで（セリフにかぶせない）
        k = min(1.0, max(0.0, (lt - 0.3) / 0.8))
        if k > 0:
            f2 = f.filter(ImageFilter.GaussianBlur(10 * k))
            f.alpha_composite(Image.blend(f.convert("RGB"), f2.convert("RGB"), k).convert("RGBA"))
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            d.rounded_rectangle((60, 1000, W - 60, 1400), 48, fill=(255, 252, 245, 238), outline=(240, 170, 150),
                                width=6)
            outlined(d, (W / 2, 1110), "田中家の続きは平日20時", font(58), (236, 92, 108), sw=8, anchor="mm")
            d.rounded_rectangle((220, 1250, W - 220, 1340), 44, fill=(236, 120, 140, 245))
            d.text((W / 2, 1295), "フォローしてね", font=font(48), fill=(255, 255, 255), anchor="mm")
            paste(f, layer, 0, 0, k)
    for v, sp, sub, st in sc["lines"]:
        ln = len(vo[v]) / SR
        if sub and st - 0.03 <= lt < st + ln + 0.15:
            im = sub_img(sp, sub)
            y = 1010 if name == "scold" else 1330
            paste(f, im, 0, y - im.height / 2, ease((lt - st + 0.03) / 0.1))
    if name != "end":
        paste(f, small_logo(), 30, 300)
    return f


def main():
    vo = {k: voice(k) for k in VOICE}
    t, scenes = 0.0, []
    for name, clip, cst, lines, dur in SCENES:
        lt, timed = 0.0, []
        for v, sp, sub, st in lines:
            lt += st
            timed.append((v, sp, sub, lt))
            lt += len(vo[v]) / SR
        if name == "nod":
            dur = lt + 0.8  # 「……そっか。」のあと約0.8秒の余韻
        else:
            dur = max(dur, lt + 0.2)
        scenes.append(dict(name=name, clip=clip, cst=cst, lines=timed, dur=dur, t0=t))
        t += dur
    total = t
    print(f"合計 {total:.1f} 秒")
    music = music_bed(total, 0.06)
    nod = next(s for s in scenes if s["name"] == "nod")
    env = np.ones_like(music)
    j0 = int((nod["t0"] + nod["lines"][0][3]) * SR)  # 「そっか」から、BGMを少し下げて余韻を残す
    ramp = int(SR * 0.6)
    env[j0:j0 + ramp] = np.linspace(1.0, 0.45, ramp)
    env[j0 + ramp:] = 0.45
    mix = load_loop(AMBIENCE, total, 0.02) + music * env
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
            for i in range(9):
                sfx(tap(), s["t0"] + 1.0 + i * 0.1)
            sfx(message_pop(), s["t0"] + 0.9 + 1.2)
    duck = np.convolve(duck, np.ones(3000) / 3000, "same")
    mix = mix * duck + voices
    fade = int(SR * 0.8)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    wav = KIT / "_mix.wav"
    wavfile.write(wav, SR, (mix * 32767).astype(np.int16))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for s in scenes:
        for i, f in enumerate(frames(s["clip"], s["cst"], s["dur"])):
            proc.stdin.write(decorate(f, s, i / FPS, vo, s["t0"] + i / FPS).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
