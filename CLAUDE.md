# x-auto - X(Twitter)投稿生成システム

## このリポジトリについて
AIパワーユーザー・個人開発者のX投稿を生成・レビュー・投稿するシステム。
- **運用アカウント**: @SundererD27468（user_id: `1805557649876172801`）
- CiCブラウザログイン・X API（tweepy）認証トークンの両方がこのアカウントに紐付け

## ツイート生成ルーティング

「ツイートを作って」と言われたら、まず以下の判定フローでルートを決める。

```
ツイート生成指示
  │
  ├─ ネタ/テーマがユーザーから提供されていない
  │   → デフォルト: themed-buzz-to-tweet ワークフロー（ネタ探しから開始）
  │
  ├─ ネタ/テーマがユーザーから提供されている
  │   → generate-tweet / long-form-tweet（生成のみ）
  │
  ├─ 他人のツイートへのコメント → quote-rt（移植予定・未作成）
  └─ @IT_Tom_study文体指定 → tom-style-tweet
```

### デフォルト: バズツイートワークフロー（ネタ探し→生成→レビュー）

ネタ/テーマの指定がない「ツイート作って」はこちらに分類。

| 発火キーワード | 参照先 |
|--------------|--------|
| 「ツイート作って」（ネタ指定なし） | `workflows/themed-buzz-to-tweet.md` |
| 「バズツイート」「buzz」 | 同上 |
| 「テーマツイート」 | 同上 |
| 「ネタ探して」「ネタない？」 | 同上 |
| テーマ指定あり（「AI系の」「開発系の」等） | 同上（--theme指定で抽出） |

ワークフローの6フェーズ: 方向性確認→抽出→Grok/Discord→ネタ選定→生成→レビュー

### ネタ提供済み: 生成スキル（整形・生成のみ）

ユーザーが既にネタ・テキスト・体験談を持っている場合に使用。

| 種別 | 条件 | スキル | 文字数 |
|------|------|--------|--------|
| **短文ツイート** | ネタ提供済み。ニュース速報・知見共有・BIP(Build in Public) | `skills/generate-tweet/PROMPT.md` | 300字以内 |
| **長文ツイート** | 新ツール紹介・技術解説・深掘り分析 | `skills/long-form-tweet/PROMPT.md` | 250-350字目安 |
| **引用RT** | 他人のツイートへのコメント | `skills/quote-rt/PROMPT.md`（移植予定・未作成） | 100字以内 |
| **Tom風** | @IT_Tom_study文体の再現 | `skills/tom-style-tweet/skill.md` | 制限なし |
| **短文(バズ版)** | [EXPERIMENTAL] 「バズ版で」「buzz版で」指定時 | `skills/generate-tweet-buzz/PROMPT.md` | 140字以内 |

## サムネイル生成ルーティング（MANDATORY）

**発火条件（以下のいずれか1つでも該当したら、作業開始前にスキルを読む）:**
- 「サムネイル」「サムネ」「thumbnail」「画像生成」
- 「Nano Banana」「nanobanana」「Lovart」「Genspark」「CreateVision」「Gemini」「Craiyon」
- ツイート作成フローの派生で画像作成が必要になった場合
- note記事用のサムネイル作成指示

**必須読み込み先（作業前に絶対読む）:**
`C:\Users\Tenormusica\.claude\skills\genspark-thumbnail-generator\SKILL.md`

