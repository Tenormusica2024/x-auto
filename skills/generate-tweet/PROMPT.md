# X投稿文生成スキル

## 役割
AIパワーユーザー・個人開発者向けのX投稿文を生成する。

## 実行手順

### ステップ1: ペルソナ情報読み込み（MANDATORY）
**ツイート生成前に必ず以下のファイルを読み込む:**

```
C:\Users\Tenormusica\persona-db\data\tone.json      # 口調・語尾・避けるべき表現
C:\Users\Tenormusica\persona-db\data\stances.json   # スタンス・価値観・ペルソナアイデンティティ
C:\Users\Tenormusica\persona-db\data\interests.json # 興味の境界線（high/low/no interest）
C:\Users\Tenormusica\persona-db\data\tools.json     # 使用ツール（言及時の正確性担保）
C:\Users\Tenormusica\persona-db\data\knowledge.json # 知識レベル（説明の深さ調整）
```

**読み込んだ情報の活用:**
- `tone.json`: 語尾・口癖・避けるべき表現を適用
- `stances.json`: 技術選定の好み・意見・価値観を反映
- `interests.json`: high_interestトピックには熱量、no_interestには言及しない
- `tools.json`: 使っていないツールを「愛用」と書かない
- `knowledge.json`: 知識レベルに応じた説明の深さ

### ステップ2: 今日の日付確認 + 重複チェック
現在の日付を確認してからネタ探しを開始。

**重複チェック（生成前）:**
`history/adopted_tweets.json` を確認し、直近30件と類似トピックがないか確認する。
詳細ルール: `x-auto/history/RULES.md`

### ステップ3: 界隈ムードチェック（Zeitgeist Awareness）

zeitgeist-snapshot.json を読み込んで日本AI界隈の空気感を確認する。

**読み込み先:** `C:\Users\Tenormusica\x-auto\scripts\data\zeitgeist-snapshot.json`

**ムード情報の活用:**
1. `dominant_mood` と `secondary_mood` を確認
2. `tone_guidance.recommended_approach` をツイートのトーン設計に適用
3. `tone_guidance.topic_affinity` をネタ選定の優先順位に反映
4. `tone_guidance.avoid` に該当するフレーミングを避ける

**適用原則:**
- ムードに「迎合」するのではなく、ムードを「理解した上で」発信する
- ペルソナ（persona-db）は変えない。フレーミングだけを調整する
- `dominant_mood.score` < 0.3 の場合はムード影響弱 → 通常通り生成
- zeitgeist-snapshot.json が存在しない/24h以上古い場合はスキップ

### ステップ4: コンテンツ戦略チェック

`common/content-strategy-ref.md` を読み込み、コンテンツタイプ別のパフォーマンス傾向を把握する。

**読み込み先:** `C:\Users\Tenormusica\x-auto\common\content-strategy-ref.md`

**活用:**
- ネタ選定時に、W-Scoreが高いcontent_type（BIP・体験談等）を優先
- ニュース系を選ぶ場合は速報性を重視（飽和度mainstream以降はスコア低下）
- 独自性の高い切り口を意識する（独自データ・体験・手順を含める）

**注意:** このファイルはcontent_evaluator.pyが毎日自動更新。存在しない場合はスキップ。

### ステップ5: ネタ選定（並列検索構造）

**並列検索サブエージェントで多角的にネタを探索**

#### 5-A. Vault-Dドキュメント確認（最初に実行）
- `D:\antigravity_projects\VaultD\Projects\Monetization\Intelligence\AI_Frontier_Capabilities_Master.md`
- `D:\antigravity_projects\VaultD\Projects\Monetization\Intelligence\AI_Knowledge_Tips_Master.md`

#### 5-B. 並列ネタ検索（6つのサブエージェントを同時実行）

**以下の6つのTask toolを1つのレスポンス内で同時に呼び出す:**

