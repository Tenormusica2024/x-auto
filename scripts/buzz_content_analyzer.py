"""
buzz_content_analyzer.py - 他者バズツイート多次元分析パイプライン

毎日収集されるバズツイート（buzz-tweets-latest.json）をGroq LLMで多次元分類し、
「他者のどういうツイートがウケるか」のパターンを抽出する。
分析結果は content-strategy-ref.md の「ソースB」セクションに反映。

評価軸（7つ - content_evaluator.pyの6軸 + virality_factor）:
  - content_type: ai_news / bip / opinion / how-to / quote_rt / engagement / humor / data_insight / other
  - originality: 独自性（1-5）
  - media_contribution: 画像寄与度
  - news_saturation: ニュース飽和度（ai_newsのみ）
  - bip_authenticity: BIP真正性（bipのみ）
  - ai_citation_value: AI引用価値（1-5）
  - virality_factor: バズ要因（なぜウケたか）

使い方:
  python -X utf8 buzz_content_analyzer.py            # 通常実行
  python -X utf8 buzz_content_analyzer.py --dry-run   # 分類のみ（保存なし）
  python -X utf8 buzz_content_analyzer.py --force      # 本日分を全て再評価
  python -X utf8 buzz_content_analyzer.py --days 7     # 蓄積分析の対象日数

コスト: $0.00（Groq無料枠）
"""

import sys
import os
import json
import asyncio
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv

# GROQ_API_KEYを.envから読み込み
load_dotenv(Path(r"C:\Users\Tenormusica\x-auto-posting\.env"))
load_dotenv(Path(r"C:\Users\Tenormusica\Documents\ai-buzz-extractor-dev\.env"), override=False)
load_dotenv(Path(r"C:\Users\Tenormusica\Documents\ai-buzz-extractor\.env"), override=False)

sys.path.insert(0, str(Path(__file__).parent))
from x_client import (
    notify_discord, save_to_obsidian, today_str, now_str,
    DATA_DIR, OBSIDIAN_BASE,
)

logger = logging.getLogger(__name__)

# --- 定数 ---

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
OBSIDIAN_EVAL = OBSIDIAN_BASE / "evaluations"
BUZZ_EVAL_PATH = DATA_DIR / "buzz_content_evaluations.json"
BUZZ_TWEETS_PATH = DATA_DIR / "buzz-tweets-latest.json"
KEY_PERSONS_PATH = DATA_DIR / "key_persons.json"
STRATEGY_REF_PATH = Path(r"C:\Users\Tenormusica\x-auto\common\content-strategy-ref.md")

BATCH_SIZE = 5
BATCH_DELAY = 5.0
BACKOFF_SCHEDULE = [5, 15, 30, 60]
RETENTION_DAYS = 30

# --- LLMプロンプト（他者バズツイート成功要因分析用） ---

BUZZ_CLASSIFICATION_PROMPT = """\
あなたはX(Twitter)バズツイートの成功要因分析の専門家です。
以下のツイートはいずれも高エンゲージメント（500いいね以上）を獲得したツイートです。
各ツイートを多次元で評価し、「なぜバズったか」の要因をJSON配列で返してください。

## 評価軸の定義

### content_type（コンテンツ種別）
- "ai_news": AIやテクノロジーのニュース・速報・新サービス紹介
- "bip": Build in Public（開発過程・作業ログ・進捗報告・個人開発）
- "opinion": 意見・考察・ポエム・業界への見解
- "how-to": 使い方・ハウツー・Tips・具体的手順の共有
- "quote_rt": 他人のツイートへのコメント・引用
- "engagement": 挨拶・お礼・日常会話・交流目的
- "humor": ネタ・ジョーク・おもしろ体験・皮肉
- "data_insight": 独自データ・ベンチマーク・数値分析
- "other": 上記に該当しないもの

### originality（独自性 1-5）
1: 他人の情報をほぼそのまま転載・翻訳しただけ
2: 既知の情報に最小限のコメントを追加
3: 既知の情報に自分なりの分析・視点を追加
4: 独自の体験・データ・洞察が主体
5: 完全にオリジナルな知見・発見・体験

### media_contribution（画像の寄与度）
- "essential": 画像がコンテンツの本体（画像なしでは意味が通じない）
- "enhancing": 画像がテキストを補強（注目度アップ）
- "irrelevant": 画像とテキストの関連が薄い（アイキャッチ目的のみ）
- "none": 画像なし

### news_saturation（ニュース飽和度 - ai_newsの場合のみ）
- "first_mover": 日本語圏で最初期に取り上げた
- "early": 早めだが既に何人かが言及済み
- "mainstream": 多くのアカウントが既に取り上げている
- "late": 話題が一巡した後
- "n/a": ニュース系ではない

### bip_authenticity（BIPの真正性 1-5 - bipの場合のみ）
1: 一般論・抽象的な「やってます」報告
2: 表面的（ツール名を挙げただけ等）
3: 具体的な作業内容があるが数字・成果がない
4: 具体的な体験・苦労・発見が含まれる
5: 数字・スクショ・具体的成果と率直な所感がある

### ai_citation_value（AI引用価値 1-5）
AI検索がこのツイートを一次ソースとして引用する可能性（5項目中の該当数）:
- 独自データや具体的な数値を含む
- 再現可能な具体手順を含む
- 個人の実体験に基づく知見
- 他で見つからない一次情報
- 検証可能な主張（リンク・ソース付き）

### virality_factor（バズ要因 - このツイートが高エンゲージメントを獲得した主要因を1つ選択）
- "controversy": 議論・賛否を呼ぶ内容
- "relatability": 共感・「わかる」を誘発する内容
- "information_value": 有用な情報・知見を含む
- "entertainment": 面白い・ネタとして楽しめる
- "authority": 発信者の権威性・専門性による信頼
- "timeliness": タイミングの良さ（旬のトピックに即応）
- "emotional_trigger": 感情を揺さぶる内容（不安・怒り・感動等）

## ツイート一覧

{tweets_block}

## 出力形式
JSON配列で返してください。各要素に tweet_index（0始まり）を含めてください。
bipではないツイートの bip_authenticity は null にしてください。
ai_newsではないツイートの news_saturation は "n/a" にしてください。

```json
[
  {{
    "tweet_index": 0,
    "content_type": "opinion",
    "originality": 4,
    "media_contribution": "none",
    "news_saturation": "n/a",
    "bip_authenticity": null,
    "ai_citation_value": 2,
    "virality_factor": "relatability"
  }}
]
```"""


