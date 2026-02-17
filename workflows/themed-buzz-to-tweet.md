# ネタ探し→ツイート生成ワークフロー

方向性確認 → ネタ収集（twscrape/Grok/Discord） → フィルタ・選定 → ツイート生成 → レビューの一連フロー。
BIP・エンジニアの生き方・AIニュースの3方向に対応。

## 発火条件

- テーマを絞ったツイート生成指示（「AIコーディング系のツイート作って」等）
- バズツイートを参考にしたネタ探し指示
- ネタ指定なしの「ツイート作って」（デフォルトルート）

## フロー概要

```
Phase 0: 方向性確認（ユーザーに1問だけ聞く）
    ↓
Phase 1: テーマ特化バズ抽出（themed_buzz_extractor.py）
    ↓
Phase 2: Grok API + Discord #en-buzz-tweetsで最前線の文脈取得
    ↓
Phase 3: 一般論フィルタ + 方向別ネタ選定
    ↓
Phase 4: ツイート生成（方向別スキル選択）
    ↓
Phase 5: レビュー + 品質判定
```

## Phase 0: 方向性確認（MANDATORY）

ワークフロー開始時に、ユーザーに**1問だけ**方向性を聞く。ユーザーの初期指示が雑でも、ここで方向を確定させる。

**質問**: 「今日はどの方向でいく？」

| 選択肢 | 内容 | ネタ探しの重点 |
|--------|------|--------------|
| **BIP（個人開発ジャーニー）** | 作った・壊れた・出した・売れた系 | twscrape + Grok（苦労/達成/感情キーワード） |
| **エンジニアの生き方** | AI時代のキャリア・役割・スキル論 | Discord #en-buzz-tweets + Grok（議論/問い系） |
| **AIニュース** | 最新のAI動向・ツール・発表 | Grok API + AI_Frontier_Capabilities_Master.md |
| **おまかせ** | 全ソースから良いネタを選定 | 全ソース横断、スコア高い順 |

**Phase 0をスキップしない。** ユーザーが「AI系ツイート作って」と言っても、BIP/生き方/ニュースのどれかで出力が全く変わるため。

**例外**: ユーザーが明示的に方向を指定している場合はPhase 0をスキップ可能
- 「BIPツイート作って」→ BIP確定
- 「エンジニアの将来系のツイート」→ エンジニアの生き方確定
- 「最新AIニュースでツイート」→ AIニュース確定

**おまかせの実行手順**: Phase 1を実行 + Phase 2で全方向のGrokクエリを実行 + Phase 3で全ソースからスコア上位のネタを選び、ネタの性質から方向を自動決定する。以降のPhase 4-5はその方向に従う

## Phase 1: テーマ特化バズ抽出

twscrapeで日本語バズツイートを抽出する。汎用のbuzz_tweet_extractor.pyとは別スクリプト。

**方向別の使い分け:**
- **BIP**: Phase 1を実行（日本語バズが主要ソース、`--theme ai-coding-role`）
- **エンジニアの生き方**: Phase 1はスキップ。Discord + Grokの英語ソースの方がネタが豊富。日本語圏の議論も拾いたい場合のみ実行
- **AIニュース**: Phase 1はスキップ。Phase 2のGrok `--mode web` + `AI_Frontier_Capabilities_Master.md` を主力にする（ai-news用themeは未実装）
- **おまかせ**: Phase 1を実行

```bash
python -X utf8 "C:\Users\Tenormusica\x-auto\scripts\themed_buzz_extractor.py" --theme ai-coding-role
```

| 項目 | 値 |
|------|-----|
| 検索期間 | 48h |
| min_faves | 200 |
| 出力件数 | 上位50件 |
| 出力先 | `scripts/data/themed-buzz-{theme}-{date}.json` |
| accounts.db | `C:\Users\Tenormusica\Documents\ai-buzz-extractor-dev\accounts.db` |

### テーマ一覧確認

```bash
python -X utf8 "C:\Users\Tenormusica\x-auto\scripts\themed_buzz_extractor.py" --list-themes
```

### 英語バズツイートの補完ソース

Phase 1は日本語ツイート中心のため母数が少ない場合がある。英語バズツイートは以下で補完（詳細手順はPhase 2参照）:

- **Discord #en-buzz-tweets**（自動配信・無料）: Phase 2で参照。特に「エンジニアの生き方」方向で有効
- **Grok API**（主力）: Phase 2で実行。`lang:en` クエリで直接取得
- **定期抽出パイプライン**（補助）: TweeterPyベースの自動抽出データ
  - 抽出済みデータ: `C:\Users\Tenormusica\en_buzz_tweets_final.json`
  - 除外ルール: `C:\Users\Tenormusica\en_buzz_exclusion_rules.json`

