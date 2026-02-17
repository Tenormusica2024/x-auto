"""
trend_detector.py - X上のAIトレンド検出 + 下書き生成

毎朝のfrontier intelligenceレポートからキーワードを動的抽出し、
X Search APIで各トピックの盛り上がり度を計測。
ホットトピックを検出したら下書きテンプレートを生成し、Discord通知する。

使い方:
  python -X utf8 trend_detector.py              # 通常実行
  python -X utf8 trend_detector.py --threshold 30  # 閾値を下げて感度UP
  python -X utf8 trend_detector.py --dry-run       # API呼び出しなしでキーワード抽出のみ

コスト: トピック10件 x 検索 = ~$0.50（約75円）
"""

import sys
import re
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent))
from x_client import (
    get_x_client, notify_discord, save_to_obsidian,
    today_str, now_str,
    OBSIDIAN_TRENDS, DRAFTS_DIR, FRONTIER_REPORT, DATA_DIR,
    MY_USER_IDS,
)


def extract_topics_from_frontier() -> list[dict]:
    """
    AI_Frontier_Capabilities_Master.mdの「本日のハイライト」セクションから
    トピック名と要約を動的抽出する。

    抽出対象: 各行の **太字** 部分（コロン前まで）
    例: "- **Claude Sonnet 5 "Fennec" 正式リリース**: 説明..." → topic="Claude Sonnet 5", summary="説明..."
    """
    if not FRONTIER_REPORT.exists():
        print(f"[ERROR] frontier report が見つかりません: {FRONTIER_REPORT}")
        return []

    content = FRONTIER_REPORT.read_text(encoding="utf-8")

    # 「本日のハイライト」セクションを抽出
    highlight_match = re.search(
        r"### 本日のハイライト.*?\n(.*?)(?=\n---|\n### \d+\.)",
        content,
        re.DOTALL,
    )
    if not highlight_match:
        print("[WARN] 「本日のハイライト」セクションが見つかりません")
        return []

    highlight_text = highlight_match.group(1)

    topics = []
    # 各行から **太字**: 要約 のパターンを抽出
    for line in highlight_text.strip().split("\n"):
        # "- **Topic Name**: summary text" 形式にマッチ
        match = re.match(r"- \*\*(.+?)\*\*:\s*(.+)", line.strip())
        if match:
            raw_topic = match.group(1)
            summary = match.group(2).strip()

            # トピック名からX検索用のクエリに変換
            # 引用符や補足情報を除去して固有名詞を抽出
            search_query = _clean_topic_for_search(raw_topic)

            if search_query:
                topics.append({
                    "raw": raw_topic,
                    "query": search_query,
                    "summary": summary[:100],
                })

    print(f"[OK] {len(topics)}件のトピックを抽出")
    return topics


def _clean_topic_for_search(raw_topic: str) -> str:
    """
    トピック名をX Search API用のクエリに変換。
    「Claude Sonnet 5 "Fennec" 正式リリース」→ 「Claude Sonnet 5」
    「GPT-5.2 + GPT-5.3-Codex」→ 「GPT-5.2」
    「Anthropic $20B調達・$350B評価 + IPO準備」→ 「Anthropic IPO」
    """
    # 日本語の説明部分を除去（「正式リリース」「調達」等）
    topic = re.sub(r'[""「」]', '', raw_topic)

    # 「+」以降は別トピックなので最初の部分だけ使う
    topic = topic.split("+")[0].strip()
    # 「・」も同様
    topic = topic.split("・")[0].strip()

    # 日本語の動詞・形容詞を除去してキーワードだけ残す
    # 英数字・ハイフン・ドットを含む単語を抽出
    words = re.findall(r'[A-Za-z0-9][\w\-\.]*[A-Za-z0-9]|[A-Za-z0-9]', topic)

    if words:
        return " ".join(words[:3])  # 最大3語で検索

    # 英語のキーワードが見つからない場合は元のテキストの最初の部分を使用
    # 日本語のみのトピック（稀なケース）
    short = topic.split(" ")[0][:20]
    return short if len(short) >= 2 else ""