# --- データI/O ---

def load_buzz_tweets() -> dict:
    """buzz-tweets-latest.json を読み込み。鮮度チェック付き"""
    if not BUZZ_TWEETS_PATH.exists():
        return {"tweets": []}
    data = json.loads(BUZZ_TWEETS_PATH.read_text(encoding="utf-8"))
    # 24時間以内のデータのみ有効
    gen_at = data.get("generated_at", "")
    if gen_at:
        try:
            gen_time = datetime.fromisoformat(gen_at)
            if (datetime.now(gen_time.tzinfo) - gen_time).total_seconds() > 86400:
                print(f"[WARN] buzz-tweets-latest.json は24時間以上前のデータ ({gen_at})")
        except (ValueError, TypeError):
            pass
    return data


def load_key_persons() -> dict:
    """key_persons.json を読み込み"""
    if not KEY_PERSONS_PATH.exists():
        return {"persons": {}}
    return json.loads(KEY_PERSONS_PATH.read_text(encoding="utf-8"))


def load_buzz_evaluations() -> dict:
    """蓄積データ読み込み"""
    if BUZZ_EVAL_PATH.exists():
        return json.loads(BUZZ_EVAL_PATH.read_text(encoding="utf-8"))
    return {
        "metadata": {
            "last_updated": "",
            "total_evaluated": 0,
            "date_range": {"oldest": "", "newest": ""},
            "retention_days": RETENTION_DAYS,
        },
        "evaluations": {},
        "daily_index": {},
    }


