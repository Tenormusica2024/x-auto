# 落選パターン確認（rejection_log参照手順）

## 概要

`history/rejection_log.json` を読み込み、直近の落選パターンを把握して同じ失敗を回避する。
tweet-quality-judgeがB/C/D判定時に記録したデータを、次回の生成で活用する成長フィードバックループ。

## 読み込み先

`C:\Users\Tenormusica\x-auto\history\rejection_log.json`

## 活用方法

1. `rejections` 配列の直近10件を確認
2. `primary_failure` の頻出項目を特定（例: `freshness` が3回連続 → 鮮度に特に注意）
3. `failure_reason` の具体的内容を確認し、同じミスを避ける
4. `content_type` の傾向を確認（特定ジャンルで落ち続けていないか）

## 回避アクション例

| primary_failure | 回避アクション |
|----------------|---------------|
| `freshness` | 一次情報の発表日確認をより厳格に |
| `expression_quality` | 敬語調・翻訳感チェックを意識的に強化 |
| `developer_value` | ネタ選定段階で技術的価値を重視 |
| `post_value` | 5条件（value-rules.md）との照合を強化 |
| `accuracy` | 数値・出典の検証を徹底 |
| `discourse_freshness` | discourse-freshness.mdとの照合を強化 |
| `practicality` | 読者が次のアクションを取れるか確認 |
| `verifiability` | 主張の検証可能性を確認 |

## 注意

- rejection_log.json が存在しない/空の場合はスキップ
- 生成前の「データインプット」フェーズで読み込む（コンテンツ戦略チェックの直後が推奨）
