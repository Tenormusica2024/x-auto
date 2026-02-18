"""
saturation_quantifier.py - ニュース飽和度の定量計測

ai_newsツイートに対して、twscrapeで同トピックのツイート件数を実測し、
LLMの推測（first_mover/early/mainstream/late/rehash）を定量データで補強する。

仕組み:
  1. ai_newsツイートのテキストからトピックキーワードを抽出（Groq LLM）
  2. twscrapeでキーワード検索し、直近24-72hのツイート件数を計測
  3. 件数 + 時間経過 + キーパーソン出現率から飽和度スコアを算出

使い方（単体テスト）:
  python -X utf8 saturation_quantifier.py                    # 直近のai_newsで計測
  python -X utf8 saturation_quantifier.py --tweet-id <id>    # 特定ツイートで計測
  python -X utf8 saturation_quantifier.py --dry-run           # キーワード抽出のみ

連携:
  content_evaluator.py --quantitative  から呼び出される

コスト: $0.00（Groq無料枠 + twscrape非公式API）
"""

import asyncio
import json
import math
import os
import re
import sqlite3
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import Counter
from typing import Any

import httpx

# twscrape_patch適用
_PATCH_PATH = Path(
    os.environ.get(
        "TWSCRAPE_PATCH_DIR",
        str(Path.home() / "Documents" / "ai-buzz-extractor-dev" / "scripts"),
    )
)
sys.path.insert(0, str(_PATCH_PATH))
try:
    import twscrape_patch  # noqa: F401
except ImportError:
    pass

from twscrape import API

from dotenv import load_dotenv

# .env読み込み（パスは環境変数で上書き可能）
_ENV_PRIMARY = Path(
    os.environ.get(
        "X_AUTO_ENV_PATH",
        str(Path.home() / "x-auto-posting" / ".env"),
    )
)
_ENV_SECONDARY = Path(
    os.environ.get(
        "BUZZ_EXTRACTOR_ENV_PATH",
        str(Path.home() / "Documents" / "ai-buzz-extractor-dev" / ".env"),
    )
)
load_dotenv(_ENV_PRIMARY)
load_dotenv(_ENV_SECONDARY, override=False)

# === 定数 ===

ACCOUNTS_DB = Path(
    os.environ.get(
        "TWSCRAPE_ACCOUNTS_DB",
        str(Path.home() / "Documents" / "ai-buzz-extractor-dev" / "accounts.db"),
    )
)
DATA_DIR = Path(__file__).parent / "data"
KEY_PERSONS_PATH = DATA_DIR / "key_persons.json"
EVAL_PATH = DATA_DIR / "content_evaluations.json"

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
BACKOFF_SCHEDULE = [5, 15, 30, 60]

JST = timezone(timedelta(hours=9))

# twscrape検索の上限（飽和度計測用: 件数カウントが目的なので少なめ）
SATURATION_QUERY_LIMIT = 50

# クエリ間待機秒数（レート制限対策）
QUERY_DELAY = 2.0

# キーワード抽出時のツイートテキスト最大文字数
TWEET_TEXT_MAX_CHARS = 500

# --- スコア算出用の定数 ---

# 件数シグナルの正規化基準値（log1p(COUNT_SIGNAL_MAX)が1.0に対応）
COUNT_SIGNAL_MAX = 100
# 時間シグナルの最大時間（この経過で1.0に到達）
TIME_SIGNAL_MAX_HOURS = 72.0
# KPシグナルの最大人数（この人数で1.0に到達）
KP_SIGNAL_MAX_COUNT = 5.0
# 信頼度算出の基準サンプル数（この件数で信頼度1.0）
CONFIDENCE_SAMPLE_MAX = 30.0

# 重み付け合成の比率
WEIGHT_COUNT = 0.40
WEIGHT_TIME = 0.35
WEIGHT_KP = 0.25

# スコア→レベルの閾値
LEVEL_THRESHOLDS = [
    (0.15, "first_mover"),
    (0.35, "early"),
    (0.60, "mainstream"),
    (0.80, "late"),
]
LEVEL_DEFAULT = "rehash"

# 時間帯分布のバケットサイズ（時間単位）
HOURLY_BUCKET_SIZE = 6

