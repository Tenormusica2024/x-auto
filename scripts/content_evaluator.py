"""
content_evaluator.py - X コンテンツ多次元評価分析

ツイートをLLM（Groq）で多次元分類し、コンテンツ戦略の有効性を定量評価する。
daily_metrics.py が蓄積した tweet_details.json を入力として使用。

評価軸:
  - content_type: コンテンツ種別（ai_news / bip / opinion / how-to / quote_rt / engagement / other）
  - originality: 独自性（1-5、大手インフルエンサーの二番煎じか独自知見か）
  - media_contribution: 画像の寄与度（essential / enhancing / irrelevant / none）
  - news_saturation: ニュース飽和度（first_mover / early / mainstream / late / rehash / n/a）
  - bip_authenticity: BIPの真正性（1-5、具体的体験か一般論か。BIPのみ）
  - ai_citation_value: AI引用価値（1-5、AI検索で一次ソースとして引用されるか）
  - reputation_risk: レピュテーションリスク（1-5、信頼毀損リスク。煽り・誤情報・攻撃的批判等）

使い方:
  python -X utf8 content_evaluator.py            # 未分類ツイートを評価 + レポート生成
  python -X utf8 content_evaluator.py --dry-run  # 分類のみ（レポート・保存なし）
  python -X utf8 content_evaluator.py --force    # 全ツイート再評価

コスト: $0.00（Groq無料枠）
"""

import sys
import os
import json
import asyncio
import argparse
import logging
from pathlib import Path
from datetime import datetime

import httpx
from dotenv import load_dotenv

# GROQ_API_KEYを.envから読み込み（zeitgeist_detector.pyと同じ）
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
EVAL_PATH = DATA_DIR / "content_evaluations.json"

# 1バッチあたりのツイート数（プロンプトサイズ管理）
BATCH_SIZE = 5
# バッチ間待機（Groq free tier RPM 30対策: 5秒 → 12 RPM safe）
BATCH_DELAY = 5.0
BACKOFF_SCHEDULE = [5, 15, 30, 60]

CLASSIFICATION_PROMPT = """\
あなたはX(Twitter)コンテンツ戦略の専門アナリストです。
以下のツイートを多次元で評価してJSON配列で返してください。

## 評価軸の定義

### content_type（コンテンツ種別）
- "ai_news": AIやテクノロジーのニュース・速報・新サービス紹介
- "bip": Build in Public（開発過程・作業ログ・進捗報告・個人開発）
- "opinion": 意見・考察・ポエム・業界への見解
- "how-to": 使い方・ハウツー・Tips・具体的手順の共有
- "quote_rt": 他人のツイートへのコメント・引用
- "engagement": 挨拶・お礼・日常会話・交流目的
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
- "first_mover": 日本語圏で最初期に取り上げた（発表から数時間以内）
- "early": 早めだが既に何人かが言及済み（12時間以内）
- "mainstream": 多くのアカウントが既に取り上げている
- "late": 話題が一巡した後
- "rehash": 大手インフルエンサーが既に詳しく解説済みの内容を後追い
- "n/a": ニュース系ではない

### bip_authenticity（BIPの真正性 1-5 - bipの場合のみ）
1: AIが書いたような一般論・抽象的な「やってます」報告
2: 具体性はあるが表面的（ツール名を挙げただけ等）
3: 具体的な作業内容があるが数字・成果がない
4: 具体的な体験・苦労・発見が含まれる
5: 数字・スクショ・具体的成果と率直な所感がある

### ai_citation_value（AI引用価値 1-5）
AI検索（ChatGPT、Perplexity等）がこのツイートを一次ソースとして引用する可能性。
以下の5項目のうち該当する数がスコアになる（0該当=1、5該当=5）:
- 独自データや具体的な数値を含む（ベンチマーク結果・コスト比較・設定値等）
- 再現可能な具体手順を含む（コマンド・設定方法・ステップバイステップ）
- 個人の実体験に基づく知見（実際に試した結果・遭遇した問題と解決策）
- 他で見つからない一次情報（公式未記載の仕様・独自発見・未報告のバグ等）
- 検証可能な主張（リンク・ソース・スクリーンショット付き）

### reputation_risk（レピュテーションリスク 1-5）
このツイートが発信者の長期的な信頼・好感度に与えるリスク。
1: リスクなし（有益な知見共有・誠実なBIP・建設的な意見）
2: 軽微なリスク（やや断定的だが根拠がある・軽い自虐）
3: 中程度のリスク（根拠なしの断定・他者の成果を自分の手柄のように紹介・過度な煽り見出し）
4: 高リスク（誤情報の拡散・低品質AI生成画像＋不正確な説明・特定個人や製品への攻撃的批判）
5: 重大リスク（デマ・差別的表現・炎上目的の挑発・著作権侵害の疑い）

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
    "content_type": "ai_news",
    "originality": 3,
    "media_contribution": "none",
    "news_saturation": "early",
    "bip_authenticity": null,
    "ai_citation_value": 2,
    "reputation_risk": 1
  }}
]
```"""


