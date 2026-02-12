# Claude Code x GEO戦略ツイート5本 v2（2026-02-12）

戦略軸: Claude Code追い風局面。上級者でも知らない深い用途 x GEO/Build in Public
難易度: 高（既存ユーザーの90%が知らないレベル）

---

## Tweet 1: Hooks品質ゲート（PreToolUse/PostToolUse）

Claude CodeのHooksにはPreToolUse/PostToolUseっていう「ツール実行の前後に自動でスクリプトを挟む」仕組みがある。git pushの前に自動テスト実行とかファイル保存後にlint走らせるとかCI/CDをローカルに持ってこれる

さらにUserPromptSubmitフックで入力テキストを前処理できるから「特定キーワード検知→自動コンテキスト読み込み」の条件分岐も組める。Hooksの存在は知ってても具体的なイベント種別まで使い分けてる人はほぼいないと思うんだよね。Claude Codeの自動化ポテンシャルの本体はここにある

引用リンク: なし（自身の運用経験）

---

## Tweet 2: Skills定期実行パイプライン（SKILL.md + cron/Task Scheduler）【Politeモード】

Claude Codeは.claude/skills/にSKILL.mdを置くとカスタムコマンドになります。これをclaude -p(非対話モード)とcron(Mac/Linux)やTask Scheduler(Windows)に載せると毎朝自動で実行される仕組みが作れます

情報収集から分析して構造化レポートを生成し記事ドラフトまで出力する全自動パイプラインを組むと実質的にOpenClawやDeep Researchと同じような自動リサーチ環境が手元で動いている状態になります。毎朝6時に最新レポートが生成されている状態を人力ゼロで維持できるのはかなり便利だと感じています

引用リンク: なし（自身の運用経験）

---

## Tweet 3: サブエージェント並列オーケストレーション

Claude CodeのTask toolで1セッションから複数サブエージェントを並列起動できる。Exploreエージェントでコードベース調査しつつBashエージェントでテスト実行しつつgeneral-purposeで外部リサーチ。全部同時に走らせてメインで結果を統合する

実質1人で5人分の並列作業ができる。Build in Publicでこの「ソロ開発なのにチーム体制」の実態を見せるとAIが書けない体験記になる。開発スピードの具体的な数値を出せばGEOで引用されやすい一次データにもなる

引用リンク: なし（自身の運用経験）

---

## Tweet 4: Context Engineering（CLAUDE.md 3階層 + auto-memory + /compact制御）

Claude CodeのCLAUDE.mdはグローバル(~/.claude/)→プロジェクト直下→サブディレクトリの3階層で上書きできる。さらにauto-memoryでセッション跨ぎの記憶が永続化されて/compactのタイミング制御で情報の取捨選択もできる

これはContext Engineeringっていう「AIの認知をファイル設計で意図的にコントロールする」上位概念だと思ってる。プロンプトエンジニアリングの次のレイヤー。この深さで構造化された解説記事はAI検索に引用されやすいしまだ書いてる人がほぼいない

引用リンク: なし（自身の運用 + 概念整理）

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
