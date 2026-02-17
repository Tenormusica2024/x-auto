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


def main():
    days, output_mode = parse_args()

    if not DB_PATH.exists():
        print(json.dumps({"error": f"DB not found: {DB_PATH}"}))
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    result = extract_discourse_signals(conn, days)
    result["fetched_at"] = datetime.now().isoformat()
    result["db_path"] = str(DB_PATH)
    conn.close()

    output_json = json.dumps(result, ensure_ascii=False, indent=2)

    if output_mode == "file":
        out_path = OUTPUT_DIR / "buzz-db-discourse-signals.json"
        out_path.write_text(output_json, encoding="utf-8")
        print(f"Saved to {out_path}", file=sys.stderr)

    print(output_json)


if __name__ == "__main__":
    main()
