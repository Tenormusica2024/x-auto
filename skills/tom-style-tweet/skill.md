# tom-style-tweet

@IT_Tom_study文体ツイート生成スキル

## 概要

@IT_Tom_studyの文体を再現し、価値あるエンジニアナレッジを含むツイートを生成する。
トピック深度4レベル（情報→戦略→実践→価値観転換）の体系化。

## 起動条件

以下のキーワードで自動起動:
- 「Tom風ツイート」「@IT_Tom_study風」
- 「エンジニアナレッジツイート」
- `/tom-style-tweet`

---

## ファイル構成

```
tom-style-tweet/
├── skill.md                        # このファイル（スキル概要）
├── STYLE_LEARNING_PROMPT.md        # 文体ラーニングフレームワーク（汎用）
└── tom-style/
    ├── TOM_STYLE_PROMPT.md         # @IT_Tom_study文体再現プロンプト
    ├── TOPIC_DEPTH_ANALYSIS.md     # トピック深度4レベル分析
    └── THUMBNAIL_PROMPT.md         # サムネイル画像生成プロンプト
```

---

## 実行フロー

```
1. TOM_STYLE_PROMPT.md を読み込む
1.5. common/content-strategy-ref.md を読み込み、W-Scoreが高いcontent_typeを把握
     （存在しない場合はスキップ）
1.7. common/rejection-log-ref.md の手順に従い、直近の落選傾向を確認して同じ失敗を回避
1.8. common/user-corrections-ref.md の手順に従い、ユーザー修正傾向を確認して事前回避
2. TOPIC_DEPTH_ANALYSIS.md でトピック・深度を決定
3. 重複チェック（下記参照）
4. 5つのパターンから選択して生成:
   - パターン1: 問いかけ型（30%）
   - パターン2: 問い提起→回答型（25%）
   - パターン3: 失敗談×教訓型（20%）
   - パターン4: 議論への主張型（15%）
   - パターン5: 情報共有型（10%）
5. 統合品質チェックリストで確認
6. 必要に応じて THUMBNAIL_PROMPT.md でサムネイル生成
7. Discord #tweet-drafts 自動保存（下記セクション参照）
```

---

## 重複チェック方法

### チェック対象

過去5件のツイートと比較して以下を確認:

| チェック項目 | 重複判定基準 | 対策 |
|------------|-------------|------|
| 構造パターン | 同じパターン（問いかけ型等）が連続 | 別パターンを選択 |
| トピックカテゴリ | 同じカテゴリが3回連続 | 別カテゴリから選択 |
| 深度レベル | 同じレベルが3回連続 | 深度を変える |
| 文末表現 | 「〜次第。」が連続 | 「試す価値あり。」等に変更 |
| 独特表現 | 「ただし！」が連続 | 「でも正直、」等に変更 |

### 実装方法

```python
# 過去ツイート履歴ファイル（存在する場合）
HISTORY_FILE = "tweet_history.json"

# チェックロジック（概念）
def check_duplicate(new_tweet, history):
    recent_5 = history[-5:]

    # 構造パターンチェック
    if new_tweet.pattern == recent_5[-1].pattern:
        return "REJECT: 同じパターン連続"

    # トピックカテゴリチェック
    if all(t.category == new_tweet.category for t in recent_5[-3:]):
        return "REJECT: 同じカテゴリ3連続"

    # 文末表現チェック
    if new_tweet.ending in [t.ending for t in recent_5[-2:]]:
        return "WARN: 文末表現が近い"

    return "PASS"
```

### 履歴ファイル形式

```json
{
  "tweets": [
    {
      "id": "tweet_001",
      "date": "2026-01-31",
      "pattern": "問いかけ型",
      "category": "設計思考",
      "depth": "Lv3",
      "ending": "〜次第。",
      "special_phrase": "ただし！",
      "char_count": 135,
      "content": "ツイート本文..."
    }
  ]
}
```

---

## トピック・深度レベル

| 深度 | 説明 | 割合（目安） |
|------|------|------|
| Lv1 情報提供 | 単なる情報共有 | 5-10% |
| Lv2 戦略的提言 | 「何をすべきか」の方向性 | 30-35% |
| Lv3 実践的ナレッジ | 「どうやるか」の具体論 | 40-45% |
| Lv4 価値観転換 | パラダイムシフト | 15-20% |