# --- データI/O ---

def load_tweet_details() -> dict:
    """tweet_details.json を読み込み"""
    path = DATA_DIR / "tweet_details.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"tweets": [], "last_updated": ""}


def load_evaluations() -> dict:
    """content_evaluations.json を読み込み"""
    if EVAL_PATH.exists():
        return json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    return {"evaluations": {}, "last_updated": ""}


def save_evaluations(data: dict):
    """content_evaluations.json を保存"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EVAL_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] 評価データ保存: {EVAL_PATH}")


# --- Groq LLM 分類 ---

async def classify_tweets(
    tweets: list[dict], api_key: str
) -> list[dict]:
    """ツイート群をGroq LLMでバッチ分類"""
    results = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        for batch_start in range(0, len(tweets), BATCH_SIZE):
            batch = tweets[batch_start : batch_start + BATCH_SIZE]
            batch_results = await _classify_batch(client, batch, api_key)
            results.extend(batch_results)

            # バッチ間待機
            if batch_start + BATCH_SIZE < len(tweets):
                print(f"  [WAIT] {BATCH_DELAY}秒待機（rate limit対策）...")
                await asyncio.sleep(BATCH_DELAY)

            print(f"  [PROGRESS] {min(batch_start + BATCH_SIZE, len(tweets))}/{len(tweets)} 完了")

    return results


async def _classify_batch(
    client: httpx.AsyncClient,
    tweets: list[dict],
    api_key: str,
) -> list[dict]:
    """1バッチ（最大5ツイート）をGroqで分類"""
    # プロンプト組み立て
    tweets_block = ""
    for i, t in enumerate(tweets):
        media_info = f"画像: {t.get('media_type', 'なし')}" if t.get("has_media") else "画像: なし"
        tweets_block += f"### ツイート {i}（{media_info}）\n{t.get('text', '')}\n\n"

    prompt = CLASSIFICATION_PROMPT.format(tweets_block=tweets_block)

    # Groq API呼び出し（リトライ付き）
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
                    "max_tokens": 1500,
                },
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()

            # JSON抽出（```json ... ``` 対応）
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            parsed = json.loads(content)

            # tweet_idを付与して返す
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
            "media_contribution": "none" if not t.get("has_media") else "enhancing",
            "news_saturation": "n/a",
            "bip_authenticity": None,
            "ai_citation_value": 2,
            "reputation_risk": 1,
            "evaluated_at": datetime.now().isoformat(),
        }
        for t in tweets
    ]


# --- 分析関数群 ---

def analyze_by_content_type(tweets: list[dict], evals: dict) -> dict:
    """コンテンツタイプ別パフォーマンス分析"""
    type_data = {}
    for t in tweets:
        ev = evals.get(t["id"])
        if not ev:
            continue
        ct = ev["content_type"]
        if ct not in type_data:
            type_data[ct] = {"impressions": [], "eng_rates": [], "w_scores": [], "count": 0}
        type_data[ct]["impressions"].append(t.get("impressions", 0))
        type_data[ct]["eng_rates"].append(t.get("engagement_rate", 0))
        type_data[ct]["w_scores"].append(t.get("weighted_score", 0))
        type_data[ct]["count"] += 1

    result = {}
    for ct, data in type_data.items():
        n = data["count"]
        result[ct] = {
            "count": n,
            "avg_imp": round(sum(data["impressions"]) / n) if n else 0,
            "avg_eng": round(sum(data["eng_rates"]) / n, 2) if n else 0,
            "avg_w_score": round(sum(data["w_scores"]) / n, 1) if n else 0,
        }
    return result


def analyze_media_effect(tweets: list[dict], evals: dict) -> dict:
    """画像効果の分離分析"""
    groups = {"with_media": [], "without_media": []}
    contribution_data = {}

    for t in tweets:
        ev = evals.get(t["id"])
        if not ev:
            continue
        key = "with_media" if t.get("has_media") else "without_media"
        groups[key].append(t)

        mc = ev.get("media_contribution", "none")
        if mc not in contribution_data:
            contribution_data[mc] = {"impressions": [], "w_scores": []}
        contribution_data[mc]["impressions"].append(t.get("impressions", 0))
        contribution_data[mc]["w_scores"].append(t.get("weighted_score", 0))

    result = {}
    for key, tlist in groups.items():
        n = len(tlist)
        if n:
            result[key] = {
                "count": n,
                "avg_imp": round(sum(t.get("impressions", 0) for t in tlist) / n),
                "avg_w_score": round(
                    sum(t.get("weighted_score", 0) for t in tlist) / n, 1
                ),
            }

    result["by_contribution"] = {}
    for mc, data in contribution_data.items():
        n = len(data["impressions"])
        if n:
            result["by_contribution"][mc] = {
                "count": n,
                "avg_imp": round(sum(data["impressions"]) / n),
                "avg_w_score": round(sum(data["w_scores"]) / n, 1),
            }
    return result


def analyze_originality(tweets: list[dict], evals: dict) -> dict:
    """独自性スコア × パフォーマンス分析"""
    score_data = {}
    for t in tweets:
        ev = evals.get(t["id"])
        if not ev:
            continue
        orig = ev.get("originality", 3)
        if orig not in score_data:
            score_data[orig] = {"impressions": [], "w_scores": []}
        score_data[orig]["impressions"].append(t.get("impressions", 0))
        score_data[orig]["w_scores"].append(t.get("weighted_score", 0))

    result = {}
    for score, data in sorted(score_data.items()):
        n = len(data["impressions"])
        result[score] = {
            "count": n,
            "avg_imp": round(sum(data["impressions"]) / n) if n else 0,
            "avg_w_score": round(sum(data["w_scores"]) / n, 1) if n else 0,
        }
    return result


def analyze_news_saturation(tweets: list[dict], evals: dict) -> dict:
    """ニュース飽和度 × パフォーマンス分析"""
    sat_data = {}
    for t in tweets:
        ev = evals.get(t["id"])
        if not ev:
            continue
        sat = ev.get("news_saturation", "n/a")
        if sat == "n/a":
            continue
        if sat not in sat_data:
            sat_data[sat] = {"impressions": [], "w_scores": []}
        sat_data[sat]["impressions"].append(t.get("impressions", 0))
        sat_data[sat]["w_scores"].append(t.get("weighted_score", 0))

    # 飽和度順にソート
    order = ["first_mover", "early", "mainstream", "late", "rehash"]
    result = {}
    for sat in order:
        if sat in sat_data:
            data = sat_data[sat]
            n = len(data["impressions"])
            result[sat] = {
                "count": n,
                "avg_imp": round(sum(data["impressions"]) / n) if n else 0,
                "avg_w_score": round(sum(data["w_scores"]) / n, 1) if n else 0,
            }
    return result


def analyze_reputation_risk(tweets: list[dict], evals: dict) -> dict:
    """レピュテーションリスクスコア × パフォーマンス分析

    「impは高いが信頼を毀損する」パターンの検出が目的。
    W-Scoreが高いのにリスクも高いツイートは要注意。
    """
    risk_data = {}
    for t in tweets:
        ev = evals.get(t["id"])
        if not ev:
            continue
        risk = ev.get("reputation_risk", 1)
        if risk not in risk_data:
            risk_data[risk] = {"impressions": [], "w_scores": [], "tweets": []}
        risk_data[risk]["impressions"].append(t.get("impressions", 0))
        risk_data[risk]["w_scores"].append(t.get("weighted_score", 0))
        # リスク3以上のツイートは個別に記録（要注意ツイート特定用）
        if risk >= 3:
            risk_data[risk]["tweets"].append({
                "id": t["id"],
                "text_preview": t.get("text", "")[:60].replace("\n", " "),
                "w_score": t.get("weighted_score", 0),
                "impressions": t.get("impressions", 0),
            })

    result = {}
    for score in sorted(risk_data.keys()):
        data = risk_data[score]
        n = len(data["impressions"])
        result[score] = {
            "count": n,
            "avg_imp": round(sum(data["impressions"]) / n) if n else 0,
            "avg_w_score": round(sum(data["w_scores"]) / n, 1) if n else 0,
            "flagged_tweets": data.get("tweets", []),
        }
    return result


# --- レポート生成 ---

def generate_eval_report(
    tweets: list[dict],
    evals: dict,
    type_analysis: dict,
    media_analysis: dict,
    orig_analysis: dict,
    sat_analysis: dict,
    risk_analysis: dict = None,
) -> str:
    """Obsidian用の評価レポートMarkdownを生成"""
    evaluated_tweets = [t for t in tweets if t["id"] in evals]
    n = len(evaluated_tweets)

    # 最高/最低 weighted_score
    best = max(evaluated_tweets, key=lambda t: t.get("weighted_score", 0)) if evaluated_tweets else None
    worst = min(evaluated_tweets, key=lambda t: t.get("weighted_score", 0)) if evaluated_tweets else None

    report = f"""# コンテンツ評価レポート - {today_str()}