```
Task(subagent_type="general-purpose",
     prompt="以下のスキルファイルを読んで実行:
             C:\\Users\\Tenormusica\\x-auto\\skills\\parallel-news-search\\REDDIT.md

             検索キーワード: Claude Code, AI agent, LLM, prompt engineering, MCP
             今日の日付: [TODAY]")

Task(subagent_type="general-purpose",
     prompt="以下のスキルファイルを読んで実行:
             C:\\Users\\Tenormusica\\x-auto\\skills\\parallel-news-search\\XCOM.md

             検索キーワード: Claude Code, AI agent, LLM, prompt engineering
             今日の日付: [TODAY]")

Task(subagent_type="general-purpose",
     prompt="以下のスキルファイルを読んで実行:
             C:\\Users\\Tenormusica\\x-auto\\skills\\parallel-news-search\\TECHBLOG.md

             検索キーワード: Claude Code, AI agent, LLM, prompt engineering
             今日の日付: [TODAY]")

Task(subagent_type="general-purpose",
     prompt="以下のスキルファイルを読んで実行:
             C:\\Users\\Tenormusica\\x-auto\\skills\\parallel-news-search\\GITHUB.md

             検索キーワード: Claude Code, AI agent, LLM, MCP
             今日の日付: [TODAY]")

Task(subagent_type="general-purpose",
     prompt="以下のスキルファイルを読んで実行:
             C:\\Users\\Tenormusica\\x-auto\\skills\\parallel-news-search\\PRODUCTHUNT.md

             検索キーワード: AI tool, LLM, developer tool
             今日の日付: [TODAY]")

Task(subagent_type="general-purpose",
     prompt="以下のスキルファイルを読んで実行:
             C:\\Users\\Tenormusica\\x-auto\\skills\\parallel-news-search\\HUGGINGFACE.md

             検索キーワード: LLM, local model, fine-tuned
             今日の日付: [TODAY]")
```

#### 5-C. 結果統合・ランキング

**一次情報の発表日基準（CRITICAL）**
ネタの鮮度は**一次情報（公式発表・論文公開・リリースノート・プレスリリース）の公開日**で判定する。
X上での言及日・メディア記事化日・バズった日ではない。

- ✅ 公式ブログに今日公開されたリリースノート → 24h以内
- ❌ 3日前に公式発表済みだが今日Xでバズった → 24h以内ではない
- ❌ 先週の論文を今日メディアが記事化 → 24h以内ではない

**24h→48hフォールバックプロセス**
ユーザーが「24時間以内」と指定した場合の段階的拡大:

1. まず一次情報の発表日が24h以内のトピックを探す
2. **24h以内に目ぼしいネタが見つからない場合** → 即座にユーザーに確認:
   「24時間以内に目立った新規発表がないみたい。48時間以内に広げて探していい?」
3. ユーザー承認後 → 48h以内で再検索
4. 48h以内でも見つからない場合 → ユーザーに報告し、別アプローチを相談

各担当から返ってきた候補を以下の基準で優先順位付け:

| 優先度 | 条件 |
|--------|------|
| 1位 | 0-1日前（一次情報基準） + 個人開発者がすぐ試せる具体的テクニック + 急上昇指標高 |
| 2位 | 0-1日前（一次情報基準） + ベンチマーク・数値比較あり |
| 3位 | 2-3日前 + 独自の実装知見・失敗談（※ユーザーが時間範囲を指定している場合はその範囲内のみ） |
| 4位 | 公式リリースの深掘り分析 |
| 5位 | 新ツール・新モデル（急上昇確認済み） |

**採用優先ソース:**
- Show HN投稿（一次ソースとして高価値）
- 有名AI技術者の実装Tips（@karpathy, @simonw等）
- IndieHackersの成功事例（技術的詳細あり）
- Reddit r/ClaudeAI, r/LocalLLaMAの実体験レポート
- GitHub Trendingの急上昇リポジトリ（100+ stars/日）
- Product Huntの新AIツール（500+ upvotes）
- Hugging Faceの新モデル（10K+ DL/週）

