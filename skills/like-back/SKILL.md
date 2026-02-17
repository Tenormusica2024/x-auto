# like-back スキル定義

## 発火条件
「いいね返し」「like back」「2倍返し」「いいね返しスキル」

## 前提条件
- Claude in Chrome が使用可能であること
- X.comにログイン済みのブラウザセッション（@SundererD27468）
- Python環境（tweepy, python-dotenv インストール済み）
- X API認証情報（`C:\Users\Tenormusica\x-auto-posting\.env`）

## 実行フロー概要
1. `collect_likers.py` でAPI経由のデータ収集（3-5秒）
2. `target_users.json` を読んでCiCでいいね返し実行（1ユーザー10-15秒）
3. `like_history.json` 自動更新 + 結果報告

## ファイル構成
```
skills/like-back/
├── SKILL.md              # 本ファイル（スキル定義）
├── PROMPT.md             # CiC操作手順（実行時参照）
├── collect_likers.py     # API: いいねユーザー一括収集
├── config.json           # 設定（日次上限・リピーターボーナス・履歴有効期間）
├── like_history.json     # 処理履歴
├── target_users.json     # collect_likers.py の出力（CiCが読む）
├── register_task.ps1     # Task Scheduler登録スクリプト
└── CIC_TEST_LOG.md       # テスト詳細ログ（開発参考）
```

## 実行コマンド

### 対話モード（推奨）
```powershell
"C:\Users\Tenormusica\.bun\bin\claude.exe" --chrome
# → 「like-backスキルを実行して」と指示
```

### 自動実行モード
```powershell
"C:\Users\Tenormusica\.bun\bin\claude.exe" --chrome --dangerously-skip-permissions -p "x-autoのlike-backスキルを実行してください。C:\Users\Tenormusica\x-auto\skills\like-back\PROMPT.md を読んで手順に従ってください。"
```

## 定期実行（Task Scheduler）

CiCが必須のため、完全無人の定期実行は `--chrome --dangerously-skip-permissions` が前提。

```powershell
# 登録済み（register_task.ps1 で実行）
# タスク名: x-auto-like-back / 毎日21:30 JST / State: Ready
# 再登録が必要な場合:
powershell -ExecutionPolicy Bypass -File "C:\Users\Tenormusica\x-auto\skills\like-back\register_task.ps1"
```

**前提条件**: Chromeが起動していてX.comにログイン済みであること。
**推奨時間帯**: 21:00-22:00（daily_metrics実行後、1日のツイート活動が落ち着いた頃）

## コスト
- API（データ収集）: ~$0.03/回（ツイート取得 + liking_users 5回）
- CiC（いいね実行）: $0.00（ブラウザ操作のため無料）
- Claude Code時間: 約5-10分/回（10ユーザー処理時）
