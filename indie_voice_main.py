"""
Indie Voice - メイン実行スクリプト
r/vibecodingからAI開発者の声を収集し、Claudeがツイート生成するためのデータを準備

Usage:
    python indie_voice_main.py --collect          # 収集のみ
    python indie_voice_main.py --prepare          # 収集→分類→Claude用データ準備
    python indie_voice_main.py --test             # テストモード（API不要）
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# パスを追加（indie_voiceパッケージをインポート可能に）
sys.path.insert(0, str(Path(__file__).parent))

from indie_voice import RedditVoiceCollector, ContentClassifier
from indie_voice.generators import TweetDataPreparer, TweetCandidate


def collect_posts(args) -> list:
    """r/vibecodingから投稿を収集"""
    print("")
    print("=" * 60)
    print("STEP 1: Collecting posts from Reddit")
    print("=" * 60)

    collector = RedditVoiceCollector()

    if not collector.connect():
        print("")
        print("Reddit API not configured. Using test mode.")
        return get_test_posts()

    # 収集パラメータ
    subreddits = args.subreddits.split(',') if args.subreddits else ['vibecoding']
    sort_by = args.sort or 'hot'
    limit = args.limit or 30

    all_posts = []
    for subreddit in subreddits:
        print(f"")
        print(f"Collecting from r/{subreddit}...")
        posts = collector.collect_from_subreddit(
            subreddit_name=subreddit.strip(),
            sort_by=sort_by,
            limit=limit
        )
        all_posts.extend(posts)
        print(f"  -> Found {len(posts)} AI-related posts")

    if all_posts:
        filepath = collector.save_posts(all_posts)
        print(f"")
        print(f"Total collected: {len(all_posts)} posts")
        print(f"Saved to: {filepath}")

    return all_posts


def classify_posts(posts: list) -> list:
    """投稿を分類"""
    print("")
    print("=" * 60)
    print("STEP 2: Classifying posts")
    print("=" * 60)

    classifier = ContentClassifier()

    # 分類実行
    classified = classifier.classify_batch(posts)

    # 統計表示
    categories = {}
    for post, cls in classified:
        cat = cls.primary_category
        categories[cat] = categories.get(cat, 0) + 1

    print("")
    print("Classification Results:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count} posts")

    # 高ポテンシャルをフィルタ
    high_potential = classifier.filter_high_potential(posts, min_score=0.3)
    print(f"")
    print(f"High potential posts (score >= 0.3): {len(high_potential)}")

    # 保存
    if high_potential:
        filepath = classifier.export_classified(high_potential)
        print(f"Saved to: {filepath}")

    return high_potential


def prepare_for_claude(classified_posts: list) -> str:
    """Claudeがツイート生成できる形式でデータを準備"""
    print("")
    print("=" * 60)
    print("STEP 3: Preparing data for Claude")
    print("=" * 60)

    preparer = TweetDataPreparer()

    # 候補を準備
    candidates = preparer.prepare_batch(classified_posts)

    # ファイルにエクスポート
    filepath = preparer.export_candidates(candidates)

    # Claude用フォーマットを出力
    output = preparer.format_for_claude(candidates)
    print("")
    print(output)

    return filepath


def get_test_posts() -> list:
    """テスト用のサンプル投稿"""
    return [
        {
            'id': 'test1',
            'subreddit': 'vibecoding',
            'title': 'I wasted 3 days trying to get Claude Code to work on my legacy codebase',
            'text': '''Honestly, I thought AI coding tools would be a game changer.
            But after 3 days of debugging hallucinated code, I'm ready to give up.
            The tool kept suggesting fixes that introduced MORE bugs.
            Spent literally 8 hours on one function that I could have written in 30 minutes.
            Total nightmare. Never again for complex codebases.''',
            'author': 'frustrated_dev',
            'score': 245,
            'upvote_ratio': 0.89,
            'num_comments': 67,
            'url': 'https://reddit.com/r/vibecoding/test1',
            'created_utc': datetime.now().isoformat(),
            'collected_at': datetime.now().isoformat(),
            'experience_types': ['failure'],
            'has_numbers': True,
            'ai_tools_mentioned': ['claude', 'claude code']
        },
        {
            'id': 'test2',
            'subreddit': 'vibecoding',
            'title': 'Shipped my first SaaS in 2 weeks using Cursor + Claude',
            'text': '''Finally launched! $500 MRR in the first month.
            The key was using Claude for architecture decisions and Cursor for implementation.
            Pro tip: Don't let AI write tests - it's terrible at edge cases.
            But for CRUD operations? Absolutely game changing. 10x faster.''',
            'author': 'happy_founder',
            'score': 892,
            'upvote_ratio': 0.95,
            'num_comments': 134,
            'url': 'https://reddit.com/r/vibecoding/test2',
            'created_utc': datetime.now().isoformat(),
            'collected_at': datetime.now().isoformat(),
            'experience_types': ['success'],
            'has_numbers': True,
            'ai_tools_mentioned': ['cursor', 'claude']
        },
        {
            'id': 'test3',
            'subreddit': 'vibecoding',
            'title': 'What I learned after 6 months of vibe coding',
            'text': '''Here's my honest take after building 4 projects with AI tools:
            1. Great for greenfield, terrible for legacy
            2. Always review generated code - found 3 security bugs last week
            3. Best for boilerplate and boring tasks
            4. Still need to understand the code - AI is a tool, not a replacement
            The trick is knowing when to use it and when to write by hand.''',
            'author': 'veteran_coder',
            'score': 1234,
            'upvote_ratio': 0.97,
            'num_comments': 256,
            'url': 'https://reddit.com/r/vibecoding/test3',
            'created_utc': datetime.now().isoformat(),
            'collected_at': datetime.now().isoformat(),
            'experience_types': ['learning'],
            'has_numbers': True,
            'ai_tools_mentioned': ['vibe coding']
        }
    ]


def run_prepare_pipeline(args):
    """収集→分類→Claude用データ準備の完全パイプライン"""
    # Step 1: 収集
    posts = collect_posts(args)

    if not posts:
        print("")
        print("No posts collected. Exiting.")
        return

    # Step 2: 分類
    classified = classify_posts(posts)

    if not classified:
        print("")
        print("No high-potential posts found. Exiting.")
        return

    # Step 3: Claude用データ準備
    filepath = prepare_for_claude(classified)

    print("")
    print("=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Collected: {len(posts)} posts")
    print(f"Classified: {len(classified)} high-potential posts")
    print(f"Data exported to: {filepath}")
    print("")
    print("Next step: Use the data above to generate tweets with Claude")


def run_test_mode():
    """テストモード（API不要）"""
    print("")
    print("=" * 60)
    print("TEST MODE - Using sample data")
    print("=" * 60)

    # テストデータを使用
    posts = get_test_posts()
    print(f"Using {len(posts)} test posts")

    # 分類
    classified = classify_posts(posts)

    if not classified:
        print("")
        print("No posts passed classification. Exiting.")
        return

    # Claude用データ準備
    filepath = prepare_for_claude(classified)

    print("")
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print(f"Posts: {len(posts)}")
    print(f"Classified: {len(classified)}")
    print(f"Data exported to: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description='Indie Voice - AI開発者の声からツイート用データを準備'
    )

    parser.add_argument('--collect', action='store_true',
                       help='Collect posts from Reddit')
    parser.add_argument('--prepare', action='store_true',
                       help='Run full pipeline: collect -> classify -> prepare for Claude')
    parser.add_argument('--test', action='store_true',
                       help='Run in test mode with sample data')

    # 収集オプション
    parser.add_argument('--subreddits', type=str, default='vibecoding',
                       help='Comma-separated subreddit names (default: vibecoding)')
    parser.add_argument('--sort', type=str, default='hot',
                       choices=['hot', 'new', 'top', 'rising'],
                       help='Sort method (default: hot)')
    parser.add_argument('--limit', type=int, default=30,
                       help='Number of posts per subreddit (default: 30)')

    # 入力ファイルオプション
    parser.add_argument('--input', type=str,
                       help='Input JSON file for classification')

    args = parser.parse_args()

    # モード選択
    if args.test:
        run_test_mode()
    elif args.prepare:
        run_prepare_pipeline(args)
    elif args.collect:
        collect_posts(args)
    else:
        # デフォルト: テストモード
        print("No mode specified. Running test mode...")
        print("Use --help to see available options.")
        run_test_mode()


if __name__ == '__main__':
    main()
