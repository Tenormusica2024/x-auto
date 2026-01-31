# morning-greeting-tweet

朝の挨拶ツイート生成スキル（@IT_Tom_study文体対応版）

## 概要

自然で人間らしい朝の挨拶ツイートを生成する。AIらしさを完全に排除し、リアルな人間の朝の声を再現。
@IT_Tom_studyの文体を再現し、価値あるエンジニアナレッジを含むツイートも生成可能。

## 起動条件

以下のキーワードで自動起動:
- 「朝ツイート」「朝の挨拶」「おはようツイート」
- 「Tom風ツイート」「@IT_Tom_study風」
- `/morning-greeting-tweet`

## 生成可能なツイートタイプ

| タイプ | 説明 | 使用プロンプト |
|-------|------|---------------|
| 朝の挨拶（シンプル） | 自然な朝の挨拶 | PROMPT.md |
| 朝の挨拶（昨日の活動） | 昨日の具体的な活動を含む挨拶 | PROMPT.md + REAL_DATA_EXAMPLES.md |
| エンジニアナレッジ（Tom風） | @IT_Tom_study文体のナレッジシェア | TOM_STYLE_PROMPT.md + TOPIC_DEPTH_ANALYSIS.md |

---

## ファイル構成

```
morning-greeting-tweet/
├── skill.md                    # このファイル（スキル概要）
├── PROMPT.md                   # メインの生成プロンプト
├── REVIEW_PROMPT.md            # レビュー用プロンプト
├── REAL_DATA_EXAMPLES.md       # 実データ例集
├── MORNING_TWEET_PATTERNS.md   # 朝ツイートパターン集
├── ADOPTED_TWEETS.json         # 採用ツイート履歴
└── style-analysis/             # 文体分析・ラーニング
    ├── STYLE_LEARNING_PROMPT.md    # 文体ラーニングフレームワーク（汎用）
    └── tom-style/                   # @IT_Tom_study文体
        ├── TOM_STYLE_PROMPT.md      # 文体再現プロンプト
        ├── TOPIC_DEPTH_ANALYSIS.md  # トピック深度分析
        └── THUMBNAIL_PROMPT.md      # サムネイル生成プロンプト
```

---

## 実行フロー

### 1. 朝の挨拶ツイート生成

```
1. PROMPT.md を読み込む
2. persona-db の情報を読み込む
3. ADOPTED_TWEETS.json で重複回避チェック
4. パターン選定 → ツイート生成
5. REVIEW_PROMPT.md でレビュー
6. 採用されたら ADOPTED_TWEETS.json に記録
```

### 2. エンジニアナレッジツイート生成（Tom風）

```
1. TOM_STYLE_PROMPT.md を読み込む
2. TOPIC_DEPTH_ANALYSIS.md でトピック・深度を決定
3. 5つのパターンから選択して生成
4. 品質チェックリストで確認
5. 必要に応じて THUMBNAIL_PROMPT.md でサムネイル生成
```

---

## 品質基準

### 共通（絶対禁止）

- 絵文字（完全禁止）
- 「！」の連投
- 「頑張ろう」「頑張ります」等のCTA
- 「素晴らしい一日になりますように」等の詩的表現
- 英語混在（「Good morning!」等）
- 意識高い系の短文改行

### Tom風ツイート追加基準

- 1行1文
- 情報単位で空行
- 問いかけ → 回答 → 具体例の流れ
- 「ただし！」で誤解を訂正
- 読点（、）は最小限

---

## 関連スキル

- `x-auto-quote-retweet` - 引用リツイート自動化
- `human-like-tweet` - AI感のないツイート生成
- `generate-tweet` - 汎用ツイート生成