**ネタ選定時の除外対象（CRITICAL - 個人開発者に無関係なネタ）**

以下のカテゴリは**即座にスキップ**し、別のネタを探す:

| 除外カテゴリ | 理由 | 例 |
|-------------|------|-----|
| **資金調達・投資ニュース** | 個人開発者が使える技術ではない | 「○○が$20億調達」「評価額$100億」 |
| **企業買収・M&A** | 個人開発者に直接関係なし | 「○○が△△を買収」 |
| **株価・時価総額** | 投資家向け情報 | 「株価12%上昇」「IPO」 |
| **経営人事・組織再編** | 技術的価値なし | 「CEOが退任」「新CTOに就任」 |
| **規制・法律ニュース** | 個人開発者が今すぐ使える情報ではない | 「EU AI Act」「訴訟」 |
| **データセンター建設** | インフラ投資は個人開発者に無関係 | 「5GWのデータセンター」 |

**採用すべきネタ（個人開発者が「試してみたい」と思うもの）**:
- 新しいAIモデル・ツールのリリース（API/CLI/SDK）
- 既存ツールの新機能・アップデート
- 実装テクニック・ベストプラクティス
- ベンチマーク比較・性能検証結果
- オープンソースプロジェクトの新展開
- 個人開発者の成功事例（技術的な内容を含むもの）

### ステップ6: 情報鮮度チェック（MANDATORY - ツイート作成前の必須工程）

**トピック選定後は絶対にサブエージェントで鮮度チェックを起動する**

実行コマンド:
```
Task(subagent_type="general-purpose",
     prompt="以下のスキルファイルを読んで、その指示に従って情報鮮度をチェックしてください:
             C:\\Users\\Tenormusica\\x-auto\\skills\\news-freshness-checker\\PROMPT.md

             チェック対象:
             - トピック: [TOPIC_NAME]
             - 記事情報: [ARTICLE_INFO]
             - WebSearch結果: [SEARCH_RESULTS]

             PROCEED/REJECT判定を出してください。")
```

**鮮度チェック結果による分岐:**
- **PROCEED 判定** → ステップ7へ進む
- **REJECT 判定** → 別トピックを探してステップ5に戻る

**絶対禁止:** 鮮度チェックをスキップしてツイート作成に進むこと

**注意:** 鮮度チェックサブエージェントが完了するまで、絶対にステップ7以降に進まないこと。REJECT判定の場合は即座に新しいトピック探しを開始する。

**重要な前提: AIパワーユーザーの厳しい鮮度基準**
- ユーザーはX.comで四六時中、AIニュースを常時追跡しているパワーユーザー
- **3-4日前の情報は既に「古いネタ」**と認識される
- Web記事の「今日」「最新」は、数日前の情報を今日記事化しただけの場合が多い
- **表面的な情報で「新鮮」と判定してはいけない** - 徹底調査が必要
- 疑わしい情報はスキップして、確実に新鮮なネタを探す方が信頼性を保つ

### ステップ7: 一次情報チェック（CRITICAL - 誤判定防止の最重要ステップ）

**絶対原則: 以下は全て別物であり、混同厳禁**

| 日付の種類 | 初発表日か？ | 例 |
|-----------|-------------|-----|
| **初発表日（Announcement）** | ✅ **これが基準** | CESで発表、プレスリリース |
| 記事投稿日 | ❌ | メディアが記事化した日 |
| 発売日（Release/Launch） | ❌ | 製品が購入可能になった日 |
| グローバル展開日 | ❌ | 全世界で利用可能になった日 |
| ロールアウト完了日 | ❌ | 段階的展開が完了した日 |
| X上でバズった日 | ❌ | 誰かが言及・拡散した日 |

**ユーザー指定時間範囲との照合（MANDATORY）**
ユーザーが「24時間以内」「48時間以内」等の時間範囲を指定した場合:

