"""
x_client.py - X API + Discord通知の共通モジュール

daily_metrics.py / trend_detector.py から共有で使用する。
"""

import os
from pathlib import Path
from datetime import datetime

import tweepy
import requests
from dotenv import load_dotenv

# --- 自分のアカウント情報（キーパーソン蓄積から除外する用） ---
MY_USER_IDS = {
    "1805557649876172801",  # @SundererD27468（API連携アカウント）
}

# --- パス定数 ---
ENV_PATH = Path(r"C:\Users\Tenormusica\x-auto-posting\.env")
OBSIDIAN_BASE = Path(r"D:\antigravity_projects\VaultD\Projects\Monetization\Intelligence\x-analytics")
OBSIDIAN_DAILY = OBSIDIAN_BASE / "daily"
OBSIDIAN_TRENDS = OBSIDIAN_BASE / "trends"
OBSIDIAN_WEEKLY = OBSIDIAN_BASE / "weekly"
DRAFTS_DIR = Path(r"C:\Users\Tenormusica\x-auto\drafts")
DATA_DIR = Path(r"C:\Users\Tenormusica\x-auto\scripts\data")
FRONTIER_REPORT = Path(r"D:\antigravity_projects\VaultD\Projects\Monetization\Intelligence\AI_Frontier_Capabilities_Master.md")

# .envを読み込み
load_dotenv(ENV_PATH)


def get_x_client() -> tweepy.Client:
    """tweepy v2 Client を生成して返す"""
    client = tweepy.Client(
        bearer_token=os.getenv("X_BEARER_TOKEN"),
        consumer_key=os.getenv("X_API_KEY"),
        consumer_secret=os.getenv("X_API_SECRET"),
        access_token=os.getenv("X_ACCESS_TOKEN"),
        access_token_secret=os.getenv("X_ACCESS_SECRET"),
        wait_on_rate_limit=True,
    )
    return client


def get_my_user_id(client: tweepy.Client) -> int:
    """認証ユーザーのIDを取得"""
    me = client.get_me()
    return me.data.id


def get_my_profile(client: tweepy.Client) -> dict:
    """認証ユーザーのプロフィール情報（フォロワー数等）を取得"""
    me = client.get_me(user_fields=["public_metrics", "created_at"])
    pm = me.data.public_metrics
    return {
        "id": str(me.data.id),
        "username": me.data.username,
        "followers": pm.get("followers_count", 0),
        "following": pm.get("following_count", 0),
        "tweet_count": pm.get("tweet_count", 0),
        "listed_count": pm.get("listed_count", 0),
    }


def notify_discord(message: str) -> bool:
    """Discord Webhookにメッセージ送信。成功でTrue"""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[WARN] DISCORD_WEBHOOK_URL が .env に未設定")
        return False

    # Discordメッセージ上限は2000文字
    if len(message) > 2000:
        message = message[:1997] + "..."

    resp = requests.post(webhook_url, json={"content": message}, timeout=10)
    if resp.status_code == 204:
        return True
    else:
        print(f"[WARN] Discord通知失敗: {resp.status_code} {resp.text}")
        return False


def notify_discord_with_file(message: str, file_path: str, filename: str = "") -> bool:
    """Discord Webhookにファイル添付でメッセージ送信。動画・画像の配信に使用"""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[WARN] DISCORD_WEBHOOK_URL が .env に未設定")
        return False

    if not filename:
        filename = Path(file_path).name

    # メッセージ上限2000文字
    if len(message) > 2000:
        message = message[:1997] + "..."

    try:
        with open(file_path, "rb") as f:
            resp = requests.post(
                webhook_url,
                data={"content": message},
                files={"file": (filename, f)},
                timeout=120,
            )
        if resp.status_code == 200:
            print(f"[OK] Discord送信（ファイル添付）: {filename}")
            return True
        else:
            print(f"[WARN] Discordファイル送信失敗: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"[ERROR] Discordファイル送信エラー: {e}")
        return False


def notify_discord_drafts(tweet_text: str, label: str = "") -> bool:
    """ツイート下書きを #tweet-drafts チャンネルに送信"""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL_DRAFTS")
    if not webhook_url:
        print("[WARN] DISCORD_WEBHOOK_URL_DRAFTS が .env に未設定")
        return False

    header = f"**[Tweet Draft]** {label}\n\n" if label else "**[Tweet Draft]**\n\n"
    message = f"{header}{tweet_text}"

    if len(message) > 2000:
        message = message[:1997] + "..."

    resp = requests.post(webhook_url, json={"content": message}, timeout=10)
    if resp.status_code == 204:
        print(f"[OK] Discord #tweet-drafts 送信完了: {label or '(no label)'}")
        return True
    else:
        print(f"[WARN] Discord #tweet-drafts 送信失敗: {resp.status_code} {resp.text}")
        return False


def save_to_obsidian(subdir: Path, filename: str, content: str) -> Path:
    """Obsidian Vaultにmarkdownファイルを保存"""
    subdir.mkdir(parents=True, exist_ok=True)
    filepath = subdir / filename
    filepath.write_text(content, encoding="utf-8")
    print(f"[OK] Obsidian保存: {filepath}")
    return filepath


def today_str() -> str:
    """今日の日付文字列 (YYYY-MM-DD)"""
    return datetime.now().strftime("%Y-%m-%d")


def now_str() -> str:
    """現在時刻の文字列 (YYYY-MM-DD HH:MM)"""
    return datetime.now().strftime("%Y-%m-%d %H:%M")
