# x-auto - X(Twitter)投稿生成システム

## このリポジトリについて
AIパワーユーザー・個人開発者(@sena_09_04)のX投稿を生成・レビュー・投稿するシステム。

## ツイート種別ルーティング

「ツイートを作って」と言われたら、まずここで種別を判定し、該当スキルのPROMPT.mdを読む。

| 種別 | 条件 | スキル | 文字数 |
|------|------|--------|--------|
| **短文ツイート** | デフォルト。ニュース速報・知見共有 | `skills/generate-tweet/PROMPT.md` | 140字以内 |
| **長文ツイート** | 新ツール紹介・技術解説・深掘り分析 | `skills/long-form-tweet/PROMPT.md` | 250-350字目安 |
| **引用RT** | 他人のツイートへのコメント | `skills/quote-rt/PROMPT.md` | 100字以内 |
| **Tom風** | @IT_Tom_study文体の再現 | `skills/tom-style-tweet/skill.md` | 制限なし |
| **BIPツイート** | Build in Public系（今日やったこと・苦労・学び） | `skills/generate-tweet/PROMPT.md` | 140字以内 |
| **短文(バズ版)** | [EXPERIMENTAL] バズ文体適用版。テスト段階 | `skills/generate-tweet-buzz/PROMPT.md` | 140字以内 |

**判定に迷ったら**: 短文ツイート（generate-tweet）をデフォルトとする。
**バズ版の発火条件**: 以下のいずれかでバズ版（generate-tweet-buzz）を使用:
- 「バズ版で」「buzz版で」
- 「AIBuzzExtractor版で」「これ版で」「これバージョンで」
- ai-buzz-extractor.vercel.appのURLを直接投げてきた場合

## 共通ルール（全スキル共通・必ず参照）

各スキルのPROMPT.mdを読む**前に**、以下の共通ルールを読むこと:

| ファイル | 内容 |
|---------|------|
| `common/persona-ref.md` | persona-db参照手順（口調・スタンス・興味・ツール・知識） |
| `common/anti-ai-rules.md` | AI臭い表現の禁止ルール（統合版） |
| `common/format-rules.md` | フォーマット共通ルール（読点・絵文字・ハッシュタグ・改行等） |
| `common/expression-rules.md` | 推奨語尾・禁止語尾・表現スタイル |
| `common/buzz-style-reference.md` | バズ文体パターン分析（generate-tweet-buzzから参照） |

**読み込み順序**: persona-ref.md -> anti-ai-rules.md -> format-rules.md -> expression-rules.md -> 各スキルPROMPT.md

## ユーティリティスキル（生成後に使用）

| スキル | 用途 |
|--------|------|
| `skills/review-tweet/PROMPT.md` | 基本ルール準拠レビュー |
| `skills/tweet-quality-judge/PROMPT.md` | 有益性の厳格判定（A/B/C/D） |
| `skills/news-freshness-checker/PROMPT.md` | 情報鮮度チェック |
| `skills/post-tweet/PROMPT.md` | Claude in ChromeでのX投稿実行 |

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
├── common/                # 共通ルール（全スキルが参照）
│   ├── persona-ref.md     # persona-db参照手順
│   ├── anti-ai-rules.md   # AI臭い表現禁止（統合版）
│   ├── format-rules.md    # フォーマット共通ルール
│   └── expression-rules.md # 表現スタイルルール
├── skills/                # スキル別プロンプト
│   ├── generate-tweet/    # 短文ツイート生成
│   ├── long-form-tweet/   # 長文ツイート生成
│   ├── quote-rt/          # 引用RTコメント生成（移植予定）
│   ├── tom-style-tweet/   # Tom風ツイート生成
│   ├── tom-style/         # Tom風長文ツイート生成
│   ├── review-tweet/      # ツイートレビュー
│   ├── tweet-quality-judge/ # 品質判定
│   ├── news-freshness-checker/ # 鮮度チェック
│   ├── parallel-news-search/   # 並列ネタ検索
│   └── post-tweet/        # 投稿実行
├── scripts/               # 分析・自動化スクリプト
│   ├── x_client.py        # 共通モジュール（X API / Discord / Obsidian / プロフィール取得）
│   ├── daily_metrics.py   # 日次メトリクス分析 + フォロワー追跡 + パターン分析
│   ├── trend_detector.py  # トレンド検出 + 下書き生成 + キーパーソン蓄積
│   ├── zeitgeist_detector.py    # AI界隈ムード検知（Groq LLM分類 → スナップショット生成）
│   ├── buzz_tweet_extractor.py  # twscrapeバズツイート抽出（min_faves:500、zeitgeist補完用）
│   ├── grok_video_generator.py  # Grok動画パイプラインCLI
│   ├── grok_video_prompts.py    # 5レイヤープロンプト生成エンジン
│   └── data/              # 蓄積データJSON群
│       ├── metrics_history.json      # 日次メトリクス集計履歴
│       ├── follower_history.json     # フォロワー数日次推移
│       ├── tweet_details.json        # ツイート単位詳細（パターン分析用）
│       ├── key_persons.json          # トピック別キーパーソン蓄積
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
| `zeitgeist_detector.py` | 毎日 07:00 | ツイートのムード分類 → スナップショット生成（ツイート生成トーン調整用） | $0.00 |
| `trend_detector.py` | 毎日 06:30 | frontier reportからトピック抽出 → X検索 → 下書き生成 + キーパーソン蓄積 | ~$0.50 |
| `daily_metrics.py` | 毎日 21:00 | imp/eng率分析 + フォロワー追跡 + パターン分析（時間帯/文字数） | ~$0.105 |

