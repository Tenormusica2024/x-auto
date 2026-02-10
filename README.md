# X Auto Posting System

X(Twitter)自動投稿システム - Claude Code + Task Scheduler による定期実行

## 概要

AIパワーユーザー・個人開発者向けのX投稿を自動生成・投稿するシステム。
Claude in Chrome を使用してログイン状態を維持しながら自動投稿を実行。

## 投稿パターン

### パターンA: ニュース速報系
- **鮮度要件**: 1日以内の初発表ニュースを最優先
- **一次情報チェック**: 記事投稿日ではなく、ニュースの初発表日を基準に判定
- **拡張ロールアウト・対応地域追加は新ニュースとして扱わない**

### パターンB: 深堀り知見共有系
- 有力記事/ブログ/スレッドを参照し、知見を深堀りして共有
- 実体験レポート、比較分析、独自検証結果があるソースを優先

## 投稿ルール

### 基本フォーマット
- 読点（、）完全禁止 → 文の区切りは改行のみ
- 絵文字0個（完全禁止）
- ハッシュタグ禁止
- 敬語禁止（温和な常体で統一）
- 画像または引用リンク必須

### 禁止事項
- AI臭い丁寧語 → 「〜ですね」「〜と思います」の多用NG
- 伸ばし棒語尾 → 「〜だよなー」「〜かなー」NG
- 表面的感想 → 「すごい」「驚いた」だけで終わるNG
- 宣伝臭いリプライ誘導 → 「みんなどんな工夫してる?」NG
- 当たり前の結論で締めない → 「継続が大事」等NG
- 宣伝・共有アピール禁止 → 「〜も納得ですね」「参考になる」NG
- レトリカル・クエスチョン（修辞疑問）避ける → 「なぜか?」等の自問自答型NG
- 同一段落内の過剰改行 → 2-3文は繋げて1つの塊に

### ペルソナ
- **キャラクター**: オタク＆AI博識マン
- **特徴**: 技術的知識豊富、最新AIトレンドに詳しい
- **スタンス**: 表面的リアクションではなく技術の本質・意味・インパクトを捉える

## 技術構成

### 使用ツール
- **Claude in Chrome**: ログイン状態でのブラウザ自動操作
- **Task Scheduler**: Windows定期実行
- **Claude Code Skills**: 投稿生成・レビュー用プロンプト

### ディレクトリ構成
```
x-auto/
├── README.md                 # 本ファイル
├── skills/
│   ├── generate-tweet/       # ツイート生成スキル
│   │   └── PROMPT.md
│   ├── review-tweet/         # ツイートレビュースキル
│   │   └── PROMPT.md
│   └── post-tweet/           # 投稿実行スキル
│       └── PROMPT.md
├── scripts/
│   ├── wrapper.ps1           # Task Scheduler用ラッパー
│   └── post.bat              # 投稿実行バッチ
└── logs/                     # 実行ログ
```

## Task Scheduler設定

### 実行頻度
- 1日2-3回推奨
- 朝（9:00）、昼（12:00）、夕方（18:00）

### 設定手順
1. `wrapper.ps1` を Task Scheduler に登録
2. トリガー: 毎日指定時刻
3. 操作: `powershell.exe -File wrapper.ps1`

## 情報ソース

### メインソース（定期更新）
- `D:\antigravity_projects\VaultD\Projects\Monetization\Intelligence\AI_Frontier_Capabilities_Master.md`
- `D:\antigravity_projects\VaultD\Projects\Monetization\Intelligence\AI_Knowledge_Tips_Master.md`

### 最新ネタ探索
- X.com バズツイート
- Reddit/HN 最新スレッド
- 技術ブログ（Medium, dev.to, Zenn）

## 関連ドキュメント

- 詳細ルール: `D:\antigravity_projects\VaultD\Projects\Monetization\Intelligence\permanent\x-algorithm-monetization\README.md`
- 鮮度判定サブエージェント: `C:\Users\Tenormusica\.claude\skills\x-post-freshness-checker\PROMPT.md`