---

## 統合品質チェックリスト

### 必須要件（すべて満たす必要あり）

- [ ] 1行1文 + 情報単位で空行
- [ ] 絵文字なし
- [ ] 文字数140字以内（推奨）/ 280字以内（上限）
- [ ] 深度Lv2以上
- [ ] 読点（、）は1文に1つまで

### 品質要件（2/3以上満たす）

- [ ] 「ただし！」等の独特表現を1つ以上使用
- [ ] 箇条書き（・）で具体策を2-3個提示
- [ ] 「〜次第。」「試す価値あり。」等の結論表現

### 差別化要件（1つ以上満たす）

- [ ] 失敗体験に基づいている
- [ ] 常識への反証がある
- [ ] パラダイムシフトを提示
- [ ] 「あれ？そうなんだ」と思わせる

### 重複回避要件

- [ ] 直近5件と同じパターンになっていない
- [ ] 同じ文末表現が連続していない
- [ ] 同じトピックカテゴリが3回連続していない

---

## 品質基準

### 基本文体ルール

- 1行1文
- 情報単位で空行
- 問いかけ → 回答 → 具体例の流れ
- 「ただし！」で誤解を訂正
- 読点（、）は最小限

### 禁止事項

- 絵文字の使用
- 読点（、）の多用
- 敬語の過剰使用
- 長文1つの羅列

---

## トピックカテゴリ

| カテゴリ | トピック例 | 深度レベル |
|---------|-----------|-----------|
| 設計思考 | 責務分離、設計レビュー | Lv3 実践的 |
| AI時代の価値観 | AIで稼ぐ、バイブコーディング脱却 | Lv3-4 |
| AIガバナンス・規制 | AI推進法、個人情報保護、国際競争 | Lv2-4 |
| 学習方法論 | 資格と実務、英語の重要性 | Lv2 戦略的 |
| セルフブランディング | 発信目的、学習ログ宣言 | Lv2 戦略的 |

---

## Discord #tweet-drafts 自動保存（MANDATORY）

**ツイート文を生成したら、ユーザーに提示すると同時にDiscord #tweet-draftsに自動保存する。**

```python
import sys
sys.path.insert(0, r'C:\Users\Tenormusica\x-auto\scripts')
from dotenv import load_dotenv
load_dotenv(r'C:\Users\Tenormusica\x-auto-posting\.env')
from x_client import notify_discord_drafts

notify_discord_drafts("[ツイート本文]", label="[トピック要約]")
```

- DISCORD_WEBHOOK_URL_DRAFTS未設定時は警告を出してスキップ（フロー全体は止めない）
- 複数案生成時は全案を個別に送信

---

## 採用確認・履歴記録（MANDATORY - 実行フロー最終ステップ）

**ツイート提示後、必ず以下を実行:**

1. ユーザーに「採用する？」と確認
2. 採用の場合 → 履歴に記録
3. 不採用・修正依頼の場合 → 修正して再提示

### 採用時の記録手順

```
1. history/adopted_tweets.json を Read
2. 新規エントリを追加:
   {
     "id": "YYYY-MM-DD-NNN",
     "adopted_at": "ISO8601",
     "topic": "トピック要約（20字以内）",
     "pattern": "パターン名",
     "skill_used": "tom-style-tweet",
     "char_count": 文字数,
     "sources": [{"name": "...", "url": "..."}],
     "content": "本文"
   }
3. Write で保存
4. 「履歴に記録したよ♪」と報告
```

### 重複チェック（生成前）

生成開始時（実行フローのステップ3）で `history/adopted_tweets.json` を確認し、直近30件と類似トピックがないか確認する。

詳細ルール: `x-auto/history/RULES.md`

---

## 関連スキル

- `morning-greeting-tweet` - 朝の挨拶ツイート生成
- `x-auto-quote-retweet` - 引用リツイート自動化
- `human-like-tweet` - AI感のないツイート生成
- `history/RULES.md` - 採用履歴管理ルール
