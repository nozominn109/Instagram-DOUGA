"""【ひな形】ショート1本（10〜20秒）を仕上げる。新しい回は、このファイルをコピーして使う。

    cp scripts/short_template.py scripts/<回の名前>.py     # 例: scripts/bento1124.py
    → 下の「★ここを変える」だけを書きかえる → python3 scripts/<回の名前>.py

素材の置き場所（<回の名前> は NAME と同じ）:
    output/<回の名前>/keyframes/  … 決まった絵（ChatGPT）
    output/<回の名前>/clips/      … Klingの動画（1080x1916・5秒）。ファイル名は場面の動画名と同じ
    output/<回の名前>/voices/     … 声（ElevenLabs）。言い直しを切ったもの。蒼は tools.py sora で加工ずみのもの
できあがり: output/<回の名前>/<回の名前>.mp4

決まりごと（スキル .claude/skills/tanaka-reel を参照）:
- タイトルは0秒目から全部（動きなし・instant=True）。人物の顔・頭にかからない位置。セリフ字幕と同時に出さない
- 保存バナー「全文はキャプションに。保存してね」は中盤に1回（大事なセリフの場面には重ねない）
- AIの答え（大事な1行）は大きな字幕で2秒以上止める
- 最後は余韻のあと、セリフにかぶせずに「田中家の続きは平日20時／フォローしてね」
"""
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from assemble_ai import AMBIENCE, FPS, H, ROOT, SR, W, load_loop, music_bed, sub_img, message_pop, tap
from render import FONT_B, INK, back_out, ease, font, outlined, paste, phone_screen, sparkles
from short_ai_ok import small_logo, text_block

# ★ここを変える（1）回の名前（output/ の下のフォルダ名）
NAME = "ue1123"
KIT = ROOT / "output" / NAME
CLIPS, VOICES = KIT / "clips", KIT / "voices"
OUT = KIT / f"{NAME}.mp4"

# ★ここを変える（2）タイトル（0秒目から TITLE_SEC 秒だけ出す）。(文字, 大きさ, 色) と、上からの位置
TITLE = [("上の子ばっかり", 84, (236, 92, 108)), ("怒っちゃう", 100, (236, 92, 108))]
TITLE_Y = 1160      # 顔にかからない高さ（画面の下のほう。1437より下は避ける）
TITLE_SEC = 1.0     # タイトルを出す秒数。最初のセリフ字幕は、このあとに出す

# ★ここを変える（3）声（ファイル名（.mp3なし）, 速さ）。基準：ショートは1.2〜1.5倍。ゆっくり言わせたい所は1.0〜1.2
VOICE = {"a1": ("A1_aina", 1.25), "a2": ("A2_sora", 1.3), "a3": ("A3_aina", 1.3), "a4": ("A4_sora", 1.3),
         "a5": ("A5_aina", 1.1)}

# ★ここを変える（4）スマホ画面の文（相談とAIの答え）。答えの大きな字幕は ANS_SUB（改行は \n）
ASK = "きょうだい喧嘩で、つい上の子ばかり叱ってしまいます。どう声をかけたらいい？"
ANS = "叱る前に、決めつけず、上の子の気持ちを聞いて"
ANS_SUB = "叱る前に、決めつけず、\n上の子の気持ちを聞いて"

