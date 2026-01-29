"""
Human-Like Tweet Generator
収集・分類した個人開発エンジニアの声から
Claudeがツイートを生成するための構造化データを提供

注: 実際のツイート生成はClaude（会話中）が担当
    このモジュールはデータ整形とエクスポートのみ
"""

import json
from typing import List, Dict, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class TweetCandidate:
    """Claudeに渡すツイート候補データ"""
    post_id: str
    category: str                  # failure, success, learning
    title: str                     # 元投稿のタイトル
    summary: str                   # 要約（日本語翻訳用）
    key_points: List[str]          # 核心ポイント
    numbers: List[str]             # 具体的な数字（期間、金額等）
    ai_tools: List[str]            # 言及されたAIツール
    emotion: str                   # 感情タイプ
    source_url: str                # 元投稿URL
    engagement: Dict               # スコア、コメント数等


@dataclass
class GeneratedTweet:
    """生成されたツイートを保持するデータクラス"""
    original_post_id: str
    category: str
    japanese_text: str
    character_count: int
    source_url: str
    key_insight: str
    emotion_tag: str


class TweetDataPreparer:
    """Claudeがツイート生成するためのデータを準備するクラス"""

    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / 'data'
        self.data_dir.mkdir(exist_ok=True)

    def prepare_candidate(self, post: Dict, classification: Dict) -> TweetCandidate:
        """
        投稿データと分類結果からツイート候補を作成

        Args:
            post: Reddit投稿データ
            classification: 分類結果

        Returns:
            TweetCandidate: Claudeに渡す構造化データ
        """
        import re

        # 数字情報を抽出
        full_text = f"{post.get('title', '')} {post.get('text', '')}"
        numbers = re.findall(
            r'\d+\s*(hours?|days?|weeks?|months?|\$[\d,]+|%|k\b|users?|MRR|ARR)',
            full_text, re.IGNORECASE
        )

        # 分類情報から取得（ClassificationResultオブジェクトまたはdict対応）
        if hasattr(classification, 'key_phrases'):
            key_phrases = classification.key_phrases
        else:
            key_phrases = classification.get('key_phrases', [])

        if hasattr(classification, 'summary'):
            summary = classification.summary
        else:
            summary = classification.get('summary', '')

        if hasattr(classification, 'primary_category'):
            category = classification.primary_category
        else:
            category = classification.get('primary_category', 'general')

        return TweetCandidate(
            post_id=post.get('id', ''),
            category=category,
            title=post.get('title', ''),
            summary=summary,
            key_points=key_phrases[:5],  # 最大5つ
            numbers=numbers[:3],  # 最大3つ
            ai_tools=post.get('ai_tools_mentioned', []),
            emotion=self._determine_emotion(category, classification),
            source_url=post.get('url', ''),
            engagement={
                'score': post.get('score', 0),
                'comments': post.get('num_comments', 0),
                'upvote_ratio': post.get('upvote_ratio', 0)
            }
        )

    def _determine_emotion(self, category: str, classification) -> str:
        """感情タイプを決定"""
        if hasattr(classification, 'emotional_intensity'):
            emotional_intensity = classification.emotional_intensity
        else:
            emotional_intensity = classification.get('emotional_intensity', 0)

        emotions = {
            'failure': ('frustration', 'reflection')[emotional_intensity < 0.5],
            'success': ('excitement', 'satisfaction')[emotional_intensity < 0.5],
            'learning': ('discovery', 'insight')[emotional_intensity < 0.5],
        }
        return emotions.get(category, 'neutral')

    def prepare_batch(
        self,
        classified_posts: List[Tuple[Dict, Dict]]
    ) -> List[TweetCandidate]:
        """複数の投稿からツイート候補を一括作成"""
        candidates = []
        for post, classification in classified_posts:
            candidate = self.prepare_candidate(post, classification)
            candidates.append(candidate)
        return candidates

    def export_candidates(
        self,
        candidates: List[TweetCandidate],
        filename: str = None
    ) -> str:
        """ツイート候補をJSONファイルに出力"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"tweet_candidates_{timestamp}.json"

        filepath = self.data_dir / filename

        export_data = [asdict(c) for c in candidates]

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"Exported {len(export_data)} candidates to {filepath}")
        return str(filepath)

    def format_for_claude(self, candidates: List[TweetCandidate]) -> str:
        """
        Claudeがツイート生成しやすい形式でフォーマット

        この出力をClaudeに渡してツイート生成を依頼する
        """
        output = []
        output.append("=" * 60)
        output.append("TWEET GENERATION REQUEST")
        output.append("=" * 60)
        output.append("")
        output.append("## Instructions")
        output.append("- Generate Japanese tweets (max 280 chars)")
        output.append("- No emojis")
        output.append("- Natural, human-like tone")
        output.append("- Include specific numbers if available")
        output.append("- Keep AI tool names (Claude, Cursor, etc.)")
        output.append("")

        for i, c in enumerate(candidates, 1):
            output.append(f"--- Candidate {i} [{c.category}] ---")
            output.append(f"Title: {c.title}")
            output.append(f"Summary: {c.summary}")
            output.append(f"Key Points: {', '.join(c.key_points) if c.key_points else 'None'}")
            output.append(f"Numbers: {', '.join(c.numbers) if c.numbers else 'None'}")
            output.append(f"AI Tools: {', '.join(c.ai_tools) if c.ai_tools else 'None'}")
            output.append(f"Emotion: {c.emotion}")
            output.append(f"Engagement: score={c.engagement['score']}, comments={c.engagement['comments']}")
            output.append(f"Source: {c.source_url}")
            output.append("")

        return "\n".join(output)


# 後方互換性のためのエイリアス
class HumanTweetGenerator(TweetDataPreparer):
    """後方互換性のためのエイリアスクラス"""

    def __init__(self, gemini_api_key: str = None):
        super().__init__()
        # Gemini APIは使用しない（Claudeが生成するため）
        self.model = None

    def generate(self, post: Dict, classification: Dict, use_ai: bool = True) -> GeneratedTweet:
        """
        後方互換性のための生成メソッド

        実際のツイート生成はClaudeが行うため、
        ここではプレースホルダーを返す
        """
        candidate = self.prepare_candidate(post, classification)

        # プレースホルダーテキスト（Claudeが後で置換）
        placeholder = f"[CLAUDE_GENERATE: {candidate.category}] {candidate.title[:50]}..."

        return GeneratedTweet(
            original_post_id=candidate.post_id,
            category=candidate.category,
            japanese_text=placeholder,
            character_count=len(placeholder),
            source_url=candidate.source_url,
            key_insight=candidate.key_points[0] if candidate.key_points else '',
            emotion_tag=candidate.emotion
        )

    def generate_batch(
        self,
        classified_posts: List[Tuple[Dict, Dict]],
        use_ai: bool = True,
        limit: int = 10
    ) -> List[GeneratedTweet]:
        """後方互換性のためのバッチ生成"""
        tweets = []
        for post, classification in classified_posts[:limit]:
            tweet = self.generate(post, classification, use_ai)
            tweets.append(tweet)
        return tweets

    def export_tweets(self, tweets: List[GeneratedTweet], filename: str = None) -> str:
        """生成したツイートをJSONファイルに出力"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"generated_tweets_{timestamp}.json"

        filepath = self.data_dir / filename

        export_data = [
            {
                'original_post_id': t.original_post_id,
                'category': t.category,
                'japanese_text': t.japanese_text,
                'character_count': t.character_count,
                'source_url': t.source_url,
                'key_insight': t.key_insight,
                'emotion_tag': t.emotion_tag
            }
            for t in tweets
        ]

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"Exported {len(export_data)} tweets to {filepath}")
        return str(filepath)

    def preview_tweets(self, tweets: List[GeneratedTweet]) -> None:
        """生成したツイートをプレビュー表示"""
        print("")
        print("=" * 60)
        print("GENERATED TWEETS PREVIEW")
        print("=" * 60)

        for i, tweet in enumerate(tweets, 1):
            print(f"")
            print(f"--- Tweet {i} [{tweet.category}] ({tweet.character_count} chars) ---")
            print(tweet.japanese_text)
            print(f"Source: {tweet.source_url}")
            print(f"Emotion: {tweet.emotion_tag}")