def save_buzz_evaluations(data: dict):
    """蓄積データ保存"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BUZZ_EVAL_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] バズ評価データ保存: {BUZZ_EVAL_PATH}")


# --- Groq LLM 分類 ---

async def classify_buzz_tweets(
    tweets: list[dict], api_key: str
) -> list[dict]:
    """バズツイートをGroq LLMでバッチ分類"""
    results = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        for batch_start in range(0, len(tweets), BATCH_SIZE):
            batch = tweets[batch_start : batch_start + BATCH_SIZE]
            batch_results = await _classify_buzz_batch(client, batch, api_key)
            results.extend(batch_results)

            if batch_start + BATCH_SIZE < len(tweets):
                print(f"  [WAIT] {BATCH_DELAY}秒待機（rate limit対策）...")
                await asyncio.sleep(BATCH_DELAY)

            print(f"  [PROGRESS] {min(batch_start + BATCH_SIZE, len(tweets))}/{len(tweets)} 完了")

    return results


async def _classify_buzz_batch(
    client: httpx.AsyncClient,
    tweets: list[dict],
    api_key: str,
) -> list[dict]:
    """1バッチ（最大5ツイート）をGroqで分類"""
    # プロンプト組み立て（エンゲージメント指標を含む）
    tweets_block = ""
    for i, t in enumerate(tweets):
        # buzz-tweets-latest.jsonにはhas_mediaがないのでテキストからメディア推定
        tweets_block += (
            f"### ツイート {i}\n"
            f"いいね:{t.get('likes', 0)} / RT:{t.get('retweets', 0)} / "
            f"引用:{t.get('quotes', 0)} / リプライ:{t.get('replies', 0)}\n"
            f"{t.get('text', '')}\n\n"
        )

    prompt = BUZZ_CLASSIFICATION_PROMPT.format(tweets_block=tweets_block)

    for attempt in range(4):
        try:
            response = await client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 2000,
                },
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()

            # JSON抽出
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            parsed = json.loads(content)

            # tweet_id・evaluated_atを付与
            for item in parsed:
                idx = item.get("tweet_index", 0)
                if 0 <= idx < len(tweets):
                    item["tweet_id"] = tweets[idx]["id"]
                    item["evaluated_at"] = datetime.now().isoformat()
            return parsed

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait = BACKOFF_SCHEDULE[min(attempt, len(BACKOFF_SCHEDULE) - 1)]
                retry_after = e.response.headers.get("retry-after")
                if retry_after:
                    try:
                        wait = float(retry_after) + 1
                    except ValueError:
                        pass
                print(f"  [WARN] Rate limited (429), {wait}秒後にリトライ...")
                await asyncio.sleep(wait)
                continue
            logger.error(f"HTTP error ({e.response.status_code}): {e}")
            break

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.error(f"Raw content: {content[:200]}")
            break

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            break

    # 失敗時はデフォルト値
    print(f"  [WARN] バッチ分類失敗。デフォルト値を使用")
    return [
        {
            "tweet_id": t["id"],
            "content_type": "other",
            "originality": 3,
            "media_contribution": "none",
            "news_saturation": "n/a",
            "bip_authenticity": None,
            "ai_citation_value": 2,
            "virality_factor": "information_value",
            "evaluated_at": datetime.now().isoformat(),
        }
        for t in tweets
    ]


# --- key_persons照合 ---

def enrich_with_key_persons(
    classifications: list[dict],
    tweets: list[dict],
    key_persons: dict,
) -> list[dict]:
    """分類結果にkey_personsの属性を付与"""
    # username→user_idの逆引き辞書
    username_to_uid = {}
    for uid, person in key_persons.get("persons", {}).items():
        uname = person.get("username", "")
        if uname:
            username_to_uid[uname.lower().lstrip("@")] = uid

    # tweet_id→tweet情報の辞書
    tweet_by_id = {t["id"]: t for t in tweets}

    for cls in classifications:
        tid = cls.get("tweet_id")
        tweet = tweet_by_id.get(tid, {})
        username = tweet.get("username", "").lower().lstrip("@")

        uid = username_to_uid.get(username)
        if uid:
            person = key_persons["persons"][uid]
            # 出現トピック上位3つ
            topics = sorted(
                person.get("topics", {}).items(),
                key=lambda kv: kv[1],
                reverse=True,
            )[:3]
            cls["key_person"] = {
                "is_key_person": True,
                "total_appearances": person.get("total_appearances", 0),
                "top_topics": [t[0] for t in topics],
            }
        else:
            cls["key_person"] = {
                "is_key_person": False,
                "total_appearances": 0,
                "top_topics": [],
            }

    return classifications


# --- パターン抽出分析 ---

def analyze_buzz_by_content_type(evals: list[dict]) -> dict:
    """content_type別のエンゲージメント統計"""
    type_data = {}
    for ev in evals:
        ct = ev.get("content_type", "other")
        td = ev.get("tweet_data", {})
        if ct not in type_data:
            type_data[ct] = {
                "likes": [], "retweets": [], "quotes": [], "replies": [],
                "eng_scores": [], "count": 0,
            }
        type_data[ct]["likes"].append(td.get("likes", 0))
        type_data[ct]["retweets"].append(td.get("retweets", 0))
        type_data[ct]["quotes"].append(td.get("quotes", 0))
        type_data[ct]["replies"].append(td.get("replies", 0))
        type_data[ct]["eng_scores"].append(td.get("engagement_score", 0))
        type_data[ct]["count"] += 1

    result = {}
    for ct, data in type_data.items():
        n = data["count"]
        if n == 0:
            continue
        result[ct] = {
            "count": n,
            "avg_eng_score": round(sum(data["eng_scores"]) / n),
            "avg_likes": round(sum(data["likes"]) / n),
            "avg_retweets": round(sum(data["retweets"]) / n),
            "avg_quotes": round(sum(data["quotes"]) / n),
            "avg_replies": round(sum(data["replies"]) / n),
        }
    return result


def analyze_buzz_by_originality(evals: list[dict]) -> dict:
    """独自性スコア別のエンゲージメント統計"""
    score_data = {}
    for ev in evals:
        orig = ev.get("originality", 3)
        td = ev.get("tweet_data", {})
        if orig not in score_data:
            score_data[orig] = {"eng_scores": [], "likes": []}
        score_data[orig]["eng_scores"].append(td.get("engagement_score", 0))
        score_data[orig]["likes"].append(td.get("likes", 0))

    result = {}
    for score, data in sorted(score_data.items()):
        n = len(data["eng_scores"])
        if n == 0:
            continue
        result[score] = {
            "count": n,
            "avg_eng_score": round(sum(data["eng_scores"]) / n),
            "avg_likes": round(sum(data["likes"]) / n),
        }
    return result


def analyze_virality_factors(evals: list[dict]) -> dict:
    """バズ要因（virality_factor）の分布と統計"""
    factor_data = {}
    for ev in evals:
        vf = ev.get("virality_factor", "information_value")
        td = ev.get("tweet_data", {})
        if vf not in factor_data:
            factor_data[vf] = {"eng_scores": [], "count": 0}
        factor_data[vf]["eng_scores"].append(td.get("engagement_score", 0))
        factor_data[vf]["count"] += 1

    result = {}
    for vf, data in factor_data.items():
        n = data["count"]
        if n == 0:
            continue
        result[vf] = {
            "count": n,
            "avg_eng_score": round(sum(data["eng_scores"]) / n),
        }
    return result


def analyze_key_person_patterns(evals: list[dict]) -> dict:
    """key_personsの出現者パターン分析"""
    person_data = {}
    for ev in evals:
        kp = ev.get("key_person", {})
        if not kp.get("is_key_person"):
            continue
        td = ev.get("tweet_data", {})
        username = td.get("username", "unknown")
        if username not in person_data:
            person_data[username] = {
                "count": 0,
                "content_types": [],
                "virality_factors": [],
                "total_eng": 0,
                "total_appearances": kp.get("total_appearances", 0),
            }
        person_data[username]["count"] += 1
        person_data[username]["content_types"].append(ev.get("content_type", "other"))
        person_data[username]["virality_factors"].append(ev.get("virality_factor", ""))
        person_data[username]["total_eng"] += td.get("engagement_score", 0)

    # バズ出現回数の多い順にソート
    result = {}
    for username, data in sorted(person_data.items(), key=lambda kv: kv[1]["count"], reverse=True):
        # content_typeの最頻値
        ct_counts = {}
        for ct in data["content_types"]:
            ct_counts[ct] = ct_counts.get(ct, 0) + 1
        top_ct = max(ct_counts, key=ct_counts.get) if ct_counts else "other"

        # virality_factorの最頻値
        vf_counts = {}
        for vf in data["virality_factors"]:
            if vf:
                vf_counts[vf] = vf_counts.get(vf, 0) + 1
        top_vf = max(vf_counts, key=vf_counts.get) if vf_counts else ""

        result[username] = {
            "buzz_count": data["count"],
            "total_eng": data["total_eng"],
            "top_content_type": top_ct,
            "top_virality_factor": top_vf,
            "cumulative_appearances": data["total_appearances"],
        }
    return result


# --- GC ---

def gc_old_evaluations(data: dict, retention_days: int = RETENTION_DAYS):
    """retention_days以前のデータを削除"""
    cutoff = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
    dates_to_remove = [d for d in data["daily_index"] if d < cutoff]
    removed = 0
    for date in dates_to_remove:
        for tid in data["daily_index"][date]:
            data["evaluations"].pop(tid, None)
            removed += 1
        del data["daily_index"][date]

    # metadata更新
    remaining_dates = sorted(data["daily_index"].keys())
    if remaining_dates:
        data["metadata"]["date_range"] = {
            "oldest": remaining_dates[0],
            "newest": remaining_dates[-1],
        }
    else:
        data["metadata"]["date_range"] = {"oldest": "", "newest": ""}
    data["metadata"]["total_evaluated"] = len(data["evaluations"])

    if removed:
        print(f"[GC] {len(dates_to_remove)}日分 / {removed}件を削除（{cutoff}以前）")


# --- レポート生成 ---

def generate_buzz_eval_report(
    today_evals: list[dict],
    all_evals: list[dict],
    type_analysis: dict,
    orig_analysis: dict,
    virality_analysis: dict,
    kp_analysis: dict,
    analysis_days: int,
) -> str:
    """Obsidian用のバズツイート分析レポートMarkdownを生成"""
    n_today = len(today_evals)
    n_all = len(all_evals)

    # 本日の最高エンゲージメント
    best = max(today_evals, key=lambda e: e.get("tweet_data", {}).get("engagement_score", 0)) if today_evals else None

    report = f"""# バズツイート分析レポート - {today_str()}