## Phase 2: Grok APIで最前線の文脈取得

Claude Code単独では鮮度が落ちる傾向があるため、Grok APIで「今この瞬間のホットな議論」を取得する。

### 目的

- 一般論と最前線の議論を区別するための基準情報を得る
- Claude Codeの知識カットオフを補完する
- Phase 0で選んだ方向に合ったネタを直接取得する

### Discord #en-buzz-tweets の参照（エンジニアの生き方方向で特に有効）

Captain Hookが約1時間ごとに英語バズツイート14-20件を自動投稿。Like数ソート済み・日本語要約付き。

- チャンネル: `https://discord.com/channels/1471143157432320238/1473225110063415316`
- サーバー: 自動化通知
- 形式: `@username (xxxxL): [日本語要約]` + 元ツイートURL

```
参照手順（CiC必須）:
1. CiCでDiscordタブを開く（またはナビゲート）
2. #en-buzz-tweets チャンネルの最新投稿を read_page で読み取り
3. 方向に合うツイートをピックアップ（ユーザー名・Like数・要約・URL）
```

**CiCが使えない場合**（`claude --chrome` で起動していないセッション）: Discord参照をスキップし、Grok APIに集中する。Grokのクエリに英語キーワードを多めに入れて補完する。

### Grok API 実行例（Phase 0の方向別）

```bash
# === BIP方向 ===
python -X utf8 "C:\Users\Tenormusica\scripts\grok_research.py" --mode x "claude code cursor building shipped debugging frustrated finally fixed solo developer indie hacker 2026 lang:en"
python -X utf8 "C:\Users\Tenormusica\scripts\grok_research.py" --mode x "\"build in public\" AI coding shipped launched broke fixed 2026 lang:en min_faves:30"

# === エンジニアの生き方方向 ===
python -X utf8 "C:\Users\Tenormusica\scripts\grok_research.py" --mode x "AI replacing engineers software developer career future role 2026 lang:en min_faves:50"
python -X utf8 "C:\Users\Tenormusica\scripts\grok_research.py" --mode x "vibe coding エンジニア 不要 役割 2026年 最新の議論"

# === AIニュース方向 ===
python -X utf8 "C:\Users\Tenormusica\scripts\grok_research.py" --mode x "AI announcement release launch new model 2026 lang:en min_faves:100"
python -X utf8 "C:\Users\Tenormusica\scripts\grok_research.py" --mode web "AI 最新ニュース 2026年2月"
```

### コスト

1クエリ約0.4-0.9円（grok-4-fast）。3クエリ実行で約2円。

### Grokクエリ設計のコツ

- `lang:en` で英語圏のツイートを直接取得（日本語圏より母数が多い）
- **BIP方向**: 感情キーワード（frustrated, finally fixed, shipped, struggle, win）を混ぜる
- **エンジニアの生き方方向**: キャリア・役割キーワード（replacing, career, future, role, hiring, unnecessary）を使う
- **AIニュース方向**: 製品・発表キーワード（release, launch, announcement, new model）を使う
- `min_faves:30` 以上で品質フィルタ

## Phase 3: 一般論フィルタ + 方向別ネタ選定

Phase 1（日本語バズ）、Phase 2（Grok + Discord）の結果を統合し、Phase 0の方向に沿ってネタを選定する。

### 議論進行度による鮮度判定（MANDATORY）

**`common/discourse-freshness.md` を参照し、ネタの論点がどの段階にあるか確認する。**

| 段階 | 対応 |
|------|------|
| [消化済] | この論点では書かない。除外 |
| [主流化中] | そのまま書くと遅い。主流化の先の問題点を切り口にする |
| [最前線] | ここから書く |
| [未マッピング] | Phase 2のGrok API結果で現在地を確認してから判断 |

**一般論フィルタ（従来基準も併用）:**

以下に該当する論点は「一般論」として除外:

- 大方のAIユーザーが既に認識している（耳にタコができる状態）
- 「AIは便利」「プロンプトが大事」「設計力が重要」レベルの抽象論
- Phase 2のGrok結果と照合して、数ヶ月前から言われている内容
- `discourse-freshness.md` で[消化済]にマッピングされている論点

### 方向別ネタ採用基準

Phase 0で選んだ方向に応じて、採用基準を切り替える。

#### BIP（個人開発ジャーニー）

| 基準 | 例 |
|------|-----|
| 開発中の具体的な苦労 | バグ格闘、デプロイ失敗、環境構築地獄 |
| 達成の瞬間 | ようやく動いた、ship完了、初ユーザー獲得 |
| AIでも解決しない問題のトラブルシュート | 数時間格闘→AI投入→秒で解決の感情ギャップ |
| ポジティブシンキング | しんどいけど前に進んでる系 |
| 開発者あるあるの共感 | 未完プロジェクト増殖、やめる判断の難しさ |

