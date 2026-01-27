# 並列ネタ検索オーケストレーター

## 役割
複数のソースから同時並列でAI関連の実装テクニック・ベストプラクティスを検索し、最も価値の高いネタを発見する。

## 実行構造

```
┌─────────────────────────────────────────────────────────┐
│                 並列ネタ検索オーケストレーター              │
└─────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
    ┌───────────┐   ┌───────────┐   ┌───────────┐
    │  Reddit   │   │  X.com    │   │ Tech Blog │
    │  担当     │   │  担当     │   │  担当     │
    └───────────┘   └───────────┘   └───────────┘
            │               │               │
            └───────────────┼───────────────┘
                            │
                            ▼
                    ┌───────────┐
                    │ 結果統合  │
                    │ ランキング │
                    └───────────┘
```

## 並列実行コマンド

以下の3つのTask toolを**同時に**実行する:

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

## 結果統合基準

各担当から返ってきた候補を以下の基準でランキング:

| 優先度 | 条件 |
|--------|------|
| 1位 | 0-1日前 + 個人開発者がすぐ試せる具体的テクニック |
| 2位 | 0-1日前 + ベンチマーク・数値比較あり |
| 3位 | 2-3日前 + 独自の実装知見・失敗談 |
| 4位 | 公式リリースの深掘り分析 |

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