**実行方法（手動）:**
```bash
cd C:\Users\Tenormusica\x-auto\scripts
python -X utf8 buzz_tweet_extractor.py            # バズツイート抽出
python -X utf8 buzz_tweet_extractor.py --dry-run  # 検索のみ（保存なし）
python -X utf8 zeitgeist_detector.py              # ムード分析（limit=50）
python -X utf8 zeitgeist_detector.py --dry-run    # 分析のみ（保存なし）
python -X utf8 zeitgeist_detector.py --limit 10   # 件数指定
python -X utf8 trend_detector.py                  # 通常実行
python -X utf8 trend_detector.py --dry-run        # キーワード抽出のみ
python -X utf8 daily_metrics.py                   # 直近20件分析
python -X utf8 daily_metrics.py --count 10        # 件数指定
```

**出力先:**
- Obsidian日報: `VaultD\...\x-analytics\daily\metrics-YYYY-MM-DD.md`
- Obsidianトレンド: `VaultD\...\x-analytics\trends\trends-YYYY-MM-DD.md`
- Obsidianムード: `VaultD\...\x-analytics\zeitgeist\zeitgeist-YYYY-MM-DD.md`
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
**アカウント**: @SundererD27468
**権限**: Read + Write + Direct Messages

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

### tweepy使い方（スクリプトから直接呼ぶ場合）
```python
import tweepy
from dotenv import load_dotenv
import os

load_dotenv(r"C:\Users\Tenormusica\x-auto-posting\.env")

client = tweepy.Client(
    bearer_token=os.getenv("X_BEARER_TOKEN"),
    consumer_key=os.getenv("X_API_KEY"),
    consumer_secret=os.getenv("X_API_SECRET"),
    access_token=os.getenv("X_ACCESS_TOKEN"),
    access_token_secret=os.getenv("X_ACCESS_SECRET"),
)

# 投稿（$0.010）
client.create_tweet(text="ツイート内容")

# 直近ツイート取得（$0.005 x N件）
me = client.get_me()
tweets = client.get_users_tweets(
    id=me.data.id, max_results=5,
    tweet_fields=["created_at", "public_metrics", "text"]
)
```

## Grok動画生成パイプライン（CiC経由）

Grok Imagineで動画生成→ダウンロード→Discord配信する自動化パイプライン。
**CiCセッション（`claude --chrome`）が必須。**

**スキル詳細**: `C:\Users\Tenormusica\.claude\skills\grok-video-generator\SKILL.md`

| スクリプト | 役割 |
|-----------|------|
| `scripts/grok_video_prompts.py` | 5レイヤープロンプト生成エンジン |
| `scripts/grok_video_generator.py` | パイプラインCLI（prompt/detect/move/discord） |
| `scripts/x_client.py` | Discord webhook送信（`notify_discord_with_file`） |

**実行方法:**
```bash
python -X utf8 grok_video_generator.py prompt                          # プロンプト生成
python -X utf8 grok_video_generator.py detect --post-id <id>           # D:\Downloadsからmp4検出
python -X utf8 grok_video_generator.py move <file_path> --name <name>  # 所定フォルダへ移動
python -X utf8 grok_video_generator.py discord <file_path>             # Discord送信
```

**保存先**: `scripts/data/grok-videos/`
**ダウンロード先**: `D:\Downloads`（Chrome設定固定）
**動画仕様**: 480p (464x688), 6秒, 24FPS, 音声あり, 50本/日（Premium $8）

## 外部依存

| リソース | パス | 用途 |
|---------|------|------|
| persona-db | `C:\Users\Tenormusica\persona-db\` | ペルソナデータ（口調・スタンス等） |
| Vault-D AI情報 | `D:\antigravity_projects\VaultD\Projects\Monetization\Intelligence\` | AI最新ニュースソース |
| x-auto-posting（旧版） | `C:\Users\Tenormusica\x-auto-posting\` | X API認証情報・引用RTシステム（GUI自動化） |
