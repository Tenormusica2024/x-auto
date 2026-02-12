# Claude Code x GEO戦略ツイート5本 v2（2026-02-12）

戦略軸: Claude Code追い風局面。上級者でも知らない深い用途 x GEO/Build in Public
難易度: 高（既存ユーザーの90%が知らないレベル）

---

## Tweet 1: Hooks品質ゲート（PreToolUse/PostToolUse）

Claude CodeのHooksにはPreToolUse/PostToolUseっていう「ツール実行の前後に自動でスクリプトを挟む」仕組みがある。git pushの前に自動テスト実行とかファイル保存後にlint走らせるとかCI/CDをローカルに持ってこれる

さらにUserPromptSubmitフックで入力テキストを前処理できるから「特定キーワード検知→自動コンテキスト読み込み」の条件分岐も組める。Hooksの存在は知ってても具体的なイベント種別まで使い分けてる人はほぼいないと思うんだよね。Claude Codeの自動化ポテンシャルの本体はここにある

引用リンク: なし（自身の運用経験）

### サムネイル画像プロンプト（日本アニメ風 2パターン）

**パターンA: 品質ゲートの番人（ファンタジー寄り）**
```
Japanese anime style illustration, a young programmer at a futuristic desk, a large translucent shield barrier between the code editor and a git push button, the shield has glowing green checkmarks and red X marks floating around it, small robot sentinels inspecting code before it passes through the gate, warm lighting from monitors, cyberpunk meets cozy workspace aesthetic, vibrant colors with teal and orange accents, no text overlay, 16:9 aspect ratio
```

**パターンB: 自動品質チェック（メカニカル工場風）**
```
Japanese anime style illustration, a conveyor belt system in a clean high-tech factory, code files moving along the belt, robot arms with magnifying glasses inspecting each file, some files get green stamps of approval while others get redirected with red warning lights, a young developer watching from a control panel with a satisfied expression, bright industrial lighting with blue and yellow accents, Makoto Shinkai inspired clean aesthetic, no text overlay, 16:9 aspect ratio
```

---

## Tweet 2: Skills定期実行パイプライン（SKILL.md + cron/Task Scheduler）【Politeモード】

Claude Codeは.claude/skills/にSKILL.mdを置くとカスタムコマンドになります。Macならcron(またはlaunchd)でWindowsならTask Schedulerでclaude -pをスケジュール登録すると毎朝自動で実行される仕組みが作れます

話題のOpenClawはメッセージングアプリ経由の常駐型エージェントですがClaude Codeはスケジュール実行型で出力フォーマットをSKILL.mdで構造化できます。情報収集から分析して構造化レポート生成まで全自動パイプラインを組むとOpenClaw相当の自動リサーチ環境がcron一行で定期実行できます。常駐させなくても毎朝6時に勝手にレポートが生成されている状態を作れるのは便利だと感じています

引用リンク: なし（自身の運用経験）

### サムネイル画像プロンプト（日本アニメ風 2パターン）

**パターンA: 朝の自動化（穏やかな日常系）**
```
Japanese anime style illustration, a young programmer sleeping peacefully in bed at dawn, warm morning sunlight through window curtains, while a glowing laptop on the desk shows a terminal with scrolling text and auto-generated reports, digital clock showing 6:00 AM, cozy room with coffee mug and tech books, soft color palette with orange sunrise tones, Studio Ghibli inspired warm atmosphere, no text overlay, 16:9 aspect ratio
```

**パターンB: 自動パイプライン（SF寄りメカニカル）**
```
Japanese anime style illustration, a confident young developer sitting back in chair with arms crossed and a satisfied smile, multiple holographic screens floating around showing data flows and automated pipelines, one screen shows a cron schedule another shows a structured report being generated, futuristic but clean workspace, cool blue and purple neon accents contrasting with warm desk lamp light, Makoto Shinkai inspired detailed lighting, no text overlay, 16:9 aspect ratio
```

---

## Tweet 3: サブエージェント並列オーケストレーション

Claude CodeのTask toolで1セッションから複数サブエージェントを並列起動できる。Exploreエージェントでコードベース調査しつつBashエージェントでテスト実行しつつgeneral-purposeで外部リサーチ。全部同時に走らせてメインで結果を統合する

実質1人で5人分の並列作業ができる。Build in Publicでこの「ソロ開発なのにチーム体制」の実態を見せるとAIが書けない体験記になる。開発スピードの具体的な数値を出せばGEOで引用されやすい一次データにもなる

引用リンク: なし（自身の運用経験）

### サムネイル画像プロンプト（日本アニメ風 2パターン）

**パターンA: 並列チーム（戦隊ヒーロー風）**
```
Japanese anime style illustration, a young developer sitting at center desk, surrounded by 5 translucent holographic AI agent avatars each doing different tasks simultaneously, one agent reads code files, another runs tests in terminal, another searches the web, another writes documentation, another reviews pull requests, energy lines connecting all agents back to the developer, dynamic composition with radial layout, vibrant purple and cyan color scheme, action manga inspired dynamic pose, no text overlay, 16:9 aspect ratio
```

