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

## DONE: ツイート効果評価ツール

2つのパイプラインで実現:
- **content_evaluator.py**: 自己ツイートのW-Score評価 + 7軸分類（ソースA）
- **buzz_content_analyzer.py**: 他者バズツイートの7軸分類 + パターン抽出（ソースB）
- **content-strategy-ref.md**: 両分析の統合ガイダンスを自動生成

元々の「投稿効果の定量評価」は、W-Score（Xアルゴリズム重み付きエンゲージメント）と多次元分類の組み合わせで達成

---

## DONE: 他者ツイート分析パイプライン（buzz_content_analyzer.py）

`buzz_content_analyzer.py` として実装完了。Task Scheduler 06:45 登録済み。

### 実装内容
- `buzz-tweets-latest.json` → Groq LLM 7軸分類（content_type/originality/media_contribution/news_saturation/bip_authenticity/ai_citation_value/virality_factor）
- `buzz_content_evaluations.json` に30日蓄積（GC付き）
- key_persons.json照合（username逆引き）
- content-strategy-ref.mdのマルチソース構造（ソースA: 自己 / ソースB: 他者 / 統合ガイダンス）
- Obsidianレポート（buzz-eval-YYYY-MM-DD.md）

### 下流連携

- DONE: `content-strategy-ref.md`: ソースA+Bの統合ガイダンス動的生成（4象限分析: 最強カテゴリ/改善チャンス/ニッチ強み + 自分のW-Score実数値付き）
- 未着手: `discourse-freshness.md`: 実データベースの議論進行度判定に移行
- 未着手: `zeitgeist-snapshot.json`: バズツイート分類精度の向上

---

## content_evaluator.py 拡張

### DONE: 好感度/レピュテーションリスク判定

`reputation_risk`（1-5）としてCLASSIFICATION_PROMPTに7軸目を追加。

- 「インプは高いが反感を買う」パターンの検出（リスク3以上をフラグ表示）
- 煽り系・二次利用感のあるコンテンツのリスクスコア化
- Obsidianレポートにレピュテーションリスク分析セクション追加
- content-strategy-ref.md（ソースA）にリスクインサイト追加
- 個別ツイート評価一覧でリスク2以上を表示

### DONE: AIエージェントSEO適性の精度向上

ai_citation_valueを5項目チェックリスト方式に改修済み:
- 独自データや具体的な数値を含む
- 再現可能な具体手順を含む
- 個人の実体験に基づく知見
- 他で見つからない一次情報
- 検証可能な主張（リンク・ソース・スクショ付き）

### DONE: コンテンツ戦略の方向性反映

`_generate_dynamic_guidance()`のW-Scoreベース自動ランキングにより、データドリブンで反映済み:
- ニュース系はW-Score実績から自動的に「下位」表示
- BIPはW-Score実績から自動的に「上位」表示
- `bip_authenticity`（1-5）でBIPの質を段階評価
- `news_saturation`で速報性を段階評価（first_mover/early/mainstream/late/rehash）

### ニュース飽和度の定量化（将来）
- 現状はGroq LLMの推測のみ
- twscrapeで同トピックの既存ツイート件数を実測する方式
- buzz-tweets-latest.json / key_persons.json との照合
