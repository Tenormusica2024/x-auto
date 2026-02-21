# X投稿実行スキル

## 役割
Claude in Chrome を使用してX(Twitter)に投稿を実行する。

## 前提条件
- Claude in Chrome が使用可能であること
- X.comにログイン済みのブラウザセッションがあること

## 実行手順

### ステップ1: 投稿画面にアクセス
```
https://x.com/compose/tweet
```

### ステップ2: ログイン状態確認
- ログインしていない場合は指定アカウントでログイン
- デフォルトアカウント: @sena_09_04

### ステップ3: ツイート入力
1. テキストエリアにツイート本文をペースト
2. 引用リンクがある場合は本文末尾に追加

### ステップ3.5: 画像添付（画像がある場合）

**優先順位:**
1. **PowerShellクリップボード + Ctrl+V（推奨）**
2. JS DataTransfer API（base64サイズ制限あり）
3. dialog_filler.py（フォールバック）

**推奨手順（PowerShellクリップボード方式）:**
```bash
powershell -File - <<'PS1'
Add-Type -Assembly System.Windows.Forms
Add-Type -Assembly System.Drawing
$img = [System.Drawing.Image]::FromFile("IMAGE_PATH")
[System.Windows.Forms.Clipboard]::SetImage($img)
Write-Host "Image copied to clipboard"
$img.Dispose()
PS1
```
→ テキストエリアをクリック → `key("ctrl+v")` → wait(3秒) → スクショ確認

**注意:** IMAGE_PATHにはローカルファイルパスのみ使用すること（UNCパス `\\server\share\...` は禁止）

**詳細な手順・フォールバック方法:** `C:\Users\Tenormusica\.claude\skills\x-draft-saver\SKILL.md` Phase 3 参照

### ステップ4: 投稿前確認
1. スクリーンショットを撮影
2. 以下を確認:
   - テキストが正しく入力されているか
   - 引用リンクがプレビュー表示されているか
   - 「ポストする」ボタンが有効か

### ステップ5: 投稿実行
- 「ポストする」ボタンをクリック
- 投稿完了後のスクリーンショットを撮影

## 実行コマンド例

```powershell
"C:\Users\Tenormusica\.bun\bin\claude.exe" --chrome --dangerously-skip-permissions -p "X.comに以下のツイートを投稿してください:

[ツイート本文]

引用リンク: [URL]

手順:
1. https://x.com/compose/tweet にアクセス
2. ツイート文を入力
3. 投稿を実行
4. 完了後スクリーンショットを撮影"
```

## ログ出力
実行結果を以下に記録:
- `C:\Users\Tenormusica\x-auto\logs\YYYY-MM-DD_HH-MM-SS.log`
