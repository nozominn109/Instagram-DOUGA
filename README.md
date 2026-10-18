# 田中家のAIじかん — Instagramリール制作

親子 × AI × Z世代 のアカウント向け、田中家のアニメーションリール。

## 第1話「読書感想文編」

- 完成動画（リール用・約32秒）: [`output/tanakake_ep01_dokusho.mp4`](output/tanakake_ep01_dokusho.mp4)
  （1080×1920 / 30fps / H.264 + AAC）
- 台本ノーカット版（約53秒・旧演出）: [`output/tanakake_ep01_dokusho_full53s.mp4`](output/tanakake_ep01_dokusho_full53s.mp4)

### 演出

- 家族全員がこたつを囲むリビングの1シーン（みかん・原稿用紙・本・マグ、ソファに蒼、足元にチャッピー）
- カメラがパン・ズームで話している人を追いかける
- 口パク：VOICEVOX の音素タイミングに合わせて 閉じ／半開き／開き を切り替え（希亜はママの腕の中で口パク）
- まばたき、呼吸の揺れ、話すときの小さな動き
- スマホ画面アップ（プロンプト入力・AIの返信）を2回挟む

### 構成

| 秒 | シーン |
|---|---|
| 0–3 | 家族団欒の全景 → フック「宿題をAIに丸投げ！？」→ 莉奈「AIくーん…」 |
| 3–6.4 | パパが横からひょっこり「ズルはダメだぞー！」→ 莉奈「ラクじゃん〜！」 |
| 6.4–8.7 | ママが「丸投げはダメ！」とスマホをスッと取り上げる |
| 8.7–12 | スマホ画面アップ：プロンプト全文＋要点にマーカー |
| 12–18.7 | 莉奈「ズルくない！」→ ママ「AIは素敵な相棒」→ 莉奈「質問して〜！」 |
| 18.7–22.7 | AIくんの返信がスマホに届く |
| 22.7–29.3 | 莉奈「やばっ！」→ パパ遠い目 → 蒼「じー……」→ 希亜「あーあー！」→ チャッピー「ワン！」 |
| 29.3–31.9 | 家族全景に戻ってエンドカード |

### 投稿キャプション案

```
宿題、AIに丸投げしてない…？😳

AIに「全部書いて」はNG🙅‍♀️
でも「質問して」ってお願いすれば
子どもが“自分の言葉”で書ける相棒に✨

📌 今日のプロンプト（保存して使ってね）
「あなたは小学5年生の〇〇の感想を引き出す優しいインタビュアーです。
【本のタイトル】の読書感想文が書けるよう、感想を引き出す質問を3つ、
必ず1個ずつ順番に質問して！」

AIは「使わせる・使わせない」じゃなく「どう使うか」。
田中家と一緒に、親子でAIとの付き合い方を学ぼう👨‍👩‍👧‍👦

#AI子育て #親子の会話 #読書感想文 #ChatGPT活用 #思春期の子育て #小学生ママ #AI教育 #田中家のAIじかん

音声：VOICEVOX:玄野武宏 / VOICEVOX:冥鳴ひまり / VOICEVOX:春日部つむぎ / VOICEVOX:ナースロボ＿タイプＴ / VOICEVOX:あいえるたん / VOICEVOX:満別花丸
```

> VOICEVOX の音声は各キャラクターの利用規約に従い、上記のようなクレジット表記が必要です。
> 教室集客など商用利用の前に、各キャラクターの規約を確認してください。

## 動画生成AIでクオリティを上げる

初心者向けの手順とツール選び: [`docs/beginner_guide.md`](docs/beginner_guide.md)

[`docs/ep01_production_kit.md`](docs/ep01_production_kit.md) にカット表と画像・動画プロンプトをまとめています。

```bash
python3 scripts/kit.py       # output/ep01_kit/ にカット音声・構図参考画像・字幕(SRT)
# 動画生成AIで作った素材を output/ep01_kit/clips/C01.mp4 〜 C13.mp4 として置く（一部だけでもOK）
python3 scripts/assemble.py  # 字幕・スマホ画面・エンドカード・音声を重ねて output/tanakake_ep01_dokusho_ai.mp4
```

## 作り直し方

```bash
pip install numpy scipy pillow opencv-contrib-python-headless   # ffmpeg も必要
# VOICEVOX ENGINE を起動（https://github.com/VOICEVOX/voicevox_engine/releases）
./run --host 127.0.0.1 --port 50021

python3 scripts/cutout.py     # キャラシートから透過PNGを切り出し
python3 scripts/hires.py      # EDSR x4 で超解像（build/EDSR_x4.pb が必要）→ assets/characters_hires/
python3 scripts/voices.py     # VOICEVOX でセリフ音声＋口パク用タイミング
python3 scripts/background.py # リビング背景を描画
python3 scripts/render.py     # output/ にMP4を書き出し
python3 scripts/render.py --stills 5 20   # 指定秒の静止画だけ確認
```

- 台本・キャスト（声・速さ）: `scripts/story.py`
- 口・目の位置と差分生成: `scripts/faces.py`
- キャラ配置・カメラワーク・演出: `scripts/render.py`（`CAST`, `cam_keys`, `live_frame`）
- こたつ・ソファ・背景: `scripts/background.py`

## クレジット

- 音声: VOICEVOX（玄野武宏、冥鳴ひまり、春日部つむぎ、ナースロボ＿タイプＴ、あいえるたん、満別花丸）
- 超解像: EDSR（OpenCV dnn_superres, Saafke/EDSR_Tensorflow のモデル）
- フォント: M PLUS Rounded 1c（SIL Open Font License 1.1）
- BGM・効果音・背景・小物: スクリプトで生成