# ★ここを変える（5）場面: (名前, 動画, 動画の開始秒, [(声キー, 話す人, 字幕, 場面内の開始秒)], 最低の長さ)
#   話す人: aina / sora / rina / satoru / ai（字幕の色が変わる）
#   名前が "phone" の場面はスマホ画面（最初の PHONE_FACE 秒は動画をそのまま見せてから、ぼかしてスマホ）
#   名前が "nod" の場面は、声のあと NOD_TAIL 秒の余韻をとり、そこからBGMを少し下げる
#   名前が "end" の場面は、フェードでエンドカード
#   最初の場面の声の開始秒は、タイトルとかぶらないよう TITLE_SEC より少し前（0.7など）にする
SCENES = [
    ("scold", "1_scold", 0.0, [("a1", "aina", "蒼！お兄ちゃんなんだから、\n我慢しなさい！", 0.7)], 0.0),
    ("back", "2_back", 0.3, [("a2", "sora", "どうせ、俺だけ怒られるし。", 0.08)], 0.0),
    ("phone", "3_hatto", 0.5, [], 4.2),
    ("sorry", "4_sorry", 0.2, [("a3", "aina", "……ごめん。\nいきなり蒼だけ怒って。", 0.08)], 0.0),
    ("talk", "5_talk", 0.3, [("a4", "sora", "……莉奈が先に、\n俺のゲーム消した。", 0.08)], 0.0),
    ("nod", "4_sorry", 3.0, [("a5", "aina", "……そっか。", 0.08)], 2.0),
    ("end", "4_sorry", 4.2, [], 1.7),
]
PHONE_FACE = 0.6    # スマホ場面の最初に、動画（はっとした顔など）を見せる秒数
NOD_TAIL = 0.8      # 最後のセリフのあとの余韻
SUB_Y = 1330        # セリフ字幕の高さ（最初の場面はタイトルの上の 1010）

# ここから下は、ふつうは変えなくてよい


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
    if gt < TITLE_SEC:  # タイトルは0秒目から全部見せる（人物の顔にかからない位置）
        y = TITLE_Y
        for txt, size, col in TITLE:
            text_block(f, [(txt, size, col)], y, lt, instant=True)
            y += size + 26
    if name == "phone":
        if lt >= PHONE_FACE:  # 最初の PHONE_FACE 秒は、はっとした愛奈をそのまま見せ、そのあと背景をぼかしてスマホ画面を出す
            f = ImageEnhance.Brightness(f.filter(ImageFilter.GaussianBlur(14))).enhance(0.85)
            t = lt - PHONE_FACE
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            msgs = [("me", ASK, int(len(ASK) * min(1, t / 0.85)), (), 0)]
            if t > 0.9:
                msgs.append(("ai", ANS, int(len(ANS) * min(1, (t - 0.9) / 0.4)), (), 0))
            phone_screen(layer, t, msgs, "", 1.0)
            f.alpha_composite(layer, (0, 170))
            if t >= 1.0:  # 答えは、大きな字幕で約2.3秒止める
                im = sub_img("ai", ANS_SUB)
                paste(f, im, 0, 1330 - im.height / 2, ease((t - 1.0) / 0.15))
            note(f, t, 2.0, "全文はキャプションに。保存してね", y=1160)  # 保存バナーは、AI相談の後半に1回
    if name == "end":  # 余韻のあと、フェードで（セリフにかぶせない）
        k = min(1.0, max(0.0, (lt - 0.2) / 0.7))
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
        if sc["t0"] == 0:  # 最初の場面のセリフ字幕は、タイトルが消えたあとに出す
            st_show = TITLE_SEC
        else:
            st_show = st - 0.03
        if sub and max(st_show, st - 0.03) <= lt < st + ln + 0.15:
            im = sub_img(sp, sub)
            y = 1010 if sc["t0"] == 0 else SUB_Y
            paste(f, im, 0, y - im.height / 2, ease((lt - max(st_show, st - 0.03)) / 0.1))
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
            dur = lt + NOD_TAIL  # 最後のセリフのあとの余韻
        else:
            dur = max(dur, lt + 0.2)
        scenes.append(dict(name=name, clip=clip, cst=cst, lines=timed, dur=dur, t0=t))
        t += dur
    total = t
    print(f"合計 {total:.1f} 秒")
    music = music_bed(total, 0.06)
    env = np.ones_like(music)
    nod = next((s for s in scenes if s["name"] == "nod" and s["lines"]), None)
    if nod:  # 最後のセリフから、BGMを少し下げて余韻を残す
        j0 = int((nod["t0"] + nod["lines"][0][3]) * SR)
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
                sfx(tap(), s["t0"] + PHONE_FACE + 0.1 + i * 0.09)
            sfx(message_pop(), s["t0"] + PHONE_FACE + 0.9)
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
