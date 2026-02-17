"""
daily_metrics.py - X ツイートパフォーマンス日次分析

自分の直近ツイートのインプレッション・エンゲージメント率を取得し、
Obsidian Vaultにレポートを保存する。

機能:
  - ツイートメトリクス分析（imp / eng率 / top5）
  - フォロワー成長トラッキング（日次推移記録）
  - エンゲージメントパターン分析（時間帯 / 文字数 x eng率）

使い方:
  python -X utf8 daily_metrics.py          # 直近20件を分析
  python -X utf8 daily_metrics.py --count 10  # 直近10件を分析

コスト: 20件取得 + プロフィール1回 = ~$0.105（約16円）

content_evaluator.py と連携:
  - tweet_details.json にツイート本文・メディア情報・重み付きスコアを蓄積
  - content_evaluator.py がLLM分類で多次元評価を実施
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# 同ディレクトリのx_clientをインポート
sys.path.insert(0, str(Path(__file__).parent))
from x_client import (
    get_x_client, get_my_user_id, get_my_profile, notify_discord,
    save_to_obsidian, today_str, now_str,
    OBSIDIAN_DAILY, DATA_DIR,
)


# --- フォロワー履歴 ---

def load_follower_history() -> dict:
    """フォロワー履歴JSONを読み込み"""
    path = DATA_DIR / "follower_history.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"history": []}


def save_follower_history(data: dict):
    """フォロワー履歴JSONを保存"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "follower_history.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] フォロワー履歴保存: {path}")


def track_followers(profile: dict) -> dict:
    """フォロワー数を記録し、前日比を計算"""
    fh = load_follower_history()

    prev_followers = None
    if fh["history"]:
        prev_followers = fh["history"][-1].get("followers", 0)

    growth = None
    growth_pct = None
    if prev_followers is not None and prev_followers > 0:
        growth = profile["followers"] - prev_followers
        growth_pct = round(growth / prev_followers * 100, 2)

    entry = {
        "date": today_str(),
        "followers": profile["followers"],
        "following": profile["following"],
        "tweet_count": profile["tweet_count"],
        "listed_count": profile["listed_count"],
        "growth": growth,
        "growth_pct": growth_pct,
    }
    fh["history"].append(entry)
    save_follower_history(fh)

    return entry


# --- ツイート詳細履歴（パターン分析用） ---

def load_tweet_details() -> dict:
    """ツイート詳細JSONを読み込み（パターン分析用の蓄積データ）"""
    path = DATA_DIR / "tweet_details.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"tweets": [], "last_updated": ""}


