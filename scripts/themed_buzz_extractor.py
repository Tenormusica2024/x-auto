#!/usr/bin/env python3
"""
テーマ特化バズツイート抽出スクリプト (Themed Buzz Tweet Extractor)

twscrapeで特定テーマのバズツイートを抽出し、
ツイート生成のネタソース（論点・視点・空気感）として活用する。

buzz_tweet_extractor.pyのパターンを横展開。
テーマ辞書方式で複数テーマに対応可能。

コスト: $0.00（twscrape = 非公式API）

使い方:
  python -X utf8 themed_buzz_extractor.py --theme ai-coding-role
  python -X utf8 themed_buzz_extractor.py --theme ai-coding-role --dry-run
  python -X utf8 themed_buzz_extractor.py --list-themes
"""

import asyncio
import json
import sys
import os
import traceback
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

# twscrape_patchを先に適用（Twitter JSON解析エラー対策）
PATCH_PATH = Path(r"C:\Users\Tenormusica\Documents\ai-buzz-extractor-dev\scripts")
sys.path.insert(0, str(PATCH_PATH))
try:
    import twscrape_patch  # demjson3フォールバック適用
except ImportError:
    print("[WARNING] twscrape_patch not found - JSON parsing may fail")

from twscrape import API

# === 設定 ===

# accounts.db（ai-buzz-extractor-devと共有）
ACCOUNTS_DB = Path(r"C:\Users\Tenormusica\Documents\ai-buzz-extractor-dev\accounts.db")

# 出力先
OUTPUT_DIR = Path(__file__).parent / "data"

# Obsidianレポート出力先
OBSIDIAN_DIR = Path(r"D:\antigravity_projects\VaultD\Projects\Monetization\Intelligence\x-analytics\buzz-tweets")

# 各クエリの取得上限
QUERY_LIMIT = 50

# 最終出力件数
MAX_OUTPUT = 50

# 検索期間（時間）
SEARCH_RANGE_HOURS = 48

# クエリ間待機秒数（レート制限対策）
QUERY_DELAY = 2

# JST timezone
JST = timezone(timedelta(hours=9))


# === テーマ辞書 ===
# 将来のテーマ追加はここにエントリを追加するだけでOK

THEME_QUERIES = {
    "ai-coding-role": {
        "description": "AIコーディング時代の人間エンジニアの役割",
        "min_faves": 200,
        "queries": [
            {"label": "AIコーディング",     "query": "AIコーディング min_faves:200 lang:ja"},
            {"label": "Vibe Coding",       "query": "vibe coding min_faves:200 lang:ja"},
            {"label": "AI開発xエンジニア",  "query": "AI 開発 エンジニア min_faves:200 lang:ja"},
            {"label": "Claude Code",       "query": "Claude Code min_faves:200 lang:ja"},
            {"label": "AIxプログラマ",      "query": "AI プログラマー 不要 min_faves:200 lang:ja"},
            {"label": "Copilot開発",       "query": "Copilot 開発 min_faves:200 lang:ja"},
            {"label": "エンジニア不要論",    "query": "エンジニア 不要 AI min_faves:200 lang:ja"},
        ],
    },
}


