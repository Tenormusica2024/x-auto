r"""
collect_likers.py - いいねユーザー一括収集 + 履歴差分算出

X API経由で自分の最新ツイートにいいねした人を収集し、
like_history.jsonと照合して未処理ユーザーリストを出力する。

使い方:
  cd C:\Users\Tenormusica\x-auto\skills\like-back
  python collect_likers.py              # 通常実行
  python collect_likers.py --dry-run    # 収集のみ（履歴更新なし）
  python collect_likers.py --count 3    # チェックするツイート数を指定
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone

# x_client.py を参照するためにパスを追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from x_client import get_x_client, MY_USER_IDS

# --- 定数 ---
JST = timezone(timedelta(hours=9))
SKILL_DIR = Path(__file__).resolve().parent
HISTORY_FILE = SKILL_DIR / "like_history.json"
CONFIG_FILE = SKILL_DIR / "config.json"
MY_USER_ID = "1805557649876172801"  # @SundererD27468

# --- 履歴の有効期間（この日数以内に処理済みならスキップ） ---
HISTORY_EXPIRY_DAYS = 7


def load_config() -> dict:
    """config.jsonを読み込む"""
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {"daily_like_limit": 20, "likes_per_user": 2, "tweet_check_count": 5}


def load_history() -> dict:
    """like_history.jsonを読み込む"""
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return {"last_run": None, "processed": {}}


def save_history(history: dict) -> None:
    """like_history.jsonを保存"""
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_recent_tweets(client, user_id: str, count: int = 5) -> list[dict]:
    """自分の最新ツイート（リツイート除外）を取得。いいね1件以上のもののみ返す。"""
    resp = client.get_users_tweets(
        id=user_id,
        max_results=min(count * 2, 100),  # いいね0件を除外するため多めに取得
        tweet_fields=["public_metrics", "created_at"],
        exclude=["retweets"],
    )
    if not resp.data:
        return []

    tweets = []
    for tweet in resp.data:
        likes = tweet.public_metrics.get("like_count", 0)
        if likes > 0:
            tweets.append({
                "id": str(tweet.id),
                "text": tweet.text[:80],
                "like_count": likes,
                "created_at": str(tweet.created_at),
            })
        if len(tweets) >= count:
            break
    return tweets


def get_liking_users(client, tweet_id: str) -> list[dict]:
    """ツイートにいいねしたユーザー一覧を取得（OAuth 1.0a User Context必須）"""
    resp = client.get_liking_users(
        id=tweet_id,
        user_fields=["username", "name", "protected", "public_metrics"],
        user_auth=True,
    )
    if not resp.data:
        return []

    users = []
    for user in resp.data:
        # 自分自身を除外
        if str(user.id) in MY_USER_IDS:
            continue
        # 非公開アカウントを除外
        if user.protected:
            continue
        users.append({
            "id": str(user.id),
            "username": user.username,
            "name": user.name,
            "followers": user.public_metrics.get("followers_count", 0),
        })
    return users


def filter_by_history(users: list[dict], history: dict) -> tuple[list[dict], list[dict]]:
    """履歴と照合して未処理/処理済みに分ける"""
    now = datetime.now(JST)
    expiry_threshold = now - timedelta(days=HISTORY_EXPIRY_DAYS)

    new_users = []
    skipped_users = []

    for user in users:
        username = user["username"]
        if username in history.get("processed", {}):
            last_liked = history["processed"][username].get("last_liked_at", "")
            if last_liked:
                last_liked_dt = datetime.fromisoformat(last_liked)
                if last_liked_dt > expiry_threshold:
                    skipped_users.append(user)
                    continue
        new_users.append(user)

    return new_users, skipped_users


def main():
    parser = argparse.ArgumentParser(description="いいねユーザー収集")
    parser.add_argument("--dry-run", action="store_true", help="収集のみ（出力するが保存しない）")
    parser.add_argument("--count", type=int, default=5, help="チェックするツイート数")
    args = parser.parse_args()

    config = load_config()
    history = load_history()
    client = get_x_client()

    daily_limit = config.get("daily_like_limit", 20)
    likes_per_user = config.get("likes_per_user", 2)
    repeater_bonus = config.get("repeater_bonus", 1)

    # --- ステップ1: 最新ツイート取得 ---
    print(f"[1/3] 最新ツイート取得中（上位{args.count}件、いいね1件以上）...")
    tweets = get_recent_tweets(client, MY_USER_ID, count=args.count)
    if not tweets:
        print("[!] いいねが付いたツイートが見つかりません")
        return

    for t in tweets:
        print(f"  - {t['id']}: {t['text'][:50]}... ({t['like_count']}L)")

    # --- ステップ2: 各ツイートのいいねユーザー収集 ---
    print(f"\n[2/3] いいねユーザー収集中...")
    all_users = {}  # username -> user info + source_tweets
    for tweet in tweets:
        likers = get_liking_users(client, tweet["id"])
        for user in likers:
            username = user["username"]
            if username not in all_users:
                all_users[username] = {**user, "source_tweets": []}
            all_users[username]["source_tweets"].append(tweet["id"])

    print(f"  ユニークユーザー: {len(all_users)}人")

    # リピーター検出（複数ツイートにいいねした人）
    repeaters = {u: info for u, info in all_users.items() if len(info["source_tweets"]) > 1}
    if repeaters:
        repeater_strs = [f"@{u}({len(info['source_tweets'])}回)" for u, info in repeaters.items()]
        print(f"  リピーター: {', '.join(repeater_strs)}")

    # --- ステップ3: 履歴差分算出 ---
    print(f"\n[3/3] 履歴照合中...")
    user_list = list(all_users.values())
    new_users, skipped_users = filter_by_history(user_list, history)

    print(f"  新規（未処理）: {len(new_users)}人")
    print(f"  スキップ（処理済み）: {len(skipped_users)}人")

    # 各ユーザーのいいね返し数を算出（リピーターにはボーナス加算）
    for user in new_users:
        is_repeater = len(user.get("source_tweets", [])) > 1
        user["likes_count"] = likes_per_user + (repeater_bonus if is_repeater else 0)

    # 日次上限でユーザーを切る（各ユーザーのlikes_countを累積して判定）
    today_users = []
    remaining_users = []
    likes_budget = daily_limit
    for user in new_users:
        if likes_budget >= user["likes_count"]:
            today_users.append(user)
            likes_budget -= user["likes_count"]
        else:
            remaining_users.append(user)

    # --- 結果出力 ---
    total_likes_today = sum(u["likes_count"] for u in today_users)
    result = {
        "timestamp": datetime.now(JST).isoformat(),
        "tweets_checked": len(tweets),
        "total_likers": len(all_users),
        "new_users": len(new_users),
        "skipped_users": len(skipped_users),
        "total_likes_planned": total_likes_today,
        "today": [
            {
                "username": u["username"],
                "name": u["name"],
                "followers": u["followers"],
                "source_tweets": u["source_tweets"],
                "likes_count": u["likes_count"],
            }
            for u in today_users
        ],
        "remaining": [u["username"] for u in remaining_users],
    }

    # JSON出力（CiCが読み取る用）
    output_file = SKILL_DIR / "target_users.json"
    if not args.dry_run:
        output_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n[OK] {output_file} に出力しました")
    else:
        print(f"\n[DRY-RUN] 出力内容:")

    # サマリ表示
    print(f"\n{'='*50}")
    print(f"本日の対象: {len(today_users)}人 / いいね計{total_likes_today}件 (上限: {daily_limit}件)")
    print(f"{'='*50}")
    for i, u in enumerate(today_users, 1):
        likes_label = f"{u['likes_count']}L" if u.get("likes_count", 2) != likes_per_user else f"{likes_per_user}L"
        repeat_mark = " [REPEATER]" if u.get("likes_count", 2) > likes_per_user else ""
        print(f"  {i:2d}. @{u['username']:<20s} ({u['followers']:,}フォロワー) → {likes_label}{repeat_mark}")

    if remaining_users:
        print(f"\n翌日に持ち越し: {len(remaining_users)}人")
        for u in remaining_users:
            print(f"  - @{u['username']}")

    print(f"\nAPIコスト: ${0.005 * (1 + len(tweets)):.3f} (ツイート取得1回 + liking_users{len(tweets)}回)")


if __name__ == "__main__":
    main()