**読んでから作業する理由:**
- サービス優先順位（Lovart > Google AI Studio > Gemini 3 UI > ...）
- ダウンロード先が `D:\Downloads\`（`C:\Users\...\Downloads\` ではない）
- 用途別スタイルガイド（note用 vs X用で全く異なる）
- CiC操作手順・トラブルシュート手順

**絶対禁止:** スキル未読のまま直接Gemini/Lovart等にアクセスしてサムネイル生成を開始すること

---

## Discord #tweet-drafts 自動保存（MANDATORY）

**ツイート文を生成したら自動的にDiscord #tweet-draftsに保存する。**

- 関数: `x_client.py` の `notify_discord_drafts(tweet_text, label)`
- webhook: `.env` の `DISCORD_WEBHOOK_URL_DRAFTS`
- タイミング: ツイート文をユーザーに提示するタイミングで同時に送信
- スキル外で直接ツイートを生成した場合も同様に送信する
- webhook未設定時は警告のみでフロー全体は止めない

## 共通ルール（全スキル共通・必ず参照）

各スキルのPROMPT.mdを読む**前に**、以下の共通ルールを読むこと:

| ファイル | 内容 |
|---------|------|
| `common/persona-ref.md` | persona-db参照手順（口調・スタンス・興味・ツール・知識） |
| `common/anti-ai-rules.md` | AI臭い表現の禁止ルール（統合版） |
| `common/format-rules.md` | フォーマット共通ルール（読点・絵文字・ハッシュタグ・改行等） |
| `common/expression-rules.md` | 推奨語尾・禁止語尾・表現スタイル |
| `common/value-rules.md` | 投稿価値ルール（信頼残高基準・5条件・時間責任・自己テスト） |
| `common/discourse-freshness.md` | 議論進行度マップ（論点の鮮度を段階で判定。一般論着地防止） |
| `common/buzz-style-reference.md` | バズ文体パターン分析（generate-tweet-buzz専用、通常の読み込み順序には含まない） |
| `common/content-strategy-ref.md` | コンテンツ戦略リファレンス（content_evaluator.pyが毎日自動生成。W-Score順のcontent_type優先度等） |
| `common/rejection-log-ref.md` | 落選パターン確認手順（rejection_log.jsonの読み込み・活用方法・回避アクション） |
| `common/user-corrections-ref.md` | ユーザー修正ログ参照手順（人間フィードバックの蓄積・傾向把握） |

**読み込み順序**: persona-ref.md -> anti-ai-rules.md -> format-rules.md -> expression-rules.md -> value-rules.md -> discourse-freshness.md -> content-strategy-ref.md -> rejection-log-ref.md -> user-corrections-ref.md -> 各スキルPROMPT.md

## ユーティリティスキル（MANDATORY: 該当キーワード検出時はスキルを読んでから作業）

| スキル | 発火キーワード | 用途 |
|--------|--------------|------|
| `skills/review-tweet/PROMPT.md` | 「レビュー」「チェック」 | 基本ルール準拠レビュー |
| `skills/tweet-quality-judge/PROMPT.md` | 「判定」「品質」「A判定」 | 有益性の厳格判定（A/B/C/D） |
| `skills/news-freshness-checker/PROMPT.md` | 「鮮度」「古くない？」 | 情報鮮度チェック |
| `skills/post-tweet/PROMPT.md` | 「投稿して」「ポストして」 | Claude in ChromeでのX投稿実行 |
| `skills/like-back/SKILL.md` | 「いいね返し」「like back」「等価返し」 | API収集+CiC等価いいね返し（collect_likers.py→CiC実行） |
| `~/.claude/skills/x-draft-saver/SKILL.md` | 「下書き」「draft」「保存して」 | CiC経由でx.comに下書き保存 |

**CiC操作中でもスキルは発火する。** 既にcompose画面を開いていても、ユーザーから「下書き保存して」「投稿して」等の指示が来たら、該当SKILL.md/PROMPT.mdを読んでから手順に従うこと。「あとはボタン押すだけ」でもスキルに安全装置・検証手順が定義されている。

## ネタ探索

| スキル | ソース |
|--------|--------|
| `skills/parallel-news-search/REDDIT.md` | Reddit |
| `skills/parallel-news-search/XCOM.md` | X.com |
| `skills/parallel-news-search/TECHBLOG.md` | 技術ブログ |
| `skills/parallel-news-search/GITHUB.md` | GitHub Trending |
| `skills/parallel-news-search/PRODUCTHUNT.md` | Product Hunt |
| `skills/parallel-news-search/HUGGINGFACE.md` | Hugging Face |

## ディレクトリ構成

```
x-auto/
├── CLAUDE.md              # 本ファイル（ルーティングテーブル）
├── TODO.md                # ペンディング機能・ロードマップ
├── README.md              # プロジェクト概要
├── workflows/             # 複数スキル横断ワークフロー定義
│   └── themed-buzz-to-tweet.md  # テーマ特化バズ→ツイート生成フロー
├── common/                # 共通ルール（全スキルが参照）
│   ├── persona-ref.md     # persona-db参照手順
│   ├── anti-ai-rules.md   # AI臭い表現禁止（統合版）
│   ├── format-rules.md    # フォーマット共通ルール
│   ├── expression-rules.md # 表現スタイルルール
│   ├── value-rules.md     # 投稿価値ルール（5条件・自己テスト）
│   ├── discourse-freshness.md # 議論進行度マップ（論点鮮度の段階判定）
│   ├── buzz-style-reference.md # バズ文体パターン分析
│   └── content-strategy-ref.md # コンテンツ戦略リファレンス（content_evaluator.pyが毎日自動生成）
├── skills/                # スキル別プロンプト
│   ├── generate-tweet/    # 短文ツイート生成
│   ├── generate-tweet-buzz/ # 短文バズ版ツイート生成（EXPERIMENTAL）
│   ├── long-form-tweet/   # 長文ツイート生成
│   ├── quote-rt/          # 引用RTコメント生成（移植予定・未作成）
│   ├── tom-style-tweet/   # Tom風ツイート生成
│   ├── tom-style/         # Tom風長文ツイート生成
│   ├── review-tweet/      # ツイートレビュー
│   ├── tweet-quality-judge/ # 品質判定
│   ├── news-freshness-checker/ # 鮮度チェック
│   ├── parallel-news-search/   # 並列ネタ検索
│   ├── post-tweet/        # 投稿実行
│   └── like-back/         # いいね等価返し（collect_likers.py + CiC実行）
├── docs/                  # ドキュメント
│   └── lessons-archive.md # 教訓アーカイブ（反映済み分のバックアップ）
├── scripts/               # 分析・自動化スクリプト
│   ├── x_client.py        # 共通モジュール（X API / Discord / Obsidian / プロフィール取得）
│   ├── daily_metrics.py   # 日次メトリクス分析 + フォロワー追跡 + パターン分析
│   ├── trend_detector.py  # トレンド検出 + 下書き生成 + キーパーソン蓄積
│   ├── zeitgeist_detector.py    # AI界隈ムード検知（Groq LLM分類 → スナップショット生成）
│   ├── buzz_tweet_extractor.py  # twscrapeバズツイート抽出（min_faves:500、zeitgeist補完用）
│   ├── saturation_quantifier.py # ニュース飽和度の定量計測（twscrape実測 + Groqキーワード抽出）
│   ├── weekly_summary.py        # 週次サマリー自動生成（TOP3/BOTTOM3 + content_type別 + 推奨事項）
│   ├── grok_video_generator.py  # Grok動画パイプラインCLI
│   ├── grok_video_prompts.py    # 5レイヤープロンプト生成エンジン
│   └── data/              # 蓄積データJSON群
│       ├── metrics_history.json      # 日次メトリクス集計履歴
│       ├── follower_history.json     # フォロワー数日次推移
│       ├── tweet_details.json        # ツイート単位詳細（パターン分析用）
│       ├── key_persons.json          # トピック別キーパーソン蓄積（自分除外・GC・username自動解決付き）
│       ├── zeitgeist-snapshot.json   # ムードスナップショット（ツイート生成が参照）
│       ├── buzz-tweets-latest.json   # バズツイート抽出結果（zeitgeistが参照）
│       ├── posting_time_reference.md # X投稿タイミング一般傾向
│       └── grok-videos/             # Grok生成動画の保存先
├── history/               # 採用済みツイート履歴
├── drafts/                # 下書き（trend_detectorが自動生成）
└── logs/                  # 実行ログ
```

## 分析スクリプト（Task Scheduler自動実行）

| スクリプト | スケジュール | 機能 | コスト/回 |
|-----------|------------|------|----------|
| `buzz_tweet_extractor.py` | 毎日 06:30 | twscrapeでAI関連バズツイート上位100件を抽出（zeitgeist補完用） | $0.00 |
| `buzz_content_analyzer.py` | 毎日 06:45 | バズツイートGroq LLM 7軸分類 + 蓄積 + content-strategy-ref.mdソースB更新 | $0.00 |
| `themed_buzz_extractor.py` | 手動実行 | テーマ特化バズツイート抽出（48h/min_faves:200/上位50件） | $0.00 |
| `zeitgeist_detector.py` | 毎日 07:00 | ツイートのムード分類 → スナップショット生成（ツイート生成トーン調整用） | $0.00 |
| `trend_detector.py` | 毎日 06:30 | frontier reportからトピック抽出 → X検索 → 下書き生成 + キーパーソン蓄積 + username自動解決 + GC | ~$0.53 |
| `daily_metrics.py` | 毎日 21:00 | imp/eng率分析 + フォロワー追跡 + パターン分析（時間帯/文字数） | ~$0.105 |
| `content_evaluator.py` | 毎日 21:05 | ツイート多次元評価（content_type/originality/ai_citation_value等） + Obsidianレポート | $0.00 |
| `saturation_quantifier.py` | 手動 or `--quantitative` | ai_newsのニュース飽和度をtwscrapeで定量計測（Groqキーワード抽出 + 件数実測） | $0.00 |
| `weekly_summary.py` | 毎週日曜 22:00 | 週次サマリー自動生成（TOP3/BOTTOM3 + content_type別 + 時間帯/文字数パターン + 推奨事項） | $0.00 |
| `discourse-freshness-updater` | 毎週日曜 20:00 | Grok APIで議論進行度マップ（discourse-freshness.md）を自動更新。スキル定義: `~/.claude/skills/discourse-freshness-updater/SKILL.md` | ~5-7円 |

**実行方法（手動）:**
```bash
cd C:\Users\Tenormusica\x-auto\scripts
python -X utf8 buzz_tweet_extractor.py            # バズツイート抽出
python -X utf8 buzz_tweet_extractor.py --dry-run  # 検索のみ（保存なし）
python -X utf8 buzz_content_analyzer.py           # バズツイートGroq分類 + 蓄積 + ref更新
python -X utf8 buzz_content_analyzer.py --dry-run # 分類のみ（保存なし）
python -X utf8 buzz_content_analyzer.py --force   # 本日分を全て再評価
python -X utf8 buzz_content_analyzer.py --days 7  # 蓄積分析の対象日数指定
python -X utf8 themed_buzz_extractor.py --theme ai-coding-role  # テーマ特化抽出
python -X utf8 themed_buzz_extractor.py --list-themes           # テーマ一覧
python -X utf8 zeitgeist_detector.py              # ムード分析（limit=50）
python -X utf8 zeitgeist_detector.py --dry-run    # 分析のみ（保存なし）
python -X utf8 zeitgeist_detector.py --limit 10   # 件数指定
python -X utf8 trend_detector.py                  # 通常実行
python -X utf8 trend_detector.py --dry-run        # キーワード抽出のみ
python -X utf8 daily_metrics.py                   # 直近20件分析
python -X utf8 daily_metrics.py --count 10        # 件数指定
python -X utf8 content_evaluator.py               # 未分類ツイートを評価 + レポート生成
python -X utf8 content_evaluator.py --force        # 全ツイート再評価
python -X utf8 content_evaluator.py --quantitative # 評価 + ai_news飽和度の定量計測
python -X utf8 saturation_quantifier.py            # 飽和度定量計測（単体実行、直近5件）
python -X utf8 saturation_quantifier.py --dry-run  # キーワード抽出のみ（twscrape検索なし）
python -X utf8 saturation_quantifier.py --limit 10 # 計測件数指定
python -X utf8 weekly_summary.py                   # 先週の週次サマリー生成
python -X utf8 weekly_summary.py --weeks 1         # 先々週のサマリー生成
python -X utf8 weekly_summary.py --dry-run         # 標準出力のみ（保存なし）
```

**出力先:**
- Obsidian日報: `VaultD\...\x-analytics\daily\metrics-YYYY-MM-DD.md`
- Obsidian評価(自己): `VaultD\...\x-analytics\evaluations\eval-YYYY-MM-DD.md`
- Obsidian評価(バズ): `VaultD\...\x-analytics\evaluations\buzz-eval-YYYY-MM-DD.md`
- Obsidianトレンド: `VaultD\...\x-analytics\trends\trends-YYYY-MM-DD.md`
- Obsidianムード: `VaultD\...\x-analytics\zeitgeist\zeitgeist-YYYY-MM-DD.md`
- Obsidian週報: `VaultD\...\x-analytics\weekly\weekly-summary-YYYY-MM-DD.md`
- 下書き: `x-auto\drafts\trend-YYYY-MM-DD-*.md`
- Discord: #x-trend-alerts

**ロードマップ:** `D:\antigravity_projects\VaultD\Projects\Monetization\Intelligence\x-analytics\x-auto-feature-roadmap.md`

## X API Pay-Per-Use（公式API）- 積極活用推奨

X公式API（従量課金制）経由での投稿・読取・インプレッション取得・DM送信。
**コストが極めて安い（投稿1件1.5円）ため、積極的に使ってよい。**

### コスト感覚（重要）
| 操作 | 単価 | 感覚 |
|------|------|------|
| ツイート投稿 | $0.010（約1.5円） | タダ同然。遠慮なく使う |
| ツイート読取 | $0.005（約0.75円） | 1日50件読んでも37円 |
| プロフィール取得 | $0.010（約1.5円） | 気にしない |
| $5チャージ | 投稿500回分 or 読取1,000回分 | 数ヶ月持つ |

**→ CiCで投稿するかAPI経由で投稿するか迷ったらAPI経由を選んでよい。**
**→ インプレッション取得やメトリクス分析は気軽に実行してよい。**

### 設定・実行方法
**設定ファイル**: `C:\Users\Tenormusica\x-auto-posting\.env`（認証キー5種格納済み）
**テストスクリプト**: `C:\Users\Tenormusica\x-auto-posting\x_api_test.py`
**依存**: `tweepy>=4.14.0`（インストール済み）
**アカウント**: @SundererD27468（user_id: `1805557649876172801`）
**権限**: Read + Write + Direct Messages
**自分除外定数**: `x_client.py` の `MY_USER_IDS`（キーパーソン蓄積から自アカウントを除外）

**テストコマンド:**
```bash
cd C:\Users\Tenormusica\x-auto-posting
python -X utf8 x_api_test.py auth      # 認証テスト
python -X utf8 x_api_test.py read      # 直近5件取得（インプレッション付き）
python -X utf8 x_api_test.py metrics   # 直近10件インプレッション順ランキング
python -X utf8 x_api_test.py post      # 投稿（確認プロンプトあり、$0.010）
python -X utf8 x_api_test.py search    # キーワード検索
```
注意: Windows環境では `-X utf8` フラグ必須（絵文字のcp932エンコードエラー回避）

### 公式APIの利点（非公式API/CiCとの比較）
| 機能 | 非公式API/CiC | 公式API |
|------|--------------|---------|
| 投稿 | CiCで可能だがセッション競合リスク | **セッション競合なし、確実に投稿** |
| 複数アカウント投稿 | ブラウザプロファイル切替が必要 | **トークン差し替えで即切替** |
| インプレッション取得 | **取得不可** | **API限定データ、数値で取得可能** |
| DM送信 | 手動のみ | **特定ユーザーへの自動送信** |
| 安定性 | ブラウザ依存、bot検出リスク | **公式なので安定** |
| 並列実行 | 1セッション1操作 | **スクリプトから同時実行可能** |
| コスト | CiC無料（ただしClaude Code時間消費） | **投稿1.5円、読取0.75円** |

### 活用シナリオ
1. **ツイート投稿**: 別セッションで生成したツイート文をAPI経由で投稿（CiC不要）
2. **インプレッション分析**: どのツイートが刺さってるかデータで把握
3. **CiC競合回避**: 他セッションがCiC使用中でもAPI経由なら投稿可能
4. **将来の複数アカウント運用**: OAuthトークン切替で即対応可能
5. **DM自動送信**: 特定ユーザーへの個別DM（ユーザー指示時のみ）

### tweepy使い方
`x_client.py` の `get_x_client()` でクライアント取得 → `client.create_tweet(text="...")` で投稿。
詳細は `x_client.py` と `x_api_test.py` を参照。

## Grok動画生成パイプライン（CiC経由）

Grok Imagineで動画生成→ダウンロード→Discord配信。CiCセッション（`claude --chrome`）必須。
**スキル詳細・実行方法**: `C:\Users\Tenormusica\.claude\skills\grok-video-generator\SKILL.md`

| スクリプト | 役割 |
|-----------|------|
| `scripts/grok_video_prompts.py` | 5レイヤープロンプト生成エンジン |
| `scripts/grok_video_generator.py` | パイプラインCLI（prompt/detect/move/discord） |

**保存先**: `scripts/data/grok-videos/` | **動画仕様**: 480p, 6秒, 24FPS, 50本/日

## 外部依存

| リソース | パス | 用途 |
|---------|------|------|
| persona-db | `C:\Users\Tenormusica\persona-db\` | ペルソナデータ（口調・スタンス等） |
| Vault-D AI情報 | `D:\antigravity_projects\VaultD\Projects\Monetization\Intelligence\` | AI最新ニュースソース |
| x-auto-posting（旧版） | `C:\Users\Tenormusica\x-auto-posting\` | X API認証情報・引用RTシステム（GUI自動化） |

## 学んだ教訓

**全教訓アーカイブ**: `docs/lessons-archive.md`（各ルールファイルに反映済みの18件を移動）

**再発防止で特に重要な3パターン:**
- **フロー省略禁止**: 「テスト」「草案」等の理由でステップを省略しない。全手順履行が絶対原則
- **手順省略をAI側で判断しない**: persona-db読み込み等、毎回必須のステップは理由を問わず実行する
- **スキル存在時は必ず事前読み込み**: スキルファイルを読まずに直接操作を開始しない