def search_x_for_topic(client, query: str, max_results: int = 3) -> dict:
    """
    X Search APIでトピックの盛り上がりを計測。
    直近のツイートを検索し、ヒートスコアを計算する。
    author_id情報も抽出してキーパーソン分析に活用。
    """
    search_query = f"{query} lang:ja -is:retweet"

    try:
        tweets = client.search_recent_tweets(
            query=search_query,
            max_results=max_results,
            tweet_fields=["created_at", "public_metrics", "author_id", "text"],
            expansions=["author_id"],
            user_fields=["username", "name"],
        )
    except Exception as e:
        print(f"[WARN] 検索失敗 ({query}): {e}")
        return {"tweet_count": 0, "heat_score": 0, "avg_likes": 0, "avg_retweets": 0, "top_tweets": [], "authors": []}

    if not tweets.data:
        return {"tweet_count": 0, "heat_score": 0, "avg_likes": 0, "avg_retweets": 0, "top_tweets": [], "authors": []}

    # author_id -> username のマッピングを構築
    user_map = {}
    if tweets.includes and "users" in tweets.includes:
        for u in tweets.includes["users"]:
            user_map[str(u.id)] = {"username": u.username, "name": u.name}

    tweet_count = len(tweets.data)
    total_likes = sum(t.public_metrics.get("like_count", 0) for t in tweets.data)
    total_rts = sum(t.public_metrics.get("retweet_count", 0) for t in tweets.data)
    avg_likes = total_likes / tweet_count
    avg_rts = total_rts / tweet_count

    # ヒートスコア: ツイート数 x (1 + 平均いいね x 0.5 + 平均RT x 1.0)
    heat_score = tweet_count * (1 + avg_likes * 0.5 + avg_rts * 1.0)

    # 上位ツイートを保存（いいね順）+ author_id抽出
    sorted_tweets = sorted(
        tweets.data,
        key=lambda t: t.public_metrics.get("like_count", 0),
        reverse=True,
    )
    top_tweets = []
    # author_idごとの合計エンゲージメントを集計
    author_engagement = {}
    for t in tweets.data:
        aid = str(t.author_id)
        likes = t.public_metrics.get("like_count", 0)
        rts = t.public_metrics.get("retweet_count", 0)
        if aid not in author_engagement:
            uinfo = user_map.get(aid, {})
            author_engagement[aid] = {
                "username": uinfo.get("username", ""),
                "name": uinfo.get("name", ""),
                "tweet_count": 0, "total_likes": 0, "total_rts": 0,
            }
        author_engagement[aid]["tweet_count"] += 1
        author_engagement[aid]["total_likes"] += likes
        author_engagement[aid]["total_rts"] += rts

    for t in sorted_tweets[:3]:
        text = t.text.replace("\n", " ")[:80]
        aid_tw = str(t.author_id)
        uinfo_tw = user_map.get(aid_tw, {})
        top_tweets.append({
            "text": text,
            "likes": t.public_metrics.get("like_count", 0),
            "retweets": t.public_metrics.get("retweet_count", 0),
            "author_id": aid_tw,
            "username": uinfo_tw.get("username", ""),
        })

    # エンゲージメントが高い順にauthor情報をリスト化
    authors = sorted(
        [
            {"author_id": aid, **data}
            for aid, data in author_engagement.items()
        ],
        key=lambda a: a["total_likes"] + a["total_rts"],
        reverse=True,
    )

    return {
        "tweet_count": tweet_count,
        "heat_score": round(heat_score, 1),
        "avg_likes": round(avg_likes, 1),
        "avg_retweets": round(avg_rts, 1),
        "top_tweets": top_tweets,
        "authors": authors,
    }


def _format_top_tweets(top_tweets: list[dict]) -> str:
    """上位ツイートをMarkdownリストに変換"""
    lines = []
    for i, t in enumerate(top_tweets, 1):
        lines.append(f'{i}. "{t["text"]}" (like: {t["likes"]}, RT: {t["retweets"]})')
    return "\n".join(lines) if lines else "（データなし）"


