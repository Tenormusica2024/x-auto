#!/usr/bin/env python3
"""
バズツイート抽出スクリプト (Buzz Tweet Extractor)

twscrapeでAI関連バズツイート上位100件を抽出し、
zeitgeist_detectorのデータソース補完 + ツイート生成のネタソースとして活用する。

ai-buzz-extractorのキーワード設計では拾えない悲観論（失業不安・規制懸念等）を
min_faves:500の広めクエリで補完する。

実行スケジュール: 毎日 06:30 JST（zeitgeist_detector 07:00の前）
コスト: $0.00/日（twscrape = 非公式API）

出力:
- x-auto/scripts/data/buzz-tweets-latest.json
- Obsidian日次レポート
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

from twscrape import API, AccountsPool

# === 設定 ===

# accounts.db（ai-buzz-extractor-devと共有）
ACCOUNTS_DB = Path(r"C:\Users\Tenormusica\Documents\ai-buzz-extractor-dev\accounts.db")

# 出力先
OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_JSON = OUTPUT_DIR / "buzz-tweets-latest.json"

# Obsidianレポート出力先
OBSIDIAN_DIR = Path(r"D:\antigravity_projects\VaultD\Projects\Monetization\Intelligence\x-analytics\buzz-tweets")

# 検索クエリ設計
# AI全般 + ネガティブ系 + モデル名で界隈の空気感を網羅的に拾う
SEARCH_QUERIES = [
    {"label": "AI全般",    "query": "AI min_faves:500 lang:ja"},
    {"label": "ChatGPT",  "query": "ChatGPT min_faves:500 lang:ja"},
    {"label": "Claude",   "query": "Claude min_faves:500 lang:ja"},
    {"label": "Gemini AI","query": "Gemini AI min_faves:500 lang:ja"},  # "Gemini AI"でアイドルノイズ軽減
    {"label": "AI不安系",  "query": "AI 仕事 min_faves:500 lang:ja"},    # 失業不安・雇用影響
    {"label": "AI規制系",  "query": "AI 規制 min_faves:500 lang:ja"},    # 規制議論・倫理
    {"label": "LLM技術",  "query": "LLM min_faves:500 lang:ja"},        # 技術者コミュニティ
]

# 各クエリの取得上限
QUERY_LIMIT = 50

# 最終出力件数
MAX_OUTPUT = 100

# クエリ間待機秒数（レート制限対策）
QUERY_DELAY = 2

# JST timezone
JST = timezone(timedelta(hours=9))


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

        # locks はUTCで保存 → aware datetimeに変換してJST比較
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
    Score = 引用RT×5 + リプライ×4 + RT×2 + いいね×1

    NOTE: zeitgeist_detector側の_calc_engagement()は likes+RT*2+quotes*3 で
    「影響度」を測る別の式を使用。用途が異なるため意図的に別計算。
    - 本スクリプト: 議論を呼んでいるか（引用RT・リプライ重視）→ バズ度
    - zeitgeist側: 拡散力（いいね・RT重視）→ 影響度
    """
    likes = tweet.likeCount or 0
    retweets = tweet.retweetCount or 0
    quotes = tweet.quoteCount or 0
    replies = tweet.replyCount or 0
    return quotes * 5 + replies * 4 + retweets * 2 + likes * 1