# キーワード抽出プロンプト
KEYWORD_EXTRACTION_PROMPT = """\
あなたはX(Twitter)のニュース分析の専門家です。
以下のツイートからニュースの「トピック」を特定し、
X検索用のキーワードを生成してください。

## ルール
- ツイートが言及している**具体的なニュース・発表・リリース**を特定する
- **primary_keywordは「そのニュース固有」の2-4語フレーズにする（1語の固有名詞だけでは不可）**
  - 悪い例: "Codex"（一般的すぎる。Codex全般のツイートが全てヒットしてしまう）
  - 良い例: "Codex コードレビュー"（この記事固有のトピック）
  - 悪い例: "Claude Code"（常時流通するワード）
  - 良い例: "Claude Code Klaus"（この話題固有の組み合わせ）
- secondary_keywordsも同様に特定性の高いフレーズにする
- 一般的すぎる単語（「AI」「すごい」「ツール」等）は単独で使わない
- 日本語と英語の混合フレーズも可

## 入力ツイート

{tweet_text}

## 出力形式（JSON）
```json
{{
  "topic": "トピックの簡潔な説明（日本語）",
  "primary_keyword": "そのニュース固有の2-4語フレーズ（X検索用）",
  "secondary_keywords": ["補助フレーズ1", "補助フレーズ2"],
  "news_date_estimate": "推定発表日（YYYY-MM-DD or unknown）"
}}
```"""

# LLMレスポンスからJSONブロックを抽出する正規表現
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def log(msg: str, level: str = "INFO"):
    timestamp = datetime.now(JST).strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


# === レート制限チェック（buzz_tweet_extractor.pyと同じロジック） ===

def check_rate_limit() -> tuple[bool, str | None]:
    """accounts.dbからtwscrapeのレート制限状態を事前確認"""
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

        lock_time_utc = datetime.strptime(
            search_lock, "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)
        lock_time_jst = lock_time_utc.astimezone(JST)
        now = datetime.now(JST)

        if now >= lock_time_jst:
            return True, None
        else:
            return False, lock_time_jst.strftime("%H:%M:%S")

    except Exception as e:
        log(f"accounts.db読み込みエラー: {e}", "WARNING")
        return True, None
    finally:
        if conn:
            conn.close()


# === キーパーソンDB読み込み ===

def load_key_persons() -> dict[str, dict[str, Any]]:
    """key_persons.jsonからusername→情報の逆引き辞書を構築"""
    if not KEY_PERSONS_PATH.exists():
        return {}

    raw = json.loads(KEY_PERSONS_PATH.read_text(encoding="utf-8"))
    persons = raw.get("persons", {})

    # username→person_data の逆引き
    username_map: dict[str, dict[str, Any]] = {}
    for uid, pdata in persons.items():
        uname = pdata.get("username", "")
        if uname:
            username_map[uname.lower().lstrip("@")] = {
                "user_id": uid,
                "total_appearances": pdata.get("total_appearances", 0),
                "topics": pdata.get("topics", {}),
            }
    return username_map


# === LLMレスポンスからJSON抽出 ===

def _extract_json_from_llm(content: str) -> dict | None:
    """LLMレスポンス文字列からJSONオブジェクトを安全に抽出する"""
    # ```json ... ``` または ``` ... ``` ブロックを正規表現で取得
    match = _JSON_BLOCK_RE.search(content)
    if match:
        content = match.group(1).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


# === Groqでキーワード抽出 ===

async def extract_topic_keywords(
    tweet_text: str,
    api_key: str,
    http_client: httpx.AsyncClient | None = None,
) -> dict | None:
    """ツイートテキストからニューストピックのキーワードを抽出"""
    prompt = KEYWORD_EXTRACTION_PROMPT.format(
        tweet_text=tweet_text[:TWEET_TEXT_MAX_CHARS]
    )

    # 外部からクライアントを受け取れるように（接続プール再利用）
    own_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=30.0)

    try:
        for attempt in range(3):
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
                        "max_tokens": 300,
                    },
                )
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()

                parsed = _extract_json_from_llm(content)
                if parsed is None:
                    log(f"キーワード抽出パースエラー: JSONブロックが見つかりません", "ERROR")
                    return None
                return parsed

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    wait = BACKOFF_SCHEDULE[min(attempt, len(BACKOFF_SCHEDULE) - 1)]
                    log(f"Rate limited, {wait}秒待機...", "WARNING")
                    await asyncio.sleep(wait)
                    continue
                log(f"HTTP error: {e.response.status_code}", "ERROR")
                return None
            except (json.JSONDecodeError, KeyError) as e:
                log(f"キーワード抽出パースエラー: {e}", "ERROR")
                return None
            except Exception as e:
                log(f"キーワード抽出エラー: {e}", "ERROR")
                return None
    finally:
        if own_client:
            await client.aclose()

    return None


