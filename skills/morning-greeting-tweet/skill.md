# morning-greeting-tweet

朝の挨拶ツイート生成スキル

## 概要

自然で人間らしい朝の挨拶ツイートを生成する。AIらしさを完全に排除し、リアルな人間の朝の声を再現。

## 起動条件

以下のキーワードで自動起動:
- 「朝ツイート」「朝の挨拶」「おはようツイート」
- `/morning-greeting-tweet`

## 生成可能なツイートタイプ

| タイプ | 説明 | 使用プロンプト |
|-------|------|---------------|
| 朝の挨拶（シンプル） | 自然な朝の挨拶 | PROMPT.md |
| 朝の挨拶（昨日の活動） | 昨日の具体的な活動を含む挨拶 | PROMPT.md + REAL_DATA_EXAMPLES.md |

---

## ファイル構成

```
morning-greeting-tweet/
├── skill.md                    # このファイル（スキル概要）
├── PROMPT.md                   # メインの生成プロンプト
├── REVIEW_PROMPT.md            # レビュー用プロンプト
├── REAL_DATA_EXAMPLES.md       # 実データ例集
├── MORNING_TWEET_PATTERNS.md   # 朝ツイートパターン集
└── ADOPTED_TWEETS.json         # 採用ツイート履歴
```

---

## 実行フロー

### 朝の挨拶ツイート生成

```
1. PROMPT.md を読み込む
2. persona-db の情報を読み込む
3. ADOPTED_TWEETS.json で重複回避チェック
4. パターン選定 → ツイート生成
5. REVIEW_PROMPT.md でレビュー
6. 採用されたら ADOPTED_TWEETS.json に記録
```

---

## 品質基準

### 絶対禁止

- 絵文字（完全禁止）
- 「！」の連投
- 「頑張ろう」「頑張ります」等のCTA
- 「素晴らしい一日になりますように」等の詩的表現
- 英語混在（「Good morning!」等）
- 意識高い系の短文改行

---

## 関連スキル

- `x-auto-quote-retweet` - 引用リツイート自動化
- `human-like-tweet` - AI感のないツイート生成
- `generate-tweet` - 汎用ツイート生成
