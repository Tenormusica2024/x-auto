# Tweet Quality Judge Skill

ツイート文の品質を第三者視点で厳しく評価するサブエージェント

## 機能
- 情報の正確性・鮮度を厳格チェック
- 開発者向け価値を評価
- A判定でのみ投稿許可

## フロー位置
1. generate-tweet（ツイート生成）
2. news-freshness-checker（情報鮮度チェック）
3. review-tweet（基本ルールチェック）
4. **tweet-quality-judge（厳しめ品質判定）** ← ここ
5. 投稿実行

## 評価基準
- 情報正確性・鮮度: 厳格
- 実用性・検証可能性: ニュース性質考慮で適度
- A/B/C/D判定、A判定のみ合格