# === ツイート処理ヘルパー（Q1/Q2共通） ===

def _process_search_tweet(
    tweet,
    all_tweets: dict,
    key_persons: dict[str, dict[str, Any]],
    kp_found_usernames: set[str],
    kp_found: list[dict],
    cutoff_dt: datetime,
) -> bool:
    """検索結果の1ツイートを処理し、all_tweetsとkp_foundに追加する。

    Returns:
        True: 新規ツイートとして追加された / False: 重複or範囲外でスキップ
    """
    tid = tweet.id
    if tid in all_tweets:
        return False

    # 日付フィルタ: lookback_hours以内のツイートのみカウント
    if tweet.date:
        tweet_dt = (
            tweet.date.astimezone(JST)
            if tweet.date.tzinfo
            else tweet.date.replace(tzinfo=timezone.utc).astimezone(JST)
        )
        if tweet_dt < cutoff_dt:
            return False

    uname = tweet.user.username.lower() if tweet.user else ""
    is_kp = uname in key_persons

    all_tweets[tid] = {
        "created_at": tweet.date.isoformat() if tweet.date else "",
        "username": uname,
        "is_key_person": is_kp,
        "likes": tweet.likeCount or 0,
    }

    # KP重複チェック: setで O(1) 判定
    if is_kp and uname not in kp_found_usernames:
        kp_found_usernames.add(uname)
        kp_found.append({
            "username": uname,
            "appearances": key_persons[uname].get("total_appearances", 0),
        })

    return True


# === twscrapeで1クエリ実行 ===

async def _run_search_query(
    api: API,
    query: str,
    all_tweets: dict,
    key_persons: dict[str, dict[str, Any]],
    kp_found_usernames: set[str],
    kp_found: list[dict],
    cutoff_dt: datetime,
) -> int:
    """twscrapeで1つの検索クエリを実行し、新規追加件数を返す。

    レート制限検出時は -1 を返す。
    """
    added = 0
    try:
        async for tweet in api.search(query, limit=SATURATION_QUERY_LIMIT):
            if _process_search_tweet(
                tweet, all_tweets, key_persons,
                kp_found_usernames, kp_found, cutoff_dt,
            ):
                added += 1
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            log("レート制限検出（HTTP 429）", "WARNING")
            return -1
        log(f"検索エラー（HTTP {e.response.status_code}）: {e}", "ERROR")
    except Exception as e:
        # twscrape内部で発生する非HTTPのレート制限エラーもHTTPStatusErrorでない場合がある
        err_str = str(e).lower()
        if "429" in err_str or "rate" in err_str:
            log("レート制限検出", "WARNING")
            return -1
        log(f"検索エラー: {e}", "ERROR")
    return added


# === ツイート統計の集計 ===