生成時刻: {now_str()}
分析対象: {n}件

## 戦略サマリー
"""
    if best:
        preview = best.get("text", "")[:50].replace("\n", " ")
        report += f"- 最高W-Score: {best.get('weighted_score', 0)} — {preview}...\n"
    if worst:
        preview = worst.get("text", "")[:50].replace("\n", " ")
        report += f"- 最低W-Score: {worst.get('weighted_score', 0)} — {preview}...\n"

    # コンテンツタイプ別
    if type_analysis:
        report += "\n## コンテンツタイプ別成績\n\n"
        report += "| タイプ | 件数 | 平均imp | 平均eng率 | 平均W-Score |\n"
        report += "|--------|------|---------|-----------|-------------|\n"
        for ct in sorted(type_analysis, key=lambda k: type_analysis[k]["avg_w_score"], reverse=True):
            d = type_analysis[ct]
            report += f"| {ct} | {d['count']} | {d['avg_imp']:,} | {d['avg_eng']:.1f}% | {d['avg_w_score']} |\n"

    # 画像効果
    if media_analysis:
        report += "\n## 画像効果分析\n\n"
        report += "| 画像有無 | 件数 | 平均imp | 平均W-Score |\n"
        report += "|----------|------|---------|-------------|\n"
        for key in ["with_media", "without_media"]:
            if key in media_analysis:
                d = media_analysis[key]
                label = "画像あり" if key == "with_media" else "画像なし"
                report += f"| {label} | {d['count']} | {d['avg_imp']:,} | {d['avg_w_score']} |\n"

        if media_analysis.get("by_contribution"):
            report += "\n### 画像寄与度別\n\n"
            report += "| 寄与度 | 件数 | 平均imp | 平均W-Score |\n"
            report += "|--------|------|---------|-------------|\n"
            for mc, d in media_analysis["by_contribution"].items():
                report += f"| {mc} | {d['count']} | {d['avg_imp']:,} | {d['avg_w_score']} |\n"

    # 独自性
    if orig_analysis:
        report += "\n## 独自性スコア分布\n\n"
        report += "| 独自性 | 件数 | 平均imp | 平均W-Score |\n"
        report += "|--------|------|---------|-------------|\n"
        for score, d in orig_analysis.items():
            report += f"| {score}/5 | {d['count']} | {d['avg_imp']:,} | {d['avg_w_score']} |\n"

    # ニュース飽和度
    if sat_analysis:
        report += "\n## ニュース飽和度分析\n\n"
        report += "| 飽和度 | 件数 | 平均imp | 平均W-Score |\n"
        report += "|--------|------|---------|-------------|\n"
        for sat, d in sat_analysis.items():
            report += f"| {sat} | {d['count']} | {d['avg_imp']:,} | {d['avg_w_score']} |\n"

    # レピュテーションリスク
    if risk_analysis:
        report += "\n## レピュテーションリスク分析\n\n"
        report += "| リスク | 件数 | 平均imp | 平均W-Score |\n"
        report += "|--------|------|---------|-------------|\n"
        for score, d in risk_analysis.items():
            label = {1: "リスクなし", 2: "軽微", 3: "中程度", 4: "高", 5: "重大"}.get(score, str(score))
            report += f"| {score}/5 ({label}) | {d['count']} | {d['avg_imp']:,} | {d['avg_w_score']} |\n"

        # リスク3以上のツイートをフラグ表示
        flagged = []
        for score, d in risk_analysis.items():
            if score >= 3:
                flagged.extend(d.get("flagged_tweets", []))
        if flagged:
            report += "\n### 要注意ツイート（リスク3以上）\n\n"
            for ft in sorted(flagged, key=lambda x: x["w_score"], reverse=True):
                report += f"- W:{ft['w_score']} | imp:{ft['impressions']:,} | {ft['text_preview']}...\n"

    # 個別ツイート評価一覧
    report += "\n## 個別ツイート評価\n\n"
    for t in sorted(evaluated_tweets, key=lambda x: x.get("weighted_score", 0), reverse=True):
        ev = evals[t["id"]]
        preview = t.get("text", "")[:60].replace("\n", " ")
        report += f"- **W:{t.get('weighted_score', 0)}** | {ev['content_type']} | "
        report += f"独自性:{ev.get('originality', '?')} | "
        if ev.get("news_saturation") and ev["news_saturation"] != "n/a":
            report += f"飽和:{ev['news_saturation']} | "
        if ev.get("bip_authenticity") is not None:
            report += f"BIP真正:{ev['bip_authenticity']} | "
        report += f"AI引用:{ev.get('ai_citation_value', '?')}"
        # リスクスコアが2以上の場合のみ表示（1=リスクなしは省略）
        risk = ev.get("reputation_risk", 1)
        if risk >= 2:
            report += f" | リスク:{risk}"
        report += f"\n  {preview}...\n\n"

    return report


# --- 戦略サマリー生成（ツイート生成スキル向け） ---

STRATEGY_REF_PATH = Path(r"C:\Users\Tenormusica\x-auto\common\content-strategy-ref.md")

# サンプル数が少ないときの信頼度表示閾値
_MIN_SAMPLES_RELIABLE = 5
_MIN_SAMPLES_USABLE = 3


def _generate_dynamic_guidance(
    ct: str,
    ct_data: dict,
    type_ranking: list[tuple[str, dict]],
    total_count: int,
) -> str:
    """content_typeごとのガイダンスを蓄積データから動的に生成する。

    ハードコードされた文言ではなく、データの相対的な位置関係から文言を導出。
    サンプル数が少ない場合は信頼度注記を付与。
    """
    count = ct_data["count"]
    avg_ws = ct_data["avg_w_score"]
    avg_imp = ct_data["avg_imp"]

    # サンプル数が少なすぎる場合
    if count < _MIN_SAMPLES_USABLE:
        return f"データ不足（{count}件）"

    # 全タイプのW-Score平均と比較
    all_ws = [d["avg_w_score"] for _, d in type_ranking]
    all_imp = [d["avg_imp"] for _, d in type_ranking]
    overall_avg_ws = sum(all_ws) / len(all_ws) if all_ws else 0
    overall_avg_imp = sum(all_imp) / len(all_imp) if all_imp else 0

    # 順位（1-indexed）
    rank = next(
        (i + 1 for i, (c, _) in enumerate(type_ranking) if c == ct),
        len(type_ranking),
    )
    total_types = len(type_ranking)

    # W-ScoreとImpの相対評価
    ws_ratio = avg_ws / overall_avg_ws if overall_avg_ws else 1.0
    imp_ratio = avg_imp / overall_avg_imp if overall_avg_imp else 1.0

    parts = []

    # 順位に基づくポジション表現
    if rank == 1:
        parts.append("W-Score最高")
    elif rank <= total_types * 0.4:
        parts.append("W-Score上位")
    elif rank >= total_types * 0.8:
        parts.append("W-Score下位")

    # W-Score vs Imp の乖離パターン（タイプの特性を自動判定）
    if ws_ratio >= 1.3 and imp_ratio < 0.8:
        # W-Score高い + imp低い = 深い反応あるが拡散は弱い
        parts.append("深い反応を生むが拡散力は弱い")
    elif ws_ratio < 0.7 and imp_ratio >= 1.3:
        # W-Score低い + imp高い = 広くリーチするが浅い
        parts.append("impは稼げるがW-Scoreは低め")
    elif ws_ratio >= 1.2 and imp_ratio >= 1.2:
        # 両方高い
        parts.append("拡散力・反応とも高パフォーマンス")
    elif ws_ratio < 0.7 and imp_ratio < 0.7:
        parts.append("拡散・反応とも低調")

    # サンプル数注記
    if count < _MIN_SAMPLES_RELIABLE:
        parts.append(f"n={count}のため参考値")

    return "。".join(parts) if parts else ""


def generate_strategy_ref(
    tweets: list[dict],
    evals: dict,
    type_analysis: dict,
    media_analysis: dict,
    orig_analysis: dict,
    sat_analysis: dict,
    risk_analysis: dict = None,
):
    """ツイート生成スキルが参照する戦略サマリーを common/content-strategy-ref.md に出力

    content_evaluator.pyの分析結果を「ソースA」セクションとして書き込む。
    ソースB（buzz_content_analyzer.py由来）以降のセクションは保持する。
    """
    n = len([t for t in tweets if t["id"] in evals])
    if n == 0:
        return

    # コンテンツタイプをW-Score降順でランキング
    type_ranking = sorted(
        type_analysis.items(),
        key=lambda kv: kv[1]["avg_w_score"],
        reverse=True,
    )

    # 独自性スコア別の傾向を抽出
    orig_insight = ""
    if orig_analysis:
        scores = sorted(orig_analysis.keys())
        low_scores = [s for s in scores if s <= 2]
        high_scores = [s for s in scores if s >= 4]
        if low_scores and high_scores:
            low_avg = sum(orig_analysis[s]["avg_w_score"] for s in low_scores) / len(low_scores)
            high_avg = sum(orig_analysis[s]["avg_w_score"] for s in high_scores) / len(high_scores)
            if high_avg > low_avg:
                orig_insight = f"独自性4-5は平均W-Score {high_avg:.1f}、独自性1-2は{low_avg:.1f}（独自性が高いほど深い反応）"
            else:
                orig_insight = f"独自性4-5は平均W-Score {high_avg:.1f}、独自性1-2は{low_avg:.1f}（独自性と反応は比例していない）"

    # 画像効果の傾向
    media_insight = ""
    if "with_media" in media_analysis and "without_media" in media_analysis:
        w = media_analysis["with_media"]
        wo = media_analysis["without_media"]
        imp_diff = w["avg_imp"] - wo["avg_imp"]
        ws_diff = round(w["avg_w_score"] - wo["avg_w_score"], 1)
        media_insight = (
            f"画像あり: 平均imp {w['avg_imp']:,} / W-Score {w['avg_w_score']} "
            f"(画像なし比: imp {'+' if imp_diff >= 0 else ''}{imp_diff:,}, "
            f"W-Score {'+' if ws_diff >= 0 else ''}{ws_diff})"
        )

    # ニュース飽和度の傾向
    sat_insight = ""
    if sat_analysis:
        best_sat = max(sat_analysis.items(), key=lambda kv: kv[1]["avg_w_score"])
        sat_insight = f"ニュース系は飽和度'{best_sat[0]}'が最もW-Score高い（{best_sat[1]['avg_w_score']}）"

    # レピュテーションリスクの傾向
    risk_insight = ""
    if risk_analysis:
        total = sum(d["count"] for d in risk_analysis.values())
        risky_count = sum(d["count"] for s, d in risk_analysis.items() if s >= 3)
        if risky_count > 0:
            risky_pct = round(risky_count / total * 100, 1) if total else 0
            risk_insight = f"リスク3以上: {risky_count}件/{total}件（{risky_pct}%）— 煽り・根拠不足・二次利用感に注意"
        else:
            risk_insight = f"全{total}件がリスク2以下（良好）"

    # ソースAセクションのMarkdown生成
    source_a = f"""## ソースA: 自己ツイート分析（content_evaluator.py）