def generate_draft(topic: dict, x_data: dict) -> str:
    """ホットトレンドの下書きテンプレートを生成"""
    date = today_str()
    return f"""# [トレンド検出] {topic['raw']}（下書き）

作成日: {date}
検出元: trend_detector（自動生成）

## トレンドデータ
- X上の言及数: {x_data['tweet_count']}件（直近）
- 平均いいね: {x_data['avg_likes']}
- 平均RT: {x_data['avg_retweets']}
- ヒートスコア: {x_data['heat_score']}

## 参考ツイート（上位3件）
{_format_top_tweets(x_data['top_tweets'])}

## ネタメモ
- frontier intelligence要約: {topic['summary']}
- 検索クエリ: {topic['query']}
- 切り口候補: 速報 / 比較 / 実体験 / 解説

---
**注意**: この下書きはトレンド検出の素材です。ツイート文はgenerate-tweetスキルで別途生成してください。
"""


def generate_trend_report(results: list[dict], top_persons: list[dict] | None = None) -> str:
    """Obsidian用のトレンドレポートを生成"""
    date = today_str()

    hot = [r for r in results if r["x_data"]["heat_score"] > 0]
    hot_sorted = sorted(hot, key=lambda r: r["x_data"]["heat_score"], reverse=True)

    rows = []
    for i, r in enumerate(hot_sorted, 1):
        rows.append(
            f"| {i} | {r['topic']['raw'][:40]} | {r['topic']['query']} | "
            f"{r['x_data']['tweet_count']} | {r['x_data']['avg_likes']} | "
            f"{r['x_data']['heat_score']} |"
        )
    table = "\n".join(rows) if rows else "| - | データなし | - | - | - | - |"

    report = f"""# X トレンドレポート - {date}

生成時刻: {now_str()}
ソース: AI_Frontier_Capabilities_Master.md

## トレンドランキング

| 順位 | トピック | 検索クエリ | 言及数 | 平均like | heat |
|------|---------|-----------|--------|---------|------|
{table}

## 検出サマリー
- 分析トピック数: {len(results)}
- 言及あり: {len(hot)}件
- 言及なし: {len(results) - len(hot)}件
"""

    # ホットトピックの詳細
    for r in hot_sorted[:5]:
        t = r["topic"]
        x = r["x_data"]
        report += f"\n### {t['raw']}\n"
        report += f"- クエリ: `{t['query']}`\n"
        report += f"- heat: {x['heat_score']} | 言及: {x['tweet_count']}件 | avg like: {x['avg_likes']}\n"
        report += f"- 要約: {t['summary']}\n"
        if x["top_tweets"]:
            report += "- 上位ツイート:\n"
            for i, tw in enumerate(x["top_tweets"], 1):
                report += f'  {i}. "{tw["text"]}" (like:{tw["likes"]})\n'
        # トピック別の注目発信者（Xプロフィールリンク付き）
        authors = x.get("authors", [])
        if authors:
            top_author = authors[0]
            author_label = (
                f"[@{top_author['username']}](https://x.com/{top_author['username']})"
                if top_author.get('username')
                else f"id={top_author['author_id']}"
            )
            report += f"- 注目発信者: {author_label} "
            report += f"(like:{top_author['total_likes']}, RT:{top_author['total_rts']})\n"

    # キーパーソンセクション（蓄積データ）
    if top_persons:
        report += "\n## キーパーソン（累積エンゲージメント TOP5）\n\n"
        report += "| 順位 | アカウント | 出現回数 | 累積like | 累積RT | 関連トピック |\n"
        report += "|------|-----------|----------|---------|--------|-------------|\n"
        for i, p in enumerate(top_persons, 1):
            top_topics = sorted(p["topics"].items(), key=lambda x: x[1], reverse=True)[:3]
            topics_str = ", ".join(f"{t[0]}({t[1]})" for t in top_topics)
            # Xプロフィールリンク付きアカウント表示
            acct = (
                f"[@{p['username']}](https://x.com/{p['username']})"
                if p.get('username')
                else p['author_id']
            )
            report += (
                f"| {i} | {acct} | {p['total_appearances']} | "
                f"{p['total_likes']} | {p['total_rts']} | {topics_str} |\n"
            )
        report += "\n"

    return report


# --- キーパーソン蓄積（Feature 3: 競合監視の副産物方式） ---

def load_key_persons() -> dict:
    """キーパーソンJSONを読み込み"""
    path = DATA_DIR / "key_persons.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"persons": {}, "last_updated": ""}


