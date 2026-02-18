"""
ai-buzz-extractor DB から discourse-freshness 更新用のデータを抽出する。

用途: discourse-freshness-updater から呼び出し、
      直近のバズツイートからAIコーディング議論の動向を把握する。

使い方:
  python -X utf8 fetch_buzz_db.py                    # 直近7日のサマリー
  python -X utf8 fetch_buzz_db.py --days 14           # 期間指定
  python -X utf8 fetch_buzz_db.py --output file       # ファイル出力

出力: JSON形式（カテゴリ別上位ツイート + キーワード頻度 + 議論トレンド）
"""

import sqlite3
import json
import sys
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

DB_PATH = Path(r"C:\Users\Tenormusica\Documents\ai-buzz-extractor\ai_buzz.db")
BUZZ_EVALS_JSON = Path(__file__).parent / "data" / "buzz_content_evaluations.json"
OUTPUT_DIR = Path(__file__).parent / "data"

# discourse-freshness に関連するカテゴリ
RELEVANT_CATEGORIES = [
    "AI系ツール",
    "AIナレッジ",
    "AI体験談・雑談",
    "AIモデル",
    "AIニュース",
    "AI批判・規制推進",
]

# AIコーディング議論の検出キーワード（discourse-freshness.mdの各セクション対応）
DISCOURSE_KEYWORDS = {
    "code_review": [
        "review", "レビュー", "agent team", "PR agent", "品質", "quality",
        "code review", "並列レビュー", "multi-agent",
    ],
    "vibe_coding": [
        "vibe coding", "CLAUDE.md", "rules file", "context window",
        "コンテキスト", "ドキュメント駆動", "document-first", "cursor rules",
        "定義書", "記憶ファイル",
    ],
    "human_role": [
        "エンジニア不要", "replacing engineer", "developer role",
        "設計力", "career", "キャリア", "不要論", "一人で",
        "solo developer", "人間の役割", "AI時代",
    ],
    "ai_writing": [
        "文章力", "writing quality", "creative", "創作",
        "小説", "novel", "human level", "人間超え",
    ],
    "ai_agent": [
        "agent", "エージェント", "MCP", "agentic", "orchestrat",
        "tool use", "autonomous", "自律", "マルチエージェント",
    ],
}


def parse_args():
    days = 7
    output_mode = "stdout"
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--days" and i + 1 < len(args):
            days = int(args[i + 1])
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output_mode = args[i + 1]
            i += 2
        else:
            i += 1
    return days, output_mode


def keyword_match(text, keywords):
    """テキストにキーワードが含まれるかチェック"""
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            return True
    return False


def extract_discourse_signals(conn, days):
    """discourse-freshness関連のシグナルを抽出"""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    cursor = conn.cursor()

    # カテゴリ別集計
    cursor.execute("""
        SELECT category, COUNT(*) as cnt, AVG(likes) as avg_likes
        FROM tweets
        WHERE created_at > ? AND category IN ({})
        GROUP BY category ORDER BY cnt DESC
    """.format(",".join("?" * len(RELEVANT_CATEGORIES))),
        [cutoff] + RELEVANT_CATEGORIES
    )
    category_stats = [
        {"category": r[0], "count": r[1], "avg_likes": round(r[2], 1)}
        for r in cursor.fetchall()
    ]

    # 全関連ツイート取得
    cursor.execute("""
        SELECT text, username, likes, category, created_at, url
        FROM tweets
        WHERE created_at > ? AND category IN ({})
        ORDER BY likes DESC
    """.format(",".join("?" * len(RELEVANT_CATEGORIES))),
        [cutoff] + RELEVANT_CATEGORIES
    )
    all_tweets = cursor.fetchall()

    # discourse領域別にマッチするツイートを分類
    discourse_signals = {}
    for area, keywords in DISCOURSE_KEYWORDS.items():
        matched = []
        for t in all_tweets:
            text = t[0]
            if keyword_match(text, keywords):
                matched.append({
                    "text": text[:200],
                    "username": t[1],
                    "likes": t[2],
                    "category": t[3],
                    "created_at": t[4],
                    "url": t[5],
                })
        # 上位10件に絞る
        discourse_signals[area] = {
            "total_matches": len(matched),
            "top_tweets": matched[:10],
        }

    # 全体のエンゲージメント上位（カテゴリ横断）
    top_overall = [
        {
            "text": t[0][:200],
            "username": t[1],
            "likes": t[2],
            "category": t[3],
            "created_at": t[4],
            "url": t[5],
        }
        for t in all_tweets[:20]
    ]

    return {
        "period_days": days,
        "cutoff_date": cutoff[:10],
        "total_relevant_tweets": len(all_tweets),
        "category_stats": category_stats,
        "discourse_signals": discourse_signals,
        "top_engagement": top_overall,
    }


