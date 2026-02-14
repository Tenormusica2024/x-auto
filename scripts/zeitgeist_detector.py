"""
zeitgeist_detector.py - AI界隈の時流（ムード）検知システム

ai-buzz-extractor が収集したツイートデータを分析し、
日本のAI界隈の「空気感」をスナップショットとして出力する。
ツイート生成パイプラインがこのスナップショットを参照して
トーンやトピック選定を微調整する。

依存:
- ai-buzz-extractor の ai_buzz.db（SQLite直接クエリ）
- Groq API (llama-3.3-70b-versatile) - classifier.pyと同じパターン
- x_client.py の共有インフラ（Discord通知・Obsidian保存・パス定数）
"""

import asyncio
import json
import logging
import math
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

# x_client.py の共有インフラをインポート
sys.path.insert(0, str(Path(__file__).parent))
from x_client import (
    notify_discord,
    save_to_obsidian,
    DATA_DIR,
    OBSIDIAN_BASE,
    today_str,
    now_str,
)

load_dotenv(Path(r"C:\Users\Tenormusica\x-auto-posting\.env"))
# GROQ_API_KEYはai-buzz-extractor-devの.envに格納
load_dotenv(Path(r"C:\Users\Tenormusica\Documents\ai-buzz-extractor-dev\.env"), override=False)
load_dotenv(Path(r"C:\Users\Tenormusica\Documents\ai-buzz-extractor\.env"), override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# --- 定数 ---
AI_BUZZ_DB = Path(r"C:\Users\Tenormusica\ai-buzz-extractor\ai_buzz.db")
AI_BUZZ_JSON = Path(r"C:\Users\Tenormusica\Documents\ai-buzz-extractor\data.json")
BUZZ_TWEETS_JSON = DATA_DIR / "buzz-tweets-latest.json"  # buzz_tweet_extractor.pyの出力
SNAPSHOT_PATH = DATA_DIR / "zeitgeist-snapshot.json"
OBSIDIAN_ZEITGEIST = OBSIDIAN_BASE / "zeitgeist"

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# ムードカテゴリ定義
MOOD_CATEGORIES = [
    "excitement",   # 新技術・新リリースへの興奮・期待
    "anxiety",      # AIの進化に対する不安・仕事を奪われる恐怖
    "fatigue",      # AI疲れ・情報過多・ついていけない感
    "pragmatic",    # 実用的な活用報告・淡々とした技術共有
    "skepticism",   # AI過大評価への疑問・本当に使えるの？
    "controversy",  # 賛否両論・倫理議論・意見が割れてる
    "humor",        # ネタ・ジョーク・AI面白体験
]

# ムード→トーンガイダンス マッピング
TONE_GUIDANCE_MAP = {
    "excitement": {
        "recommended_approach": "ride_the_wave",
        "framing_advice": "盛り上がりに乗りつつ冷静な技術的視点を加える。「試してみたけど確かにいい」という当事者トーンが有効",
        "avoid": ["冷水を浴びせる表現", "過度な慎重論", "盛り上がりの否定"],
        "topic_affinity": {
            "high": ["新リリースの技術解説", "ベンチマーク比較", "実際に試してみた系"],
            "medium": ["関連ツール紹介", "今後の展望"],
            "low": ["慎重論", "リスク懸念の列挙"],
        },
    },
    "anxiety": {
        "recommended_approach": "empathetic_pragmatic",
        "framing_advice": "不安に共感しつつ具体的に今やれることを示す。「大丈夫」とは言わない。現実を認めた上で自分がどう動いてるかを淡々と共有",
        "avoid": ["楽観論の押し付け", "不安の否定", "煽り"],
        "topic_affinity": {
            "high": ["実用Tips", "個人開発者の生存戦略", "AIと共存する具体的方法"],
            "medium": ["新モデルの技術解説", "ツール比較"],
            "low": ["企業の資金調達", "抽象的な未来予測"],
        },
    },
    "fatigue": {
        "recommended_approach": "low_pressure_value",
        "framing_advice": "軽く読める実用Tips。「まとめたから使って」スタイル。情報疲れしてる人にも負担をかけない密度",
        "avoid": ["長文での解説", "新概念の導入", "危機感の煽り"],
        "topic_affinity": {
            "high": ["すぐ使えるTips", "コピペ可能な設定", "時短テクニック"],
            "medium": ["軽いツール紹介", "小さな改善報告"],
            "low": ["大型アップデートの網羅的解説", "業界全体の動向分析"],
        },
    },
    "pragmatic": {
        "recommended_approach": "deep_dive",
        "framing_advice": "同じ実務派に向けた密度の高い情報。技術的深掘りが歓迎される空気",
        "avoid": ["表面的な紹介", "感情的な表現", "過度な簡略化"],
        "topic_affinity": {
            "high": ["技術的深掘り", "実装詳細", "パフォーマンス比較"],
            "medium": ["新ツール紹介", "ワークフロー改善"],
            "low": ["抽象的な議論", "感情的な話題"],
        },
    },
    "skepticism": {
        "recommended_approach": "evidence_based",
        "framing_advice": "数値やベンチマークで裏付けた客観的な評価。「実際に測ってみたらこうだった」が刺さる",
        "avoid": ["根拠なき楽観", "メーカー発表の鵜呑み", "無条件の推奨"],
        "topic_affinity": {
            "high": ["ベンチマーク結果", "実測データ", "競合比較"],
            "medium": ["技術的な制約の解説", "代替手段の提案"],
            "low": ["プレスリリースの転載", "発表内容のまとめ"],
        },
    },
    "controversy": {
        "recommended_approach": "balanced_perspective",
        "framing_advice": "両論併記しつつ自分の立場を明確にする。「こういう見方もあるけど自分はこう思う」",
        "avoid": ["一方的な断定", "論争を煽る表現", "中立を装った逃げ"],
        "topic_affinity": {
            "high": ["多角的な分析", "自分のスタンス表明", "具体的な根拠付き意見"],
            "medium": ["関連する技術的事実", "歴史的経緯"],
            "low": ["感情的な煽り", "極端な立場"],
        },
    },
    "humor": {
        "recommended_approach": "lighthearted_insight",
        "framing_advice": "ネタを入口に技術的な気づきへ繋げる。軽い空気感を活かしつつ情報価値も提供",
        "avoid": ["真面目すぎる解説", "説教っぽいトーン", "ユーモアの否定"],
        "topic_affinity": {
            "high": ["面白いAI活用事例", "意外な発見", "AI生成物のネタ"],
            "medium": ["軽いTips", "ツールの裏技"],
            "low": ["深刻な話題", "規制・倫理議論"],
        },
    },
}

# --- センチメント分析プロンプト ---
MOOD_ANALYSIS_PROMPT = """あなたはX(Twitter)の日本語AI界隈のムード分析の専門家です。
以下のツイートを読み、発信者とそれに反応しているコミュニティの感情・スタンスを分類してください。

ムードカテゴリ:
- excitement: 新技術・新リリースへの興奮・期待・ワクワク感
- anxiety: AIの進化に対する不安・仕事を奪われる恐怖・将来への懸念
- fatigue: AI疲れ・情報過多・「もうついていけない」感
- pragmatic: 実用的な活用報告・淡々とした技術共有・Tips系
- skepticism: AI過大評価への疑問・「本当に使えるの?」感
- controversy: 意見が割れてる論争・賛否両論・倫理議論
- humor: ネタ・ジョーク・AI面白体験

ツイート内容:
{tweet_text}

出力形式（JSONのみ、説明不要）:
{{"mood": "カテゴリ名", "intensity": 0.0から1.0, "topic_hint": "何についての話か20字以内"}}"""


class MoodClassifier:
    """Groq APIを使ったツイートムード分類器（classifier.pyのパターン横展開）"""

    # 429リトライ時の段階的バックオフ（秒）。Retry-Afterヘッダーがない場合に使用
    BACKOFF_SCHEDULE = [5, 15, 30, 60]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set")
        self.client = httpx.AsyncClient(timeout=30.0)
        self._closed = False
        self.error_count = 0
        self.total_requests = 0

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self.client.aclose()

    async def __aenter__(self) -> "MoodClassifier":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def classify_mood(self, tweet_text: str) -> dict:
        """
        1ツイートのムードを分類

        Returns:
            {"mood": str, "intensity": float, "topic_hint": str}
        """
        self.total_requests += 1

        # 長すぎるツイートは切り詰め
        if len(tweet_text) > 2000:
            tweet_text = tweet_text[:2000] + "..."

        prompt = MOOD_ANALYSIS_PROMPT.format(tweet_text=tweet_text)

        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    GROQ_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": GROQ_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 100,
                    },
                )
                response.raise_for_status()

                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()

                # JSON部分を抽出（```json ... ``` で囲まれている場合も対応）
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()

                parsed = json.loads(content)
                mood = parsed.get("mood", "pragmatic")
                intensity = float(parsed.get("intensity", 0.5))
                topic_hint = parsed.get("topic_hint", "")

                # ムード名の正規化
                if mood.lower() not in MOOD_CATEGORIES:
                    logger.warning(f"Unknown mood '{mood}', defaulting to 'pragmatic'")
                    mood = "pragmatic"
                    intensity = 0.3

                return {"mood": mood.lower(), "intensity": intensity, "topic_hint": topic_hint}

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    if attempt < max_retries - 1:
                        # Retry-Afterヘッダー優先、なければ段階的バックオフ
                        retry_after = e.response.headers.get("retry-after")
                        if retry_after:
                            try:
                                wait_time = float(retry_after) + 1  # 数値秒 + 1秒マージン
                            except ValueError:
                                # HTTP-date形式（RFC 7231）の場合はバックオフにフォールバック
                                logger.warning(f"Non-numeric Retry-After '{retry_after}', using backoff schedule")
                                wait_time = self.BACKOFF_SCHEDULE[min(attempt, len(self.BACKOFF_SCHEDULE) - 1)]
                        else:
                            wait_time = self.BACKOFF_SCHEDULE[min(attempt, len(self.BACKOFF_SCHEDULE) - 1)]
                        logger.warning(f"Rate limited (429), retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # 全リトライ消費: 通常エラーと区別するために専用ログ
                        self.error_count += 1
                        logger.error(f"Rate limit (429) persists after {max_retries} retries - giving up on this tweet")
                        break
                self.error_count += 1
                logger.error(f"Mood classification HTTP error ({e.response.status_code}): {e}")
                break

            except (json.JSONDecodeError, Exception) as e:
                self.error_count += 1
                logger.error(f"Mood classification error: {e}")
                break

        error_rate = self.error_count / self.total_requests if self.total_requests > 0 else 0
        if error_rate > 0.8 and self.total_requests >= 20:
            raise RuntimeError(
                f"Mood classification error rate too high: {error_rate:.1%} "
                f"({self.error_count}/{self.total_requests})"
            )

        return {"mood": "pragmatic", "intensity": 0.3, "topic_hint": ""}

    async def classify_batch(
        self,
        tweets: list[dict],
        batch_size: int = 1,
        delay: float = 2.5,
    ) -> list[dict]:
        """
        複数ツイートを一括ムード分類（Groq free tier RPM 30対策: シリアル実行 + 2.5秒待機 + 429リトライ）

        batch_size=1, delay=2.5 → 24 RPM（Groq無料枠RPM 30以内）。
        batch_size=3だと実効60 RPMになり429連発するため、シリアル化して確実にRPM内に収める。

        Args:
            tweets: [{"text": str, "likes": int, "retweets": int, ...}, ...]
            batch_size: バッチサイズ（並列実行数、free tierは1推奨）
            delay: バッチ間の待機時間（秒）

        Returns:
            [{"mood": str, "intensity": float, "topic_hint": str, "tweet": dict}, ...]
        """
        results = []

        for i in range(0, len(tweets), batch_size):
            batch = tweets[i : i + batch_size]
            batch_results = await asyncio.gather(
                *[self.classify_mood(t["text"]) for t in batch],
                return_exceptions=True,
            )

            for tweet, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Batch mood error: {result}")
                    results.append({
                        "mood": "pragmatic",
                        "intensity": 0.3,
                        "topic_hint": "",
                        "tweet": tweet,
                    })
                else:
                    result["tweet"] = tweet
                    results.append(result)

            # バッチ間待機（最後のバッチ以外）
            if i + batch_size < len(tweets):
                await asyncio.sleep(delay)

            logger.info(f"Progress: {min(i + batch_size, len(tweets))}/{len(tweets)} tweets analyzed")

        return results


def fetch_recent_tweets(hours: int = 24, limit: int = 50) -> list[dict]:
    """
    ツイートデータを取得（SQLite優先、なければJSON fallback）+ buzz-tweetsマージ

    データソース:
    1. SQLite (ai_buzz.db): 直近N時間のツイートをエンゲージメント順で取得
    2. JSON (data.json): 全ツイートをエンゲージメント順で取得
    3. buzz-tweets-latest.json: buzz_tweet_extractor.pyの高エンゲージメントツイート

    buzz-tweetsは1,2のメインソースにマージし、重複排除してエンゲージメント順でソート。
    ai-buzz-extractorが拾えない悲観論・規制系ツイートを補完する。
    """
    # メインソースからツイート取得
    main_tweets = []
    if AI_BUZZ_DB.exists():
        main_tweets = _fetch_from_sqlite(hours, limit)
    elif AI_BUZZ_JSON.exists():
        main_tweets = _fetch_from_json(hours, limit)
    else:
        logger.warning(f"No main data source: {AI_BUZZ_DB} / {AI_BUZZ_JSON}")

    # buzz-tweetsをマージ（存在すれば）
    buzz_tweets = _fetch_from_buzz_json()
    if buzz_tweets:
        main_tweets = _merge_tweets(main_tweets, buzz_tweets, limit)

    if not main_tweets:
        logger.error("No tweets from any source")

    return main_tweets


def _fetch_from_sqlite(hours: int, limit: int) -> list[dict]:
    """SQLiteからツイート取得"""
    conn = None
    try:
        conn = sqlite3.connect(str(AI_BUZZ_DB), timeout=5)
        conn.row_factory = sqlite3.Row

        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        since_str = since.isoformat()

        query = """
            SELECT id, created_at, username, text, likes, retweets, quotes, replies, url, lang, category
            FROM tweets
            WHERE created_at >= ?
              AND lang = 'ja'
            ORDER BY (likes + retweets * 2 + quotes * 3) DESC
            LIMIT ?
        """

        rows = conn.execute(query, (since_str, limit)).fetchall()
        tweets = [dict(row) for row in rows]
        logger.info(f"Fetched {len(tweets)} tweets from SQLite (last {hours}h, ja only)")
        return tweets
    except Exception as e:
        logger.error(f"DB query error: {e}")
        return []
    finally:
        if conn:
            conn.close()


def _fetch_from_json(hours: int, limit: int) -> list[dict]:
    """
    data.json からツイート取得（英語・日本語両方のフィールド名に対応）

    英語フィールド版: created_at, username, text, likes, retweets, quotes, replies, url, category
    日本語フィールド版: 投稿日時, ユーザー名, 本文, いいね, RT, 引用, 返信, URL, category
    """
    try:
        raw = json.loads(AI_BUZZ_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"JSON parse error: {e}")
        return []

    raw_tweets = raw.get("tweets", [])
    logger.info(f"Loaded {len(raw_tweets)} tweets from data.json")

    # フィールド名の自動検出（先頭ツイートで判定）
    is_english = False
    if raw_tweets and "text" in raw_tweets[0]:
        is_english = True
        logger.info("Detected English field names in data.json")
    else:
        logger.info("Detected Japanese field names in data.json")

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    filtered = []
    for t in raw_tweets:
        # 日時パース（日本時間として扱う）
        try:
            dt_str = t.get("created_at" if is_english else "投稿日時", "")
            # 複数の日時フォーマットに対応
            dt = None
            for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                try:
                    dt = datetime.strptime(dt_str[:len(fmt.replace("%", "x"))], fmt)
                    break
                except ValueError:
                    continue
            if dt is None:
                # ISO 8601形式（タイムゾーン付き）
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            else:
                dt = dt.replace(tzinfo=timezone(timedelta(hours=9)))

            # hours=0 なら時間フィルタ無効（全件）
            if hours > 0 and dt < since:
                continue
        except (ValueError, TypeError):
            pass  # パース失敗は含める（データ損失防止）

        # フィールド名を正規化（英語版はそのまま、日本語版は変換）
        if is_english:
            normalized = {
                "created_at": t.get("created_at", ""),
                "username": t.get("username", ""),
                "text": t.get("text", ""),
                "likes": t.get("likes", 0),
                "retweets": t.get("retweets", 0),
                "quotes": t.get("quotes", 0),
                "replies": t.get("replies", 0),
                "url": t.get("url", ""),
                "category": t.get("category", "未分類"),
            }
        else:
            normalized = {
                "created_at": t.get("投稿日時", ""),
                "username": t.get("ユーザー名", ""),
                "text": t.get("本文", ""),
                "likes": t.get("いいね", 0),
                "retweets": t.get("RT", 0),
                "quotes": t.get("引用", 0),
                "replies": t.get("返信", 0),
                "url": t.get("URL", ""),
                "category": t.get("category", "未分類"),
            }
        filtered.append(normalized)

    # エンゲージメント順でソート（_calc_engagementと同じ式）
    filtered.sort(key=_calc_engagement, reverse=True)

    result = filtered[:limit]
    logger.info(f"Fetched {len(result)} tweets from JSON (hours={hours}, limit={limit})")
    return result


def _fetch_from_buzz_json() -> list[dict]:
    """
    buzz-tweets-latest.json からツイート取得
    buzz_tweet_extractor.pyが06:30に生成するmin_faves:500の高品質ツイート。
    24時間以内のファイルのみ有効（古いデータは無視）。
    """
    if not BUZZ_TWEETS_JSON.exists():
        return []

    try:
        raw = json.loads(BUZZ_TWEETS_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"buzz-tweets JSON parse error: {e}")
        return []

    # ファイルの鮮度チェック（24時間以内のみ有効）
    generated_at = raw.get("generated_at", "")
    try:
        gen_dt = datetime.fromisoformat(generated_at)
        # tzinfo=Noneの場合はJSTとして扱う
        if gen_dt.tzinfo is None:
            gen_dt = gen_dt.replace(tzinfo=timezone(timedelta(hours=9)))
        age_hours = (datetime.now(gen_dt.tzinfo) - gen_dt).total_seconds() / 3600
        if age_hours > 24:
            logger.info(f"buzz-tweets is stale ({age_hours:.1f}h old) - skipping")
            return []
    except (ValueError, TypeError):
        pass  # パース失敗時は含める

    tweets = raw.get("tweets", [])
    # zeitgeist_detectorの正規化フォーマットに変換
    normalized = []
    for t in tweets:
        normalized.append({
            "created_at": t.get("created_at", ""),
            "username": t.get("username", ""),
            "text": t.get("text", ""),
            "likes": t.get("likes", 0),
            "retweets": t.get("retweets", 0),
            "quotes": t.get("quotes", 0),
            "replies": t.get("replies", 0),
            "url": t.get("url", ""),
            "category": "未分類",
            "_source": "buzz_extractor",  # ソース識別用
        })

    logger.info(f"Loaded {len(normalized)} tweets from buzz-tweets-latest.json")
    return normalized


def _calc_engagement(t: dict) -> int:
    """エンゲージメントスコア計算（拡散力・影響度重視: likes + RT*2 + quotes*3）

    NOTE: buzz_tweet_extractor側のcalculate_engagement()は quotes*5+replies*4+RT*2+likes*1 で
    「バズ度（議論性）」を測る別の式を使用。用途が異なるため意図的に別計算。
    本関数はzeitgeist内のソート・マージ・SQLiteクエリと一致させる統一式。
    """
    return t.get("likes", 0) + t.get("retweets", 0) * 2 + t.get("quotes", 0) * 3


def _merge_tweets(main: list[dict], buzz: list[dict], limit: int) -> list[dict]:
    """
    メインソースとbuzz-tweetsをマージ（重複排除 + エンゲージメント順ソート）
    URLベースで重複判定し、エンゲージメントスコアが高い方を残す。
    URLなしツイートもすべて保持する。
    """
    # URL → tweet のマップ（メインソース優先）
    seen_urls: dict[str, dict] = {}
    # URLなしツイートのリスト
    no_url_tweets: list[dict] = []

    for t in main:
        url = t.get("url", "")
        if url:
            seen_urls[url] = t
        else:
            no_url_tweets.append(t)

    # buzz-tweetsをマージ（重複は高エンゲージメント側を採用）
    for t in buzz:
        url = t.get("url", "")
        if not url:
            no_url_tweets.append(t)
            continue
        if url in seen_urls:
            existing = seen_urls[url]
            if _calc_engagement(t) > _calc_engagement(existing):
                seen_urls[url] = t
        else:
            seen_urls[url] = t

    merged = list(seen_urls.values()) + no_url_tweets
    merged.sort(key=_calc_engagement, reverse=True)

    result = merged[:limit]
    logger.info(f"Merged: {len(main)} main + {len(buzz)} buzz -> {len(merged)} unique -> {len(result)} (limit {limit})")
    return result


def aggregate_moods(classified: list[dict]) -> dict:
    """
    ムード分析結果をエンゲージメント重み付きで集約

    重み = intensity * log1p(likes + retweets * 2)
    → バズってるツイートほど界隈の空気を反映しているが、対数で極端な影響を緩和
    """
    weighted_scores = {mood: 0.0 for mood in MOOD_CATEGORIES}
    topic_hints_by_mood = {mood: [] for mood in MOOD_CATEGORIES}

    for item in classified:
        mood = item["mood"]
        intensity = item["intensity"]
        tweet = item["tweet"]

        # エンゲージメントで重み付け
        engagement = tweet.get("likes", 0) + tweet.get("retweets", 0) * 2
        weight = intensity * math.log1p(engagement)

        weighted_scores[mood] += weight

        # トピックヒントを収集（代表ツイート選定用）
        if item.get("topic_hint"):
            topic_hints_by_mood[mood].append({
                "hint": item["topic_hint"],
                "engagement": engagement,
                "text": tweet["text"][:80],
                "username": tweet.get("username", ""),
            })

    # 正規化
    total = sum(weighted_scores.values())
    if total == 0:
        # データなしの場合はpragmaticをデフォルトに
        return {
            "mood_distribution": {mood: 1.0 / len(MOOD_CATEGORIES) for mood in MOOD_CATEGORIES},
            "dominant_mood": "pragmatic",
            "dominant_score": 0.14,
            "secondary_mood": "excitement",
            "secondary_score": 0.14,
            "topic_hints_by_mood": topic_hints_by_mood,
        }

    distribution = {mood: score / total for mood, score in weighted_scores.items()}

    # ドミナントムード（最高スコア）
    sorted_moods = sorted(distribution.items(), key=lambda x: x[1], reverse=True)
    dominant_mood, dominant_score = sorted_moods[0]
    secondary_mood, secondary_score = sorted_moods[1]

    return {
        "mood_distribution": distribution,
        "dominant_mood": dominant_mood,
        "dominant_score": dominant_score,
        "secondary_mood": secondary_mood,
        "secondary_score": secondary_score,
        "topic_hints_by_mood": topic_hints_by_mood,
    }


def generate_snapshot(aggregated: dict, tweets_analyzed: int) -> dict:
    """zeitgeist-snapshot.json の完全なスナップショットを生成"""
    dominant = aggregated["dominant_mood"]
    guidance = TONE_GUIDANCE_MAP.get(dominant, TONE_GUIDANCE_MAP["pragmatic"])

    # トレンディングエモーション: ドミナント・セカンダリのトピックヒントから抽出
    trending = []
    for mood in [aggregated["dominant_mood"], aggregated["secondary_mood"]]:
        hints = aggregated["topic_hints_by_mood"].get(mood, [])
        # エンゲージメント上位3件のヒントを追加
        sorted_hints = sorted(hints, key=lambda x: x["engagement"], reverse=True)[:3]
        trending.extend([h["hint"] for h in sorted_hints if h["hint"]])
    # 重複除去しつつ順序保持
    seen = set()
    trending_unique = []
    for t in trending:
        if t not in seen:
            seen.add(t)
            trending_unique.append(t)

    # 代表ツイート（ドミナントムードのエンゲージメント上位3件）
    representative = []
    dominant_hints = aggregated["topic_hints_by_mood"].get(dominant, [])
    for h in sorted(dominant_hints, key=lambda x: x["engagement"], reverse=True)[:3]:
        representative.append({
            "text": h["text"],
            "username": h["username"],
            "mood": dominant,
            "engagement": h["engagement"],
        })

    # 前回スナップショットとの比較
    previous = _load_previous_snapshot()

    snapshot = {
        "generated_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "tweets_analyzed": tweets_analyzed,
        "dominant_mood": {
            "mood": dominant,
            "score": round(aggregated["dominant_score"], 3),
            "description": guidance["framing_advice"][:60],
        },
        "secondary_mood": {
            "mood": aggregated["secondary_mood"],
            "score": round(aggregated["secondary_score"], 3),
        },
        "mood_distribution": {
            k: round(v, 3) for k, v in aggregated["mood_distribution"].items()
        },
        "trending_emotions": trending_unique[:5],
        "representative_tweets": representative,
        "tone_guidance": guidance,
        "previous_snapshot": previous,
    }

    return snapshot


def _load_previous_snapshot() -> dict:
    """前回のスナップショットを読み込み（比較用）"""
    if not SNAPSHOT_PATH.exists():
        return {"dominant_mood": "unknown", "score": 0.0, "shift": "initial"}

    try:
        prev = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        prev_mood = prev.get("dominant_mood", {}).get("mood", "unknown")
        prev_score = prev.get("dominant_mood", {}).get("score", 0.0)
        return {
            "dominant_mood": prev_mood,
            "score": prev_score,
            "shift": "",  # 後で設定
        }
    except Exception:
        return {"dominant_mood": "unknown", "score": 0.0, "shift": "parse_error"}


def save_snapshot(snapshot: dict) -> None:
    """zeitgeist-snapshot.json を保存"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Snapshot saved: {SNAPSHOT_PATH}")


def save_obsidian_report(snapshot: dict) -> None:
    """Obsidian Vaultに日次ムードレポートを保存"""
    d = snapshot
    dm = d["dominant_mood"]
    sm = d["secondary_mood"]
    dist = d["mood_distribution"]

    # ムード分布を棒グラフ風に表現
    bar_lines = []
    for mood, score in sorted(dist.items(), key=lambda x: x[1], reverse=True):
        bar_len = int(score * 40)
        marker = " **<--**" if mood == dm["mood"] else ""
        bar_lines.append(f"| {mood:12s} | {'=' * bar_len:<40s} | {score:.1%}{marker} |")

    bars = "\n".join(bar_lines)

    # 代表ツイート
    rep_lines = []
    for t in d.get("representative_tweets", []):
        rep_lines.append(f"- @{t['username']}: {t['text']}... (eng: {t['engagement']})")
    reps = "\n".join(rep_lines) if rep_lines else "- (なし)"

    # トレンディングエモーション
    emotions = ", ".join(d.get("trending_emotions", ["(なし)"]))

    content = f"""# Zeitgeist Report - {today_str()}

## Summary
- **Dominant Mood**: {dm['mood']} ({dm['score']:.1%})
- **Secondary Mood**: {sm['mood']} ({sm['score']:.1%})
- **Tweets Analyzed**: {d['tweets_analyzed']}
- **Generated**: {d['generated_at']}

## Mood Distribution

| Mood | Distribution | Score |
|------|-------------|-------|
{bars}

## Trending Emotions
{emotions}

## Representative Tweets
{reps}

## Tone Guidance
- **Approach**: {d['tone_guidance']['recommended_approach']}
- **Framing**: {d['tone_guidance']['framing_advice']}
- **Avoid**: {', '.join(d['tone_guidance']['avoid'])}

## Previous Snapshot
- **Previous Mood**: {d['previous_snapshot']['dominant_mood']}
- **Shift**: {d['previous_snapshot'].get('shift', 'N/A')}
"""
    save_to_obsidian(OBSIDIAN_ZEITGEIST, f"zeitgeist-{today_str()}.md", content)


def detect_mood_shift(snapshot: dict) -> Optional[str]:
    """前回からのムードシフトを検出。シフトがあればDiscord通知用メッセージを返す"""
    prev = snapshot.get("previous_snapshot", {})
    prev_mood = prev.get("dominant_mood", "unknown")
    curr_mood = snapshot["dominant_mood"]["mood"]
    curr_score = snapshot["dominant_mood"]["score"]

    if prev_mood == "unknown" or prev_mood == curr_mood:
        # シフト更新
        snapshot["previous_snapshot"]["shift"] = f"{prev_mood} (stable)"
        return None

    shift_msg = f"{prev_mood} -> {curr_mood}"
    snapshot["previous_snapshot"]["shift"] = shift_msg

    return (
        f"**[Zeitgeist Shift Detected]**\n"
        f"Mood: {shift_msg}\n"
        f"Score: {curr_score:.1%}\n"
        f"Trending: {', '.join(snapshot.get('trending_emotions', []))}"
    )


async def run(hours: int = 24, limit: int = 50, dry_run: bool = False) -> dict:
    """メイン実行フロー"""
    logger.info(f"=== Zeitgeist Detector Start (last {hours}h, limit {limit}) ===")

    # 1. データ取得
    tweets = fetch_recent_tweets(hours=hours, limit=limit)
    if not tweets:
        logger.warning("No tweets found. Generating default snapshot.")
        snapshot = generate_snapshot(
            aggregate_moods([]),
            tweets_analyzed=0,
        )
        if not dry_run:
            save_snapshot(snapshot)
        return snapshot

    # 2. ムード分析（Groq free tier RPM 30: シリアル実行 + 2.5秒待機）
    async with MoodClassifier() as classifier:
        classified = await classifier.classify_batch(tweets, batch_size=1, delay=2.5)
        logger.info(
            f"Classification complete: {classifier.total_requests} requests, "
            f"{classifier.error_count} errors"
        )

    # 3. 集約
    aggregated = aggregate_moods(classified)

    # 4. スナップショット生成
    snapshot = generate_snapshot(aggregated, tweets_analyzed=len(tweets))

    # 5. ムードシフト検出
    shift_msg = detect_mood_shift(snapshot)

    if dry_run:
        logger.info("[DRY RUN] Snapshot not saved")
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return snapshot

    # 6. 保存
    save_snapshot(snapshot)
    save_obsidian_report(snapshot)

    # 7. Discord通知（シフト検出時のみ）
    if shift_msg:
        logger.info(f"Mood shift detected: {shift_msg}")
        notify_discord(shift_msg)

    dm = snapshot["dominant_mood"]
    logger.info(
        f"=== Zeitgeist Detector Complete ===\n"
        f"  Dominant: {dm['mood']} ({dm['score']:.1%})\n"
        f"  Tweets: {len(tweets)}\n"
    )

    return snapshot


def main():
    import argparse

    parser = argparse.ArgumentParser(description="AI界隈の時流（ムード）検知")
    parser.add_argument("--hours", type=int, default=24, help="分析対象の時間範囲（デフォルト: 24h）")
    parser.add_argument("--limit", type=int, default=50, help="分析対象のツイート上限（デフォルト: 50）")
    parser.add_argument("--dry-run", action="store_true", help="保存せずに結果を表示")
    args = parser.parse_args()

    asyncio.run(run(hours=args.hours, limit=args.limit, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