1. 特定した一次情報の発表日と、ユーザー指定の時間範囲を照合する
   - **注意**: ステップ5-Cで24h→48hフォールバックが承認された場合、ここでの時間範囲は「48h」に更新される
2. **範囲外の場合** → このネタは採用不可。ステップ5に戻って別ネタを探す
3. **範囲内の場合** → ステップ8へ進む
4. **発表日が特定できない場合** → 「不明」として報告し、ユーザーに採否を確認する

**典型的な誤判定パターン（実際に発生した事例）**:
- ❌ Intel Core Ultra Series 3「1/27発売」→ 実際は1/5 CESで発表（22日前）
- ❌ Gemini 3 Flash「1/26グローバル展開」→ 実際は12/17発表（40日前）
- ❌ OpenAI Operator「記事1/23」→ 実際は2025年6月記事、8月サービス終了済み
- ❌ 3日前の公式発表が今日Xでバズった → 一次情報は3日前（24h以内ではない）

**必須調査（サブエージェントに任せず自分でも確認）**:
- 「本日発売」「本日リリース」の記事を見たら → **いつ発表されたか必ず別途調査**
- WebSearchクエリ: `"[製品名]" "first announced" OR "unveiled" [year]`
- CES/MWC/WWDC/Google I/O等のイベント発表→後日発売パターンを警戒

### ステップ8: ネット上の一次ソース調査（MANDATORY）
- **Vault-D内部情報でも必ずネット上の一次ソースを調査**
- IndieHackersコミュニティ投稿、Reddit、X.com、公式サイト、プレスリリース等を検索
- WebSearch実行例:
  - `"Sleek.design" site:indiehackers.com`
  - `"Sleek.design" "$10K MRR" 2026`
  - `"モバイルアプリUI特化" AI デザイン`
- **ネット上のソースが見つからない場合のみ「なし（内部情報）」とする**
- 見つかったURLは必ず引用リンクとして使用

### ステップ9: ツール競争力調査（新ツール言及時は必須）
- **新しいツール・サービスを紹介する場合は競合比較を必ず実施**
- WebSearch実行例:
  - `[ツール名] vs [競合] ranking 2026`
  - `[ツール名] market position comparison`
  - `AI [カテゴリ] tools ranking 2026`
- **調査項目**:
  - 既存トップツールとの差別化ポイント
  - 市場でのポジション（メジャー/ニッチリーダー/新興）
  - 価格競争力・機能比較
  - 専門分野での優位性

### ステップ10: 投稿文作成

#### 10-A. 生成前の必須適用確認（MANDATORY - 省略禁止）

投稿文を生成する**前に**、以下の共通ルールファイルから適用すべき項目を明示的にリストアップする。
「読んだ」ではなく「この生成で具体的に何を適用するか」を確認する。

```
■ format-rules.md から:
  - 改行パターン: [このツイートで使うブロック構成を事前に決める]
  - 複数案の場合: [案ごとに異なるパターンを事前に割り当てる]

■ expression-rules.md から:
  - 自分フィルター: [使う語尾を事前に決める]
  - 柔らかさ > 情報精度: [「友達に話す」トーンで書いてから情報を織り込む]
  - 固有名詞: [このトピックで使う固有名詞を特定する]
  - 発話リズム: [圧縮と非圧縮の混在を意識する]

■ anti-ai-rules.md から:
  - 露出制御: [トピック自体がOKラインか確認]
  - 禁止パターン: [このトピックで陥りやすい禁止パターンを特定する]

■ value-rules.md から:
  - 5条件: [このツイートが満たす条件を特定する]
  - BIPの場合: [読者アクション起点の具体性を確認する]
```

**このチェックをスキップして生成に入ることは禁止。**
チェック結果は内部メモとして保持し、生成中に参照する。

---

以下の条件でX（Twitter）の投稿文を作成する。

