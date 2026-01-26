# News Freshness Checker Skill

ニュース・トピックの情報鮮度を厳格にチェックするサブエージェント

## 機能
- 今日の日付の自動確認
- 初発表日と記事投稿日の区別
- 経過日数の正確な計算
- 鮮度判定（FRESH/ACCEPTABLE/REQUIRES_JUSTIFICATION/STALE）
- 深堀り価値判定（4-14日経過の場合）

## フロー位置
1. トピック発見・選択
2. **news-freshness-checker（情報鮮度チェック）** ← ここ
3. 合格 → generate-tweet（ツイート生成）
4. 不合格 → 別トピック探し

## 判定基準
- 0-1日: FRESH（最優先）
- 2-3日: ACCEPTABLE 
- 4-14日: 深堀り価値判定必須
- 14日超: STALE（即却下）

## REJECT時のアクション
- 即座に別のより新鮮なトピックを探す
- 理由を明確に説明