def save_tweet_details(data: dict):
    """ツイート詳細JSONを保存"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "tweet_details.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] ツイート詳細保存: {path}")


def compute_weighted_score(
    likes: int, retweets: int, replies: int,
    quotes: int, bookmarks: int, impressions: int,
) -> float:
    """Xアルゴリズム公式重み（2025年9月公開）に基づくエンゲージメントスコア。
    1000インプレッションあたりの「深い反応」を数値化。
    高スコア = 会話・保存を生むコンテンツ（アルゴリズムが評価）
    低スコア = 見られるだけで流れるコンテンツ
    """
    raw = (
        likes * 0.5
        + retweets * 1.0
        + replies * 13.5
        + quotes * 13.5
        + bookmarks * 10.0
    )
    if impressions > 0:
        return round(raw / impressions * 1000, 1)
    return 0.0


def save_tweet_details_for_analysis(metrics: list[dict]):
    """メトリクスデータをツイート詳細JSONに蓄積（重複排除）"""
    details = load_tweet_details()
    existing_ids = {t["id"] for t in details["tweets"]}

    added = 0
    for t in metrics:
        if t["id"] in existing_ids:
            continue

        # 投稿時間帯を抽出（JST = UTC+9）
        hour = None
        if t["created_at"]:
            try:
                dt = datetime.fromisoformat(t["created_at"])
                jst_hour = (dt.hour + 9) % 24
                hour = jst_hour
            except (ValueError, AttributeError):
                pass

        w_score = compute_weighted_score(
            t["likes"], t["retweets"], t["replies"],
            t.get("quotes", 0), t.get("bookmarks", 0), t["impressions"],
        )

        details["tweets"].append({
            "id": t["id"],
            "date": today_str(),
            "text": t["text"],
            "text_length": len(t["text"]),
            "hour": hour,
            "impressions": t["impressions"],
            "likes": t["likes"],
            "retweets": t["retweets"],
            "replies": t["replies"],
            "quotes": t.get("quotes", 0),
            "bookmarks": t.get("bookmarks", 0),
            "has_media": t.get("has_media", False),
            "media_type": t.get("media_type"),
            "engagement_rate": t["engagement_rate"],
            "weighted_score": w_score,
        })
        existing_ids.add(t["id"])
        added += 1

    details["last_updated"] = now_str()
    save_tweet_details(details)
    print(f"[OK] ツイート詳細: {added}件追加（合計{len(details['tweets'])}件）")


# --- パターン分析 ---

def analyze_patterns(details: dict) -> dict | None:
    """
    蓄積されたツイート詳細データからパターンを分析。
    7件以上のデータがある場合のみ分析実行。
    """
    tweets = details["tweets"]
    if len(tweets) < 7:
        print(f"[INFO] パターン分析スキップ（データ{len(tweets)}件 < 7件）")
        return None

    # 時間帯ごとの平均インプレッション・eng率
    hour_data = {}
    for t in tweets:
        h = t.get("hour")
        if h is None:
            continue
        if h not in hour_data:
            hour_data[h] = {"impressions": [], "eng_rates": []}
        hour_data[h]["impressions"].append(t["impressions"])
        hour_data[h]["eng_rates"].append(t["engagement_rate"])

    hour_analysis = {}
    for h, data in sorted(hour_data.items()):
        imps = data["impressions"]
        engs = data["eng_rates"]
        hour_analysis[h] = {
            "count": len(imps),
            "avg_imp": round(sum(imps) / len(imps)),
            "avg_eng": round(sum(engs) / len(engs), 2),
        }

    # ゴールデンタイム判定（平均impが最も高い時間帯 TOP3）
    golden_hours = sorted(
        hour_analysis.items(),
        key=lambda x: x[1]["avg_imp"],
        reverse=True,
    )[:3]

    # 文字数レンジごとの平均eng率
    length_buckets = {
        "~50": {"range": (0, 50), "impressions": [], "eng_rates": []},
        "51~100": {"range": (51, 100), "impressions": [], "eng_rates": []},
        "101~140": {"range": (101, 140), "impressions": [], "eng_rates": []},
        "141~200": {"range": (141, 200), "impressions": [], "eng_rates": []},
        "201~280": {"range": (201, 280), "impressions": [], "eng_rates": []},
        "280~": {"range": (281, 9999), "impressions": [], "eng_rates": []},
    }
    for t in tweets:
        tl = t.get("text_length", 0)
        for bucket_name, bucket in length_buckets.items():
            low, high = bucket["range"]
            if low <= tl <= high:
                bucket["impressions"].append(t["impressions"])
                bucket["eng_rates"].append(t["engagement_rate"])
                break

    length_analysis = {}
    for name, bucket in length_buckets.items():
        if bucket["impressions"]:
            imps = bucket["impressions"]
            engs = bucket["eng_rates"]
            length_analysis[name] = {
                "count": len(imps),
                "avg_imp": round(sum(imps) / len(imps)),
                "avg_eng": round(sum(engs) / len(engs), 2),
            }

    return {
        "total_tweets_analyzed": len(tweets),
        "hour_analysis": hour_analysis,
        "golden_hours": golden_hours,
        "length_analysis": length_analysis,
    }


# --- メトリクス取得 ---

def fetch_metrics(client, user_id: int, count: int = 20) -> list[dict]:
    """直近ツイートのメトリクスを取得（bookmark/quote/media含む拡張版）"""
    tweets = client.get_users_tweets(
        id=user_id,
        max_results=min(count, 100),
        tweet_fields=["created_at", "public_metrics", "text", "attachments"],
        expansions=["attachments.media_keys"],
        media_fields=["type"],
    )

    if not tweets.data:
        print("[WARN] ツイートが見つかりません")
        return []

    # メディア情報をIDでルックアップできるようにする
    media_map = {}
    if tweets.includes and "media" in tweets.includes:
        for m in tweets.includes["media"]:
            media_map[m.media_key] = m.type  # photo / video / animated_gif

    results = []
    for tweet in tweets.data:
        # RT（他人のリツイート）は自分のコンテンツではないので除外
        if tweet.text.startswith("RT @"):
            continue
        m = tweet.public_metrics
        imp = m.get("impression_count", 0)
        likes = m.get("like_count", 0)
        rts = m.get("retweet_count", 0)
        replies = m.get("reply_count", 0)
        quotes = m.get("quote_count", 0)
        bookmarks = m.get("bookmark_count", 0)

        # メディア情報の抽出
        has_media = False
        media_type = None
        if tweet.attachments and "media_keys" in tweet.attachments:
            media_keys = tweet.attachments["media_keys"]
            if media_keys:
                has_media = True
                # 最初のメディアのタイプを採用
                media_type = media_map.get(media_keys[0])

        eng_rate = ((likes + rts) / imp * 100) if imp > 0 else 0.0

        results.append({
            "id": str(tweet.id),
            "text": tweet.text,
            "created_at": tweet.created_at.isoformat() if tweet.created_at else "",
            "impressions": imp,
            "likes": likes,
            "retweets": rts,
            "replies": replies,
            "quotes": quotes,
            "bookmarks": bookmarks,
            "has_media": has_media,
            "media_type": media_type,
            "engagement_rate": round(eng_rate, 2),
        })

    return results


# --- メトリクス履歴 ---

def load_history() -> dict:
    """メトリクス履歴JSONを読み込み"""
    history_path = DATA_DIR / "metrics_history.json"
    if history_path.exists():
        return json.loads(history_path.read_text(encoding="utf-8"))
    return {"history": []}


def save_history(data: dict):
    """メトリクス履歴JSONを保存"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    history_path = DATA_DIR / "metrics_history.json"
    history_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 履歴保存: {history_path}")


