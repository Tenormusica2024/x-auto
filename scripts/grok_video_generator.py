"""
grok_video_generator.py - Grok動画生成パイプラインのユーティリティ

CiCセッション内のClaude Codeが呼び出すヘルパー関数群。
ブラウザ操作自体はCiCツールで行い、このスクリプトは
プロンプト生成・ファイル検出・Discord送信を担当する。

使い方（CLIテスト用）:
  python -X utf8 grok_video_generator.py prompt                   # プロンプト1件生成
  python -X utf8 grok_video_generator.py prompt --category sf_parkour
  python -X utf8 grok_video_generator.py detect --post-id <id>    # D:\Downloadsからmp4検出
  python -X utf8 grok_video_generator.py discord <file_path>      # Discord送信
  python -X utf8 grok_video_generator.py move <file_path>         # 所定フォルダへ移動
"""

import sys
import shutil
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

# 定数
DOWNLOAD_DIR = Path(r"D:\Downloads")
SAVE_DIR = Path(r"C:\Users\Tenormusica\x-auto\scripts\data\grok-videos")
JST = timezone(timedelta(hours=9))


def generate_prompt(category: Optional[str] = None, seed: Optional[int] = None) -> dict:
    """プロンプト1件を生成して返す"""
    from grok_video_prompts import generate_prompt as _gen
    return _gen(category=category, seed=seed)


def detect_downloaded_video(
    post_id: str,
    timeout_sec: int = 30,
    poll_interval: float = 2.0,
) -> Optional[Path]:
    """
    D:\Downloadsからpost_id名のmp4ファイルを検出する。
    Chromeのダウンロード完了を待機するためポーリングする。

    ダウンロードファイル名パターン:
      - {post_id}.mp4
      - {post_id} (1).mp4 （重複時）
      - generated_video.mp4 / generated_video (1).mp4
    """
    start = time.time()
    while time.time() - start < timeout_sec:
        # ダウンロードファイル名パターン（Grokのダウンロードボタンが生成する名前）
        # grok-video-{post_id}.mp4 / {post_id}.mp4 / generated_video.mp4
        candidates = list(DOWNLOAD_DIR.glob(f"grok-video-{post_id}*.mp4"))
        candidates += list(DOWNLOAD_DIR.glob(f"{post_id}*.mp4"))
        candidates += list(DOWNLOAD_DIR.glob("generated_video*.mp4"))

        # .crdownload（ダウンロード中）を除外し、最新のファイルを選択
        completed = [
            f for f in candidates
            if not f.suffix.endswith(".crdownload")
            and f.stat().st_size > 100_000  # 100KB以上（破損ファイル除外）
            and (time.time() - f.stat().st_mtime) < 600  # 10分以内に作成されたもの
        ]

        if completed:
            # 最新のファイルを返す
            completed.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            return completed[0]

        # .crdownloadファイルがあればダウンロード中
        downloading = list(DOWNLOAD_DIR.glob(f"{post_id}*.crdownload"))
        if downloading:
            print(f"[INFO] ダウンロード中... {downloading[0].name}")

        time.sleep(poll_interval)

    print(f"[WARN] {timeout_sec}秒以内にファイルが見つかりませんでした")
    return None


def move_to_save_dir(source: Path, custom_name: Optional[str] = None) -> Path:
    """ダウンロードしたファイルを所定フォルダに移動・リネーム"""
    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    if custom_name:
        dest_name = custom_name if custom_name.endswith(".mp4") else f"{custom_name}.mp4"
    else:
        ts = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
        dest_name = f"grok_video_{ts}.mp4"

    dest = SAVE_DIR / dest_name

    # 同名ファイルが存在する場合はサフィックス追加
    counter = 1
    while dest.exists():
        stem = dest_name.rsplit(".", 1)[0]
        dest = SAVE_DIR / f"{stem}_{counter}.mp4"
        counter += 1

    shutil.move(str(source), str(dest))
    print(f"[OK] 移動: {source.name} -> {dest}")
    return dest


def send_to_discord(
    file_path: str,
    prompt_info: Optional[dict] = None,
    post_id: str = "",
) -> bool:
    """動画ファイルをDiscordに送信"""
    # x_client.pyのimportパスを追加
    sys.path.insert(0, str(Path(__file__).parent))
    from x_client import notify_discord_with_file

    p = Path(file_path)
    size_mb = p.stat().st_size / 1024 / 1024

    # メッセージ構築
    lines = ["**Grok Video Generated**"]
    if prompt_info:
        lines.append(f"Category: {prompt_info.get('category_name', 'N/A')}")
    if post_id:
        lines.append(f"Post: https://grok.com/imagine/post/{post_id}")
    lines.append(f"Size: {size_mb:.2f} MB")
    lines.append(f"File: {p.name}")

    if prompt_info and prompt_info.get("prompt"):
        # プロンプトが長い場合は切り詰め
        prompt_text = prompt_info["prompt"]
        if len(prompt_text) > 500:
            prompt_text = prompt_text[:497] + "..."
        lines.append(f"\nPrompt:\n```\n{prompt_text}\n```")

    message = "\n".join(lines)
    return notify_discord_with_file(message, str(p), p.name)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Grok動画生成パイプラインユーティリティ")
    sub = parser.add_subparsers(dest="command")

    # prompt コマンド
    p_prompt = sub.add_parser("prompt", help="プロンプト生成")
    p_prompt.add_argument("--category", help="カテゴリ指定")
    p_prompt.add_argument("--seed", type=int, help="乱数シード")

    # detect コマンド
    p_detect = sub.add_parser("detect", help="ダウンロード済み動画を検出")
    p_detect.add_argument("--post-id", required=True, help="GrokポストID")
    p_detect.add_argument("--timeout", type=int, default=30, help="タイムアウト秒")

    # discord コマンド
    p_discord = sub.add_parser("discord", help="Discordに動画送信")
    p_discord.add_argument("file_path", help="動画ファイルパス")
    p_discord.add_argument("--post-id", default="", help="GrokポストID")

    # move コマンド
    p_move = sub.add_parser("move", help="動画を所定フォルダに移動")
    p_move.add_argument("file_path", help="動画ファイルパス")
    p_move.add_argument("--name", help="リネーム名")

    args = parser.parse_args()

    if args.command == "prompt":
        result = generate_prompt(category=args.category, seed=args.seed)
        print(f"\nCategory: {result['category_name']} ({result['category']})")
        print(f"Prompt:\n{result['prompt']}")
        # JSON出力（パイプライン連携用）
        import json
        print(f"\n---JSON---\n{json.dumps(result, ensure_ascii=False)}")

    elif args.command == "detect":
        found = detect_downloaded_video(args.post_id, timeout_sec=args.timeout)
        if found:
            print(f"[OK] Found: {found}")
            print(f"Size: {found.stat().st_size / 1024 / 1024:.2f} MB")
        else:
            print("[FAIL] Not found")
            sys.exit(1)

    elif args.command == "discord":
        ok = send_to_discord(args.file_path, post_id=args.post_id)
        if not ok:
            sys.exit(1)

    elif args.command == "move":
        p = Path(args.file_path)
        if not p.exists():
            print(f"[ERROR] File not found: {p}")
            sys.exit(1)
        dest = move_to_save_dir(p, custom_name=args.name)
        print(f"Moved to: {dest}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