def log(msg: str, level: str = "INFO"):
    """ログ出力"""
    timestamp = datetime.now(JST).strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def check_rate_limit() -> tuple[bool, Optional[str]]:
    """accounts.dbからtwscrapeのレート制限状態を事前確認"""
    import sqlite3
    conn = None
    try:
        conn = sqlite3.connect(str(ACCOUNTS_DB))
        cursor = conn.cursor()
        cursor.execute("SELECT locks FROM accounts LIMIT 1")
        row = cursor.fetchone()

        if not row or not row[0]:
            return True, None

        locks = json.loads(row[0])
        search_lock = locks.get("SearchTimeline")

        if not search_lock:
            return True, None

        # locksはUTCで保存 → aware datetimeに変換してJST比較
        lock_time_utc = datetime.strptime(search_lock, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        lock_time_jst = lock_time_utc.astimezone(JST)
        now = datetime.now(JST)

        if now >= lock_time_jst:
            return True, None
        else:
            return False, lock_time_jst.strftime("%H:%M:%S")

    except Exception as e:
        log(f"accounts.db読み込みエラー: {e}", "WARNING")
        return True, None  # エラー時は続行を試みる
    finally:
        if conn:
            conn.close()


def calculate_engagement(tweet) -> int:
    """エンゲージメントスコア計算（バズ度重視）
    Score = 引用RT*5 + リプライ*4 + RT*2 + いいね*1
    議論を呼んでいるツイートを上位に持ってくる重み付け。
    """
    likes = tweet.likeCount or 0
    retweets = tweet.retweetCount or 0
    quotes = tweet.quoteCount or 0
    replies = tweet.replyCount or 0
    return quotes * 5 + replies * 4 + retweets * 2 + likes * 1


def _tweet_to_dict(tweet, query_label: str, engagement_score: int) -> Dict:
    """twscrapeのtweetオブジェクトをdictに変換"""
    return {
        "id": str(tweet.id),
        "created_at": tweet.date.isoformat() if tweet.date else "",
        "username": f"@{tweet.user.username}" if tweet.user else "",
        "display_name": tweet.user.displayname if tweet.user else "",
        "text": tweet.rawContent or "",
        "likes": tweet.likeCount or 0,
        "retweets": tweet.retweetCount or 0,
        "quotes": tweet.quoteCount or 0,
        "replies": tweet.replyCount or 0,
        "engagement_score": engagement_score,
        "url": tweet.url or f"https://x.com/i/status/{tweet.id}",
        "query_source": query_label,
    }


async def fetch_themed_tweets(
    theme_config: Dict,
    dry_run: bool = False,
    query_limit: int = QUERY_LIMIT,
) -> Dict:
    """テーマ特化クエリでバズツイートを収集し、重複排除してエンゲージメント順でソート"""

    # レート制限チェック
    available, next_time = check_rate_limit()
    if not available:
        log(f"twscrapeレート制限中（解除予定: {next_time}）- スキップ", "WARNING")
        return {"tweets": [], "skipped": True, "reason": f"rate_limited until {next_time}"}

    api = API(str(ACCOUNTS_DB))

    queries = theme_config["queries"]

    # 検索期間: 2日前〜今日+1日（48h範囲）
    today = datetime.now(JST).date()
    since_date = today - timedelta(days=2)
    until_date = today + timedelta(days=1)
    since_str = since_date.strftime("%Y-%m-%d")
    until_str = until_date.strftime("%Y-%m-%d")

    all_tweets: Dict[int, Dict] = {}  # tweet_id -> tweet_data（重複排除用）
    query_stats = []
    total_fetched = 0

    for i, q in enumerate(queries):
        label = q["label"]
        base_query = q["query"]
        full_query = f"{base_query} -filter:retweets since:{since_str} until:{until_str}"

        log(f"[{i+1}/{len(queries)}] {label}: {full_query}")

        fetched = 0
        errors = 0

        if dry_run:
            log(f"  (dry-run) スキップ")
            query_stats.append({"label": label, "fetched": 0, "errors": 0})
            continue

        try:
            async for tweet in api.search(full_query, limit=query_limit):
                try:
                    tweet_id = tweet.id
                    if tweet_id in all_tweets:
                        # 重複: エンゲージメントが高い方を保持
                        existing_eng = all_tweets[tweet_id]["engagement_score"]
                        new_eng = calculate_engagement(tweet)
                        if new_eng > existing_eng:
                            all_tweets[tweet_id] = _tweet_to_dict(tweet, label, new_eng)
                        continue

                    eng = calculate_engagement(tweet)
                    all_tweets[tweet_id] = _tweet_to_dict(tweet, label, eng)
                    fetched += 1

                except Exception as e:
                    errors += 1
                    log(f"  ツイート処理エラー: {e}", "WARNING")

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate" in error_msg.lower():
                log(f"  レート制限検出 - 残りクエリスキップ", "WARNING")
                query_stats.append({"label": label, "fetched": fetched, "errors": errors + 1})
                break
            else:
                log(f"  検索エラー: {e}", "ERROR")
                errors += 1

        total_fetched += fetched
        log(f"  取得: {fetched}件 (エラー: {errors})")
        query_stats.append({"label": label, "fetched": fetched, "errors": errors})

        # クエリ間待機
        if i < len(queries) - 1:
            await asyncio.sleep(QUERY_DELAY)

    # エンゲージメント順ソート → 上位MAX_OUTPUT件
    sorted_tweets = sorted(
        all_tweets.values(),
        key=lambda t: t["engagement_score"],
        reverse=True
    )[:MAX_OUTPUT]

    result = {
        "generated_at": datetime.now(JST).isoformat(),
        "search_range_hours": SEARCH_RANGE_HOURS,
        "search_period": {"since": since_str, "until": until_str},
        "query_count": len(queries),
        "total_fetched": total_fetched,
        "after_dedup": len(all_tweets),
        "exported": len(sorted_tweets),
        "query_stats": query_stats,
        "tweets": sorted_tweets,
    }

    return result


def save_json(result: Dict, theme_name: str) -> Path:
    """JSON出力（日付付きファイル名）"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(JST).strftime("%Y-%m-%d")
    output_path = OUTPUT_DIR / f"themed-buzz-{theme_name}-{date_str}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log(f"JSON保存: {output_path} ({result['exported']}件)")
    return output_path


def save_obsidian_report(result: Dict, theme_name: str, description: str) -> Optional[Path]:
    """Obsidianレポート出力"""
    try:
        OBSIDIAN_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(JST).strftime("%Y-%m-%d")
        report_path = OBSIDIAN_DIR / f"themed-{theme_name}-{date_str}.md"

        tweets = result.get("tweets", [])
        period = result.get("search_period", {})

        lines = [
            f"# Themed Buzz: {description} - {date_str}",
            "",
            f"## Summary",
            f"- **Theme**: {theme_name}",
            f"- **Description**: {description}",
            f"- **Search Range**: {result.get('search_range_hours', '?')}h",
            f"- **Total Fetched**: {result.get('total_fetched', 0)}",
            f"- **After Dedup**: {result.get('after_dedup', 0)}",
            f"- **Exported**: {result.get('exported', 0)}",
            f"- **Period**: {period.get('since', '?')} ~ {period.get('until', '?')}",
            f"- **Generated**: {result.get('generated_at', '?')}",
            "",
        ]

        # クエリ別統計
        lines.append("## Query Stats")
        lines.append("")
        lines.append("| Query | Fetched | Errors |")
        lines.append("|-------|---------|--------|")
        for qs in result.get("query_stats", []):
            lines.append(f"| {qs['label']} | {qs['fetched']} | {qs['errors']} |")
        lines.append("")

        # 上位20件の詳細
        lines.append("## Top 20 Tweets")
        lines.append("")
        for i, t in enumerate(tweets[:20], 1):
            text_preview = t["text"][:100].replace("\n", " ")
            lines.append(f"### {i}. {t['username']} (eng: {t['engagement_score']})")
            lines.append(f"- **Likes**: {t['likes']} / **RT**: {t['retweets']} / **Quotes**: {t['quotes']} / **Replies**: {t['replies']}")
            lines.append(f"- **Source Query**: {t['query_source']}")
            lines.append(f"- {text_preview}...")
            lines.append(f"- [Link]({t['url']})")
            lines.append("")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        log(f"Obsidianレポート保存: {report_path}")
        return report_path

    except Exception as e:
        log(f"Obsidianレポート保存エラー: {e}", "ERROR")
        return None


def list_themes():
    """利用可能なテーマ一覧を表示"""
    print("\n利用可能なテーマ:")
    print("-" * 60)
    for name, config in THEME_QUERIES.items():
        desc = config["description"]
        n_queries = len(config["queries"])
        min_fav = config["min_faves"]
        print(f"  {name}")
        print(f"    {desc}")
        print(f"    クエリ数: {n_queries} / min_faves: {min_fav}")
        print()


async def main():
    """メインエントリポイント"""
    import argparse
    parser = argparse.ArgumentParser(description="Themed Buzz Tweet Extractor")
    parser.add_argument("--theme", type=str, help="抽出テーマ名（例: ai-coding-role）")
    parser.add_argument("--dry-run", action="store_true", help="API呼び出しなしで動作確認")
    parser.add_argument("--limit", type=int, default=QUERY_LIMIT, help="各クエリの取得上限")
    parser.add_argument("--list-themes", action="store_true", help="利用可能なテーマ一覧")
    args = parser.parse_args()

    # テーマ一覧表示
    if args.list_themes:
        list_themes()
        return

    # テーマ必須チェック
    if not args.theme:
        print("エラー: --theme を指定してください。利用可能なテーマは --list-themes で確認できます。")
        sys.exit(1)

    # テーマ存在チェック
    if args.theme not in THEME_QUERIES:
        print(f"エラー: テーマ '{args.theme}' は見つかりません。")
        list_themes()
        sys.exit(1)

    theme_name = args.theme
    theme_config = THEME_QUERIES[theme_name]
    description = theme_config["description"]
    queries = theme_config["queries"]

    log("=" * 60)
    log(f"Themed Buzz Extractor - {theme_name}")
    log(f"  description: {description}")
    log(f"  accounts.db: {ACCOUNTS_DB}")
    log(f"  queries: {len(queries)}")
    log(f"  limit/query: {args.limit}")
    log(f"  max output: {MAX_OUTPUT}")
    log(f"  search range: {SEARCH_RANGE_HOURS}h")
    log(f"  dry-run: {args.dry_run}")
    log("=" * 60)

    # accounts.db存在チェック
    if not ACCOUNTS_DB.exists():
        log(f"accounts.db が見つかりません: {ACCOUNTS_DB}", "ERROR")
        sys.exit(1)

    try:
        result = await fetch_themed_tweets(
            theme_config=theme_config,
            dry_run=args.dry_run,
            query_limit=args.limit,
        )

        if result.get("skipped"):
            log(f"スキップ: {result.get('reason', 'unknown')}", "WARNING")
            sys.exit(0)

        # テーマ情報をresultに追加
        result["theme"] = theme_name
        result["description"] = description

        # JSON保存
        json_path = save_json(result, theme_name)

        # Obsidianレポート
        save_obsidian_report(result, theme_name, description)

        log("=" * 60)
        log(f"完了 - {result['exported']}件エクスポート → {json_path}")
        log("=" * 60)

    except Exception as e:
        log(f"致命的エラー: {e}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
