r"""
collect_likers.py - いいね等価返し用ユーザー収集 + 新規フォロワー検出

X API経由で自分の最新ツイートにいいねした人を収集し、
もらった数と同じ数だけいいねを返す（等価返し）ための対象リストを出力する。
一度処理したユーザーは永久にスキップされる。

使い方:
  cd C:\Users\Tenormusica\x-auto\skills\like-back
  python collect_likers.py              # 通常実行
  python collect_likers.py --dry-run    # 収集のみ（履歴更新なし）
  python collect_likers.py --count 3    # チェックするツイート数を指定
  python collect_likers.py --no-followers  # フォロワー検出をスキップ
"""

import json
import sys
import time
import argparse
import tweepy
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
SNAPSHOT_FILE = SKILL_DIR / "follower_snapshot.json"
MY_USER_ID = "1805557649876172801"  # @SundererD27468


def load_config() -> dict:
    """config.jsonを読み込む"""
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {
        "daily_like_limit": 20,
        "tweet_check_count": 5,
        "enable_new_follower_likes": True,
        "new_follower_likes": 1,
    }


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


# --- フォロワースナップショット管理 ---

def load_follower_snapshot() -> dict | None:
    """follower_snapshot.jsonを読み込む。存在しなければNone。"""
    if not SNAPSHOT_FILE.exists():
        return None
    try:
        return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        print("  [WARN] follower_snapshot.json が破損。初回扱いにします")
        return None


def save_follower_snapshot(followers: list[dict]) -> None:
    """現在のフォロワーリストをスナップショットとして保存"""
    # user_id -> username のdictで保存（O(1)ルックアップ用）
    snapshot = {
        "timestamp": datetime.now(JST).isoformat(),
        "follower_ids": {u["id"]: u["username"] for u in followers},
    }
    SNAPSHOT_FILE.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# --- API呼び出し ---

def api_call_with_retry(func, *args, max_retries=1, **kwargs):
    """API呼び出しのリトライラッパー。rate limit時は60秒待って1回リトライ。"""
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except tweepy.errors.TooManyRequests:
            if attempt < max_retries:
                print(f"  [!] Rate limit到達。60秒待機後にリトライ...")
                time.sleep(60)
            else:
                print(f"  [ERROR] Rate limit: リトライ上限到達。スキップします")
                return None
        except tweepy.errors.Forbidden as e:
            print(f"  [ERROR] 403 Forbidden: {e}")
            return None
        except tweepy.errors.TwitterServerError as e:
            if attempt < max_retries:
                print(f"  [!] サーバーエラー({e})。30秒待機後にリトライ...")
                time.sleep(30)
            else:
                print(f"  [ERROR] サーバーエラー: リトライ上限到達。スキップします")
                return None
        except tweepy.errors.HTTPException as e:
            # 402 Payment Required 等のHTTPエラー
            print(f"  [ERROR] HTTP {e}: スキップします")
            return None


def get_recent_tweets(client, user_id: str, count: int = 5) -> list[dict]:
    """自分の最新ツイート（リツイート除外）を取得。いいね1件以上のもののみ返す。"""
    resp = api_call_with_retry(
        client.get_users_tweets,
        id=user_id,
        max_results=min(count * 2, 100),
        tweet_fields=["public_metrics", "created_at"],
        exclude=["retweets"],
    )
    if not resp or not resp.data:
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
    resp = api_call_with_retry(
        client.get_liking_users,
        id=tweet_id,
        user_fields=["username", "name", "protected", "public_metrics"],
        user_auth=True,
    )
    if not resp or not resp.data:
        return []

    users = []
    for user in resp.data:
        if str(user.id) in MY_USER_IDS:
            continue
        if user.protected:
            continue
        users.append({
            "id": str(user.id),
            "username": user.username,
            "name": user.name,
            "followers": user.public_metrics.get("followers_count", 0),
        })
    return users


def get_current_followers(client, user_id: str) -> list[dict]:
    """自分のフォロワー一覧を取得（ページネーション対応）"""
    all_followers = []
    pagination_token = None

    while True:
        kwargs = {
            "id": user_id,
            "max_results": 1000,
            "user_fields": ["username", "name", "protected", "public_metrics"],
            "user_auth": True,
        }
        if pagination_token:
            kwargs["pagination_token"] = pagination_token

        resp = api_call_with_retry(client.get_users_followers, **kwargs)
        if not resp or not resp.data:
            break

        for user in resp.data:
            if user.protected:
                continue
            all_followers.append({
                "id": str(user.id),
                "username": user.username,
                "name": user.name,
                "followers": user.public_metrics.get("followers_count", 0),
            })

        # ページネーション: next_tokenがあれば次のページへ
        if resp.meta and resp.meta.get("next_token"):
            pagination_token = resp.meta["next_token"]
        else:
            break

    return all_followers