生成時刻: {now_str()}
分析対象: {n_today}件（本日収集分）
蓄積データ: {n_all}件（過去{analysis_days}日分）

## 本日の分析サマリー

"""
    if best:
        td = best.get("tweet_data", {})
        preview = td.get("text", "")[:50].replace("\n", " ")
        report += f"- 最高エンゲージメント: {td.get('engagement_score', 0):,} — @{td.get('username', '?')}「{preview}...」\n"

    # content_type分布（本日）
    today_ct = {}
    for ev in today_evals:
        ct = ev.get("content_type", "other")
        today_ct[ct] = today_ct.get(ct, 0) + 1
    if today_ct and n_today:
        ct_str = ", ".join(f"{ct} {c/n_today*100:.0f}%" for ct, c in sorted(today_ct.items(), key=lambda x: x[1], reverse=True)[:4])
        report += f"- content_type分布: {ct_str}\n"

    # バズ要因分布（本日）
    today_vf = {}
    for ev in today_evals:
        vf = ev.get("virality_factor", "")
        if vf:
            today_vf[vf] = today_vf.get(vf, 0) + 1
    if today_vf and n_today:
        vf_str = ", ".join(f"{vf} {c/n_today*100:.0f}%" for vf, c in sorted(today_vf.items(), key=lambda x: x[1], reverse=True)[:3])
        report += f"- 主要バズ要因: {vf_str}\n"

    # content_type別エンゲージメント（蓄積データ）
    if type_analysis:
        report += "\n## content_type別エンゲージメント（蓄積）\n\n"
        report += "| タイプ | 件数 | 平均eng | 平均likes | 平均RT | 平均quotes | 平均replies |\n"
        report += "|--------|------|---------|---------|------|----------|------------|\n"
        for ct in sorted(type_analysis, key=lambda k: type_analysis[k]["avg_eng_score"], reverse=True):
            d = type_analysis[ct]
            report += (
                f"| {ct} | {d['count']} | {d['avg_eng_score']:,} | "
                f"{d['avg_likes']:,} | {d['avg_retweets']:,} | "
                f"{d['avg_quotes']:,} | {d['avg_replies']:,} |\n"
            )

    # 独自性スコア分布
    if orig_analysis:
        report += "\n## 独自性スコア分布（蓄積）\n\n"
        report += "| 独自性 | 件数 | 平均eng | 平均likes |\n"
        report += "|--------|------|---------|----------|\n"
        for score, d in orig_analysis.items():
            report += f"| {score}/5 | {d['count']} | {d['avg_eng_score']:,} | {d['avg_likes']:,} |\n"

    # バズ要因分析
    if virality_analysis:
        report += "\n## バズ要因（virality_factor）分析（蓄積）\n\n"
        report += "| 要因 | 件数 | 平均eng |\n"
        report += "|------|------|---------|\n"
        for vf in sorted(virality_analysis, key=lambda k: virality_analysis[k]["avg_eng_score"], reverse=True):
            d = virality_analysis[vf]
            report += f"| {vf} | {d['count']} | {d['avg_eng_score']:,} |\n"

    # キーパーソン分析
    if kp_analysis:
        report += "\n## キーパーソン分析（蓄積）\n\n"
        report += "| ユーザー | バズ回数 | 合計eng | 主要タイプ | 主要バズ要因 |\n"
        report += "|---------|---------|--------|----------|------------|\n"
        for username, d in list(kp_analysis.items())[:15]:
            report += (
                f"| @{username} | {d['buzz_count']} | {d['total_eng']:,} | "
                f"{d['top_content_type']} | {d['top_virality_factor']} |\n"
            )

    # 個別ツイート評価（本日のエンゲージメント上位10件）
    report += "\n## 個別ツイート評価（本日・エンゲージメント上位10件）\n\n"
    sorted_today = sorted(
        today_evals,
        key=lambda e: e.get("tweet_data", {}).get("engagement_score", 0),
        reverse=True,
    )[:10]
    for ev in sorted_today:
        td = ev.get("tweet_data", {})
        preview = td.get("text", "")[:60].replace("\n", " ")
        report += (
            f"- **eng:{td.get('engagement_score', 0):,}** | "
            f"{ev.get('content_type', '?')} | 独自性:{ev.get('originality', '?')} | "
            f"バズ要因:{ev.get('virality_factor', '?')}\n"
            f"  @{td.get('username', '?')}: {preview}...\n\n"
        )

    return report


# --- 戦略リファレンス ソースBセクション更新 ---

SOURCE_B_MARKER = "## ソースB: 他者バズツイート分析（buzz_content_analyzer.py）"
INTEGRATED_MARKER = "## 統合ネタ選定ガイダンス"


def _parse_source_a_types() -> dict[str, dict]:
    """content-strategy-ref.mdのソースAテーブルからcontent_type別W-Scoreを解析する。

    Returns:
        {"bip": {"w_score": 18.0, "imp": 450, "count": 8, "rank": 2}, ...}
    """
    if not STRATEGY_REF_PATH.exists():
        return {}
    text = STRATEGY_REF_PATH.read_text(encoding="utf-8")
    # ソースAのコンテンツタイプ優先度テーブルを探す
    source_a_start = text.find("## ソースA:")
    source_b_start = text.find("## ソースB:")
    if source_a_start == -1:
        return {}
    section = text[source_a_start:source_b_start] if source_b_start != -1 else text[source_a_start:]
    # テーブル行を解析（| 優先度 | タイプ | 平均W-Score | 平均imp | 件数 | ガイダンス |）
    result = {}
    for line in section.split("\n"):
        line = line.strip()
        if not line.startswith("|") or "優先度" in line or "---" in line:
            continue
        cols = [c.strip() for c in line.split("|")]
        # cols: ['', '1', 'engagement', '23.0', '86', '5', 'ガイダンス文', '']
        if len(cols) < 7:
            continue
        try:
            rank = int(cols[1])
            ct = cols[2]
            w_score = float(cols[3])
            # impにカンマが含まれる場合を処理
            imp = int(cols[4].replace(",", ""))
            count = int(cols[5])
            result[ct] = {"w_score": w_score, "imp": imp, "count": count, "rank": rank}
        except (ValueError, IndexError):
            continue
    return result


def update_strategy_ref_buzz_section(
    type_analysis: dict,
    orig_analysis: dict,
    virality_analysis: dict,
    kp_analysis: dict,
    total_evaluated: int,
    analysis_days: int,
):
    """content-strategy-ref.mdの「ソースB」セクションのみを更新"""
    if not type_analysis:
        return

    # ソースBセクションを組み立て
    section_b = f"""\n{SOURCE_B_MARKER}