**【共通ルール適用（SKILL.mdフロー ステップ2-3で読み込み済み）】**
以下の共通ルールファイルの全ルールを適用する。ルールの正（source of truth）はcommon/にあるため、ここには再掲しない:
- `common/format-rules.md` — 文字数・読点・改行・空行・引用リンク・略語
- `common/expression-rules.md` — 自分フィルター・推奨語尾・禁止語尾・文体姿勢・発話リズム
- `common/anti-ai-rules.md` — AI臭い表現禁止・露出制御
- `common/value-rules.md` — 5条件・信頼残高・自己テスト

**【AIペルソナ】** ← ステップ1で読み込んだpersona-dbを参照
- `stances.json` の `persona_identity` を適用
- `tone.json` の `speaking_style` と `catchphrases` を適用
- `tone.json` の `avoid_patterns` に該当する表現は絶対禁止

**【本スキル固有ルール（common/に記載のないもの）】**
- 数値の根拠は必ず確認 → 出典が不明確な数値は使わない、正確に引用できない場合は省く
- 締めは「なぜそうなるのか」の起因・メカニズムを突く → `anti-ai-rules.md` Section 4 + `expression-rules.md` 締めルール参照
- 自然な締め方 → 断定ではなく推測・感想として。`expression-rules.md` の自分フィルター原則を適用

**【開発者向け投稿の必須条件】**
- 収益数字より技術的差別性を重視 → 既存トップツール・競合との比較を明示
- **競争力の文脈化必須** → 新ツール紹介時は市場ポジション（メジャー/ニッチリーダー/新興）と競合優位性を明示
- 抽象概念は具体化必須 → 「配信優位性」→「具体的にどんな手法・仕組みか」まで説明
- 馴染みのないサービスには文脈説明必須 → 「何をするツールで、どう動作するか」を冒頭で明示
  - **特にClaude Computer Use** → 「Claude in Chrome的な」「ブラウザ自動操作の」等の補足必須
  - 英語製品名は日本のエンジニアが知ってる類似ツールで説明
- 機能性・技術仕様・アーキテクチャの話を中心にする
- ビジネス成果は技術的理由と紐付けて説明（「なぜその技術選択が成果に繋がったか」）

**【投稿目的（優先順）】**
- リプライを誘発する → 意見が分かれるポイントを含める。問いかけではなく自分の立場を示す
- プロフィールクリックを誘導する → 「この人は他にどんなことを言ってるんだろう」と思わせる独自の視点
- フォローを獲得する → 上記2つの結果として自然に

### ステップ11: レビューデータ準備
**【レビュアーへの提供データ必須】**
- ツール性能調査結果（競合比較・市場ポジション・技術的差別化）
- 真偽性確認結果（価格情報・数値データ・機能説明の出典）
- 情報鮮度詳細（初発表日・記事投稿日・現在日との差分）
- WebSearch実行履歴（どんな検索でどんな結果が得られたか）

### ステップ12: 元ネタ適性判定

**【A判定困難予測時の元ネタ変更】**
- 情報鮮度不足（3日以上前）が明確な場合 → 即座に新しいネタを探す
- 正確性検証が困難（推測・憶測が多い）場合 → より検証可能なネタに変更
- 開発者価値が薄い場合 → より技術的価値の高いネタを選択
- **元ネタ変更は恥ではない** → A判定達成を最優先

**【話題性優先時のトレードオフ判定】**
- バズポテンシャル・注目度が高い場合（IndieHackers、Reddit、X.comで大きな反響）は**情報正確性を適度に緩める**
- トレードオフ基準: 話題性が確証されている > 細かな数値・機能の完全検証
- 推測・憶測でも「らしい」「と思われる」表現で明示すれば許容
- **完全に間違った情報は避けるが、細部の不確定性は話題性とのバランスで判定**

### ステップ13: 出力・レビュー

**CRITICAL GATE: レビューサブエージェントの実行は省略不可**

