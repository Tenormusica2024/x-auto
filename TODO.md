# x-auto TODO

## DONE: content-strategy-ref.mdのガイダンス動的生成

`_generate_dynamic_guidance()` として実装完了。

### 実装内容
- ハードコードされたif-elif文を廃止し、蓄積データの相対的位置関係から文言を自動導出
- サンプル数 n<3 → 「データ不足」、n<5 → 「参考値」注記
- 順位ベースのポジション表現（W-Score最高/上位/下位）
- W-Score対imp比から特性を自動判定（深い反応/拡散力/両方高い/両方低調）
- データが変わればガイダンス文言も自動的に変わる

---

## PENDING: ツイート効果評価ツール

generate-tweetから分離した投稿効果の定量評価システム。

### 背景
- 元々generate-tweet内に重みスコア（リプライ誘発13.5 / プロフィールクリック12.0 / フォロー獲得4.0）があったが、出典不明かつ生成時の実効性が低いため削除
- 投稿効果の評価は生成時ではなく**投稿後の独立した評価ツール**として構築すべき

### 評価の難しさ
- 投稿時間的要因（時間帯・曜日でリーチが変わる）
- 流行り廃り（トレンドに乗ったかどうか）
- 既存ファンのリアクション有無（フォロワー基盤の影響）
- 多要素が絡むため一概な評価は困難

### 方針
- **自分のツイートの評価は外れ値が多い**（フォロワー少・サンプル少）
- **他インフルエンサーのツイート評価の方が外れ値が少ない**
- 他者のツイートを分析して「何がウケるか」のパターンを抽出する方向が有効

---

## DONE: 他者ツイート分析パイプライン（buzz_content_analyzer.py）

`buzz_content_analyzer.py` として実装完了。Task Scheduler 06:45 登録済み。

### 実装内容
- `buzz-tweets-latest.json` → Groq LLM 7軸分類（content_type/originality/media_contribution/news_saturation/bip_authenticity/ai_citation_value/virality_factor）
- `buzz_content_evaluations.json` に30日蓄積（GC付き）
- key_persons.json照合（username逆引き）
- content-strategy-ref.mdのマルチソース構造（ソースA: 自己 / ソースB: 他者 / 統合ガイダンス）
- Obsidianレポート（buzz-eval-YYYY-MM-DD.md）

### 下流連携（未着手）
- `discourse-freshness.md`: 実データベースの議論進行度判定に移行
- `zeitgeist-snapshot.json`: バズツイート分類精度の向上
- `content-strategy-ref.md`: ソースA+Bの統合ガイダンス自動生成の高度化

---

## content_evaluator.py 拡張

### DONE: 好感度/レピュテーションリスク判定

`reputation_risk`（1-5）としてCLASSIFICATION_PROMPTに7軸目を追加。

- 「インプは高いが反感を買う」パターンの検出（リスク3以上をフラグ表示）
- 煽り系・二次利用感のあるコンテンツのリスクスコア化
- Obsidianレポートにレピュテーションリスク分析セクション追加
- content-strategy-ref.md（ソースA）にリスクインサイト追加
- 個別ツイート評価一覧でリスク2以上を表示

### TODO: AIエージェントSEO適性の精度向上
- ai_citation_value（現状1-5のLLM推測）をより具体的な基準に
- 「AIが一次ソースとして引用したくなるか」の定量的指標
- 独自データ・独自体験・再現可能な手順を含むかどうか

### コンテンツ戦略の方向性
- **ニュース主軸は避ける** — 二次利用感が出やすく、飽和度判定も困難
- **BIP（Build in Public）を主軸に** — 独自体験は代替不可、潜在的信頼スコア蓄積
- **AI how-to/チュートリアル** — 再現可能な具体手順は一次ソース価値が高い
- news系ツイートの評価優先度を下げ、BIP/how-toの分析精度を上げる

### ニュース飽和度の定量化（将来）
- 現状はGroq LLMの推測のみ
- twscrapeで同トピックの既存ツイート件数を実測する方式
- buzz-tweets-latest.json / key_persons.json との照合