更新: {now_str()} | ソース: buzz_content_analyzer.py | 分析対象: {total_evaluated}件（過去{analysis_days}日蓄積）

### バズ content_type 分布（エンゲージメント順）

| タイプ | 件数 | 平均eng_score | 平均likes | 平均RT |
|--------|------|-------------|---------|------|
"""
    for ct in sorted(type_analysis, key=lambda k: type_analysis[k]["avg_eng_score"], reverse=True):
        d = type_analysis[ct]
        section_b += f"| {ct} | {d['count']} | {d['avg_eng_score']:,} | {d['avg_likes']:,} | {d['avg_retweets']:,} |\n"

    # 独自性
    if orig_analysis:
        section_b += "\n### 独自性 x エンゲージメント相関（他者）\n\n"
        scores = sorted(orig_analysis.keys())
        low_scores = [s for s in scores if s <= 2]
        high_scores = [s for s in scores if s >= 4]
        if low_scores and high_scores:
            low_avg = sum(orig_analysis[s]["avg_eng_score"] for s in low_scores) / len(low_scores)
            high_avg = sum(orig_analysis[s]["avg_eng_score"] for s in high_scores) / len(high_scores)
            section_b += f"独自性4-5は平均eng {high_avg:,.0f}、独自性1-2は{low_avg:,.0f}\n"

    # バズ要因
    if virality_analysis:
        section_b += "\n### バズ要因（virality_factor）分布\n\n"
        section_b += "| 要因 | 件数 | 平均eng_score |\n"
        section_b += "|------|------|-------------|\n"
        for vf in sorted(virality_analysis, key=lambda k: virality_analysis[k]["avg_eng_score"], reverse=True):
            d = virality_analysis[vf]
            section_b += f"| {vf} | {d['count']} | {d['avg_eng_score']:,} |\n"

    # キーパーソン
    if kp_analysis:
        section_b += "\n### キーパーソン出現傾向\n\n"
        top_kps = list(kp_analysis.items())[:10]
        for username, d in top_kps:
            section_b += f"- @{username}: {d['top_content_type']}中心 / バズ{d['buzz_count']}回 / {d['top_virality_factor']}\n"

    section_b += "\n"

    # 統合ガイダンスセクション — ソースAのデータも突合して動的生成
    source_a = _parse_source_a_types()

    # ソースB: content_type上位3つ（他者バズ）
    top_types = sorted(type_analysis, key=lambda k: type_analysis[k]["avg_eng_score"], reverse=True)[:3]
    # ソースB: バズ要因上位3つ
    top_factors = sorted(virality_analysis, key=lambda k: virality_analysis[k]["avg_eng_score"], reverse=True)[:3] if virality_analysis else []

    integrated = f"""{INTEGRATED_MARKER}

