# x-auto TODO

## Feature 5: 週次サマリー自動生成

ロードマップ: `x-auto-feature-roadmap.md` Feature 5

### 概要
日次レポートの蓄積を週1で振り返り、トレンドと改善ポイントを可視化する。
データは2026-02-12から蓄積済み（1ヶ月超）で実装可能な状態。

### 実装内容
- 今週のベスト/ワーストツイート（TOP3/BOTTOM3）
- エンゲージメント率の週間推移
- 前週比の成長率
- content_type別パフォーマンス（content_evaluator.py蓄積データ活用）
- 今週検出されたホットトピック一覧
- 来週のおすすめ（高エンゲージカテゴリ・時間帯）

### 実装方針
- 新スクリプト: `weekly_summary.py`
- Task Scheduler: 毎週日曜 22:00
- 入力: `metrics_history.json` + `tweet_details.json` + `content_evaluations.json` + 日次Obsidianレポート
- 出力: Obsidian週報 + Discord通知
- 追加APIコスト: $0（蓄積データの集約のみ）

---

## Feature 4: 生成パイプライン強化（部分達成）

ロードマップ: `x-auto-feature-roadmap.md` Feature 4

### 達成済み部分
- 4a. persona-db連携 → `common/persona-ref.md` + generate-tweetフロー内で実現済み
- 4c. Discord通知強化 → `#tweet-drafts` チャネルで文案自動保存済み

### 残タスク
- 4b. 高エンゲージパターンの自動適用
  - content-strategy-ref.mdにデータはあるが、trend_detectorの下書き生成には未反映
  - `generate_draft()` がcontent_type別のW-Scoreデータを参照して構造を最適化する仕組み

---

## Feature 6: エンゲージメント返し自動化（部分実装）

ロードマップ: `x-auto-feature-roadmap.md` Feature 6

### 現状
- `skills/like-back/SKILL.md` でCiCベースのいいね返しは実装済み
- ただしロードマップ記載のAPI半自動方式（常連検出→候補提示→承認→一括実行）は未実装

### 残タスク
- 常連エンゲージャーの自動検出・ランキング化
- 日次Discord通知での候補提示
- 承認後のX API経由一括いいね
- 月$3-6（コスト承認ルール的に事前確認が必要）

---

## ロードマップ更新

`x-auto-feature-roadmap.md` 自体が2026-02-13時点で古い。
以下のスクリプトが未反映:
- zeitgeist_detector.py
- buzz_tweet_extractor.py / buzz_content_analyzer.py
- content_evaluator.py / saturation_quantifier.py
- themed_buzz_extractor.py

次回整理時にロードマップを現状に同期する。