#### エンジニアの生き方（AI時代のキャリア・役割論）

| 基準 | 例 |
|------|-----|
| AI時代のエンジニアの役割への問い | 「AIがコード書くなら人間は何をするのか」 |
| 不要論への反論・考察 | 「本番環境のCSS触ったことないでしょ」系 |
| スキルシフトの実感 | コーディング力→設計力→判断力への移行体験 |
| 共存の具体例 | AIと人間の分業が上手くいったケース |
| キャリア戦略の議論 | 「中級エンジニアは危ない」「専門性を磨け」系 |

#### AIニュース

| 基準 | 例 |
|------|-----|
| 速報性がある新発表 | 新モデルリリース、大型買収、API価格改定 |
| 開発者に直接影響する変更 | ツールの仕様変更、新機能リリース |
| 数字で語れるインパクト | 「○倍速くなった」「$○で使える」 |

### 除外フィルタ（ノイズ除去）

抽出ツイートから以下のノイズを除外する。除外ルール体系は `C:\Users\Tenormusica\en_buzz_exclusion_rules.json` に定義。

| カテゴリ | 内容 | 例 |
|---------|------|-----|
| 企業公式アカウント | プロダクト宣伝・ニュース速報系 | @claudeai, @techcrunch, @bloomberg等 |
| プロモキーワード | チュートリアル・コース勧誘・リスト記事 | "follow me for", "free ebook", "step-by-step guide" |
| 無関係コンテンツ | 開発文脈と関係のない話題 | 政治、ゴシップ |
| botパターン | 自動投稿・プレスリリース | "breaking:", "#ad", "proud to announce" |
| 短文フィルタ | URL除外後5単語未満 | リンクだけのツイート |

**原則: 個人の声（苦労・達成・感情・問い・考察）を残し、宣伝・bot・リスト記事を除外する。**

### ネタ候補の絞り込み

Phase 1+2の全ソースから、**3-5件のネタ候補に絞る**。Phase 4で各ネタから1案ずつ生成し、計3案をPhase 5に渡す。

### ペルソナとの接点チェック

persona-db 6ファイルと照合（persona-ref.mdの5ファイル + experiences.json）:
- tone.json: 禁止表現・語尾パターンとの衝突がないか
- stances.json: 自分のスタンスと矛盾しないか
- interests.json: high_interestの領域か
- tools.json: 自分が使っているツール（Claude Code MAXなど）との接点
- knowledge.json: expertレベルで語れるネタか、awareレベルなら謙虚な切り口にできるか
- experiences.json: 自分の実体験と重なるか

**ペルソナと接点がないネタは採用しない。**

## Phase 4: ツイート生成

既存のgenerate-tweetフローに乗せる。

### スキル選択（方向別）

| 方向 | 推奨スキル | 理由 |
|------|-----------|------|
| BIP | `skills/generate-tweet/PROMPT.md`（短文） | 感情ドリブン・共感型は短文が刺さる |
| エンジニアの生き方 | `skills/generate-tweet/PROMPT.md`（短文） | 問い型は短く切れた方がインパクトが出る |
| AIニュース | 内容量で判断: 数字1つ+感想→短文 / 背景解説が必要→`skills/long-form-tweet/PROMPT.md` | ニュースの重みで使い分け |
| おまかせ | ネタの性質に応じて上記から選択 | — |

### 生成候補数

**各方向3案生成する。** Phase 5でA判定を得た案のみ採用。3案すべてB以下の場合はネタ変更またはリライト。

### 読み込み順序（省略禁止）

1. `common/persona-ref.md` → persona-db 5ファイル全読み込み
2. `common/anti-ai-rules.md`
3. `common/format-rules.md`
4. `common/expression-rules.md`
5. `common/value-rules.md`
6. `common/discourse-freshness.md`（論点の鮮度段階確認）
7. `scripts/data/zeitgeist-snapshot.json`（トーン調整用）
8. スキルのPROMPT.md（BIP/生き方→`generate-tweet`、AIニュース→内容量で`generate-tweet` or `long-form-tweet`）

### 方向別の生成制約

#### 共通制約（全方向）
- 英語ツイートの論点を参考にするが**文面はコピーしない**
- Phase 2のGrok結果から得た「今の最前線」の文脈を織り込む
- 一般論的な結論で締めない

#### BIP方向
- ニュースの紹介・要約ではなく**実体験ベースの感情ドリブン**で書く
- 「問い」や「感情の吐露」型にする
- 締めは当事者としての実感・等身大の感情で終わる