def extract_buzz_eval_signals(days):
    """
    buzz_content_evaluations.json からdiscourse領域別の定量シグナルを抽出する。
    LLM分類済みの7軸データ（content_type, virality_factor, originality等）を活用して、
    DBのキーワードマッチより高精度な傾向を提供する。
    """
    if not BUZZ_EVALS_JSON.exists():
        return None

    try:
        raw = json.loads(BUZZ_EVALS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None

    evaluations = raw.get("evaluations", {})
    if not evaluations:
        return None

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # discourse領域別にツイートを分類
    discourse_signals = {area: [] for area in DISCOURSE_KEYWORDS}
    # content_type別・virality_factor別の集計
    ct_stats = Counter()
    vf_stats = Counter()
    total = 0

    for eval_data in evaluations.values():
        if eval_data.get("evaluated_date", "") < cutoff:
            continue

        total += 1
        text = eval_data.get("tweet_data", {}).get("text", "")
        ct = eval_data.get("content_type", "unknown")
        vf = eval_data.get("virality_factor", "unknown")
        orig = eval_data.get("originality", 0)
        acv = eval_data.get("ai_citation_value", 0)
        eng = eval_data.get("tweet_data", {}).get("engagement_score", 0)

        ct_stats[ct] += 1
        vf_stats[vf] += 1

        # discourse領域へのマッピング（キーワードマッチ）
        for area, keywords in DISCOURSE_KEYWORDS.items():
            if keyword_match(text, keywords):
                discourse_signals[area].append({
                    "text": text[:200],
                    "username": eval_data.get("tweet_data", {}).get("username", ""),
                    "engagement_score": eng,
                    "content_type": ct,
                    "originality": orig,
                    "ai_citation_value": acv,
                    "virality_factor": vf,
                })

    if total == 0:
        return None

    # 各領域の集計
    result = {}
    for area, tweets in discourse_signals.items():
        # エンゲージメント順ソート
        tweets.sort(key=lambda x: x["engagement_score"], reverse=True)
        if tweets:
            avg_orig = sum(t["originality"] for t in tweets) / len(tweets)
            avg_acv = sum(t["ai_citation_value"] for t in tweets) / len(tweets)
            avg_eng = sum(t["engagement_score"] for t in tweets) / len(tweets)
        else:
            avg_orig = avg_acv = avg_eng = 0

        result[area] = {
            "total_matches": len(tweets),
            "avg_originality": round(avg_orig, 1),
            "avg_ai_citation_value": round(avg_acv, 1),
            "avg_engagement": round(avg_eng),
            # 高シグナルツイート: ai_citation_value >= 3 かつ engagement >= 2000
            "high_signal_count": len([
                t for t in tweets
                if t["ai_citation_value"] >= 3 and t["engagement_score"] >= 2000
            ]),
            "top_tweets": tweets[:5],
        }

    return {
        "period_days": days,
        "total_evaluated": total,
        "content_type_distribution": dict(ct_stats.most_common()),
        "virality_factor_distribution": dict(vf_stats.most_common()),
        "discourse_signals": result,
    }


def main():
    days, output_mode = parse_args()

    result = {"fetched_at": datetime.now().isoformat()}

    # ソース1: ai-buzz-extractor DB
    if DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH))
        db_signals = extract_discourse_signals(conn, days)
        db_signals["db_path"] = str(DB_PATH)
        conn.close()
        result["db_signals"] = db_signals
    else:
        print(f"DB not found: {DB_PATH}", file=sys.stderr)
        result["db_signals"] = None

    # ソース2: buzz_content_evaluations.json（LLM分類済みバズデータ）
    buzz_eval_signals = extract_buzz_eval_signals(days)
    if buzz_eval_signals:
        result["buzz_eval_signals"] = buzz_eval_signals
        print(
            f"Buzz evals: {buzz_eval_signals['total_evaluated']} tweets (last {days}d)",
            file=sys.stderr,
        )
    else:
        result["buzz_eval_signals"] = None

    output_json = json.dumps(result, ensure_ascii=False, indent=2)

    if output_mode == "file":
        out_path = OUTPUT_DIR / "buzz-db-discourse-signals.json"
        out_path.write_text(output_json, encoding="utf-8")
        print(f"Saved to {out_path}", file=sys.stderr)

    print(output_json)


if __name__ == "__main__":
    main()
