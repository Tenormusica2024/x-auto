"""
Indie Voice - AI駆動個人開発エンジニアの声を収集・分析・ツイート用データを準備するシステム

Usage:
    from indie_voice import RedditVoiceCollector, ContentClassifier, TweetDataPreparer
"""

from .collectors.reddit_collector import RedditVoiceCollector
from .analyzers.content_classifier import ContentClassifier, ClassificationResult
from .generators.tweet_generator import (
    TweetDataPreparer,
    TweetCandidate,
    GeneratedTweet,
    HumanTweetGenerator  # 後方互換性
)

__all__ = [
    'RedditVoiceCollector',
    'ContentClassifier',
    'ClassificationResult',
    'TweetDataPreparer',
    'TweetCandidate',
    'GeneratedTweet',
    'HumanTweetGenerator'
]

__version__ = '2.0.0'
