"""
Hacker News Collector
AI駆動の個人開発エンジニアの体験談を収集するシステム
認証不要・完全無料のHacker News APIを使用
"""

import requests
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


class HackerNewsCollector:
    """Hacker NewsからAI開発者の声を収集するクラス"""

    BASE_URL = "https://hacker-news.firebaseio.com/v0"

    # AI開発関連のキーワード（これらを含む投稿を優先収集）
    AI_KEYWORDS = [
        'claude', 'claude code', 'cursor', 'copilot', 'gpt', 'chatgpt',
        'vibe coding', 'ai coding', 'ai tools', 'llm', 'gemini',
        'windsurf', 'codeium', 'tabnine', 'aider', 'replit',
        'anthropic', 'openai', 'ai assistant', 'code generation',
        'ai pair programming', 'ai developer', 'coding assistant'
    ]

    # Indie Hacker / Build in Public 関連キーワード
    INDIE_KEYWORDS = [
        'indie', 'solo', 'bootstrap', 'side project', 'saas',
        'mrr', 'arr', 'revenue', 'launched', 'shipped',
        'build in public', 'maker', 'founder', 'startup',
        'micro saas', 'one person', 'solo founder'
    ]

    # 体験談を示すキーワード（失敗/成功/学び）
    EXPERIENCE_KEYWORDS = {
        'failure': [
            'failed', 'mistake', 'bug', 'broken', 'frustrated', 'wasted',
            'wrong', 'issue', 'problem', 'struggle', 'hours', 'debug',
            'gave up', 'nightmare', 'disaster', 'learned the hard way',
            'regret', 'terrible', 'awful', 'painful'
        ],
        'success': [
            'shipped', 'launched', 'built', 'completed', 'success', 'proud',
            'finally', 'achieved', 'works', 'done', 'finished', 'released',
            'first customer', 'mrr', 'revenue', 'paying users', 'profit',
            'milestone', 'grew', 'growth'
        ],
        'learning': [
            'learned', 'realized', 'discovered', 'tip', 'lesson', 'advice',
            'insight', 'understanding', 'figured out', 'now i know',
            'game changer', 'productivity', 'workflow', 'recommend',
            'best practice', 'mistake i made', 'wish i knew'
        ]
    }

    def __init__(self):
        """Hacker News APIクライアントを初期化"""
        self.session = requests.Session()
        self.data_dir = Path(__file__).parent.parent / 'data'
        self.data_dir.mkdir(exist_ok=True)

    def _fetch_item(self, item_id: int) -> Optional[Dict]:
        """単一アイテムを取得"""
        try:
            url = f"{self.BASE_URL}/item/{item_id}.json"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error fetching item {item_id}: {e}")
        return None

    def _fetch_story_ids(self, story_type: str = 'top', limit: int = 100) -> List[int]:
        """ストーリーIDリストを取得

        Args:
            story_type: 'top', 'new', 'best', 'ask', 'show'
            limit: 取得件数
        """
        endpoints = {
            'top': 'topstories',
            'new': 'newstories',
            'best': 'beststories',
            'ask': 'askstories',
            'show': 'showstories'
        }

        endpoint = endpoints.get(story_type, 'topstories')
        url = f"{self.BASE_URL}/{endpoint}.json"

        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                ids = response.json()
                return ids[:limit] if ids else []
        except Exception as e:
            print(f"Error fetching story IDs: {e}")
        return []

    def _contains_ai_keywords(self, text: str) -> bool:
        """テキストにAI関連キーワードが含まれているか確認"""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.AI_KEYWORDS)

    def _contains_indie_keywords(self, text: str) -> bool:
        """テキストにIndie Hacker関連キーワードが含まれているか確認"""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.INDIE_KEYWORDS)

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
            r'\d+\s*(hours?|days?|weeks?|months?|years?)',  # 時間表現
            r'\$\d+[\d,]*[kKmM]?',                           # 金額
            r'\d+%',                                          # パーセント
            r'\d+\s*(users?|customers?|downloads?|subscribers?)',  # ユーザー数
            r'\d+[kK]\s*(MRR|ARR|revenue)?',                 # K表記
        ]

        numbers = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            numbers.extend(matches)

        return numbers

    def _get_ai_tools_mentioned(self, text: str) -> List[str]:
        """テキストから言及されているAIツールを抽出"""
        text_lower = text.lower()
        mentioned = []
        for kw in self.AI_KEYWORDS:
            if kw in text_lower:
                mentioned.append(kw)
        return mentioned

    def collect_stories(
        self,
        story_type: str = 'top',
        limit: int = 50,
        filter_ai: bool = True,
        filter_indie: bool = True,
        include_comments: bool = False
    ) -> List[Dict]:
        """
        Hacker Newsからストーリーを収集

        Args:
            story_type: ストーリータイプ ('top', 'new', 'best', 'ask', 'show')
            limit: 取得件数
            filter_ai: AI関連キーワードでフィルタ
            filter_indie: Indie Hacker関連キーワードでフィルタ
            include_comments: コメントも含めるか

        Returns:
            収集した投稿のリスト
        """
        print(f"Fetching {story_type} stories from Hacker News...")

        # ストーリーIDを取得
        story_ids = self._fetch_story_ids(story_type, limit * 3)  # フィルタで減るので多めに取得

        if not story_ids:
            print("No story IDs fetched")
            return []

        print(f"Fetched {len(story_ids)} story IDs, filtering...")

        posts = []

        # 並列でストーリーを取得
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_id = {
                executor.submit(self._fetch_item, sid): sid
                for sid in story_ids
            }

            for future in as_completed(future_to_id):
                story = future.result()
                if not story:
                    continue

                # 削除された投稿をスキップ
                if story.get('deleted') or story.get('dead'):
                    continue

                # storyタイプのみ（job等は除外）
                if story.get('type') != 'story':
                    continue

                title = story.get('title', '')
                text = story.get('text', '')  # Ask HN等のテキスト
                full_text = f"{title} {text}"

                # フィルタリング
                is_ai_related = self._contains_ai_keywords(full_text) if filter_ai else True
                is_indie_related = self._contains_indie_keywords(full_text) if filter_indie else True

                # AI関連 OR Indie関連のいずれかにマッチ
                if not (is_ai_related or is_indie_related):
                    continue

                # 投稿データを構築
                post_data = {
                    'id': str(story.get('id')),
                    'source': 'hackernews',
                    'story_type': story_type,
                    'title': title,
                    'text': text,
                    'author': story.get('by', '[deleted]'),
                    'score': story.get('score', 0),
                    'num_comments': story.get('descendants', 0),
                    'url': story.get('url', ''),
                    'hn_url': f"https://news.ycombinator.com/item?id={story.get('id')}",
                    'created_utc': datetime.fromtimestamp(story.get('time', 0)).isoformat(),
                    'collected_at': datetime.now().isoformat(),

                    # 分析メタデータ
                    'is_ai_related': is_ai_related,
                    'is_indie_related': is_indie_related,
                    'experience_types': self._classify_experience(full_text),
                    'has_numbers': len(self._extract_numbers(full_text)) > 0,
                    'ai_tools_mentioned': self._get_ai_tools_mentioned(full_text),
                }

                posts.append(post_data)

                # 目標件数に達したら終了
                if len(posts) >= limit:
                    break

        print(f"Collected {len(posts)} relevant stories")
        return posts

    def search_stories(
        self,
        query: str,
        limit: int = 30,
        search_type: str = 'story'
    ) -> List[Dict]:
        """
        Algolia HN Search APIでキーワード検索

        Args:
            query: 検索クエリ
            limit: 取得件数
            search_type: 'story' or 'comment'
        """
        # Algolia HN Search API
        url = "https://hn.algolia.com/api/v1/search"
        params = {
            'query': query,
            'tags': search_type,
            'hitsPerPage': limit
        }

        try:
            response = self.session.get(url, params=params, timeout=15)
            if response.status_code != 200:
                print(f"Search API error: {response.status_code}")
                return []

            data = response.json()
            hits = data.get('hits', [])

            posts = []
            for hit in hits:
                title = hit.get('title', '')
                text = hit.get('story_text', '') or ''
                full_text = f"{title} {text}"

                post_data = {
                    'id': str(hit.get('objectID')),
                    'source': 'hackernews',
                    'story_type': 'search',
                    'search_query': query,
                    'title': title,
                    'text': text,
                    'author': hit.get('author', '[deleted]'),
                    'score': hit.get('points', 0),
                    'num_comments': hit.get('num_comments', 0),
                    'url': hit.get('url', ''),
                    'hn_url': f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    'created_utc': hit.get('created_at', ''),
                    'collected_at': datetime.now().isoformat(),

                    # 分析メタデータ
                    'experience_types': self._classify_experience(full_text),
                    'has_numbers': len(self._extract_numbers(full_text)) > 0,
                    'ai_tools_mentioned': self._get_ai_tools_mentioned(full_text),
                }
                posts.append(post_data)

            print(f"Search '{query}' returned {len(posts)} results")
            return posts

        except Exception as e:
            print(f"Search error: {e}")
            return []

    def collect_ai_indie_stories(self, limit: int = 30) -> List[Dict]:
        """
        AI + Indie Hacker関連のストーリーをまとめて収集
        複数の検索クエリを使用
        """
        all_posts = []
        seen_ids = set()

        # 検索クエリリスト
        queries = [
            'claude code',
            'cursor ai coding',
            'vibe coding',
            'shipped saas',
            'indie hacker ai',
            'solo developer ai tools',
            'launched side project',
            'ai coding experience',
            'copilot productivity'
        ]

        for query in queries:
            print(f"Searching: {query}")
            posts = self.search_stories(query, limit=10)

            for post in posts:
                if post['id'] not in seen_ids:
                    seen_ids.add(post['id'])
                    all_posts.append(post)

            if len(all_posts) >= limit:
                break

        # スコア順でソート
        all_posts.sort(key=lambda x: x.get('score', 0), reverse=True)

        return all_posts[:limit]

    def save_posts(self, posts: List[Dict], filename: str = None) -> str:
        """収集した投稿をJSONファイルに保存"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"hn_posts_{timestamp}.json"

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
    collector = HackerNewsCollector()

    print("=" * 60)
    print("Hacker News Collector Test")
    print("=" * 60)

    # AI + Indie関連ストーリーを収集
    posts = collector.collect_ai_indie_stories(limit=20)

    print(f"\nCollected {len(posts)} AI/Indie related posts")

    # サンプル表示
    if posts:
        print("\n--- Sample Posts ---")
        for i, post in enumerate(posts[:3], 1):
            print(f"\n{i}. {post['title'][:60]}...")
            print(f"   Score: {post['score']}, Comments: {post['num_comments']}")
            print(f"   Experience types: {post['experience_types']}")
            print(f"   AI tools: {post['ai_tools_mentioned']}")
            print(f"   URL: {post['hn_url']}")

        # 保存
        filepath = collector.save_posts(posts)
        print(f"\nSaved to: {filepath}")


if __name__ == '__main__':
    main()