更新: {now_str()} | 分析対象: {n}件

### コンテンツタイプ優先度（W-Score順）

W-Score = Xアルゴリズム重み付きエンゲージメント。高いほど会話・保存・引用を生む。

| 優先度 | タイプ | 平均W-Score | 平均imp | 件数 | ガイダンス |
|--------|--------|------------|---------|------|-----------|
"""
    for rank, (ct, d) in enumerate(type_ranking, 1):
        guide = _generate_dynamic_guidance(ct, d, type_ranking, n)
        source_a += f"| {rank} | {ct} | {d['avg_w_score']} | {d['avg_imp']:,} | {d['count']} | {guide} |\n"

    source_a += f"""
### 独自性の効果

{orig_insight if orig_insight else "データ不足"}

### 画像の効果

{media_insight if media_insight else "データ不足"}

### ニュース飽和度

{sat_insight if sat_insight else "ニュース系ツイートのデータ不足"}

### レピュテーションリスク

{risk_insight if risk_insight else "データ不足"}
"""

    # --- マルチソース対応: 既存ファイルのソースB以降を保持 ---
    STRATEGY_REF_PATH.parent.mkdir(parents=True, exist_ok=True)
    header = "# コンテンツ戦略リファレンス\n\ncontent_evaluator.py / buzz_content_analyzer.py が自動生成。ツイート生成スキルのネタ選定・方向性判断に使用。\n\n"
    preserved_sections = ""

    if STRATEGY_REF_PATH.exists():
        existing = STRATEGY_REF_PATH.read_text(encoding="utf-8")
        # ソースB以降のセクションを抽出して保持
        source_b_marker = "## ソースB:"
        idx = existing.find(source_b_marker)
        if idx != -1:
            preserved_sections = "\n---\n\n" + existing[idx:]

    md = header + source_a
    if preserved_sections:
        md += preserved_sections
    else:
        # ソースBがまだない場合はソースAだけで完結
        md += """