**パターンB: オーケストラ指揮者（音楽メタファー）**
```
Japanese anime style illustration, a young developer standing like an orchestra conductor with a glowing baton, conducting multiple floating holographic screens arranged in a semicircle like orchestra sections, each screen shows a different task being executed autonomously, musical note particles flowing between screens representing data exchange, grand concert hall aesthetic mixed with futuristic tech, warm golden spotlight on the conductor, deep blue and gold color palette, Studio Ghibli inspired grandeur, no text overlay, 16:9 aspect ratio
```

---

## Tweet 4: Context Engineering（CLAUDE.md 3階層 + auto-memory + /compact制御）

Claude CodeのCLAUDE.mdはグローバル(~/.claude/)→プロジェクト直下→サブディレクトリの3階層で上書きできる。さらにauto-memoryでセッション跨ぎの記憶が永続化されて/compactのタイミング制御で情報の取捨選択もできる

これはContext Engineeringっていう「AIの認知をファイル設計で意図的にコントロールする」上位概念だと思ってる。プロンプトエンジニアリングの次のレイヤー。この深さで構造化された解説記事はAI検索に引用されやすいしまだ書いてる人がほぼいない

引用リンク: なし（自身の運用 + 概念整理）

### サムネイル画像プロンプト（日本アニメ風 2パターン）

**パターンA: 3層構造の塔（建築メタファー）**
```
Japanese anime style illustration, a mystical three-layer floating tower in a digital sky, bottom layer labeled Global glows blue, middle layer labeled Project glows green, top layer labeled Sub-directory glows gold, data streams flowing upward between layers like waterfalls in reverse, a young developer standing at the base looking up in awe, memory crystals orbiting the tower representing persistent context, dreamy cloud background with circuit board patterns, fantasy RPG meets tech aesthetic, warm magical lighting, no text overlay, 16:9 aspect ratio
```

**パターンB: 脳内マッピング（ニューラル風）**
```
Japanese anime style illustration, a young developer with eyes closed in meditation pose, above their head a visible neural network visualization showing three concentric rings representing context layers, innermost ring glows gold for sub-directory context, middle ring glows green for project context, outer ring glows blue for global context, memory nodes pulsing with light as information flows between layers, serene cyberpunk meditation room with floating screens, purple and teal bioluminescent accents, Ghost in the Shell inspired aesthetic, no text overlay, 16:9 aspect ratio
```

---

## Tweet 5: Self-Correcting Repository（プロジェクトCLAUDE.md自己修正ループ）【Politeモード】

Claude Codeのプロジェクト直下CLAUDE.mdにミスパターンを自動記録させるとリポジトリが時間とともに賢くなる仕組みが作れます。Boris Cherny方式のSelf-Correcting Repositoryです

表面的に真似すると発火しないことが多いのでポイントを共有します。まずグローバルCLAUDE.mdではなくプロジェクト単位のCLAUDE.mdに書くのが前提です。発火条件は「違う」「修正して」「やり直し」等の指摘キーワードを明示的に列挙しておく必要があります。記録フォーマットも「[日付] 失敗パターン: 要点 → 正しいやり方」で固定しないとClaude側が参照できません。「ミスを記録して」のような曖昧指示では発火せず「指摘を受けたら即座にこのフォーマットで追記」と具体行動で書くのが肝だと感じています

引用リンク: なし（Boris Cherny方式 + 自身の運用経験）

---

## v1からの変更点

| v1 | v2 | 変更理由 |
|----|-----|---------|
| claude -p基本紹介 | Skills + Task Scheduler全自動パイプライン | 定期実行の「仕組み」まで踏み込み |
| CLAUDE.md基本 | Context Engineering 3階層設計 | 上位概念として再定義 |
| Hooks基本紹介 | PreToolUse/PostToolUse品質ゲート | 具体的イベント種別の使い分け |
| --resume基本 | サブエージェント並列オーケストレーション | Task tool活用の高度パターン |
| 個人ブランド一般論 | Self-Correcting Repository | Boris Cherny方式の具体的手法 |

## 選定戦略サマリー

| # | 高度機能 | GEO戦略との接点 | 推定認知度 |
|---|---------|----------------|-----------|
| 1 | Hooks品質ゲート | 開発プロセス自体をコンテンツ化 | ~5% |
| 2 | Skills定期実行パイプライン | 鮮度シグナル自動維持 | ~10% |
| 3 | サブエージェント並列 | BIPの質量を並列で向上 | ~15% |
| 4 | Context Engineering | 深い解説=AI検索引用されやすい | ~10% |
| 5 | Self-Correcting Repository | AI育成記録=ユニーク体験記 | ~5% |
