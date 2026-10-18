# 第1話「読書感想文編」 動画生成AI 制作キット

人気のアニメ系リールに近い、キャラが自然に動き表情が変わるクオリティを目指すための手順書です。
**映像は動画生成AIで作り、音声・字幕・スマホ画面・エンドカード・仕上げはこのリポジトリで行う**分担にしています。

## 全体の流れ

1. **キャラの一貫性を作る**：画像AIにキャラシート（`assets/characters_sheet.webp`）を読み込ませ、下の「共通スタイル」でカットごとの1枚絵（キーフレーム）を作る
2. **動かす**：キーフレームを画像→動画AIに入れ、カットごとの「動きプロンプト」で3〜6秒の動画にする
3. **口パク**：しゃべるカットは `output/ep01_kit/voices/Cxx.wav` を動画AIのリップシンク機能に入れる
4. **組み立て**：できた動画を `output/ep01_kit/clips/C01.mp4` のように置いて `python3 scripts/assemble.py`
   → 字幕・タイトル・スマホ画面・エンドカード・BGM入りの `output/tanakake_ep01_dokusho_ai.mp4` ができる
   （素材が無いカットは今のアニメのまま。1カットずつ差し替えていけます）

### おすすめツール（2026年時点の代表例）

| 工程 | ツール例 | メモ |
|---|---|---|
| キーフレーム画像 | ChatGPT（画像生成）、Midjourney（`--cref`/Omni Reference）、Nano Banana（Gemini） | キャラシートを参照画像として毎回添付。同じチャットで続けて作るとブレにくい |
| 画像→動画 | Kling、Hailuo（MiniMax）、Google Veo、Runway、Vidu | 「開始フレーム」にキーフレームを入れる。1カット3〜6秒で十分 |
| リップシンク | Kling のリップシンク、Hedra、Veo（音声付き生成） | `voices/Cxx.wav` をアップロード |
| 声（任意で差し替え） | にじボイス、ElevenLabs、VOICEVOX（現在使用中） | 差し替える場合は同じファイル名で上書き |

> 各ツールの商用利用条件（無料プランは商用不可のことが多い）とクレジット表記は必ず確認してください。

## 共通スタイル（すべての画像プロンプトの先頭に付ける）

```
Hand-painted Japanese anime film style, soft watercolor backgrounds, warm gentle afternoon light,
cozy and nostalgic atmosphere, clean expressive character line art, vertical 9:16 composition.
Setting: a modern 2026 Tokyo apartment living room with a big window (Tokyo Skytree in the distance,
fluffy cumulus clouds), a low kotatsu table with a plaid futon, mandarin oranges, a picture book,
manuscript paper and mugs on top, a lavender sofa at the back.
Keep the characters exactly as in the attached reference sheet (faces, hair, outfits, colors).
```

キャラの説明（参照画像と一緒に使う）:

- **Satoru (dad, 43)**: black-rimmed glasses, short messy dark hair, gray zip hoodie over white T-shirt, navy sweatpants, clumsy and expressive
- **Aina (mom, 40)**: soft wavy light-brown semi-long hair, lavender cardigan, cream long skirt, gentle and reliable, often holding baby Noa
- **Sora (son, 13)**: tall, messy black hair, black hoodie, cool and aloof expression
- **Rina (daughter, 11)**: light-brown ponytail with pink scrunchie, pink sweatshirt, pink plaid skirt, bright energetic smile
- **Noa (baby girl, 0)**: pink romper, pink bow headband, chubby smiling cheeks
- **Chappy (dog)**: cream toy poodle, lavender collar with a heart tag

## カット表

秒数は今のタイムラインに合わせています（`python3 scripts/kit.py` で `frames/` に構図の参考画像、`voices/` にカットの音声が出ます）。
動画AIで作る素材は、カットの長さより少し長め（＋0.5秒）に作ると安全です。

### C01（0.0–3.2秒）全景 → 莉奈がスマホに話しかける 🔊 voices/C01.wav
- 画像: `The whole Tanaka family relaxing around the kotatsu: Rina holds up a smartphone near her face and talks to it excitedly, Aina sits beside her holding baby Noa, Sora sits on the sofa at the back looking at his own phone, Chappy lies on the futon. Wide shot, eye level.`
- 動き: `Slow gentle push-in toward Rina. Rina speaks happily to her smartphone, ponytail bouncing slightly. Aina smiles, baby Noa waves her hands, Chappy's tail wags. Subtle natural motion, steady camera.`
- 莉奈「AIくーん、読書感想文ぜーんぶ書いて！」