# --- レポート生成 ---

def generate_report(
    metrics: list[dict],
    history: dict,
    follower_entry: dict | None = None,
    pattern_data: dict | None = None,
) -> str:
    """Obsidian用のMarkdownレポートを生成"""
    date = today_str()
    total_imp = sum(t["impressions"] for t in metrics)
    total_likes = sum(t["likes"] for t in metrics)
    total_rts = sum(t["retweets"] for t in metrics)
    avg_eng = sum(t["engagement_rate"] for t in metrics) / len(metrics) if metrics else 0

    # 前回との比較
    growth_str = ""
    if history["history"]:
        prev = history["history"][-1]
        prev_imp = prev.get("total_impressions", 0)
        if prev_imp > 0:
            growth = (total_imp - prev_imp) / prev_imp * 100
            sign = "+" if growth >= 0 else ""
            growth_str = f"- 前回比: {sign}{growth:.1f}%\n"

    # フォロワー情報
    follower_str = ""
    if follower_entry:
        follower_str = f"- フォロワー: {follower_entry['followers']:,}"
        if follower_entry.get("growth") is not None:
            sign = "+" if follower_entry["growth"] >= 0 else ""
            follower_str += f"（{sign}{follower_entry['growth']}）"
        follower_str += "\n"

    # インプレッション順でソート
    sorted_metrics = sorted(metrics, key=lambda t: t["impressions"], reverse=True)

    # トップ5テーブル
    top5_rows = []
    for i, t in enumerate(sorted_metrics[:5], 1):
        text_preview = t["text"].replace("\n", " ")[:60]
        if len(t["text"]) > 60:
            text_preview += "..."
        top5_rows.append(
            f"| {i} | {text_preview} | {t['impressions']:,} | {t['likes']} | {t['retweets']} | {t['engagement_rate']:.1f}% |"
        )
    top5_table = "\n".join(top5_rows)

    report = f"""# X メトリクス日報 - {date}

生成時刻: {now_str()}
対象: 直近{len(metrics)}件のツイート

## サマリー
- 合計インプレッション: {total_imp:,}
- 合計いいね: {total_likes:,} / 合計RT: {total_rts:,}
- 平均エンゲージメント率: {avg_eng:.2f}%
{growth_str}{follower_str}
## トップ5ツイート（インプレッション順）

| 順位 | 内容 | imp | like | RT | eng率 |
|------|------|-----|------|----|-------|
{top5_table}

## 全ツイート詳細

"""

    for i, t in enumerate(sorted_metrics, 1):
        text_preview = t["text"].replace("\n", " ")[:80]
        if len(t["text"]) > 80:
            text_preview += "..."
        report += f"{i}. **{t['impressions']:,} imp** | like:{t['likes']} RT:{t['retweets']} | eng:{t['engagement_rate']:.1f}%\n"
        report += f"   {text_preview}\n\n"

    # パターン分析セクション（データ蓄積後に表示）
    if pattern_data:
        report += _generate_pattern_section(pattern_data)

    return report