---

## ネタ選定ガイダンス

- **BIP・体験談を優先**: 独自体験は代替不可。具体的な数字・苦労・発見を含めると高スコア
- **ニュースは速報性が命**: 飽和度がmainstream以降だとW-Scoreが大幅低下
- **独自分析を加える**: 同じネタでも自分の体験・データ・視点を加えるとスコア向上
- **画像は補強として有効**: imp増加効果あり。ただし画像に頼りすぎない（テキストの質が本質）
"""

    STRATEGY_REF_PATH.write_text(md, encoding="utf-8")
    print(f"[OK] 戦略リファレンス更新（ソースA）: {STRATEGY_REF_PATH}")


# --- メイン ---

async def async_main(args):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[ERROR] GROQ_API_KEY が環境変数に未設定")
        sys.exit(1)

    print("=== コンテンツ評価分析 ===")

    # ツイート詳細読み込み
    details = load_tweet_details()
    # textフィールドがあるツイートのみ対象（Phase 1拡充後のデータ）
    all_tweets = [t for t in details["tweets"] if t.get("text")]
    print(f"[INFO] text付きツイート: {len(all_tweets)}件 / 全{len(details['tweets'])}件")

    if not all_tweets:
        print("[WARN] 評価対象のツイートがありません")
        print("[HINT] daily_metrics.py を実行してデータを蓄積してください")
        return

    # 既存評価読み込み
    eval_data = load_evaluations()
    evaluated_ids = set(eval_data["evaluations"].keys())

    # 未分類ツイート抽出
    if args.force:
        target_tweets = all_tweets
        print(f"[INFO] --force: 全{len(target_tweets)}件を再評価")
    else:
        target_tweets = [t for t in all_tweets if t["id"] not in evaluated_ids]
        print(f"[INFO] 未分類: {len(target_tweets)}件（既分類: {len(evaluated_ids)}件）")

    # LLM分類実行
    if target_tweets:
        print(f"\n[1/3] Groq LLM 分類中...")
        classifications = await classify_tweets(target_tweets, api_key)

        # 評価結果をマージ
        for cls in classifications:
            tid = cls.get("tweet_id")
            if tid:
                eval_data["evaluations"][tid] = {
                    k: v for k, v in cls.items() if k != "tweet_index"
                }
        eval_data["last_updated"] = now_str()

        if not args.dry_run:
            save_evaluations(eval_data)
        else:
            print("[DRY-RUN] 評価データ保存スキップ")
            # dry-runでも分類結果を表示
            for cls in classifications:
                tid = cls.get("tweet_id", "?")
                ct = cls.get("content_type", "?")
                orig = cls.get("originality", "?")
                print(f"  {tid[:12]}... → {ct} | 独自性:{orig}")
    else:
        print("[INFO] 新規分類対象なし")

    # 分析実行
    print(f"\n[2/3] 多次元分析...")
    evals = eval_data["evaluations"]
    type_analysis = analyze_by_content_type(all_tweets, evals)
    media_analysis = analyze_media_effect(all_tweets, evals)
    orig_analysis = analyze_originality(all_tweets, evals)
    sat_analysis = analyze_news_saturation(all_tweets, evals)
    risk_analysis = analyze_reputation_risk(all_tweets, evals)

    # レポート生成
    print(f"\n[3/3] レポート生成...")
    report = generate_eval_report(
        all_tweets, evals,
        type_analysis, media_analysis, orig_analysis, sat_analysis,
        risk_analysis,
    )

    if not args.dry_run:
        filename = f"eval-{today_str()}.md"
        save_to_obsidian(OBSIDIAN_EVAL, filename, report)

        # ツイート生成スキル向け戦略サマリー更新
        generate_strategy_ref(
            all_tweets, evals,
            type_analysis, media_analysis, orig_analysis, sat_analysis,
            risk_analysis,
        )

        # Discord通知
        summary_lines = []
        for ct in sorted(type_analysis, key=lambda k: type_analysis[k]["avg_w_score"], reverse=True)[:3]:
            d = type_analysis[ct]
            summary_lines.append(f"{ct}: W-Score {d['avg_w_score']} ({d['count']}件)")

        notify_discord(
            f"**Content Evaluation** {today_str()}\n\n"
            f"評価: {len(evals)}件\n"
            + "\n".join(summary_lines)
        )
    else:
        print("\n--- レポートプレビュー ---")
        print(report[:1000])
        if len(report) > 1000:
            print(f"\n... ({len(report)}文字)")

    print(f"\n=== 完了 ===")
    print(f"評価済み: {len(evals)}件")


def main():
    parser = argparse.ArgumentParser(description="X コンテンツ多次元評価分析")
    parser.add_argument("--dry-run", action="store_true", help="分類のみ（保存・レポートなし）")
    parser.add_argument("--force", action="store_true", help="全ツイート再評価")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
