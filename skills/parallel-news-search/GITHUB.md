# GitHub Trending担当 - 急上昇リポジトリ検索

## 役割
GitHub Trendingから、個人開発者向けのAIツール・ライブラリ・実装テクニックを検索する。

## 対象

| カテゴリ | 検索方法 |
|---------|----------|
| **Daily Trending** | 今日スター急増のリポジトリ |
| **Weekly Trending** | 今週スター急増のリポジトリ |
| **AI/ML関連** | language:python topic:ai OR topic:llm |

## 検索クエリ例

WebSearchで以下を実行:

```
site:github.com/trending AI [現在の月] [現在の年]
site:github.com "stars today" LLM agent
site:github.com topic:claude-ai
site:github.com topic:langchain stars:>100
site:github.com topic:ai-agent created:>[1週間前の日付]
```

## 急上昇指標の確認

**必ず確認すべき数値:**
- **Today's stars**: 今日獲得したスター数（急上昇の直接指標）
- **Total stars**: 総スター数（信頼性の指標）
- **Fork数**: 実際に使われているかの指標
- **Last commit**: 最終更新日（メンテナンス状況）

**採用基準:**
- Today's stars: 50+ → 高優先度
- Today's stars: 20-50 → 中優先度
- Total stars: 1000+ → 信頼性あり

## 採用基準

**採用すべきリポジトリ**:
- 新しいAIエージェントフレームワーク
- LLM活用ツール・CLI
- プロンプトエンジニアリング関連
- AI開発のベストプラクティス集
- 個人開発者がすぐ試せるサンプルコード

**スキップすべきリポジトリ**:
- 企業向け大規模インフラ
- 論文実装のみ（実用性低い）
- 1週間以上前のトレンド
- ドキュメント・チュートリアルのみ（コードなし）

## 出力フォーマット

```
## GitHub Trending検索結果

### 候補1
- **リポジトリ**: [owner/repo]
- **説明**: [リポジトリ説明]
- **スター**: [総数] (今日: +[今日の増加])
- **言語**: [主要言語]
- **最終更新**: [日付]
- **URL**: [URL]
- **技術的価値**: [高/中/低] - [理由]
- **個人開発者向け度**: [高/中/低]

### 候補2
...

### 検索完了時刻: [HH:MM]
```
