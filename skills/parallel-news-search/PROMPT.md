# 並列ネタ検索オーケストレーター

## 役割
複数のソースから同時並列でAI関連の実装テクニック・ベストプラクティスを検索し、最も価値の高いネタを発見する。

## 実行構造（6並列）

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      並列ネタ検索オーケストレーター                         │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────┬───────────┬───┴───┬───────────┬───────────┐
        │           │           │       │           │           │
        ▼           ▼           ▼       ▼           ▼           ▼
  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
  │ Reddit  │ │ X.com   │ │Tech Blog│ │ GitHub  │ │ Product │ │Hugging  │
  │ 担当    │ │ 担当    │ │ 担当    │ │Trending │ │  Hunt   │ │  Face   │
  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
        │           │           │       │           │           │
        └───────────┴───────────┴───┬───┴───────────┴───────────┘
                                    │
                                    ▼
                            ┌───────────┐
                            │ 結果統合  │
                            │ ランキング │
                            └───────────┘
```

## 並列実行コマンド

以下の6つのTask toolを**同時に**実行する:

### 1. Reddit担当
```
Task(subagent_type="general-purpose",
     prompt="以下のスキルファイルを読んで実行:
             C:\\Users\\Tenormusica\\x-auto\\skills\\parallel-news-search\\REDDIT.md

             検索キーワード: [KEYWORDS]
             今日の日付: [TODAY]")
```

### 2. X.com担当
```
Task(subagent_type="general-purpose",
     prompt="以下のスキルファイルを読んで実行:
             C:\\Users\\Tenormusica\\x-auto\\skills\\parallel-news-search\\XCOM.md

             検索キーワード: [KEYWORDS]
             今日の日付: [TODAY]")
```

### 3. Tech Blog担当
```
Task(subagent_type="general-purpose",
     prompt="以下のスキルファイルを読んで実行:
             C:\\Users\\Tenormusica\\x-auto\\skills\\parallel-news-search\\TECHBLOG.md

             検索キーワード: [KEYWORDS]
             今日の日付: [TODAY]")
```

### 4. GitHub Trending担当
```
Task(subagent_type="general-purpose",
     prompt="以下のスキルファイルを読んで実行:
             C:\\Users\\Tenormusica\\x-auto\\skills\\parallel-news-search\\GITHUB.md

             検索キーワード: [KEYWORDS]
             今日の日付: [TODAY]")
```

### 5. Product Hunt担当
```
Task(subagent_type="general-purpose",
     prompt="以下のスキルファイルを読んで実行:
             C:\\Users\\Tenormusica\\x-auto\\skills\\parallel-news-search\\PRODUCTHUNT.md

             検索キーワード: [KEYWORDS]
             今日の日付: [TODAY]")
```

### 6. Hugging Face担当
```
Task(subagent_type="general-purpose",
     prompt="以下のスキルファイルを読んで実行:
             C:\\Users\\Tenormusica\\x-auto\\skills\\parallel-news-search\\HUGGINGFACE.md

             検索キーワード: [KEYWORDS]
             今日の日付: [TODAY]")
```

## 各担当の特徴・急上昇指標

| 担当 | 一次情報質 | 鮮度 | 実装Tips | 急上昇指標 |
|------|-----------|------|---------|-----------|
| Reddit | 8 | 9 | 9 | upvote/コメント数 |
| X.com | 9 | 10 | 8 | いいね/RT数 |
| Tech Blog | 9 | 8 | 9 | points/リアクション |
| GitHub Trending | 10 | 9 | 10 | 今日のスター獲得数 |
| Product Hunt | 8 | 10 | 6 | upvote数/ランキング |
| Hugging Face | 10 | 9 | 8 | Downloads急増/Likes |

## 結果統合基準

各担当から返ってきた候補を以下の基準でランキング:

| 優先度 | 条件 |
|--------|------|
| 1位 | 0-1日前 + 個人開発者がすぐ試せる具体的テクニック + 急上昇指標高 |
| 2位 | 0-1日前 + ベンチマーク・数値比較あり |
| 3位 | 2-3日前 + 独自の実装知見・失敗談 |
| 4位 | 公式リリースの深掘り分析 |
| 5位 | 新ツール・新モデル（急上昇確認済み） |

## 急上昇の定量基準

| ソース | 高優先度 | 中優先度 |
|--------|---------|---------|
| Reddit | 500+ upvotes | 100-500 upvotes |
| X.com | 1000+ いいね | 200-1000 いいね |
| Hacker News | 300+ points | 100-300 points |
| GitHub | 100+ stars/日 | 20-100 stars/日 |
| Product Hunt | 500+ upvotes | 200-500 upvotes |
| Hugging Face | 10K+ DL/週 | 1K-10K DL/週 |

## 検索キーワード例

- `Claude Code tips`
- `AI agent workflow`
- `LLM prompt engineering`
- `MCP integration`
- `AI automation`
- `GPT API best practices`
- `Cursor IDE tips`
- `Windsurf AI`
- `AI coding assistant`
- `local LLM`
- `AI tool indie hacker`