def main():
    """テスト実行"""
    preparer = TweetDataPreparer()

    # テストデータ
    test_posts = [
        {
            'id': 'test1',
            'title': 'I wasted 3 days trying to get Claude Code to work on my legacy codebase',
            'text': '''Honestly, I thought AI coding tools would be a game changer.
            But after 3 days of debugging hallucinated code, I'm ready to give up.
            Spent literally 8 hours on one function that I could have written in 30 minutes.''',
            'url': 'https://reddit.com/r/vibecoding/test1',
            'ai_tools_mentioned': ['claude', 'claude code'],
            'score': 245,
            'num_comments': 67,
            'upvote_ratio': 0.89
        },
        {
            'id': 'test2',
            'title': 'Shipped my first SaaS in 2 weeks using Cursor + Claude',
            'text': '''Finally launched! $500 MRR in the first month.
            The key was using Claude for architecture decisions and Cursor for implementation.
            Pro tip: Don't let AI write tests - it's terrible at edge cases.''',
            'url': 'https://reddit.com/r/vibecoding/test2',
            'ai_tools_mentioned': ['cursor', 'claude'],
            'score': 892,
            'num_comments': 134,
            'upvote_ratio': 0.95
        }
    ]

    test_classifications = [
        {
            'primary_category': 'failure',
            'key_phrases': ['3 days of debugging', 'hallucinated code', 'legacy codebase'],
            'emotional_intensity': 0.7,
            'summary': 'AI coding tools struggle with legacy codebases, causing frustration'
        },
        {
            'primary_category': 'success',
            'key_phrases': ['$500 MRR first month', 'Shipped in 2 weeks', 'Claude for architecture'],
            'emotional_intensity': 0.8,
            'summary': 'Built and launched SaaS quickly using AI tools'
        }
    ]

    print("=== Tweet Data Preparation Test ===")
    print("")

    # 候補を準備
    candidates = []
    for post, classification in zip(test_posts, test_classifications):
        candidate = preparer.prepare_candidate(post, classification)
        candidates.append(candidate)

    # Claudeへの出力フォーマット
    print(preparer.format_for_claude(candidates))

    # ファイルにエクスポート
    preparer.export_candidates(candidates)


if __name__ == '__main__':
    main()