def _aggregate_tweet_stats(
    all_tweets: dict, now: datetime
) -> tuple[Counter, datetime | None]:
    """all_tweetsから時間帯別分布と最古ツイートを集計する。"""
    hourly_dist: Counter = Counter()
    earliest: datetime | None = None

    for td in all_tweets.values():
        ca = td.get("created_at", "")
        if not ca:
            continue
        try:
            dt = datetime.fromisoformat(ca)
            if earliest is None or dt < earliest:
                earliest = dt
            hours_ago = (now - dt.astimezone(JST)).total_seconds() / 3600
            bucket = int(hours_ago // HOURLY_BUCKET_SIZE) * HOURLY_BUCKET_SIZE
            hourly_dist[f"{bucket}-{bucket + HOURLY_BUCKET_SIZE}h"] += 1
        except (ValueError, TypeError):
            pass

    return hourly_dist, earliest


# === twscrapeで飽和度計測 ===

async def measure_saturation(
    primary_keyword: str,
    secondary_keywords: list[str],
    key_persons: dict[str, dict[str, Any]],
    lookback_hours: int = 72,
) -> dict:
    """twscrapeでトピックの飽和度を実測する。

    Returns:
        {
            "primary_keyword": str,
            "primary_count": int,       # メインキーワードのツイート件数
            "secondary_count": int,     # 補助キーワードの追加件数
            "total_count": int,
            "key_person_count": int,    # キーパーソンの言及数
            "key_persons_found": list,  # 言及したキーパーソン名
            "earliest_mention": str,    # 最も古い言及のISO8601
            "hourly_distribution": dict,# 時間帯別ツイート件数
            "saturation_score": float,  # 0.0-1.0 の飽和度スコア
            "suggested_level": str,     # first_mover/early/mainstream/late/rehash
            "confidence": float,        # 信頼度（サンプルサイズに基づく）
        }
    """
    # レート制限チェック
    available, next_time = check_rate_limit()
    if not available:
        log(f"twscrapeレート制限中（解除: {next_time}）", "WARNING")
        return _empty_result("rate_limited")

    api = API(str(ACCOUNTS_DB))

    now = datetime.now(JST)
    since = (now - timedelta(hours=lookback_hours)).strftime("%Y-%m-%d")
    until = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    cutoff_dt = now - timedelta(hours=lookback_hours)

    all_tweets: dict = {}
    kp_found: list[dict] = []
    kp_found_usernames: set[str] = set()

    # --- Q1: メインキーワード（最も特定性が高い） ---
    primary_query = (
        f'{primary_keyword} -filter:retweets lang:ja '
        f"since:{since} until:{until}"
    )
    log(f"  Q1: {primary_query}")

    q1_result = await _run_search_query(
        api, primary_query, all_tweets, key_persons,
        kp_found_usernames, kp_found, cutoff_dt,
    )
    if q1_result == -1:
        return _empty_result("rate_limited_during_search")

    primary_count = len(all_tweets)
    log(f"  Q1結果: {primary_count}件")

    await asyncio.sleep(QUERY_DELAY)

    # --- Q2: 補助キーワード（最も特定性の高い1つだけ、レート制限対策） ---
    secondary_count = 0
    if secondary_keywords:
        sec_kw = secondary_keywords[0]
        secondary_query = (
            f'{sec_kw} -filter:retweets lang:ja '
            f"since:{since} until:{until}"
        )
        log(f"  Q2: {secondary_query}")

        q2_result = await _run_search_query(
            api, secondary_query, all_tweets, key_persons,
            kp_found_usernames, kp_found, cutoff_dt,
        )
        if q2_result >= 0:
            secondary_count = q2_result

    log(f"  Q2結果: +{secondary_count}件（合計: {len(all_tweets)}件）")

    # --- 統計集計 + スコア算出 ---
    total_count = len(all_tweets)
    kp_count = len(kp_found)

    hourly_dist, earliest = _aggregate_tweet_stats(all_tweets, now)

    saturation_score, suggested_level, confidence = _calculate_saturation(
        total_count=total_count,
        kp_count=kp_count,
        earliest=earliest,
        now=now,
        hourly_dist=hourly_dist,
    )

    return {
        "primary_keyword": primary_keyword,
        "primary_count": primary_count,
        "secondary_count": secondary_count,
        "total_count": total_count,
        "key_person_count": kp_count,
        "key_persons_found": kp_found,
        "earliest_mention": earliest.isoformat() if earliest else None,
        "hourly_distribution": dict(hourly_dist),
        "saturation_score": round(saturation_score, 3),
        "suggested_level": suggested_level,
        "confidence": round(confidence, 2),
    }


def _calculate_saturation(
    total_count: int,
    kp_count: int,
    earliest: datetime | None,
    now: datetime,
    hourly_dist: Counter,
) -> tuple[float, str, float]:
    """飽和度スコア（0.0-1.0）と推奨レベルを算出。

    3つのシグナルを重み付け合成:
    - 件数シグナル（40%）: ツイート件数の対数スケール
    - 時間シグナル（35%）: 最初の言及からの経過時間
    - KPシグナル（25%）: キーパーソンの言及率
    """
    # 件数が0なら first_mover 確定
    if total_count == 0:
        return 0.0, "first_mover", 0.3

    # --- 件数シグナル（0.0-1.0） ---
    # 0件=0.0, 5件=0.3, 15件=0.5, 50件=0.8, 100件以上=1.0
    count_signal = min(1.0, math.log1p(total_count) / math.log1p(COUNT_SIGNAL_MAX))

    # --- 時間シグナル（0.0-1.0） ---
    if earliest:
        hours_elapsed = (now - earliest.astimezone(JST)).total_seconds() / 3600
        # 2h=0.1, 6h=0.3, 12h=0.5, 24h=0.7, 48h=0.85, 72h=1.0
        time_signal = min(1.0, hours_elapsed / TIME_SIGNAL_MAX_HOURS)
    else:
        time_signal = 0.5  # 不明時は中間値

    # --- KPシグナル（0.0-1.0） ---
    # 0人=0.0, 1人=0.2, 3人=0.6, 5人以上=1.0
    kp_signal = min(1.0, kp_count / KP_SIGNAL_MAX_COUNT)

    # 重み付け合成
    saturation_score = (
        count_signal * WEIGHT_COUNT
        + time_signal * WEIGHT_TIME
        + kp_signal * WEIGHT_KP
    )

    # レベル判定（スコア→カテゴリ）
    level = LEVEL_DEFAULT
    for threshold, label in LEVEL_THRESHOLDS:
        if saturation_score < threshold:
            level = label
            break

    # 信頼度（サンプルサイズに基づく。30件以上=高信頼）
    confidence = min(1.0, total_count / CONFIDENCE_SAMPLE_MAX)

    return saturation_score, level, confidence


def _empty_result(reason: str) -> dict:
    """計測失敗時のデフォルト結果"""
    return {
        "primary_keyword": "",
        "primary_count": 0,
        "secondary_count": 0,
        "total_count": 0,
        "key_person_count": 0,
        "key_persons_found": [],
        "earliest_mention": None,
        "hourly_distribution": {},
        "saturation_score": -1.0,
        "suggested_level": "unknown",
        "confidence": 0.0,
        "error": reason,
    }


# === 対象ツイート取得（content_evaluations.jsonからai_newsを抽出） ===

def get_ai_news_tweets(limit: int = 5, tweet_id: str | None = None) -> list[dict]:
    """content_evaluations.jsonからai_newsツイートを取得。
    tweet_detailsからテキスト情報も結合する。
    """
    if not EVAL_PATH.exists():
        log("content_evaluations.json が見つかりません", "ERROR")
        return []

    eval_data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    evaluations = eval_data.get("evaluations", {})

    # tweet_details.jsonからテキスト情報を取得
    details_path = DATA_DIR / "tweet_details.json"
    text_map: dict[str, str] = {}
    if details_path.exists():
        details = json.loads(details_path.read_text(encoding="utf-8"))
        for t in details.get("tweets", []):
            text_map[t["id"]] = t.get("text", "")

    # 特定ツイート指定
    if tweet_id:
        ev = evaluations.get(tweet_id)
        if ev and ev.get("content_type") == "ai_news":
            return [{
                "id": tweet_id,
                "text": text_map.get(tweet_id, ""),
                "news_saturation_llm": ev.get("news_saturation", "n/a"),
            }]
        log(f"tweet_id={tweet_id} はai_newsではないか見つかりません", "WARNING")
        return []

    # ai_newsのみ抽出、最新順（evaluated_at降順）
    ai_news = []
    for tid, ev in evaluations.items():
        if ev.get("content_type") == "ai_news":
            text = text_map.get(tid, "")
            if text:
                ai_news.append({
                    "id": tid,
                    "text": text,
                    "news_saturation_llm": ev.get("news_saturation", "n/a"),
                    "evaluated_at": ev.get("evaluated_at", ""),
                })

    # 最新順ソート → 上位N件
    ai_news.sort(key=lambda x: x.get("evaluated_at", ""), reverse=True)
    return ai_news[:limit]


# === メイン ===

async def quantify_saturation(
    tweets: list[dict],
    api_key: str,
    dry_run: bool = False,
) -> list[dict]:
    """ai_newsツイートの飽和度を定量計測する。

    Returns:
        各ツイートの計測結果リスト
    """
    key_persons = load_key_persons()
    log(f"キーパーソンDB: {len(key_persons)}名ロード済み")

    results = []

    # httpxクライアントをループ全体で共有（接続プール再利用）
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        for i, tweet in enumerate(tweets):
            log(f"\n[{i+1}/{len(tweets)}] {tweet['id'][:12]}...")
            preview = tweet["text"][:80].replace("\n", " ")
            log(f"  テキスト: {preview}...")

            # Step 1: キーワード抽出
            keywords = await extract_topic_keywords(
                tweet["text"], api_key, http_client=http_client
            )
            if not keywords:
                log("  キーワード抽出失敗 → スキップ", "WARNING")
                results.append({
                    "tweet_id": tweet["id"],
                    "error": "keyword_extraction_failed",
                })
                continue

            log(f"  トピック: {keywords.get('topic', '?')}")
            log(f"  Primary: {keywords.get('primary_keyword', '?')}")
            log(f"  Secondary: {keywords.get('secondary_keywords', [])}")
            log(f"  LLM判定: {tweet.get('news_saturation_llm', '?')}")

            if dry_run:
                results.append({
                    "tweet_id": tweet["id"],
                    "keywords": keywords,
                    "llm_level": tweet.get("news_saturation_llm", "?"),
                    "dry_run": True,
                })
                continue

            # Step 2: twscrape計測
            measurement = await measure_saturation(
                primary_keyword=keywords["primary_keyword"],
                secondary_keywords=keywords.get("secondary_keywords", []),
                key_persons=key_persons,
            )

            # LLM判定との比較
            llm_level = tweet.get("news_saturation_llm", "n/a")
            quant_level = measurement["suggested_level"]
            match_status = "MATCH" if llm_level == quant_level else "DIFF"

            log(f"  計測結果: {measurement['total_count']}件 → {quant_level} (score={measurement['saturation_score']:.3f})")
            log(f"  KP言及: {measurement['key_person_count']}名")
            log(f"  LLM={llm_level} vs 実測={quant_level} [{match_status}]")

            results.append({
                "tweet_id": tweet["id"],
                "keywords": keywords,
                "llm_level": llm_level,
                "measurement": measurement,
                "match_status": match_status,
            })

            # ツイート間待機
            if i < len(tweets) - 1:
                await asyncio.sleep(QUERY_DELAY)

    return results


async def async_main(args):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        log("GROQ_API_KEY が環境変数に未設定", "ERROR")
        return 1

    log("=== ニュース飽和度 定量計測 ===")

    # 対象ツイート取得
    tweets = get_ai_news_tweets(
        limit=args.limit,
        tweet_id=args.tweet_id,
    )

    if not tweets:
        log("計測対象のai_newsツイートがありません", "WARNING")
        log("content_evaluator.py を先に実行してください", "HINT")
        return 0

    log(f"対象: {len(tweets)}件のai_newsツイート")

    # 計測実行
    results = await quantify_saturation(
        tweets, api_key, dry_run=args.dry_run,
    )

    # 結果サマリー
    log("\n=== 計測結果サマリー ===")
    match_count = sum(1 for r in results if r.get("match_status") == "MATCH")
    diff_count = sum(1 for r in results if r.get("match_status") == "DIFF")
    error_count = sum(1 for r in results if r.get("error"))

    log(f"  計測成功: {match_count + diff_count}件（一致: {match_count}, 不一致: {diff_count}）")
    if error_count:
        log(f"  エラー: {error_count}件")

    # 不一致の詳細
    for r in results:
        if r.get("match_status") == "DIFF":
            m = r["measurement"]
            log(
                f"  DIFF: {r['tweet_id'][:12]}... "
                f"LLM={r['llm_level']} vs 実測={m['suggested_level']} "
                f"(count={m['total_count']}, score={m['saturation_score']:.3f})"
            )

    # JSON出力（--outputオプション時）
    if args.output:
        output_path = DATA_DIR / "saturation_measurements.json"
        output_data = {
            "measured_at": datetime.now(JST).isoformat(),
            "total_measured": len(results),
            "match_count": match_count,
            "diff_count": diff_count,
            "results": results,
        }
        output_path.write_text(
            json.dumps(output_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log(f"結果保存: {output_path}")

    log("\n=== 完了 ===")
    return 0


def main():
    parser = argparse.ArgumentParser(description="ニュース飽和度の定量計測")
    parser.add_argument("--dry-run", action="store_true", help="キーワード抽出のみ（twscrape検索なし）")
    parser.add_argument("--tweet-id", type=str, help="特定ツイートIDを計測")
    parser.add_argument("--limit", type=int, default=5, help="計測対象件数（デフォルト: 5）")
    parser.add_argument("--output", action="store_true", help="結果をJSONファイルに保存")
    args = parser.parse_args()

    exit_code = asyncio.run(async_main(args))
    sys.exit(exit_code or 0)


if __name__ == "__main__":
    main()
