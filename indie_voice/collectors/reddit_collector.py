"""
r/vibecoding Reddit Collector
AI駆動の個人開発エンジニアの体験談を収集するシステム
"""

import praw
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional


class RedditVoiceCollector:
    """r/vibecoding等からAI開発者の声を収集するクラス"""

    # AI開発関連のキーワード（これらを含む投稿を優先収集）
    AI_KEYWORDS = [
        'claude', 'claude code', 'cursor', 'copilot', 'gpt', 'chatgpt',
        'vibe coding', 'ai coding', 'ai tools', 'llm', 'gemini',
        'windsurf', 'codeium', 'tabnine', 'aider', 'replit'
    ]

    # 体験談を示すキーワード（失敗/成功/学び）
    EXPERIENCE_KEYWORDS = {
        'failure': [
            'failed', 'mistake', 'bug', 'broken', 'frustrated', 'wasted',
            'wrong', 'issue', 'problem', 'struggle', 'hours', 'debug',
            'gave up', 'nightmare', 'disaster', 'learned the hard way'
        ],
        'success': [
            'shipped', 'launched', 'built', 'completed', 'success', 'proud',
            'finally', 'achieved', 'works', 'done', 'finished', 'released',
            'first customer', 'mrr', 'revenue', 'paying users'
        ],
        'learning': [
            'learned', 'realized', 'discovered', 'tip', 'lesson', 'advice',
            'insight', 'understanding', 'figured out', 'now i know',
            'game changer', 'productivity', 'workflow', 'recommend'
        ]
    }

    # 収集対象のサブレディット
    TARGET_SUBREDDITS = [
        'vibecoding',       # 最優先: 87,000+ members
        'SideProject',      # 個人開発者コミュニティ
        'indiehackers',     # インディーハッカー
        'Entrepreneur',     # 起業家コミュニティ
        'learnprogramming'  # プログラミング学習者
    ]

    def __init__(self, client_id: str = None, client_secret: str = None, user_agent: str = None):
        """
        Reddit APIクライアントを初期化

        環境変数から認証情報を取得:
        - REDDIT_CLIENT_ID
        - REDDIT_CLIENT_SECRET
        - REDDIT_USER_AGENT
        """
        self.client_id = client_id or os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('REDDIT_CLIENT_SECRET')
        self.user_agent = user_agent or os.getenv('REDDIT_USER_AGENT', 'indie-voice-collector/1.0')

        self.reddit = None
        self.data_dir = Path(__file__).parent.parent / 'data'
        self.data_dir.mkdir(exist_ok=True)

    def connect(self) -> bool:
        """Reddit APIに接続"""
        if not self.client_id or not self.client_secret:
            print("Error: Reddit API credentials not found.")
            print("Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables.")
            return False

        try:
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent
            )
            # 接続テスト（read-onlyモード）
            self.reddit.read_only = True
            return True
        except Exception as e:
            print(f"Error connecting to Reddit: {e}")
            return False

    def _contains_ai_keywords(self, text: str) -> bool:
        """テキストにAI関連キーワードが含まれているか確認"""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.AI_KEYWORDS)

    def _classify_experience(self, text: str) -> List[str]:
        """テキストを体験タイプに分類（複数可）"""
        text_lower = text.lower()
        categories = []

        for category, keywords in self.EXPERIENCE_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                categories.append(category)

        return categories if categories else ['general']

    def _extract_numbers(self, text: str) -> List[str]:
        """テキストから数字表現を抽出（具体性の指標）"""
        patterns = [
            r'\d+\s*(hours?|days?|weeks?|months?)',  # 時間表現
            r'\$\d+[\d,]*',                          # 金額
            r'\d+%',                                  # パーセント
            r'\d+\s*(users?|customers?|downloads?)', # ユーザー数
            r'\d+k|\d+K',                            # K表記
        ]

        numbers = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            numbers.extend(matches)

        return numbers

    def collect_from_subreddit(
        self,
        subreddit_name: str = 'vibecoding',
        sort_by: str = 'hot',
        limit: int = 50,
        time_filter: str = 'week'
    ) -> List[Dict]:
        """
        指定サブレディットから投稿を収集

        Args:
            subreddit_name: サブレディット名
            sort_by: ソート方法 ('hot', 'new', 'top', 'rising')
            limit: 取得件数
            time_filter: 期間フィルター（'day', 'week', 'month', 'year', 'all'）

        Returns:
            収集した投稿のリスト
        """
        if not self.reddit:
            if not self.connect():
                return []

        subreddit = self.reddit.subreddit(subreddit_name)
        posts = []

        # ソート方法に応じて投稿を取得
        if sort_by == 'hot':
            submissions = subreddit.hot(limit=limit)
        elif sort_by == 'new':
            submissions = subreddit.new(limit=limit)
        elif sort_by == 'top':
            submissions = subreddit.top(time_filter=time_filter, limit=limit)
        elif sort_by == 'rising':
            submissions = subreddit.rising(limit=limit)
        else:
            submissions = subreddit.hot(limit=limit)

        for submission in submissions:
            # 削除された投稿やリンクのみの投稿をスキップ
            if submission.removed_by_category or not submission.selftext:
                continue

            full_text = f"{submission.title} {submission.selftext}"

            # AI関連キーワードでフィルタ
            if not self._contains_ai_keywords(full_text):
                continue

            post_data = {
                'id': submission.id,
                'subreddit': subreddit_name,
                'title': submission.title,
                'text': submission.selftext,
                'author': str(submission.author) if submission.author else '[deleted]',
                'score': submission.score,
                'upvote_ratio': submission.upvote_ratio,
                'num_comments': submission.num_comments,
                'url': f"https://reddit.com{submission.permalink}",
                'created_utc': datetime.fromtimestamp(submission.created_utc).isoformat(),
                'collected_at': datetime.now().isoformat(),

                # 分析メタデータ
                'experience_types': self._classify_experience(full_text),
                'has_numbers': len(self._extract_numbers(full_text)) > 0,
                'ai_tools_mentioned': [kw for kw in self.AI_KEYWORDS if kw in full_text.lower()],
            }

            posts.append(post_data)

        return posts

    def collect_all_subreddits(
        self,
        sort_by: str = 'hot',
        limit_per_sub: int = 30
    ) -> List[Dict]:
        """全ターゲットサブレディットから収集"""
        all_posts = []

        for sub_name in self.TARGET_SUBREDDITS:
            print(f"Collecting from r/{sub_name}...")
            try:
                posts = self.collect_from_subreddit(
                    subreddit_name=sub_name,
                    sort_by=sort_by,
                    limit=limit_per_sub
                )
                all_posts.extend(posts)
                print(f"  -> Collected {len(posts)} AI-related posts")
            except Exception as e:
                print(f"  -> Error: {e}")

        return all_posts

    def search_posts(
        self,
        query: str,
        subreddit: str = 'all',
        sort: str = 'relevance',
        time_filter: str = 'month',
        limit: int = 50
    ) -> List[Dict]:
        """
        キーワード検索で投稿を収集

        Args:
            query: 検索クエリ
            subreddit: 検索対象（'all'または特定のサブレディット名）
            sort: ソート方法 ('relevance', 'hot', 'top', 'new', 'comments')
            time_filter: 期間フィルター
            limit: 取得件数
        """
        if not self.reddit:
            if not self.connect():
                return []

        posts = []

        if subreddit == 'all':
            search_results = self.reddit.subreddit('all').search(
                query, sort=sort, time_filter=time_filter, limit=limit
            )
        else:
            search_results = self.reddit.subreddit(subreddit).search(
                query, sort=sort, time_filter=time_filter, limit=limit
            )

        for submission in search_results:
            if submission.removed_by_category:
                continue

            full_text = f"{submission.title} {submission.selftext or ''}"

            post_data = {
                'id': submission.id,
                'subreddit': str(submission.subreddit),
                'title': submission.title,
                'text': submission.selftext or '',
                'author': str(submission.author) if submission.author else '[deleted]',
                'score': submission.score,
                'upvote_ratio': submission.upvote_ratio,
                'num_comments': submission.num_comments,
                'url': f"https://reddit.com{submission.permalink}",
                'created_utc': datetime.fromtimestamp(submission.created_utc).isoformat(),
                'collected_at': datetime.now().isoformat(),
                'search_query': query,
                'experience_types': self._classify_experience(full_text),
                'has_numbers': len(self._extract_numbers(full_text)) > 0,
                'ai_tools_mentioned': [kw for kw in self.AI_KEYWORDS if kw in full_text.lower()],
            }

            posts.append(post_data)

        return posts

    def save_posts(self, posts: List[Dict], filename: str = None) -> str:
        """収集した投稿をJSONファイルに保存"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"reddit_posts_{timestamp}.json"

        filepath = self.data_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(posts, f, ensure_ascii=False, indent=2)

        print(f"Saved {len(posts)} posts to {filepath}")
        return str(filepath)

    def load_posts(self, filename: str) -> List[Dict]:
        """保存した投稿を読み込み"""
        filepath = self.data_dir / filename

        if not filepath.exists():
            print(f"File not found: {filepath}")
            return []

        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


def main():
    """テスト実行"""
    collector = RedditVoiceCollector()

    # 接続テスト
    if not collector.connect():
        print("\nReddit API credentials not configured.")
        print("Please set the following environment variables:")
        print("  REDDIT_CLIENT_ID=your_client_id")
        print("  REDDIT_CLIENT_SECRET=your_client_secret")
        print("\nGet credentials at: https://www.reddit.com/prefs/apps")
        return

    print("Connected to Reddit API!")
    print("\nCollecting posts from r/vibecoding...")

    # r/vibecodingから収集テスト
    posts = collector.collect_from_subreddit(
        subreddit_name='vibecoding',
        sort_by='hot',
        limit=20
    )

    print(f"\nCollected {len(posts)} AI-related posts")

    # サンプル表示
    if posts:
        print("\n--- Sample Post ---")
        sample = posts[0]
        print(f"Title: {sample['title'][:80]}...")
        print(f"Score: {sample['score']}, Comments: {sample['num_comments']}")
        print(f"Experience types: {sample['experience_types']}")
        print(f"AI tools mentioned: {sample['ai_tools_mentioned']}")

        # 保存
        filepath = collector.save_posts(posts)
        print(f"\nSaved to: {filepath}")


if __name__ == '__main__':
    main()