def _generate_pattern_section(pd: dict) -> str:
    """パターン分析のMarkdownセクションを生成"""
    section = f"## パターン分析（蓄積{pd['total_tweets_analyzed']}件）\n\n"

    # ゴールデンタイム
    if pd["golden_hours"]:
        section += "### ゴールデンタイム（平均imp TOP3）\n\n"
        section += "| 時間帯 | 投稿数 | 平均imp | 平均eng率 |\n"
        section += "|--------|--------|---------|----------|\n"
        for hour, data in pd["golden_hours"]:
            section += f"| {hour}:00 | {data['count']}件 | {data['avg_imp']:,} | {data['avg_eng']:.1f}% |\n"
        section += "\n"

    # 時間帯分布
    if pd["hour_analysis"]:
        section += "### 時間帯別パフォーマンス\n\n"
        section += "| 時間 | 件数 | 平均imp | 平均eng率 |\n"
        section += "|------|------|---------|----------|\n"
        for hour, data in sorted(pd["hour_analysis"].items()):
            section += f"| {hour}:00 | {data['count']} | {data['avg_imp']:,} | {data['avg_eng']:.1f}% |\n"
        section += "\n"

    # 文字数分析
    if pd["length_analysis"]:
        section += "### 文字数別パフォーマンス\n\n"
        section += "| 文字数 | 件数 | 平均imp | 平均eng率 |\n"
        section += "|--------|------|---------|----------|\n"
        for name, data in pd["length_analysis"].items():
            section += f"| {name} | {data['count']} | {data['avg_imp']:,} | {data['avg_eng']:.1f}% |\n"
        section += "\n"

    return section


# --- メイン ---

def main():
    parser = argparse.ArgumentParser(description="X ツイートメトリクス日次分析")
    parser.add_argument("--count", type=int, default=20, help="取得件数（デフォルト: 20）")
    args = parser.parse_args()

    print(f"=== X メトリクス日次分析 ===")
    print(f"取得件数: {args.count}")
    print(f"推定コスト: ${args.count * 0.005 + 0.005:.3f}")
    print()

    # X APIクライアント生成
    client = get_x_client()
    user_id = get_my_user_id(client)

    # フォロワー情報取得（Feature 2）
    print("[1/4] フォロワー情報取得...")
    profile = get_my_profile(client)
    follower_entry = track_followers(profile)
    print(f"[OK] フォロワー: {profile['followers']:,}", end="")
    if follower_entry.get("growth") is not None:
        sign = "+" if follower_entry["growth"] >= 0 else ""
        print(f"（{sign}{follower_entry['growth']}）")
    else:
        print("（初回記録）")

    # メトリクス取得
    print(f"[2/4] ツイートメトリクス取得...")
    metrics = fetch_metrics(client, user_id, args.count)
    if not metrics:
        print("[ERROR] メトリクス取得失敗")
        sys.exit(1)
    print(f"[OK] {len(metrics)}件のツイートメトリクス取得完了")

    # ツイート詳細データ蓄積（Feature 1）
    print(f"[3/4] ツイート詳細データ蓄積...")
    save_tweet_details_for_analysis(metrics)

    # パターン分析（Feature 1）
    print(f"[4/4] パターン分析...")
    details = load_tweet_details()
    pattern_data = analyze_patterns(details)

    # 履歴読み込み
    history = load_history()

    # レポート生成
    report = generate_report(metrics, history, follower_entry, pattern_data)

    # Obsidianに保存
    filename = f"metrics-{today_str()}.md"
    save_to_obsidian(OBSIDIAN_DAILY, filename, report)

    # 履歴更新
    total_imp = sum(t["impressions"] for t in metrics)
    avg_eng = sum(t["engagement_rate"] for t in metrics) / len(metrics)
    top_tweet = max(metrics, key=lambda t: t["impressions"])

    history["history"].append({
        "date": today_str(),
        "total_impressions": total_imp,
        "avg_engagement_rate": round(avg_eng, 2),
        "top_tweet_id": top_tweet["id"],
        "tweet_count": len(metrics),
        "followers": profile["followers"],
    })
    save_history(history)

    # Discord通知（フォロワー情報追加）
    top = max(metrics, key=lambda t: t["impressions"])
    top_text = top["text"].replace("\n", " ")[:50]
    follower_line = f"フォロワー: {profile['followers']:,}"
    if follower_entry.get("growth") is not None:
        sign = "+" if follower_entry["growth"] >= 0 else ""
        follower_line += f"（{sign}{follower_entry['growth']}）"

    notify_discord(
        f"**x-auto Daily Metrics** {today_str()}\n\n"
        f"直近{len(metrics)}件分析完了\n"
        f"合計imp: {total_imp:,} | 平均eng率: {avg_eng:.2f}%\n"
        f"{follower_line}\n"
        f"Top: {top_text}... ({top['impressions']:,} imp)"
    )

    print(f"\n=== 完了 ===")
    print(f"合計インプレッション: {total_imp:,}")
    print(f"平均エンゲージメント率: {avg_eng:.2f}%")
    print(f"フォロワー: {profile['followers']:,}")


if __name__ == "__main__":
    main()
