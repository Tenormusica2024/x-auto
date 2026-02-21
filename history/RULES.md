# 採用ツイート履歴管理ルール

## 概要

ツイートが採用された際に履歴を記録し、重複回避・パターン分析に活用する。

---

## 記録タイミング（MANDATORY）

**以下の条件を満たした時点で即座に記録:**
- ユーザーが「採用」「これでいく」「投稿する」等の意思表示をした時
- 実際にX.comに投稿された時

---

## 記録先

```
x-auto/history/adopted_tweets.json
```

---

## 記録フォーマット

```json
{
  "id": "YYYY-MM-DD-NNN",
  "adopted_at": "ISO8601形式",
  "topic": "トピックの要約（20字以内）",
  "pattern": "使用したパターン名",
  "skill_used": "使用したスキル名",
  "char_count": 文字数,
  "sources": [
    {
      "name": "ソース名",
      "url": "URL"
    }
  ],
  "content": "ツイート本文"
}
```

### フィールド詳細

| フィールド | 必須 | 説明 |
|-----------|------|------|
| id | ✅ | `YYYY-MM-DD-NNN`形式（同日複数は連番） |
| adopted_at | ✅ | 採用日時（ISO8601） |
| topic | ✅ | トピック要約 |
| pattern | ✅ | パターン名（データ並列型、危機感ドライブ型等） |
| skill_used | ✅ | 使用スキル（generate-tweet, long-form-tweet等） |
| char_count | ✅ | 文字数 |
| sources | ✅ | 引用ソース（複数可） |
| content | ✅ | ツイート本文 |

---

## 活用方法

### 1. 重複チェック

新規ツイート生成前に履歴を確認:

```python
# 直近30件のトピックと比較
recent_topics = [t["topic"] for t in tweets[-30:]]
if similar_topic_exists(new_topic, recent_topics):
    warn("類似トピックが直近で投稿済み")
```

### 2. パターン分析

```python
# パターン別の採用数
pattern_counts = Counter([t["pattern"] for t in tweets])
# → どのパターンが多いか確認し、バリエーションを意識
```

### 3. ソース重複回避

```python
# 直近で使用したソースを確認
recent_sources = [s["url"] for t in tweets[-10:] for s in t["sources"]]
# → 同じソースの連続使用を避ける
```

---

## 記録手順（Claude Code向け）

1. ユーザーが採用を決定
2. `adopted_tweets.json` を Read で読み込み
3. 新規エントリを追加（IDは既存の最大+1）
4. `last_updated` を更新
5. Edit または Write で保存
6. （任意）git commit

---

## 注意事項

- **下書き保存（drafts/）とは別管理** - draftsは未確定、historyは確定済み
- **投稿失敗時は記録しない** - 実際に投稿成功した場合のみ
- **手動編集OK** - 誤記録の修正は手動で可

---

## 関連ファイル

- `x-auto/history/adopted_tweets.json` - 採用済みツイート履歴（成功パターン）
- `x-auto/history/rejection_log.json` - 落選理由ログ（失敗パターン。tweet-quality-judgeがB/C/D判定時に記録）
- `x-auto/drafts/` - 下書き保存（未確定）
- `x-auto/skills/generate-tweet/` - 通常ツイート生成
- `x-auto/skills/long-form-tweet/` - 長文ツイート生成