ソースA（自己ツイート分析）とソースB（他者バズ分析）の両方を踏まえた方向性。

- **バズしやすいcontent_type**: {', '.join(top_types)}（他者のバズ分布から）
- **バズの主要因**: {', '.join(top_factors)}（高エンゲージメントツイートの共通要素）
"""
    # ソースAとソースBの突合: 自分が得意 × 他者もバズる = 最強カテゴリを自動検出
    if source_a and type_analysis:
        # 両方に存在するcontent_typeで突合
        common_types = set(source_a.keys()) & set(type_analysis.keys())
        if common_types:
            # ソースAのW-Score中央値・ソースBのeng_score中央値を基準に分類
            a_scores = [source_a[ct]["w_score"] for ct in common_types]
            b_scores = [type_analysis[ct]["avg_eng_score"] for ct in common_types]
            a_median = sorted(a_scores)[len(a_scores) // 2]
            b_median = sorted(b_scores)[len(b_scores) // 2]

            # 4象限に分類
            strong_both = []  # 自分も得意 + 他者もバズる
            opportunity = []   # 自分は弱い + 他者はバズる（改善チャンス）
            niche = []         # 自分は得意 + 他者はバズらない（ニッチ強み）
            for ct in sorted(common_types):
                a_ws = source_a[ct]["w_score"]
                b_eng = type_analysis[ct]["avg_eng_score"]
                if a_ws >= a_median and b_eng >= b_median:
                    strong_both.append(ct)
                elif a_ws < a_median and b_eng >= b_median:
                    opportunity.append(ct)
                elif a_ws >= a_median and b_eng < b_median:
                    niche.append(ct)

            if strong_both:
                integrated += f"- **最強カテゴリ（自分も得意+他者もバズる）**: {', '.join(strong_both)}\n"
            if opportunity:
                integrated += f"- **改善チャンス（他者はバズるが自分は弱い）**: {', '.join(opportunity)}\n"
            if niche:
                integrated += f"- **ニッチ強み（自分は得意だが他者は少ない）**: {', '.join(niche)}\n"

    # 独自性とバズの関係（ソースBデータ）
    if orig_analysis:
        high_scores = [s for s in sorted(orig_analysis.keys()) if s >= 4]
        if high_scores:
            high_avg = sum(orig_analysis[s]["avg_eng_score"] for s in high_scores) / len(high_scores)
            integrated += f"- **独自性とバズの関係**: 独自性4-5の他者ツイートは平均eng {high_avg:,.0f}\n"

    # ソースAデータからBIP・ニュース系の自分の実績を反映
    if source_a:
        bip_data = source_a.get("bip")
        news_data = source_a.get("ai_news")
        if bip_data and bip_data["count"] >= 3:
            integrated += f"- **BIP・体験談を優先**: 自分のBIPはW-Score {bip_data['w_score']}（{bip_data['count']}件）。独自体験は代替不可\n"
        else:
            integrated += "- **BIP・体験談を優先**: 独自体験は代替不可。具体的な数字・苦労・発見を含めると高スコア\n"
        if news_data and news_data["count"] >= 3:
            integrated += f"- **ニュースは速報性が命**: 自分のai_newsはW-Score {news_data['w_score']}（{news_data['count']}件）。飽和度mainstream以降はパフォーマンス低下\n"
        else:
            integrated += "- **ニュースは速報性が命**: 飽和度がmainstream以降だとパフォーマンス低下\n"
    else:
        integrated += "- **BIP・体験談を優先**: 独自体験は代替不可。具体的な数字・苦労・発見を含めると高スコア\n"
        integrated += "- **ニュースは速報性が命**: 飽和度がmainstream以降だとパフォーマンス低下\n"
    integrated += "- **画像は補強として有効**: imp増加効果あり。ただし画像に頼りすぎない\n"

    # 既存ファイルの読み込みとセクション差し替え
    existing = ""
    if STRATEGY_REF_PATH.exists():
        existing = STRATEGY_REF_PATH.read_text(encoding="utf-8")

    # ソースBマーカー以降を差し替え
    if SOURCE_B_MARKER in existing:
        # ソースB以降を全て差し替え
        source_b_start = existing.index(SOURCE_B_MARKER)
        new_content = existing[:source_b_start] + section_b + integrated
    elif INTEGRATED_MARKER in existing:
        # 統合ガイダンスマーカー以降を差し替え
        marker_start = existing.index(INTEGRATED_MARKER)
        new_content = existing[:marker_start] + section_b + integrated
    else:
        # 既存の末尾にソースBを追加
        new_content = existing.rstrip() + "\n\n---\n\n" + section_b + integrated

    STRATEGY_REF_PATH.parent.mkdir(parents=True, exist_ok=True)
    STRATEGY_REF_PATH.write_text(new_content, encoding="utf-8")
    print(f"[OK] 戦略リファレンス（ソースB）更新: {STRATEGY_REF_PATH}")


# --- メイン ---

async def async_main(args):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[ERROR] GROQ_API_KEY が環境変数に未設定")
        sys.exit(1)

    analysis_days = args.days
    print(f"=== バズツイート分析パイプライン ===")

    # バズツイート読み込み
    buzz_data = load_buzz_tweets()
    tweets = buzz_data.get("tweets", [])
    if not tweets:
        print("[WARN] バズツイートが0件（buzz-tweets-latest.json）。スキップします")
        print("[HINT] buzz_tweet_extractor.py を実行するか、twscrapeの認証を確認してください")
        return

    print(f"[INFO] 本日のバズツイート: {len(tweets)}件")

    # 蓄積データ読み込み
    eval_data = load_buzz_evaluations()
    evaluated_ids = set(eval_data["evaluations"].keys())

    # GC実行
    gc_old_evaluations(eval_data, RETENTION_DAYS)

    # 未分類ツイート抽出
    if args.force:
        target_tweets = tweets
        print(f"[INFO] --force: 全{len(target_tweets)}件を再評価")
    else:
        target_tweets = [t for t in tweets if t["id"] not in evaluated_ids]
        print(f"[INFO] 未分類: {len(target_tweets)}件（既分類: {len(evaluated_ids)}件）")

    # key_persons読み込み
    key_persons = load_key_persons()
    kp_count = len(key_persons.get("persons", {}))
    print(f"[INFO] key_persons: {kp_count}名")

    # LLM分類実行
    today_date = today_str()
    new_classifications = []
    if target_tweets:
        print(f"\n[1/3] Groq LLM 分類中... ({len(target_tweets)}件)")
        classifications = await classify_buzz_tweets(target_tweets, api_key)

        # key_persons照合
        classifications = enrich_with_key_persons(classifications, target_tweets, key_persons)
        new_classifications = classifications

        # 蓄積データにマージ
        for cls in classifications:
            tid = cls.get("tweet_id")
            if not tid:
                continue
            # 元ツイートデータを取得
            tweet = next((t for t in tweets if t["id"] == tid), {})
            entry = {
                "tweet_id": tid,
                "evaluated_at": cls.get("evaluated_at", datetime.now().isoformat()),
                "evaluated_date": today_date,
                "tweet_data": {
                    "username": tweet.get("username", "").lstrip("@"),
                    "text": tweet.get("text", "")[:280],
                    "likes": tweet.get("likes", 0),
                    "retweets": tweet.get("retweets", 0),
                    "quotes": tweet.get("quotes", 0),
                    "replies": tweet.get("replies", 0),
                    "engagement_score": tweet.get("engagement_score", 0),
                    "query_source": tweet.get("query_source", ""),
                    "url": tweet.get("url", ""),
                },
                "content_type": cls.get("content_type", "other"),
                "originality": cls.get("originality", 3),
                "media_contribution": cls.get("media_contribution", "none"),
                "news_saturation": cls.get("news_saturation", "n/a"),
                "bip_authenticity": cls.get("bip_authenticity"),
                "ai_citation_value": cls.get("ai_citation_value", 2),
                "virality_factor": cls.get("virality_factor", "information_value"),
                "key_person": cls.get("key_person", {"is_key_person": False}),
            }
            eval_data["evaluations"][tid] = entry

        # daily_index更新
        if today_date not in eval_data["daily_index"]:
            eval_data["daily_index"][today_date] = []
        new_ids = [cls["tweet_id"] for cls in classifications if cls.get("tweet_id")]
        eval_data["daily_index"][today_date] = list(
            set(eval_data["daily_index"][today_date] + new_ids)
        )

        # metadata更新
        eval_data["metadata"]["last_updated"] = now_str()
        eval_data["metadata"]["total_evaluated"] = len(eval_data["evaluations"])
        dates = sorted(eval_data["daily_index"].keys())
        if dates:
            eval_data["metadata"]["date_range"] = {"oldest": dates[0], "newest": dates[-1]}

        if not args.dry_run:
            save_buzz_evaluations(eval_data)
        else:
            print("[DRY-RUN] 評価データ保存スキップ")
            for cls in classifications[:5]:
                tid = cls.get("tweet_id", "?")[:12]
                ct = cls.get("content_type", "?")
                vf = cls.get("virality_factor", "?")
                print(f"  {tid}... → {ct} | バズ要因:{vf}")
    else:
        print("[INFO] 新規分類対象なし")

    # 蓄積データからの分析（対象日数分）
    print(f"\n[2/3] パターン抽出分析（過去{analysis_days}日分）...")
    cutoff_date = (datetime.now() - timedelta(days=analysis_days)).strftime("%Y-%m-%d")
    all_evals = [
        ev for ev in eval_data["evaluations"].values()
        if ev.get("evaluated_date", "") >= cutoff_date
    ]
    today_evals = [
        ev for ev in eval_data["evaluations"].values()
        if ev.get("evaluated_date", "") == today_date
    ]
    print(f"[INFO] 分析対象: {len(all_evals)}件（本日: {len(today_evals)}件）")

    type_analysis = analyze_buzz_by_content_type(all_evals)
    orig_analysis = analyze_buzz_by_originality(all_evals)
    virality_analysis = analyze_virality_factors(all_evals)
    kp_analysis = analyze_key_person_patterns(all_evals)

    # レポート生成
    print(f"\n[3/3] レポート生成...")
    report = generate_buzz_eval_report(
        today_evals, all_evals,
        type_analysis, orig_analysis, virality_analysis, kp_analysis,
        analysis_days,
    )

    if not args.dry_run:
        filename = f"buzz-eval-{today_str()}.md"
        save_to_obsidian(OBSIDIAN_EVAL, filename, report)

        # 戦略リファレンス ソースB更新
        update_strategy_ref_buzz_section(
            type_analysis, orig_analysis, virality_analysis, kp_analysis,
            len(all_evals), analysis_days,
        )

        # Discord通知
        summary_lines = []
        for ct in sorted(type_analysis, key=lambda k: type_analysis[k]["avg_eng_score"], reverse=True)[:3]:
            d = type_analysis[ct]
            summary_lines.append(f"{ct}: eng {d['avg_eng_score']:,} ({d['count']}件)")

        notify_discord(
            f"**Buzz Content Analysis** {today_str()}\n\n"
            f"本日: {len(today_evals)}件 / 蓄積: {len(all_evals)}件\n"
            + "\n".join(summary_lines)
        )
    else:
        print("\n--- レポートプレビュー ---")
        print(report[:1500])
        if len(report) > 1500:
            print(f"\n... ({len(report)}文字)")

    print(f"\n=== 完了 ===")
    print(f"蓄積: {len(eval_data['evaluations'])}件")


def main():
    parser = argparse.ArgumentParser(description="他者バズツイート多次元分析パイプライン")
    parser.add_argument("--dry-run", action="store_true", help="分類のみ（保存・レポートなし）")
    parser.add_argument("--force", action="store_true", help="本日分を全て再評価")
    parser.add_argument("--days", type=int, default=RETENTION_DAYS, help=f"蓄積分析の対象日数（デフォルト: {RETENTION_DAYS}）")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
