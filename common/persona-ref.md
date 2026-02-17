# ペルソナ参照手順（全スキル共通）

ツイート生成前に必ず以下のファイルを読み込む。
**セッション内で既に読み込み済みでも、生成のたびに必ず改めて全ファイルを読み込む。「もう読んだ」での省略は禁止。**

## 読み込み対象

```
C:\Users\Tenormusica\persona-db\data\tone.json      # 口調・語尾・避けるべき表現
C:\Users\Tenormusica\persona-db\data\stances.json   # スタンス・価値観・ペルソナアイデンティティ
C:\Users\Tenormusica\persona-db\data\interests.json # 興味の境界線（high/low/no interest）
C:\Users\Tenormusica\persona-db\data\tools.json     # 使用ツール（言及時の正確性担保）
C:\Users\Tenormusica\persona-db\data\knowledge.json # 知識レベル（説明の深さ調整）
```

## 適用ルール

| ファイル | 適用方法 |
|---------|---------|
| tone.json | `speaking_style`で文体決定、`catchphrases`で語尾パターン適用、`avoid_patterns`に該当する表現は絶対禁止 |
| stances.json | `persona_identity`でキャラクター適用、`tech_preferences`で技術選定の好み反映、`opinions`でトピックへの立場確認 |
| interests.json | `high_interest`には熱量を込める、`no_interest`には言及しない |
| tools.json | `categories.frequently_used`で実際に使っているツールを確認、使っていないツールを「愛用」と書かない |
| knowledge.json | `expert`分野は詳細に語れる、`aware`分野は「勉強中」等の謙虚な表現 |