def detect_new_followers(current_followers: list[dict], snapshot: dict) -> list[dict]:
    """前回スナップショットとの差分で新規フォロワーを検出"""
    prev_ids = set(snapshot.get("follower_ids", {}).keys())
    new_followers = [u for u in current_followers if u["id"] not in prev_ids]
    return new_followers


# --- 履歴フィルタ ---

def filter_by_history(users: list[dict], history: dict) -> tuple[list[dict], list[dict]]:
    """履歴と照合して未処理/処理済みに分ける。一度処理したユーザーは永久にスキップ。"""
    new_users = []
    skipped_users = []

    for user in users:
        username = user["username"]
        if username in history.get("processed", {}):
            skipped_users.append(user)
            continue
        new_users.append(user)

    return new_users, skipped_users


def main():
    parser = argparse.ArgumentParser(description="いいねユーザー収集 + 新規フォロワー検出")
    parser.add_argument("--dry-run", action="store_true", help="収集のみ（出力するが保存しない）")
    parser.add_argument("--count", type=int, default=None, help="チェックするツイート数（未指定時はconfig.jsonのtweet_check_count）")
    parser.add_argument("--no-followers", action="store_true", help="新規フォロワー検出をスキップ")
    args = parser.parse_args()

    config = load_config()
    history = load_history()
    client = get_x_client()

    daily_limit = config.get("daily_like_limit", 20)
    # CLIの--countが未指定ならconfigのtweet_check_countを使う
    tweet_count = args.count if args.count is not None else config.get("tweet_check_count", 5)
    enable_new_follower = config.get("enable_new_follower_likes", True)
    new_follower_likes = config.get("new_follower_likes", 1)

    # ステップ数を動的に決定（フォロワー検出ありなら4ステップ、なしなら3ステップ）
    do_followers = enable_new_follower and not args.no_followers
    total_steps = 4 if do_followers else 3

    # --- ステップ1: 最新ツイート取得 ---
    print(f"[1/{total_steps}] 最新ツイート取得中（上位{tweet_count}件、いいね1件以上）...")
    tweets = get_recent_tweets(client, MY_USER_ID, count=tweet_count)
    if not tweets:
        print("[!] いいねが付いたツイートが見つかりません")
        # ツイートがなくてもフォロワー検出は続行
        if not do_followers:
            return
        tweets = []

    for t in tweets:
        print(f"  - {t['id']}: {t['text'][:50]}... ({t['like_count']}L)")

    # --- ステップ2: 各ツイートのいいねユーザー収集 ---
    print(f"\n[2/{total_steps}] いいねユーザー収集中...")
    all_likers = {}  # username -> user info + source_tweets
    for tweet in tweets:
        likers = get_liking_users(client, tweet["id"])
        for user in likers:
            username = user["username"]
            if username not in all_likers:
                all_likers[username] = {**user, "source_tweets": []}
            all_likers[username]["source_tweets"].append(tweet["id"])

    print(f"  ユニークユーザー: {len(all_likers)}人")

    # リピーター検出（複数ツイートにいいねした人）
    repeaters = {u: info for u, info in all_likers.items() if len(info["source_tweets"]) > 1}
    if repeaters:
        repeater_strs = [f"@{u}({len(info['source_tweets'])}回)" for u, info in repeaters.items()]
        print(f"  リピーター: {', '.join(repeater_strs)}")

    # 履歴差分でいいね返し対象を抽出
    liker_list = list(all_likers.values())
    new_likers, skipped_likers = filter_by_history(liker_list, history)

    print(f"  新規（未処理）: {len(new_likers)}人")
    print(f"  スキップ（処理済み）: {len(skipped_likers)}人")

    # いいね返し数を算出（等価返し: もらった数と同じ数を返す）
    for user in new_likers:
        user["likes_count"] = len(user.get("source_tweets", []))
        user["source"] = "like_back"

    # --- ステップ2.5: 新規フォロワー検出 ---
    new_follower_targets = []
    follower_api_calls = 0

    if do_followers:
        print(f"\n[3/{total_steps}] 新規フォロワー検出中...")
        try:
            current_followers = get_current_followers(client, MY_USER_ID)
            # ページ数からAPI呼び出し回数を推定（1000人/ページ）
            follower_api_calls = max(1, (len(current_followers) + 999) // 1000)
            print(f"  現在のフォロワー: {len(current_followers)}人 (API {follower_api_calls}回)")

            # 空リストの場合はAPIエラーの可能性が高い → スナップショット更新しない
            if not current_followers:
                print("  [WARN] フォロワーリストが空。API障害の可能性。スナップショット更新をスキップ")
                raise ValueError("Empty follower list")

            snapshot = load_follower_snapshot()

            if snapshot is None:
                # 初回実行: スナップショット保存のみ、いいねなし
                print("  [INFO] 初回実行: フォロワースナップショットを保存（いいねなし）")
                if not args.dry_run:
                    save_follower_snapshot(current_followers)
            else:
                raw_new_followers = detect_new_followers(current_followers, snapshot)
                print(f"  新規フォロワー（前回差分）: {len(raw_new_followers)}人")

                if raw_new_followers:
                    # 履歴フィルタで二重いいね防止
                    new_followers, skipped_followers = filter_by_history(
                        raw_new_followers, history
                    )
                    if skipped_followers:
                        print(f"  スキップ（履歴重複）: {len(skipped_followers)}人")

                    # sourceマーカーといいね数を付与
                    for user in new_followers:
                        user["source"] = "new_follower"
                        user["likes_count"] = new_follower_likes
                        user["source_tweets"] = []

                    new_follower_targets = new_followers
                    for u in new_follower_targets:
                        print(f"    + @{u['username']} ({u['followers']:,}フォロワー) [NEW FOLLOWER]")

                # スナップショットを最新状態に更新
                if not args.dry_run:
                    save_follower_snapshot(current_followers)

        except Exception as e:
            # フォロワー検出失敗時もいいね返しは続行
            print(f"  [WARN] 新規フォロワー検出でエラー: {e}")
            print("  [INFO] いいね返しのみ実行します")
            new_follower_targets = []

    # --- ステップ3(or4): 予算配分 ---
    step_num = total_steps
    print(f"\n[{step_num}/{total_steps}] 予算配分中...")

    # 優先順位: いいね返しユーザー → 新規フォロワー
    all_targets = new_likers + new_follower_targets

    today_users = []
    remaining_users = []
    likes_budget = daily_limit
    for user in all_targets:
        if likes_budget >= user["likes_count"]:
            today_users.append(user)
            likes_budget -= user["likes_count"]
        else:
            remaining_users.append(user)

    # --- 結果出力 ---
    total_likes_today = sum(u["likes_count"] for u in today_users)
    like_back_count = sum(1 for u in today_users if u.get("source") == "like_back")
    new_follower_count = sum(1 for u in today_users if u.get("source") == "new_follower")

    result = {
        "timestamp": datetime.now(JST).isoformat(),
        "tweets_checked": len(tweets),
        "total_likers": len(all_likers),
        "new_users": len(new_likers),
        "skipped_users": len(skipped_likers),
        "new_followers_detected": len(new_follower_targets),
        "total_likes_planned": total_likes_today,
        "today": [
            {
                "username": u["username"],
                "name": u["name"],
                "followers": u["followers"],
                "source_tweets": u["source_tweets"],
                "likes_count": u["likes_count"],
                "source": u.get("source", "like_back"),
            }
            for u in today_users
        ],
        "remaining": [u["username"] for u in remaining_users],
    }

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
    if like_back_count > 0:
        print(f"  いいね返し: {like_back_count}人")
    if new_follower_count > 0:
        print(f"  新規フォロワー: {new_follower_count}人")
    print(f"{'='*50}")

    for i, u in enumerate(today_users, 1):
        source_label = " [NEW FOLLOWER]" if u.get("source") == "new_follower" else ""
        repeat_mark = " [REPEATER]" if u.get("source") == "like_back" and u.get("likes_count", 1) > 1 else ""
        print(f"  {i:2d}. @{u['username']:<20s} ({u['followers']:,}フォロワー) → {u['likes_count']}L{repeat_mark}{source_label}")

    if remaining_users:
        print(f"\n本日スキップ（予算超過）: {len(remaining_users)}人")
        for u in remaining_users:
            print(f"  - @{u['username']}")

    # APIコスト計算（ツイート取得1回 + liking_users N回 + フォロワー取得M回）
    api_cost = 0.005 * (1 + len(tweets)) + 0.010 * follower_api_calls
    cost_parts = [f"ツイート取得1回 + liking_users{len(tweets)}回"]
    if follower_api_calls > 0:
        cost_parts.append(f"followers{follower_api_calls}回")
    print(f"\nAPIコスト: ${api_cost:.3f} ({' + '.join(cost_parts)})")


if __name__ == "__main__":
    main()
