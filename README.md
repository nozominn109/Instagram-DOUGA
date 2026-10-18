# 田中家のAIじかん — Instagramリール制作

親子 × AI × Z世代 のアカウント向け、田中家のアニメーションリール。

## 第1話「読書感想文編」

- 完成動画（リール用・約30秒）: [`output/tanakake_ep01_dokusho.mp4`](output/tanakake_ep01_dokusho.mp4)
  （1080×1920 / 30fps / H.264 + AAC、セリフ音声・BGM・効果音・字幕入り）
- 台本ノーカット版（約53秒）: [`output/tanakake_ep01_dokusho_full53s.mp4`](output/tanakake_ep01_dokusho_full53s.mp4)
  ※ノーカット版の台本は git 履歴（初回コミット）の `scripts/story.py` にあります

### 構成（30秒版）

| 秒 | シーン |
|---|---|
| 0–5.5 | フック「宿題をAIに丸投げ！？」→ 莉奈「AIくーん…」→ パパ「ズルはダメだぞー！」→ 莉奈「ラクじゃん〜！」 |
| 5.5–7.7 | ママ登場、スマホをスッと取り上げ「丸投げはダメ！」 |
| 7.7–11.3 | スマホ画面アップ。プロンプト全文を表示し、要点（優しいインタビュアー／質問を3つ／1個ずつ順番に）にマーカー |
| 11.3–17.4 | 莉奈「ズルくない！」→ ママ「AIは素敵な相棒」→ 莉奈「質問して〜！」 |
| 17.4–21.2 | AIくんの返信がスマホに届く |
| 21.2–25.9 | 莉奈「やばっ！」→ パパ遠い目（企画書）→ 反抗期の蒼「じー……」 |
| 25.9–27.4 | 希亜「あーあー！」チャッピー「ワン！」 |
| 27.4–30.2 | エンドカード「AIは『丸投げ』じゃなく『相棒』に。」＋フォロー誘導 |

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

#AI子育て #親子の会話 #読書感想文 #夏休みの宿題 #ChatGPT活用 #思春期の子育て #小学生ママ #AI教育 #田中家のAIじかん
```

## 作り直し方

```bash
pip install pyopenjtalk-plus numpy scipy pillow   # ffmpeg も必要
python3 scripts/cutout.py     # キャラシートから透過PNGを切り出し
python3 scripts/voices.py     # セリフ音声(オフラインTTS)とタイムライン生成
python3 scripts/background.py # リビング背景を描画
python3 scripts/render.py     # output/ にMP4を書き出し
python3 scripts/render.py --stills 5 20   # 指定秒の静止画だけ確認
```

- 台本・話者ごとの声/速さ: `scripts/story.py`
- ショット構成・演出: `scripts/render.py` の `shot_*` 関数
- キャラ画像: `assets/characters_sheet.webp`（3×2のシート）

## クレジット

- 音声合成: Open JTalk / HTS Engine（pyopenjtalk-plus）
  - パパ: HTS voice nitech_jp_atr503_m001（CC BY 3.0, 名古屋工業大学）
  - ママ・希亜: HTS voice "Mei"（CC BY 3.0, 名古屋工業大学）
  - 莉奈・AIくん・チャッピー: HTS voice tohoku-f01（CC BY 4.0, 東北大学 伊藤・能勢研究室）
- フォント: M PLUS Rounded 1c（SIL Open Font License 1.1）
- BGM・効果音・背景: スクリプトで生成