async def fetch_buzz_tweets(dry_run: bool = False, query_limit: int = QUERY_LIMIT) -> Dict:
    """全クエリでバズツイートを収集し、重複排除してエンゲージメント順でソート"""

    # レート制限チェック
    available, next_time = check_rate_limit()
    if not available:
        log(f"twscrapeレート制限中（解除予定: {next_time}）- スキップ", "WARNING")
        return {"tweets": [], "skipped": True, "reason": f"rate_limited until {next_time}"}

    api = API(str(ACCOUNTS_DB))

    # 検索期間: 昨日00:00〜今日23:59
    today = datetime.now(JST).date()
    yesterday = today - timedelta(days=1)
    since_str = yesterday.strftime("%Y-%m-%d")
    until_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    all_tweets: Dict[int, Dict] = {}  # tweet_id -> tweet_data（重複排除用）
    query_stats = []
    total_fetched = 0

    for i, q in enumerate(SEARCH_QUERIES):
        label = q["label"]
        base_query = q["query"]
        full_query = f"{base_query} -filter:retweets since:{since_str} until:{until_str}"

        log(f"[{i+1}/{len(SEARCH_QUERIES)}] {label}: {full_query}")

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
                        # 重複: エンゲージメントが高い方を保持（カウントしない）
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
        if i < len(SEARCH_QUERIES) - 1:
            await asyncio.sleep(QUERY_DELAY)

    # エンゲージメント順ソート → 上位MAX_OUTPUT件
    sorted_tweets = sorted(
        all_tweets.values(),
        key=lambda t: t["engagement_score"],
        reverse=True
    )[:MAX_OUTPUT]

    result = {
        "generated_at": datetime.now(JST).isoformat(),
        "search_period": {"since": since_str, "until": until_str},
        "query_count": len(SEARCH_QUERIES),
        "total_fetched": total_fetched,
        "after_dedup": len(all_tweets),
        "exported": len(sorted_tweets),
        "query_stats": query_stats,
        "tweets": sorted_tweets,
    }

    return result


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


def save_json(result: Dict) -> Path:
    """JSON出力"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log(f"JSON保存: {OUTPUT_JSON} ({result['exported']}件)")
    return OUTPUT_JSON


def save_obsidian_report(result: Dict) -> Optional[Path]:
    """Obsidianレポート出力"""
    try:
        OBSIDIAN_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(JST).strftime("%Y-%m-%d")
        report_path = OBSIDIAN_DIR / f"buzz-tweets-{date_str}.md"

        tweets = result.get("tweets", [])

        lines = [
            f"# Buzz Tweets - {date_str}",
            "",
            f"## Summary",
            f"- **Total Fetched**: {result.get('total_fetched', 0)}",
            f"- **After Dedup**: {result.get('after_dedup', 0)}",
            f"- **Exported**: {result.get('exported', 0)}",
            f"- **Period**: {result.get('search_period', {}).get('since', '?')} ~ {result.get('search_period', {}).get('until', '?')}",
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


async def main():
    """メインエントリポイント"""
    import argparse
    parser = argparse.ArgumentParser(description="AI Buzz Tweet Extractor")
    parser.add_argument("--dry-run", action="store_true", help="API呼び出しなしで動作確認")
    parser.add_argument("--limit", type=int, default=QUERY_LIMIT, help="各クエリの取得上限")
    args = parser.parse_args()

    query_limit = args.limit

    log("=" * 60)
    log("Buzz Tweet Extractor - Start")
    log(f"  accounts.db: {ACCOUNTS_DB}")
    log(f"  queries: {len(SEARCH_QUERIES)}")
    log(f"  limit/query: {query_limit}")
    log(f"  max output: {MAX_OUTPUT}")
    log(f"  dry-run: {args.dry_run}")
    log("=" * 60)

    # accounts.db存在チェック
    if not ACCOUNTS_DB.exists():
        log(f"accounts.db が見つかりません: {ACCOUNTS_DB}", "ERROR")
        sys.exit(1)

    try:
        result = await fetch_buzz_tweets(dry_run=args.dry_run, query_limit=query_limit)

        if result.get("skipped"):
            log(f"スキップ: {result.get('reason', 'unknown')}", "WARNING")
            sys.exit(0)

        # JSON保存
        save_json(result)

        # Obsidianレポート
        save_obsidian_report(result)

        log("=" * 60)
        log(f"完了 - {result['exported']}件エクスポート")
        log("=" * 60)

    except Exception as e:
        log(f"致命的エラー: {e}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
