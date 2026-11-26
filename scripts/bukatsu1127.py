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

# ★ここを変える（1）回の名前
NAME = "bukatsu1127"
KIT = ROOT / "output" / NAME
CLIPS, VOICES = KIT / "clips", KIT / "voices"
OUT = KIT / f"{NAME}.mp4"

# ★ここを変える（2）タイトル（0秒目から TITLE_SEC 秒）。顔にかからない画面の下
BLUE, PINK = (90, 110, 170), (236, 92, 108)
TITLE = [("好きだったのに", 80, BLUE), ("「部活やめる」って", 96, PINK), ("言い出した", 80, BLUE)]
TITLE_Y = 1100
TITLE_SEC = 0.8

# ★ここを変える（3）声（ファイル名, 速さ）。希さんが実際に作った言葉
VOICE = {"s1": ("1_sora", 1.3),   # 僕、部活やめる。
         "a2": ("2_aina", 1.0),    # えっ……（2回言うので1回目だけ）
         "a3": ("3_aina", 1.0),    # そっか、やめたいか
         "s4": ("4_sora", 1.0),    # ……別に、サッカーが嫌いになったわけじゃない
         "s5": ("5_sora", 1.0),    # ずっと試合に出られなくて。練習だけ毎日して……僕、いる意味あるのかなって
         "a6": ("6_aina", 1.0),    # 出られないの、つらかったんだね
         "s7": ("7_sora", 1.0),   # ……もうちょっとだけ、自分で考える。明日……監督に聞いてみるよ……僕には……何が足りないか（希さんが変更）
         "a8": ("8_aina", 1.0)}    # わかった（希さんが「そっか」から変更）
KEEP_PAUSE = {"s5", "s7"}   # 希さんが入れた「……」の間を残す（無音を0.9秒まで残す。蒼が考えながら話す間）

# ★ここを変える（4）スマホ画面（声なし・文字だけ。相手は「AIくん」。チャッピーとは呼ばない）
ASK = "中1の息子が突然「部活やめる」と言いました。どう声をかけたらいい？"
ANS = "まず「やめる・続ける」を決めさせず、本人の言葉をそのまま返して聞いてみて。理由は、そのあとに出てきます"
ANS_SUB = "まず「やめる・続ける」を\n決めさせず、本人の言葉を\nそのまま返して聞いてみて。\n理由は、そのあとに出てきます"

# ★ここを変える（5）場面
SCENES = [
    ("genkan", "g_sync", 0.0, [("s1", "sora", "僕、部活やめる。", 0.85),
                                  ("a2", "aina", "えっ……", 0.15)], 0.0),
    ("phone", "phone", 0.3, [], 5.0),
    ("sokka", "5_sokka", 0.0, [("a3", "aina", "そっか、やめたいか", 0.4)], 0.0),
    ("betsuni", "6_betsuni", 0.0, [("s4", "sora", "……別に、サッカーが\n嫌いになったわけじゃない", 0.8)], 0.0),
    ("honne", "honne_sync", 0.0, [("s5", "sora", "ずっと試合に出られなくて。\n練習だけ毎日して……\n僕、いる意味あるのかなって", 0.15)], 0.0),
    ("tsurai", "tsurai_sync", 0.0, [("a6", "aina", "出られないの、\nつらかったんだね", 0.2)], 0.0),
    ("ippo", "ippo_sync", 0.0, [("s7", "sora", "……もうちょっとだけ、\n自分で考える。\n明日……監督に聞いてみるよ……\n僕には……何が足りないか", 0.8)], 0.0),
    ("nod", "10_sokka2", 0.1, [("a8", "aina", "わかった", 0.3)], 0.0),
    ("end", "10_sokka2", 2.0, [], 1.5),
]
PHONE_FACE = 0.0   # 希さん：愛奈が1人でスマホを見るカットは削除。スマホ画面の寄りから
NOD_TAIL = 0.7
SUB_Y = 1330
CROP = {}
# だんだん寄せる（中心x, 中心y, 最後の倍率）。秋のベンチは、汚れていないユニフォームとひざに寄せる
ZOOM = {"3_aki": (430, 1150, 1.45)}
# 動画の使える長さ（これより後は使わず、最後のコマをゆっくり寄せる）。玄関の動画は1.6秒から愛奈が深くかがむため
CLIP_MAX = {}  # 玄関は g_sync（愛奈の口が閉じた0.5〜0.8秒をゆっくり→「えっ」で口が開く0.9〜1.6秒）で作り直し

# ここから下は、ふつうは変えなくてよい


def voice(key):
    name, tempo = VOICE[key]
    keep = 0.9 if key in KEEP_PAUSE else 0.25
    af = (f"silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_duration={keep + 0.15}:"
          f"stop_threshold=-45dB:stop_silence={keep},atempo={tempo}")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(VOICES / f"{name}.mp3"), "-af", af, "-ac", "1", "-ar",
                          str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).astype(float)
    loud = x[np.abs(x) > 0.01]
    rms = np.sqrt(np.mean(loud ** 2)) if len(loud) else 0.1
    return x * min(4.0, 10 ** (-17 / 20) / rms)  # 声の大きさをそろえる