#### エンジニアの生き方方向
- **問いを立てる構造**にする（答えを出すのではなく問いを提示）
- 不要論への単純な賛否ではなく、**自分の体験から見えた景色**を描く
- 「〜だと思わない？」「〜ってどうなんだろう」型の締めが有効
- 抽象論（「設計力が大事」「学び続けろ」）で締めない → 具体的な場面描写で終わる

#### AIニュース方向
- ニュースの要約で終わらせない → **自分にとって何が変わるか**の一言を添える
- 数字・事実を前面に出し、感想は短く締める
- 速報性が命 → 鮮度チェック（`news-freshness-checker`）必須

## Phase 5: レビュー + 品質判定

1. `common/discourse-freshness.md` で論点の段階を再確認（生成後に改めてチェック）
2. `skills/review-tweet/PROMPT.md` で基本ルール準拠チェック
3. `skills/tweet-quality-judge/PROMPT.md` でA/B/C/D判定

**レビュー依頼時にPhase 0の方向を明示する。** 例: 「エンジニアの生き方方向で生成した3案をレビューして」。方向が伝わらないと評価軸がズレる。

方向別の重点評価:

| 方向 | 重視する評価軸 | 緩和する評価軸 |
|------|--------------|--------------|
| BIP | 開発者価値・表現品質・共感度 | 情報鮮度（意見・体験型のため） |
| エンジニアの生き方 | 問いの鋭さ・当事者性・共感度 | 情報鮮度（議論型のため） |
| AIニュース | 情報鮮度・正確性・インパクト | 共感度（事実伝達型のため） |

3. A判定のみ投稿可能
4. 投稿/下書き保存:
   - CiCセッション: `skills/post-tweet/PROMPT.md` で投稿 or `x-draft-saver` で下書き保存
   - 非CiCセッション: X API経由で投稿（`x_client.py` → `create_tweet()`、$0.010/件）

## 関連パイプラインとの役割分担

| 項目 | 本ワークフロー（オンデマンド） | 定期抽出パイプライン | Discord #en-buzz-tweets |
|------|-------------------------------|---------------------|------------------------|
| トリガー | ユーザーが「ツイート作って」と指示 | Task Scheduler自動実行 | Captain Hook自動投稿（約1時間ごと） |
| 目的 | テーマ特化ツイート生成 | 英語バズツイートの素材蓄積 | 英語バズのリアルタイムフィード |
| 抽出ツール | twscrape + Grok API | TweeterPy | 外部プロジェクト（Captain Hook） |
| 除外ルール | `en_buzz_exclusion_rules.json` を参照 | 同左（共有） | 未適用（Phase 3で手動フィルタ） |
| 出力 | 投稿可能なツイート文 | フィルタ済みツイートJSON | Discordメッセージ（Like数+要約+URL） |
| 実行頻度 | 不定期（ユーザー主導） | 定期（自動） | 常時（自動） |
| コスト | Grok: 約2円/回 | $0.00 | $0.00 |

**連携方法**:
- 定期抽出パイプラインが蓄積した `en_buzz_tweets_final.json` を、Phase 3でネタソースとして参照可能
- Discord #en-buzz-tweetsは Phase 2でCiC経由で最新バッチを読み取り、方向に合うネタをピックアップ
- 主力ソースはGrok API（クエリのカスタマイズ自由度が高い）、Discord/定期抽出は無料の補完ソース

## 学んだ教訓

- ニュースネタ単体はウケが悪い傾向。BIP寄せ（苦労・達成・感情発露）やエンジニアの生き方（問い・考察）の方が共感を得やすい
- Claude Code単独だと鮮度が落ち一般論に着地しやすい。Grok APIでの鮮度チェックが必須
- 日本語バズツイート抽出だけでは母数が少ない。英語バズツイートをGrok/Discord経由で補完する
- 抽出したバズツイートの「論点」を要約するだけではAI感が出る。自分の体験に変換する工程が必要
- ツイートの方向性は「BIP」「エンジニアの生き方」「AIニュース」の3軸がある。Phase 0で方向を確定させないと、ソース選定もネタ選定もブレる
- Discord #en-buzz-tweetsは「エンジニアの生き方」方向のネタが特に豊富（AI×キャリア論のバズツイートが多い）
- バズツイートの論点を参照しても、生成時に議論の進行段階を意識しないと3-6ヶ月前の一般論に着地する。`discourse-freshness.md` の段階判定をPhase 3とPhase 5の両方で適用すること
- Claudeの一般論バイアス: デフォルトのClaudeは正しいが退屈な結論に向かう傾向がある。discourse-freshness.mdの段階マップで矯正する
