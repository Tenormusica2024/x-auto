# x-auto TODO

## Feature 5: 週次サマリー自動生成 [DONE]

`scripts/weekly_summary.py` として実装済み。Task Scheduler `X-Auto-WeeklySummary` 毎週日曜 22:00 登録済み。

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

## Feature 6: エンゲージメント返し自動化 [DONE]

CiCベース等価いいね返し（`skills/like-back/`）で運用中。API半自動方式はCiC版とのコンフリクトリスクがあるため不採用。

---

## ロードマップ更新 [DONE]

`x-auto-feature-roadmap.md` を2026-02-21時点の実装状況に同期済み。