def save_key_persons(data: dict):
    """キーパーソンJSONを保存"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "key_persons.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] キーパーソンデータ保存: {path}")


def _gc_key_persons(kp: dict):
    """
    低エンゲージメントの古いエントリを削除してJSONの肥大化を防ぐ。
    条件: first_seenが30日以上前 & 出現1回 & like 0 & RT 0
    """
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    to_delete = []
    for aid, p in kp["persons"].items():
        first_seen = p.get("first_seen", "")
        if (
            first_seen
            and first_seen < cutoff
            and p.get("total_appearances", 0) <= 1
            and p.get("total_likes", 0) == 0
            and p.get("total_rts", 0) == 0
        ):
            to_delete.append(aid)

    for aid in to_delete:
        del kp["persons"][aid]

    if to_delete:
        print(f"[GC] {len(to_delete)}件の低エンゲージメントエントリを削除")


def update_key_persons(results: list[dict]):
    """
    検索結果からauthor情報を蓄積。
    各author_idについて、どのトピックで何回登場したか・合計エンゲージメントを記録。
    """
    kp = load_key_persons()

    for r in results:
        topic_query = r["topic"]["query"]
        for author in r["x_data"].get("authors", []):
            aid = author["author_id"]

            # 自分のアカウントはキーパーソンから除外
            if aid in MY_USER_IDS:
                continue

            if aid not in kp["persons"]:
                kp["persons"][aid] = {
                    "username": author.get("username", ""),
                    "name": author.get("name", ""),
                    "first_seen": today_str(),
                    "topics": {},
                    "total_appearances": 0,
                    "total_likes": 0,
                    "total_rts": 0,
                }

            person = kp["persons"][aid]
            # usernameが取れたら常に最新値で上書き（表示名変更に追従）
            if author.get("username"):
                person["username"] = author["username"]
                person["name"] = author.get("name", "")
            person["total_appearances"] += author["tweet_count"]
            person["total_likes"] += author["total_likes"]
            person["total_rts"] += author["total_rts"]

            # トピック別の出現回数
            if topic_query not in person["topics"]:
                person["topics"][topic_query] = 0
            person["topics"][topic_query] += author["tweet_count"]

    # ガベージコレクション: 古い低エンゲージメントエントリを削除
    _gc_key_persons(kp)

    kp["last_updated"] = now_str()
    save_key_persons(kp)

    # 統計を出力
    active_persons = [
        (aid, p) for aid, p in kp["persons"].items()
        if p["total_appearances"] >= 2
    ]
    print(f"[OK] キーパーソン: {len(kp['persons'])}人記録（2回以上登場: {len(active_persons)}人）")

    return kp


def get_top_key_persons(kp: dict, limit: int = 5) -> list[dict]:
    """エンゲージメント合計が高いキーパーソンTOP N を返す"""
    ranked = sorted(
        [
            {"author_id": aid, **data}
            for aid, data in kp["persons"].items()
        ],
        key=lambda p: p["total_likes"] + p["total_rts"],
        reverse=True,
    )
    return ranked[:limit]


def resolve_unknown_usernames(client, kp: dict, persons: list[dict]) -> list[dict]:
    """
    TOP Nのキーパーソンでusername未解決のものをAPI経由で解決する。
    解決したらkey_persons.jsonにも反映して永続化する。
    コスト: 1件あたり $0.005
    """
    resolved_count = 0
    for p in persons:
        if p.get("username"):
            continue
        aid = p["author_id"]
        try:
            user = client.get_user(id=int(aid), user_fields=["username", "name"])
            if user.data:
                p["username"] = user.data.username
                p["name"] = user.data.name
                # 永続データにも反映
                if aid in kp["persons"]:
                    kp["persons"][aid]["username"] = user.data.username
                    kp["persons"][aid]["name"] = user.data.name
                resolved_count += 1
                print(f"  [RESOLVE] {aid} → @{user.data.username}")
        except Exception as e:
            print(f"  [WARN] username解決失敗 ({aid}): {e}")

    if resolved_count > 0:
        save_key_persons(kp)
        print(f"[OK] {resolved_count}件のusernameを解決")

    return persons


def main():
    parser = argparse.ArgumentParser(description="X トレンド検出 + 下書き生成")
    parser.add_argument("--threshold", type=float, default=50, help="ホットトレンド判定のヒートスコア閾値（デフォルト: 50）")
    parser.add_argument("--dry-run", action="store_true", help="API呼び出しなしでキーワード抽出のみ")
    args = parser.parse_args()

    print(f"=== X トレンド検出 ===")
    print(f"閾値: heat_score > {args.threshold}")
    print()

    # 1. frontier intelligenceからトピック抽出
    topics = extract_topics_from_frontier()
    if not topics:
        print("[ERROR] トピック抽出失敗")
        sys.exit(1)

    print("\n抽出トピック:")
    for t in topics:
        print(f"  - {t['raw'][:50]} → query: \"{t['query']}\"")

    if args.dry_run:
        print("\n[DRY-RUN] API呼び出しスキップ")
        return

    # 2. 各トピックのX上での盛り上がりを検索
    print(f"\n推定コスト: ${len(topics) * 0.005 * 10:.3f}")
    print()

    client = get_x_client()
    results = []

    for topic in topics:
        print(f"検索中: {topic['query']}...", end=" ")
        x_data = search_x_for_topic(client, topic["query"])
        print(f"→ {x_data['tweet_count']}件, heat: {x_data['heat_score']}")
        results.append({"topic": topic, "x_data": x_data})

    # 3. ホットトレンド判定
    hot_topics = [r for r in results if r["x_data"]["heat_score"] >= args.threshold]
    hot_topics.sort(key=lambda r: r["x_data"]["heat_score"], reverse=True)

    print(f"\n=== ホットトレンド: {len(hot_topics)}件 ===")

    # 4. 下書き生成（ホットトレンドのみ）
    draft_paths = []
    for r in hot_topics:
        draft_content = generate_draft(r["topic"], r["x_data"])
        # ファイル名: trend-YYYY-MM-DD-query.md（スペースをハイフンに変換）
        safe_name = r["topic"]["query"].replace(" ", "-").lower()[:30]
        draft_filename = f"trend-{today_str()}-{safe_name}.md"
        draft_path = DRAFTS_DIR / draft_filename
        DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(draft_content, encoding="utf-8")
        draft_paths.append(draft_path)
        print(f"  下書き生成: {draft_path.name}")

    # 5. キーパーソンデータ蓄積（Feature 3: 副産物方式）
    kp = update_key_persons(results)
    top_persons = get_top_key_persons(kp)

    # 5.1. username未解決のキーパーソンをAPI経由で解決
    top_persons = resolve_unknown_usernames(client, kp, top_persons)

    # 6. Obsidianにトレンドレポート保存
    report = generate_trend_report(results, top_persons)
    save_to_obsidian(OBSIDIAN_TRENDS, f"trends-{today_str()}.md", report)

    # 7. Discord通知（キーパーソン情報付き）
    discord_lines = [f"**x-auto Trend Detector** ({today_str()})\n"]

    if hot_topics:
        discord_lines.append(f"ホットトピック {len(hot_topics)}件検出:\n")
        for i, r in enumerate(hot_topics[:5], 1):
            discord_lines.append(
                f"{i}. {r['topic']['raw'][:40]} "
                f"(heat: {r['x_data']['heat_score']}, {r['x_data']['tweet_count']}件言及)"
            )
        discord_lines.append(f"\n下書き保存先: x-auto/drafts/")
    else:
        discord_lines.append(
            f"{len(results)}トピック分析完了。ホットトレンドなし（閾値: {args.threshold}）"
        )

    # キーパーソンTOP3をDiscordにも表示
    if top_persons:
        discord_lines.append("\n注目キーパーソン:")
        for i, p in enumerate(top_persons[:3], 1):
            acct = f"@{p['username']}" if p.get('username') else p['author_id']
            discord_lines.append(
                f"  {i}. {acct} (like:{p['total_likes']}, RT:{p['total_rts']}, "
                f"出現:{p['total_appearances']}回)"
            )

    notify_discord("\n".join(discord_lines))

    print(f"\n=== 完了 ===")


if __name__ == "__main__":
    main()