def frames(clip, start, dur, blur=False):
    cr = ""
    if clip in CROP:
        x, y, w = CROP[clip]
        cr = f"scale={W}:{H},crop={w}:{round(w * H / W)}:{x}:{y},"
    end = f":end={start + CLIP_MAX[clip]}" if clip in CLIP_MAX else ""
    vf = f"trim=start={start}{end},setpts=PTS-STARTPTS,fps={FPS},{cr}scale={W}:{H}:flags=lanczos"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(CLIPS / f"{clip}.mp4"), "-vf", vf, "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n, last, held = W * H * 3, None, 0
    for _ in range(round(dur * FPS)):
        buf = p.stdout.read(n)
        if len(buf) == n:
            last = Image.frombytes("RGB", (W, H), buf)
            held = 0
            f = last.copy()
            if clip in ZOOM:
                zx, zy, ze = ZOOM[clip]
                z = 1 + (ze - 1) * ease(min(1.0, _ / max(1, round(dur * FPS) - 1)))
                w, h = W / z, H / z
                x0 = min(max(0, zx - w / 2), W - w)
                y0 = min(max(0, zy - h / 2), H - h)
                f = f.crop((round(x0), round(y0), round(x0 + w), round(y0 + h))).resize((W, H), Image.LANCZOS)
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


# 口と声を合わせる（ソファの場面）：話す人の声が出ているあいだだけ動画を進め、声が止まったら同じコマで待つ。
# 聞いている人の口もと（下の箱）は、場面の最初のコマのまま止める（Klingは聞いている人の口も動かすため）
# 口もとだけ止めると、首が動いたときに顔が二重にブレる（11/26 希さん）。聞いている人は頭から胸までまとめて止める
MOUTH = {"aina": (-40, 400, 560, 1160), "sora": (585, 420, 1120, 1160)}
SYNC = {"sokka": "sora", "betsuni": "aina", "honne": "aina", "tsurai": "sora", "ippo": "aina", "nod": "sora"}


def _mask(box):
    x0, y0, x1, y1 = box
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rounded_rectangle((x0 + 20, y0 + 20, x1 - 20, y1 - 20), 60, fill=255)
    return m.filter(ImageFilter.GaussianBlur(18))


def sync_frames(sc, vo):
    n = round(sc["dur"] * FPS)
    talk = np.zeros(n, bool)
    for v, sp, sub, st in sc["lines"]:
        x = vo[v]
        for i in range(n):
            a = int((i / FPS - st) * SR)
            seg = x[max(0, a - 800):max(0, a + 800)]
            if a + 800 > 0 and len(seg) and np.sqrt(np.mean(seg ** 2)) > 0.012:
                talk[i] = True
    gen = frames(sc["clip"], sc["cst"], sc["dur"] + 2)
    cur = next(gen)
    first = cur.copy()
    still = _mask(MOUTH[SYNC[sc["name"]]])
    for i in range(n):
        if talk[i] or not sc["lines"] or i == 0:
            try:
                cur = next(gen) if i else cur
            except StopIteration:
                pass
        f = Image.composite(first, cur, still) if i else cur.copy()
        z = 1 + 0.02 * i / max(1, n - 1)  # 止まって見えないよう、場面全体をごくゆっくり寄せる
        f = f.resize((round(W * z), round(H * z)), Image.BILINEAR)
        f = f.crop(((f.width - W) // 2, (f.height - H) // 2, (f.width - W) // 2 + W, (f.height - H) // 2 + H))
        yield f.convert("RGBA")
    gen.close()


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
            if t >= 1.0:  # 答えは、大きな字幕で止める（読む時間を残す）
                im = sub_img("ai", ANS_SUB)
                k = ease((t - 1.0) / 0.15)
                box = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ImageDraw.Draw(box).rounded_rectangle((50, 1250 - im.height / 2 + 10, W - 50, 1250 + im.height / 2 - 10), 36,
                                                     fill=(60, 50, 60, 190))
                paste(f, box, 0, 0, k)  # 白いスマホ画面の上でも読めるよう、答えの字幕の下に暗い帯
                paste(f, im, 0, 1250 - im.height / 2, k)
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
        note(f, lt, 0.7, "全文はキャプションに。保存してね", y=860)  # 保存バナーは、エンドカードが出てから約0.5秒後
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
        if s["name"] in SYNC:
            gen = sync_frames(s, vo)
        else:
            gen = frames(s["clip"], s["cst"], s["dur"])
        for i, f in enumerate(gen):
            proc.stdin.write(decorate(f, s, i / FPS, vo, s["t0"] + i / FPS).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    wav.unlink()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
