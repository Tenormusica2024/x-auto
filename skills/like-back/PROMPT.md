# いいね2倍返しスキル (like-back)

## 役割
自分のツイートにいいねをくれた人の最新ツイートにいいねを返す。
もらった数の2倍のいいねを返すことでエンゲージメント関係を構築する。

## 前提条件
- Claude in Chrome が使用可能であること
- X.comにログイン済みのブラウザセッションがあること（@SundererD27468）

## 処理フロー

### フェーズ1: データ収集（API）
```powershell
cd C:\Users\Tenormusica\x-auto\skills\like-back
python collect_likers.py
```
- 最新ツイート5件のいいねユーザーをAPI経由で一括取得
- `like_history.json` と照合して未処理ユーザーを抽出
- 結果を `target_users.json` に出力

### フェーズ2: 対象ユーザー確認
`target_users.json` を読み、`today` 配列の各ユーザーに対してフェーズ3を実行する。

### フェーズ3: いいね返し実行（CiC）
各ユーザーに対して以下のパターンを繰り返す。
`target_users.json` の各ユーザーに `likes_count` フィールドがある（通常2、リピーターは3）。

```
1. navigate("https://x.com/{username}")
2. scroll(down, 5)
3. find("いいねする button")
4. 結果から「いいねする」（未いいね）のref IDを likes_count 個選択
   - 「いいねしました」はスキップ（既にいいね済み）
5. click(ref_1)
6. click(ref_2)
7. likes_count が 3 なら click(ref_3) も実行
8. ★ like_history.json にこのユーザーを即座に追記（フェーズ4参照）
9. 次のユーザーへ
```

#### CiC操作の注意点（テスト実証済み）
- **findクエリ**: `find("いいねする button")` を使う（日本語）
  - `"like button heart"` は不安定、使用禁止
- **クリック方法**: 必ず `ref` でクリック。座標クリックは禁止
- **findとclickの間にスクロールしない**: ref IDがシフトする
- **いいね済み判定**: findの戻り値に「いいねしました」を含むものはスキップ
- **リポストへのいいね**: NG（いいね通知がリポスト元に行き、対象ユーザーに届かない）
- **リポスト検出方法**: ツイート上部に「〇〇さんがリポスト」のラベルがある → そのツイートはスキップ対象。findの戻り値だけでは判別不可なので、navigate後にページ内テキストを確認する
- **リポスト中心アカウント**: オリジナルツイートが見つかるまでスクロール（最大5回）。なければそのユーザーはスキップし、次のユーザーへ進む
- **スクショ検証**: 毎ユーザーでは不要。最初と最後の確認で十分

### フェーズ4: 履歴更新（1ユーザーごとに即座実行）

**二重いいね防止のため、全員完了後ではなく1ユーザー処理するごとに即座に `like_history.json` を更新する。**
途中でセッションが落ちても、処理済みユーザーが次回再処理されることを防ぐ。

各ユーザーのいいねクリック完了直後に、以下の手順で更新:
1. `like_history.json` を Read で読む
2. 該当ユーザーの `processed` エントリを追加/更新
3. `last_run` を現在時刻に更新
4. Write で保存

```json
{
  "last_run": "ISO8601タイムスタンプ",
  "processed": {
    "username": {
      "last_liked_at": "ISO8601タイムスタンプ",
      "liked_count": 2,
      "source_tweets": ["tweet_id1"]
    }
  }
}
```

**スキップしたユーザーも記録する**: リポスト中心でオリジナルが見つからずスキップした場合も、`liked_count: 0` で記録し、次回の重複チェック対象に含める。

### フェーズ5: 結果報告
処理結果をユーザーに報告:
- 対象ツイート数
- いいねくれた人数（新規/スキップ）
- いいね返し実行数
- 翌日持ち越しユーザー（あれば）

## 設定
`config.json` で以下を調整可能:
- `daily_like_limit`: 1日のいいね上限（デフォルト: 20）
- `likes_per_user`: 1ユーザーあたりのいいね数（デフォルト: 2）
- `repeater_bonus`: 複数ツイートにいいねくれた人への追加いいね数（デフォルト: 1）
- `tweet_check_count`: チェックするツイート数（デフォルト: 5）
- `history_expiry_days`: 履歴の有効期間（デフォルト: 7日）

## 1日の上限
- いいね返し: 最大20件/日
- 上限に達したら残りは `target_users.json` の `remaining` に記録

## 注意事項
- 企業アカウント・botアカウントへのいいね返しは不要（CiCの判断に任せる）
- 非公開アカウントは `collect_likers.py` が自動除外
- いいね済みのツイートは再度いいねしない（find結果で自動判定）
- rate limit発生時は1分待って再試行

## 二重いいね防止（CRITICAL）
- `like_history.json` は1ユーザー処理ごとに即座更新（フェーズ4参照）
- `collect_likers.py` は履歴にあるユーザーを自動除外（`history_expiry_days` 以内）
- CiC実行開始前に `target_users.json` のユーザーが `like_history.json` に既に存在しないか再確認する
- 不安な場合はフェーズ1の `collect_likers.py` を `--dry-run` で先に確認
