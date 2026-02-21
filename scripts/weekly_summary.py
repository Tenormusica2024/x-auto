"""
weekly_summary.py - X 週次サマリー自動生成

日次蓄積データを週単位で集計し、パフォーマンス振り返りと改善提案を自動生成する。
LLM APIコールなし、既存データの集約のみ。追加コスト$0。

入力:
  - metrics_history.json (日次集計)
  - tweet_details.json (個別ツイート詳細)
  - follower_history.json (フォロワー推移)
  - content_evaluations.json (LLM 7軸分類)

出力:
  - Obsidian: weekly/weekly-summary-YYYY-MM-DD.md
  - Discord: #x-trend-alerts

使い方:
  python -X utf8 weekly_summary.py              # 先週のサマリー
  python -X utf8 weekly_summary.py --weeks 1    # 先々週のサマリー
  python -X utf8 weekly_summary.py --dry-run    # 標準出力のみ（保存なし）
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from x_client import (
    notify_discord, save_to_obsidian, today_str, now_str,
    OBSIDIAN_WEEKLY, DATA_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# 最低ツイート数（これ未満はスキップ）
MIN_TWEETS = 3
# 曜日の日本語表記
WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]
# 文字数バケット境界
LENGTH_BUCKETS = [(0, 50), (51, 100), (101, 150), (151, 200), (201, 280), (281, 9999)]


# ============================================================
# 期間計算
# ============================================================

def get_week_range(weeks_ago: int = 0) -> tuple[str, str]:
    """対象週の月曜〜日曜を返す。

    Args:
        weeks_ago: 0=先週, 1=先々週, ...
    Returns:
        (start_date, end_date) 例: ("2026-02-10", "2026-02-16")
    """
    today = datetime.now()
    # 今週の月曜を求める（weekday: 0=月, 6=日）
    this_monday = today - timedelta(days=today.weekday())
    # weeks_ago=0 → 先週の月曜、weeks_ago=1 → 先々週の月曜
    target_monday = this_monday - timedelta(weeks=weeks_ago + 1)
    target_sunday = target_monday + timedelta(days=6)
    return target_monday.strftime("%Y-%m-%d"), target_sunday.strftime("%Y-%m-%d")


# ============================================================
# データ読み込み
# ============================================================

def _load_json(filename: str) -> dict:
    """data/配下のJSONを読み込む。ファイルがなければ空辞書を返す。"""
    path = DATA_DIR / filename
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    logger.warning(f"{filename} が見つかりません")
    return {}


def _filter_by_date(items: list, start: str, end: str, date_key: str = "date") -> list:
    """日付範囲でフィルタ（start <= date <= end）"""
    return [item for item in items if start <= item.get(date_key, "") <= end]


def load_week_data(start: str, end: str) -> dict:
    """対象期間のデータを一括読み込み・フィルタして返す。"""
    metrics_raw = _load_json("metrics_history.json")
    tweets_raw = _load_json("tweet_details.json")
    followers_raw = _load_json("follower_history.json")
    evals_raw = _load_json("content_evaluations.json")

    return {
        "metrics": _filter_by_date(metrics_raw.get("history", []), start, end),
        "tweets": _filter_by_date(tweets_raw.get("tweets", []), start, end),
        "followers": _filter_by_date(followers_raw.get("history", []), start, end),
        "evaluations": evals_raw.get("evaluations", {}),
    }


# ============================================================
# 分析関数
# ============================================================

def calculate_overview(data: dict) -> dict:
    """週次概要統計を算出。"""
    tweets = data["tweets"]
    followers = data["followers"]

    total_imp = sum(t.get("impressions", 0) for t in tweets)
    eng_rates = [t.get("engagement_rate", 0) for t in tweets if t.get("engagement_rate")]
    avg_eng = sum(eng_rates) / len(eng_rates) if eng_rates else 0.0

    # フォロワー増減
    follower_start = followers[0]["followers"] if followers else None
    follower_end = followers[-1]["followers"] if followers else None
    follower_change = (follower_end - follower_start) if (follower_start and follower_end) else None

    return {
        "total_impressions": total_imp,
        "avg_engagement_rate": round(avg_eng, 2),
        "total_tweets": len(tweets),
        "follower_start": follower_start,
        "follower_end": follower_end,
        "follower_change": follower_change,
    }


def get_top_bottom_tweets(tweets: list, n: int = 3) -> dict:
    """W-ScoreでTOP N / BOTTOM Nを抽出。"""
    scored = [t for t in tweets if t.get("weighted_score") is not None]
    if not scored:
        return {"top": [], "bottom": []}
    sorted_tweets = sorted(scored, key=lambda t: t["weighted_score"], reverse=True)
    return {
        "top": sorted_tweets[:n],
        "bottom": sorted_tweets[-n:] if len(sorted_tweets) >= n else sorted_tweets[::-1],
    }


def analyze_content_type(tweets: list, evaluations: dict) -> list:
    """content_type別の平均W-Score・エンゲージメント率を算出。"""
    groups: dict[str, list] = defaultdict(list)
    for t in tweets:
        ev = evaluations.get(t.get("id", ""), {})
        ct = ev.get("content_type", "未分類")
        groups[ct].append(t)

    results = []
    for ct, items in groups.items():
        ws_vals = [i["weighted_score"] for i in items if i.get("weighted_score") is not None]
        eng_vals = [i["engagement_rate"] for i in items if i.get("engagement_rate")]
        results.append({
            "content_type": ct,
            "count": len(items),
            "avg_w_score": round(sum(ws_vals) / len(ws_vals), 1) if ws_vals else 0.0,
            "avg_eng_rate": round(sum(eng_vals) / len(eng_vals), 2) if eng_vals else 0.0,
        })
    return sorted(results, key=lambda r: r["avg_w_score"], reverse=True)


def analyze_daily_trend(data: dict) -> list:
    """日別のimp合計・平均eng率・投稿数を算出。"""
    day_groups: dict[str, list] = defaultdict(list)
    for t in data["tweets"]:
        day_groups[t.get("date", "")].append(t)

    results = []
    for date_str in sorted(day_groups.keys()):
        items = day_groups[date_str]
        total_imp = sum(i.get("impressions", 0) for i in items)
        eng_vals = [i["engagement_rate"] for i in items if i.get("engagement_rate")]
        avg_eng = round(sum(eng_vals) / len(eng_vals), 2) if eng_vals else 0.0

        # 曜日を取得
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            weekday = WEEKDAY_JA[dt.weekday()]
        except (ValueError, IndexError):
            weekday = "?"

        results.append({
            "date": date_str,
            "weekday": weekday,
            "impressions": total_imp,
            "avg_eng_rate": avg_eng,
            "tweet_count": len(items),
        })
    return results


def analyze_time_pattern(tweets: list) -> dict:
    """時間帯別の平均W-Scoreを算出。"""
    hour_groups: dict[int, list] = defaultdict(list)
    for t in tweets:
        h = t.get("hour")
        ws = t.get("weighted_score")
        if h is not None and ws is not None:
            hour_groups[h].append(ws)

    hourly = []
    for h in sorted(hour_groups.keys()):
        vals = hour_groups[h]
        hourly.append({
            "hour": h,
            "count": len(vals),
            "avg_w_score": round(sum(vals) / len(vals), 1),
        })
    # W-Scoreの高い順にソート
    hourly_sorted = sorted(hourly, key=lambda x: x["avg_w_score"], reverse=True)

    best = hourly_sorted[0] if hourly_sorted else None
    return {"best_hour": best, "hourly": hourly_sorted}


def analyze_length_pattern(tweets: list) -> dict:
    """文字数レンジ別の平均W-Scoreを算出。"""
    bucket_groups: dict[str, list] = defaultdict(list)
    for t in tweets:
        length = t.get("text_length", 0)
        ws = t.get("weighted_score")
        if ws is None:
            continue
        for low, high in LENGTH_BUCKETS:
            if low <= length <= high:
                label = f"{low}-{high}" if high < 9999 else f"{low}+"
                bucket_groups[label].append(ws)
                break

    buckets = []
    for label, vals in bucket_groups.items():
        buckets.append({
            "range": label,
            "count": len(vals),
            "avg_w_score": round(sum(vals) / len(vals), 1),
        })
    buckets_sorted = sorted(buckets, key=lambda x: x["avg_w_score"], reverse=True)

    best = buckets_sorted[0] if buckets_sorted else None
    return {"best_range": best, "buckets": buckets_sorted}


def compare_weeks(current: dict, previous: dict | None) -> dict | None:
    """今週と前週の比較。前週データがなければNoneを返す。"""
    if not previous or not previous.get("tweets"):
        return None

    cur_ov = calculate_overview(current)
    prev_ov = calculate_overview(previous)

    def _diff(cur_val, prev_val):
        if cur_val is None or prev_val is None:
            return None
        return cur_val - prev_val

    def _pct(cur_val, prev_val):
        if cur_val is None or prev_val is None or prev_val == 0:
            return None
        return round((cur_val - prev_val) / prev_val * 100, 1)

    return {
        "current": cur_ov,
        "previous": prev_ov,
        "imp_diff": _diff(cur_ov["total_impressions"], prev_ov["total_impressions"]),
        "imp_pct": _pct(cur_ov["total_impressions"], prev_ov["total_impressions"]),
        "eng_diff": _diff(cur_ov["avg_engagement_rate"], prev_ov["avg_engagement_rate"]),
        "tweet_diff": _diff(cur_ov["total_tweets"], prev_ov["total_tweets"]),
        "follower_diff": _diff(cur_ov["follower_change"], prev_ov["follower_change"]),
    }


# ============================================================
# 推奨事項生成（ルールベース）
# ============================================================

def generate_recommendations(
    content_perf: list,
    time_pattern: dict,
    length_pattern: dict,
    comparison: dict | None,
) -> list[str]:
    """データドリブンな推奨事項を生成（3-5項目）。"""
    recs = []

    # 1. 最強content_typeの推奨
    if content_perf and len(content_perf) >= 2:
        best = content_perf[0]
        second = content_perf[1]
        if best["avg_w_score"] > 0:
            ratio = (
                round(best["avg_w_score"] / second["avg_w_score"], 1)
                if second["avg_w_score"] > 0 else 0
            )
            recs.append(
                f"{best['content_type']}のW-Score平均{best['avg_w_score']}は"
                f"2位の{second['content_type']}({second['avg_w_score']})の{ratio}倍。"
                f"投稿比率を増やす価値あり"
            )

    # 2. 最適時間帯の推奨
    best_hour = time_pattern.get("best_hour")
    if best_hour and best_hour["count"] >= 2:
        recs.append(
            f"{best_hour['hour']}時台の投稿はW-Score平均{best_hour['avg_w_score']}で最高。"
            f"重要な投稿はこの時間帯を狙う（{best_hour['count']}件のデータ）"
        )

    # 3. 最適文字数の推奨
    best_range = length_pattern.get("best_range")
    if best_range and best_range["count"] >= 2:
        recs.append(
            f"文字数{best_range['range']}のW-Score平均{best_range['avg_w_score']}が最高。"
            f"この範囲を意識する（{best_range['count']}件のデータ）"
        )

    # 4. 前週比で悪化した指標があれば指摘
    if comparison:
        imp_pct = comparison.get("imp_pct")
        if imp_pct is not None and imp_pct < -10:
            recs.append(
                f"インプレッションが前週比{imp_pct:+.1f}%。"
                f"投稿頻度または投稿時間帯を見直す"
            )
        eng_diff = comparison.get("eng_diff")
        if eng_diff is not None and eng_diff < -0.3:
            recs.append(
                f"エンゲージメント率が前週比{eng_diff:+.2f}pt低下。"
                f"コンテンツの質（独自性・具体性）を見直す"
            )

    # 5. content_typeで件数ゼロの高パフォーマンスタイプ（機会損失）
    if content_perf:
        # 全体平均W-Scoreより高いのに件数1以下のタイプ
        all_ws = [c["avg_w_score"] for c in content_perf if c["avg_w_score"] > 0]
        avg_ws = sum(all_ws) / len(all_ws) if all_ws else 0
        for cp in content_perf:
            if cp["count"] <= 1 and cp["avg_w_score"] > avg_ws and cp["content_type"] != "未分類":
                recs.append(
                    f"{cp['content_type']}はW-Score{cp['avg_w_score']}で平均以上だが"
                    f"投稿{cp['count']}件のみ。機会損失の可能性"
                )
                break  # 1件だけ指摘

    return recs[:5]  # 最大5項目


# ============================================================
# レポート生成
# ============================================================

def _format_change(val, suffix="", plus_prefix=True) -> str:
    """変化量をフォーマット（+/-付き）"""
    if val is None:
        return "-"
    sign = "+" if val > 0 and plus_prefix else ""
    if isinstance(val, float):
        return f"{sign}{val:.1f}{suffix}"
    return f"{sign}{val:,}{suffix}"


def _truncate_text(text: str, max_len: int = 60) -> str:
    """テキストを指定文字数で切り詰め"""
    if not text:
        return ""
    return text[:max_len] + "..." if len(text) > max_len else text


def generate_report(
    start: str, end: str,
    overview: dict,
    top_bottom: dict,
    content_perf: list,
    daily_trend: list,
    time_pattern: dict,
    length_pattern: dict,
    comparison: dict | None,
    recommendations: list[str],
) -> str:
    """Obsidian用Markdownレポート生成。"""
    lines = [
        f"# X週次サマリー: {start} - {end}",
        "",
        f"生成時刻: {now_str()}",
        "",
    ]

    # --- 週次概要 ---
    lines.append("## 週次概要")
    lines.append(f"- 総インプレッション: {overview['total_impressions']:,}")
    lines.append(f"- 平均エンゲージメント率: {overview['avg_engagement_rate']:.2f}%")
    lines.append(f"- 投稿数: {overview['total_tweets']}")
    if overview["follower_start"] and overview["follower_end"]:
        fc = overview["follower_change"]
        lines.append(
            f"- フォロワー: {overview['follower_start']} -> "
            f"{overview['follower_end']} ({_format_change(fc)})"
        )
    lines.append("")

    # --- 前週比較 ---
    if comparison:
        cur = comparison["current"]
        prev = comparison["previous"]
        lines.append("## 前週比較")
        lines.append("| 指標 | 今週 | 前週 | 変化 |")
        lines.append("|------|------|------|------|")
        lines.append(
            f"| インプレッション | {cur['total_impressions']:,} "
            f"| {prev['total_impressions']:,} "
            f"| {_format_change(comparison['imp_diff'])} "
            f"({_format_change(comparison['imp_pct'], '%')}) |"
        )
        lines.append(
            f"| エンゲージメント率 | {cur['avg_engagement_rate']:.2f}% "
            f"| {prev['avg_engagement_rate']:.2f}% "
            f"| {_format_change(comparison['eng_diff'], 'pt')} |"
        )
        lines.append(
            f"| 投稿数 | {cur['total_tweets']} "
            f"| {prev['total_tweets']} "
            f"| {_format_change(comparison['tweet_diff'])} |"
        )
        lines.append("")

    # --- TOP3ツイート ---
    lines.append("## TOP3ツイート (W-Score順)")
    for i, t in enumerate(top_bottom.get("top", []), 1):
        ws = t.get("weighted_score", 0)
        imp = t.get("impressions", 0)
        text = _truncate_text(t.get("text", ""), 80)
        date = t.get("date", "?")
        hour = t.get("hour", "?")
        likes = t.get("likes", 0)
        rts = t.get("retweets", 0)
        replies = t.get("replies", 0)
        quotes = t.get("quotes", 0)
        lines.append(f"### {i}位: W-Score {ws}")
        lines.append(f"- 日時: {date} {hour}時台")
        lines.append(f"- インプレッション: {imp:,}")
        lines.append(f"- エンゲージメント: like {likes} / RT {rts} / reply {replies} / 引用 {quotes}")
        lines.append(f"- 本文: {text}")
        lines.append("")

    # --- BOTTOM3ツイート ---
    lines.append("## BOTTOM3ツイート (W-Score順)")
    for i, t in enumerate(top_bottom.get("bottom", []), 1):
        ws = t.get("weighted_score", 0)
        imp = t.get("impressions", 0)
        text = _truncate_text(t.get("text", ""), 80)
        lines.append(f"### {i}位: W-Score {ws}")
        lines.append(f"- インプレッション: {imp:,}")
        lines.append(f"- 本文: {text}")
        lines.append("")

    # --- コンテンツタイプ別 ---
    if content_perf:
        lines.append("## コンテンツタイプ別パフォーマンス")
        lines.append("| タイプ | 投稿数 | 平均W-Score | 平均eng率 |")
        lines.append("|--------|--------|-------------|-----------|")
        for cp in content_perf:
            lines.append(
                f"| {cp['content_type']} | {cp['count']} "
                f"| {cp['avg_w_score']} | {cp['avg_eng_rate']:.2f}% |"
            )
        lines.append("")

    # --- 日別トレンド ---
    if daily_trend:
        lines.append("## 日別トレンド")
        lines.append("| 日付 | imp | eng率 | 投稿数 |")
        lines.append("|------|-----|-------|--------|")
        for d in daily_trend:
            date_short = d["date"][5:]  # MM-DD形式
            lines.append(
                f"| {date_short} ({d['weekday']}) "
                f"| {d['impressions']:,} "
                f"| {d['avg_eng_rate']:.2f}% "
                f"| {d['tweet_count']} |"
            )
        lines.append("")

    # --- 時間帯パターン ---
    if time_pattern.get("hourly"):
        best = time_pattern["best_hour"]
        lines.append("## 時間帯パターン")
        if best:
            lines.append(f"最高パフォーマンス: {best['hour']}時台 (W-Score {best['avg_w_score']})")
        lines.append("")
        lines.append("| 時間帯 | 投稿数 | 平均W-Score |")
        lines.append("|--------|--------|-------------|")
        for h in time_pattern["hourly"][:8]:  # 上位8時間帯
            lines.append(f"| {h['hour']}時台 | {h['count']} | {h['avg_w_score']} |")
        lines.append("")

    # --- 文字数パターン ---
    if length_pattern.get("buckets"):
        best = length_pattern["best_range"]
        lines.append("## 文字数パターン")
        if best:
            lines.append(f"最高パフォーマンス: {best['range']}文字 (W-Score {best['avg_w_score']})")
        lines.append("")
        lines.append("| 文字数 | 投稿数 | 平均W-Score |")
        lines.append("|--------|--------|-------------|")
        for b in length_pattern["buckets"]:
            lines.append(f"| {b['range']} | {b['count']} | {b['avg_w_score']} |")
        lines.append("")

    # --- 推奨事項 ---
    if recommendations:
        lines.append("## 推奨事項")
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")

    return "\n".join(lines)


def generate_discord_summary(
    start: str, end: str,
    overview: dict,
    top_tweets: list,
    content_perf: list,
    recommendations: list[str],
) -> str:
    """Discord用コンパクト要約（2000文字制限）。"""
    # 期間をMM/DD形式で短縮
    s_short = f"{start[5:7]}/{start[8:10]}"
    e_short = f"{end[5:7]}/{end[8:10]}"

    lines = [
        f"**X週次サマリー** ({s_short}-{e_short})",
        "",
        f"- 総imp: {overview['total_impressions']:,}",
        f"- 平均eng率: {overview['avg_engagement_rate']:.2f}%",
        f"- 投稿数: {overview['total_tweets']}",
    ]

    if overview["follower_change"] is not None:
        lines.append(
            f"- フォロワー: {_format_change(overview['follower_change'])} "
            f"({overview['follower_start']} -> {overview['follower_end']})"
        )

    # TOP3
    if top_tweets:
        lines.append("")
        lines.append("**TOP3**")
        for i, t in enumerate(top_tweets[:3], 1):
            ws = t.get("weighted_score", 0)
            text = _truncate_text(t.get("text", ""), 40)
            lines.append(f"{i}. W{ws} {text}")

    # content_type上位3
    if content_perf:
        lines.append("")
        lines.append("**コンテンツタイプ別**")
        for cp in content_perf[:3]:
            lines.append(f"- {cp['content_type']}: W{cp['avg_w_score']} ({cp['count']}件)")

    # 推奨1-2件
    if recommendations:
        lines.append("")
        lines.append("**推奨**")
        for rec in recommendations[:2]:
            lines.append(f"- {rec}")

    return "\n".join(lines)


# ============================================================
# メイン処理
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="X週次サマリー生成")
    parser.add_argument("--weeks", type=int, default=0,
                        help="何週間前のサマリーを生成するか (0=先週)")
    parser.add_argument("--dry-run", action="store_true",
                        help="保存せず標準出力のみ")
    args = parser.parse_args()

    # 対象週の期間を算出
    start, end = get_week_range(args.weeks)
    logger.info(f"対象期間: {start} - {end}")

    # データ読み込み
    data = load_week_data(start, end)
    tweets = data["tweets"]

    if len(tweets) < MIN_TWEETS:
        logger.warning(
            f"対象期間のツイートが{len(tweets)}件のみ（最低{MIN_TWEETS}件必要）。スキップします"
        )
        return

    logger.info(f"ツイート {len(tweets)}件を分析")

    # 各種分析
    overview = calculate_overview(data)
    top_bottom = get_top_bottom_tweets(tweets)
    content_perf = analyze_content_type(tweets, data["evaluations"])
    daily_trend = analyze_daily_trend(data)
    time_pattern = analyze_time_pattern(tweets)
    length_pattern = analyze_length_pattern(tweets)

    # 前週データを取得して比較
    prev_start, prev_end = get_week_range(args.weeks + 1)
    prev_data = load_week_data(prev_start, prev_end)
    comparison = compare_weeks(data, prev_data)

    # 推奨事項生成
    recommendations = generate_recommendations(
        content_perf, time_pattern, length_pattern, comparison
    )

    # レポート生成
    report = generate_report(
        start, end, overview, top_bottom, content_perf,
        daily_trend, time_pattern, length_pattern,
        comparison, recommendations,
    )

    if args.dry_run:
        print(report)
        logger.info("dry-runモード: 保存をスキップ")
        return

    # Obsidian保存
    filename = f"weekly-summary-{end}.md"
    save_to_obsidian(OBSIDIAN_WEEKLY, filename, report)
    logger.info(f"Obsidian保存: {filename}")

    # Discord通知
    discord_msg = generate_discord_summary(
        start, end, overview,
        top_bottom.get("top", []),
        content_perf, recommendations,
    )
    notify_discord(discord_msg)
    logger.info("Discord通知送信")

    logger.info("週次サマリー生成完了")


if __name__ == "__main__":
    main()