### C02（3.2–6.4秒）パパが慌てて覗き込む／莉奈ふくれっ面 🔊 voices/C02.wav
- 画像: `Satoru leans in from behind Rina, peeking at her smartphone in shock, one hand on his head, sweat drop. Rina pouts. Medium two-shot.`
- 動き: `Satoru rushes into frame from the left and leans over Rina's shoulder, panicking and talking quickly with exaggerated comedic expression. Rina turns to him and pouts, then talks back. Light comedic timing.`
- パパ「えぇぇ！？そんなズルはダメだぞー！」→ 莉奈「えー、ラクじゃん〜！」

### C03（6.4–8.6秒）ママがスマホをやさしく取り上げる 🔊 voices/C03.wav
- 画像: `Aina gently takes the smartphone from Rina's hand with a kind but firm smile, holding baby Noa in her other arm. Medium shot.`
- 動き: `Aina smoothly takes the phone from Rina and talks to her warmly, wagging a finger playfully. Rina looks surprised. Soft natural motion.`
- ママ「丸投げはダメ！こうやってお願いするの。」

### C04（8.6–11.9秒）スマホ画面：プロンプト ※このリポジトリで作成（差し替え不要）

### C05（11.9–17.1秒）莉奈が納得／ママが語りかける 🔊 voices/C05.wav
- 画像: `Aina and Rina sitting side by side at the kotatsu, both looking at the smartphone together, Rina's eyes sparkling with understanding, Aina smiling kindly. Warm light from the window. Medium two-shot.`
- 動き: `Rina nods and speaks with a delighted expression. Then Aina turns to Rina and speaks gently and warmly, Rina listens and smiles. Slow subtle camera drift toward Aina.`
- 莉奈「ほんとだ、それならズルくない！」→ ママ「AIは向き合い方次第で、素敵な相棒になるんだよ」
- 長いカットなので、2本（莉奈→ママ）に分けて作り、編集アプリでつないでから `C05.mp4` にしてもOK

### C06（17.1–18.6秒）莉奈「AI、質問して〜！」 🔊 voices/C06.wav
- 画像: `Close-up of Rina holding the smartphone with both hands, calling out to it cheerfully.`
- 動き: `Rina happily talks to the smartphone, leaning forward with excitement.`

### C07（18.6–22.6秒）スマホ画面：AIの返信 ※このリポジトリで作成（差し替え不要）

### C08（22.6–24.1秒）莉奈ワクワク 🔊 voices/C08.wav
- 画像: `Close-up of Rina staring at the smartphone screen with sparkling eyes and a huge excited smile, sparkles around her.`
- 動き: `Rina gasps with joy and speaks excitedly, bouncing slightly. Quick gentle zoom-in.`
- 莉奈「やばっ！楽しく書けそう！」

### C09（24.1–26.6秒）パパ遠い目 🔊 voices/C09.wav
- 画像: `Satoru standing behind the kotatsu, gazing into the distance with a wistful, dreamy, slightly pathetic expression, a cool bluish tint, a thought bubble with a business proposal document.`
- 動き: `Satoru sighs and mutters to himself while staring into the distance, glasses glinting. Very slow push-in. Comedic melancholy.`
- パパ「僕の企画書も、相棒にしてほしいな……」

### C10（26.6–27.3秒）蒼がソファの端から冷めた目（セリフなし）
- 画像: `Sora sitting at the end of the sofa, hood half up, looking at the family with cool, unimpressed half-closed eyes. Medium close-up.`
- 動き: `Sora slowly shifts his eyes toward the family without moving his head, deadpan expression. Almost still.`

### C11（27.3–28.0秒）希亜「あーあー！」 🔊 voices/C11.wav
- 画像: `Close-up of baby Noa in Aina's arms, raising both tiny fists and babbling happily.`
- 動き: `Baby Noa babbles happily and waves her arms. Aina gently bounces her.`

### C12（28.0–29.3秒）チャッピー「ワン！」 🔊 voices/C12.wav
- 画像: `Chappy the cream toy poodle sitting on the kotatsu futon, barking happily with tail up.`
- 動き: `Chappy barks once cheerfully, ears bouncing, tail wagging fast.`

### C13（29.3–31.9秒）家族全景＋エンドカード（上にエンドカードを重ねます）
- 画像: `The whole family laughing together around the kotatsu, warm golden afternoon light, peaceful happy moment. Wide shot.`
- 動き: `Slow pull-back of the whole family laughing together, Chappy wags his tail. Gentle, heartwarming.`

## 失敗しにくくするコツ

- 1カット1アクション。動きを欲張ると顔や手が崩れやすい
- キーフレームは**縦9:16**で作る（横長だと組み立て時に左右が切れます）
- 顔が崩れたら、同じキーフレームで数回生成して一番いいものを採用
- 生成した動画のBGMや声は使わず、組み立て時に `build/mix.wav`（セリフ＋BGM）を使います
- 字幕・タイトル・エンドカードは組み立てスクリプトが重ねるので、動画AI側では文字を入れない