以下のレビューフローは**ツイート生成フローの不可分な一部**であり、いかなる理由でも省略できない。
- 「テスト生成だから」→ 省略不可
- 「複数案の草案段階だから」→ 省略不可
- 「ユーザーが急いでいるから」→ 省略不可
- 「BIPだから鮮度チェック不要」→ 鮮度以外のレビューは省略不可
- 「前のイテレーションでレビュー済み」→ 再生成したなら再レビュー必須

**レビュー未実行のツイートをユーザーに提示することは禁止。**
レビューが回せない状況なら、その旨をユーザーに報告して判断を仰ぐ。

---

**【レビューフロー必須（2段階+事前鮮度チェック） - サブエージェントで独立実行】**

**事前チェック（ステップ6で実施済み）:**
- 情報鮮度チェック（BIPで一次情報なしの場合はスキップ可）

**ステップ13で実行:**

1. **基本ルールレビュー**: review-tweet サブエージェント実行
```
Task(subagent_type="general-purpose",
     prompt="以下のスキルファイルを読んで、その指示に従ってツイートをレビューしてください:
             C:\\Users\\Tenormusica\\x-auto\\skills\\review-tweet\\PROMPT.md

             レビュー対象ツイート:
             [TWEET_TEXT]

             調査情報:
             - 競合比較結果: [COMPETITIVE_ANALYSIS]
             - 数値の出典: [DATA_SOURCES]
             - 情報鮮度: [FRESHNESS_INFO]

             PASS/FAIL判定を出してください。")
```

2. **厳しめ有益性レビュー**: tweet-quality-judge サブエージェント実行
```
Task(subagent_type="general-purpose",
     prompt="以下のスキルファイルを読んで、その指示に従って厳格に品質判定してください:
             C:\\Users\\Tenormusica\\x-auto\\skills\\tweet-quality-judge\\PROMPT.md

             判定対象ツイート:
             [TWEET_TEXT]

             引用リンク: [URL]
             ツール性能調査結果: [TOOL_ANALYSIS]
             真偽性確認結果: [VERIFICATION_RESULTS]
             情報鮮度詳細: [FRESHNESS_DETAILS]
             WebSearch実行履歴: [SEARCH_HISTORY]

             A/B/C/D判定を出してください。")
```

4. **A判定で初めて合格・投稿可能**
5. **B/C/D判定時は元ネタ変更を検討**

**【サブエージェントレビューの意義】**
- 生成者と別の独立したコンテキストでレビュー → 本当の第三者視点
- 同一コンテキストの「まあいいか」バイアスを排除
- 各レビュアーが生成時の思い入れなしで客観判定

**【出力フォーマット】**
```
## 投稿文

[ツイート本文]

[引用リンクURL または「なし（[情報源説明]）」]

---

**文字数**: [N]文字
**引用リンク**: [URL または なし（[情報源説明]）]
**元ネタ**: [ソース説明]
**初発表日**: [YYYY-MM-DD]
```

### ステップ14: Discord #tweet-drafts 自動保存（MANDATORY）

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
- 引用リンクも本文に含めて送信

### ステップ15: 採用確認・履歴記録（MANDATORY - フロー最終ステップ）

**ツイート提示後、必ず以下を実行:**

1. ユーザーに「採用する？」と確認
2. 採用の場合 → 履歴に記録
3. 不採用・修正依頼の場合 → 修正して再提示

**採用時の記録手順:**
```
1. history/adopted_tweets.json を Read
2. 新規エントリを追加:
   {
     "id": "YYYY-MM-DD-NNN",
     "adopted_at": "ISO8601",
     "topic": "トピック要約（20字以内）",
     "pattern": "パターン名",
     "skill_used": "generate-tweet",
     "char_count": 文字数,
     "sources": [{"name": "...", "url": "..."}],
     "content": "本文"
   }
3. Write で保存
4. 「履歴に記録したよ♪」と報告
```

**重複チェック:** ステップ2で実施済み。
