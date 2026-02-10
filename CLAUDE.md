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

**判定に迷ったら**: 短文ツイート（generate-tweet）をデフォルトとする。

## 共通ルール（全スキル共通・必ず参照）

各スキルのPROMPT.mdを読む**前に**、以下の共通ルールを読むこと:

| ファイル | 内容 |
|---------|------|
| `common/persona-ref.md` | persona-db参照手順（口調・スタンス・興味・ツール・知識） |
| `common/anti-ai-rules.md` | AI臭い表現の禁止ルール（統合版） |
| `common/format-rules.md` | フォーマット共通ルール（読点・絵文字・ハッシュタグ・改行等） |
| `common/expression-rules.md` | 推奨語尾・禁止語尾・表現スタイル |

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
├── scripts/               # 実行スクリプト
├── history/               # 採用済みツイート履歴
├── drafts/                # 下書き
└── logs/                  # 実行ログ
```

## 外部依存

| リソース | パス | 用途 |
|---------|------|------|
| persona-db | `C:\Users\Tenormusica\persona-db\` | ペルソナデータ（口調・スタンス等） |
| Vault-D AI情報 | `D:\antigravity_projects\VaultD\Projects\Monetization\Intelligence\` | AI最新ニュースソース |
