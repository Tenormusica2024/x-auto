"""
Content Classifier
収集した投稿を「失敗談」「成功体験」「学び」に分類し、
ツイート素材としての価値を評価するシステム
"""

import re
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ClassificationResult:
    """分類結果を保持するデータクラス"""
    post_id: str
    primary_category: str           # 主要カテゴリ: failure, success, learning
    secondary_categories: List[str] # 副次カテゴリ
    tweet_potential_score: float    # ツイート素材としての価値 (0.0-1.0)
    emotional_intensity: float      # 感情の強さ (0.0-1.0)
    specificity_score: float        # 具体性スコア (0.0-1.0)
    key_phrases: List[str]          # 抽出したキーフレーズ
    summary: str                    # 要約


class ContentClassifier:
    """投稿を分類・評価するクラス"""

    # 失敗談を示す強いシグナル
    FAILURE_SIGNALS = {
        'strong': [
            'wasted', 'nightmare', 'disaster', 'terrible', 'horrible',
            'complete failure', 'gave up', 'rage quit', 'burned out',
            'worst mistake', 'never again', 'learned the hard way',
            'cost me', 'lost', 'ruined', 'broke', 'crashed'
        ],
        'medium': [
            'failed', 'bug', 'issue', 'problem', 'struggle', 'frustrated',
            'stuck', 'confused', 'wrong', 'mistake', 'error', 'broken',
            'hours debugging', 'spent days', 'couldn\'t figure out'
        ],
        'weak': [
            'difficult', 'hard', 'challenging', 'tricky', 'annoying',
            'took longer', 'unexpected', 'surprised'
        ]
    }

    # 成功体験を示す強いシグナル
    SUCCESS_SIGNALS = {
        'strong': [
            'shipped', 'launched', 'first customer', 'first sale',
            'paying users', 'revenue', 'mrr', 'profitable', 'viral',
            'featured', 'trending', 'hit', 'milestone', 'proud'
        ],
        'medium': [
            'completed', 'finished', 'built', 'created', 'released',
            'works', 'working', 'success', 'achieved', 'accomplished',
            'finally', 'done', 'live', 'deployed'
        ],
        'weak': [
            'progress', 'moving forward', 'getting there', 'almost done',
            'good progress', 'on track'
        ]
    }

    # 学びを示す強いシグナル
    LEARNING_SIGNALS = {
        'strong': [
            'game changer', 'life saver', 'wish i knew', 'pro tip',
            'key insight', 'breakthrough', 'eureka', 'aha moment',
            'changed everything', 'total game changer', 'must know'
        ],
        'medium': [
            'learned', 'realized', 'discovered', 'figured out', 'understood',
            'tip', 'trick', 'hack', 'advice', 'recommendation', 'suggest',
            'insight', 'lesson', 'takeaway'
        ],
        'weak': [
            'interesting', 'noticed', 'found', 'seems like', 'apparently',
            'turns out', 'note to self'
        ]
    }

    # 感情の強さを示す表現
    EMOTIONAL_INTENSIFIERS = [
        'absolutely', 'completely', 'totally', 'literally', 'seriously',
        'honestly', 'genuinely', 'truly', 'actually', 'really',
        '!!!', '??', 'omg', 'wtf', 'holy', 'damn', 'wow'
    ]

    # 具体性を示すパターン
    SPECIFICITY_PATTERNS = [
        r'\d+\s*(hours?|days?|weeks?|months?)',           # 時間
        r'\$\d+[\d,]*\.?\d*',                             # 金額
        r'\d+%',                                          # パーセント
        r'\d+\s*(users?|customers?|downloads?|views?)',   # ユーザー数
        r'\d+k|\d+K',                                     # K表記
        r'v\d+\.\d+',                                     # バージョン
        r'[A-Z][a-z]+\s+(API|SDK|CLI)',                  # 具体的なツール名
    ]

    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / 'data'

    def _calculate_signal_score(self, text: str, signals: Dict[str, List[str]]) -> float:
        """シグナルに基づいてスコアを計算"""
        text_lower = text.lower()
        score = 0.0

        # 強いシグナル: 0.4点
        for signal in signals.get('strong', []):
            if signal in text_lower:
                score += 0.4

        # 中程度のシグナル: 0.2点
        for signal in signals.get('medium', []):
            if signal in text_lower:
                score += 0.2

        # 弱いシグナル: 0.1点
        for signal in signals.get('weak', []):
            if signal in text_lower:
                score += 0.1

        return min(score, 1.0)  # 上限1.0

    def _calculate_emotional_intensity(self, text: str) -> float:
        """感情の強さを計算"""
        text_lower = text.lower()
        intensity = 0.0

        # 感情強調表現のカウント
        for intensifier in self.EMOTIONAL_INTENSIFIERS:
            if intensifier in text_lower:
                intensity += 0.15

        # 感嘆符・疑問符の連続
        exclamation_count = len(re.findall(r'!{2,}', text))
        question_count = len(re.findall(r'\?{2,}', text))
        intensity += (exclamation_count + question_count) * 0.1

        # 全大文字の単語（叫び）
        caps_words = len(re.findall(r'\b[A-Z]{3,}\b', text))
        intensity += caps_words * 0.1

        return min(intensity, 1.0)

    def _calculate_specificity(self, text: str) -> float:
        """具体性スコアを計算"""
        specificity = 0.0

        for pattern in self.SPECIFICITY_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            specificity += len(matches) * 0.15

        # 引用符で囲まれた具体的な表現
        quotes = len(re.findall(r'"[^"]{10,}"', text))
        specificity += quotes * 0.1

        # コード/技術用語の存在
        tech_terms = len(re.findall(r'`[^`]+`', text))
        specificity += tech_terms * 0.05

        return min(specificity, 1.0)

    def _extract_key_phrases(self, text: str) -> List[str]:
        """ツイートに使える印象的なフレーズを抽出"""
        phrases = []

        # 引用符で囲まれたフレーズ
        quoted = re.findall(r'"([^"]{10,80})"', text)
        phrases.extend(quoted)

        # 「learned that...」パターン
        learned_patterns = re.findall(
            r'(?:learned|realized|discovered|figured out) (?:that |)([^.!?]{20,100})[.!?]',
            text, re.IGNORECASE
        )
        phrases.extend(learned_patterns)

        # 「the key is...」パターン
        key_patterns = re.findall(
            r'(?:the key|the trick|the secret|pro tip:?) (?:is |was |)([^.!?]{10,80})[.!?]',
            text, re.IGNORECASE
        )
        phrases.extend(key_patterns)

        # 数字を含む具体的な表現
        number_phrases = re.findall(
            r'([^.!?]*\d+[^.!?]{5,50})[.!?]',
            text
        )
        phrases.extend([p.strip() for p in number_phrases if len(p.strip()) > 15])

        return phrases[:5]  # 最大5フレーズ

    def _generate_summary(self, text: str, category: str) -> str:
        """投稿の要約を生成"""
        # タイトル部分（最初の文）を抽出
        first_sentence = text.split('.')[0] if '.' in text else text[:100]

        if len(first_sentence) > 100:
            first_sentence = first_sentence[:97] + '...'

        return first_sentence

    def classify(self, post: Dict) -> ClassificationResult:
        """
        単一の投稿を分類

        Args:
            post: reddit_collector.pyで収集した投稿データ

        Returns:
            ClassificationResult: 分類結果
        """
        full_text = f"{post.get('title', '')} {post.get('text', '')}"

        # 各カテゴリのスコアを計算
        failure_score = self._calculate_signal_score(full_text, self.FAILURE_SIGNALS)
        success_score = self._calculate_signal_score(full_text, self.SUCCESS_SIGNALS)
        learning_score = self._calculate_signal_score(full_text, self.LEARNING_SIGNALS)

        # 主要カテゴリを決定
        scores = {
            'failure': failure_score,
            'success': success_score,
            'learning': learning_score
        }
        primary_category = max(scores, key=scores.get)

        # 副次カテゴリ（閾値0.3以上）
        secondary_categories = [
            cat for cat, score in scores.items()
            if score >= 0.3 and cat != primary_category
        ]

        # 各種スコアを計算
        emotional_intensity = self._calculate_emotional_intensity(full_text)
        specificity_score = self._calculate_specificity(full_text)

        # ツイート素材としての価値を総合評価
        # 重み: カテゴリスコア40%, 感情20%, 具体性30%, エンゲージメント10%
        category_score = scores[primary_category]
        engagement_score = min(post.get('score', 0) / 100, 1.0)  # 100点満点換算

        tweet_potential = (
            category_score * 0.4 +
            emotional_intensity * 0.2 +
            specificity_score * 0.3 +
            engagement_score * 0.1
        )

        return ClassificationResult(
            post_id=post.get('id', ''),
            primary_category=primary_category,
            secondary_categories=secondary_categories,
            tweet_potential_score=round(tweet_potential, 3),
            emotional_intensity=round(emotional_intensity, 3),
            specificity_score=round(specificity_score, 3),
            key_phrases=self._extract_key_phrases(full_text),
            summary=self._generate_summary(full_text, primary_category)
        )

    def classify_batch(self, posts: List[Dict]) -> List[Tuple[Dict, ClassificationResult]]:
        """複数の投稿を一括分類"""
        results = []
        for post in posts:
            classification = self.classify(post)
            results.append((post, classification))
        return results

    def filter_high_potential(
        self,
        posts: List[Dict],
        min_score: float = 0.4,
        category: Optional[str] = None
    ) -> List[Tuple[Dict, ClassificationResult]]:
        """
        ツイート素材として価値の高い投稿をフィルタ

        Args:
            posts: 投稿リスト
            min_score: 最小スコア閾値
            category: フィルタするカテゴリ（None=全て）

        Returns:
            (投稿, 分類結果)のリスト（スコア降順）
        """
        results = self.classify_batch(posts)

        # フィルタ
        filtered = [
            (post, cls) for post, cls in results
            if cls.tweet_potential_score >= min_score
            and (category is None or cls.primary_category == category)
        ]

        # スコア降順でソート
        filtered.sort(key=lambda x: x[1].tweet_potential_score, reverse=True)

        return filtered

    def export_classified(self, classified_posts: List[Tuple[Dict, ClassificationResult]], filename: str = None) -> str:
        """分類結果をJSONファイルに出力"""
        if not filename:
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"classified_posts_{timestamp}.json"

        filepath = self.data_dir / filename

        export_data = []
        for post, cls in classified_posts:
            export_data.append({
                'post': post,
                'classification': {
                    'post_id': cls.post_id,
                    'primary_category': cls.primary_category,
                    'secondary_categories': cls.secondary_categories,
                    'tweet_potential_score': cls.tweet_potential_score,
                    'emotional_intensity': cls.emotional_intensity,
                    'specificity_score': cls.specificity_score,
                    'key_phrases': cls.key_phrases,
                    'summary': cls.summary
                }
            })

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"Exported {len(export_data)} classified posts to {filepath}")
        return str(filepath)


def main():
    """テスト実行"""
    classifier = ContentClassifier()

    # テストデータ
    test_posts = [
        {
            'id': 'test1',
            'title': 'I wasted 3 days trying to get Claude Code to work on my legacy codebase',
            'text': '''Honestly, I thought AI coding tools would be a game changer.
            But after 3 days of debugging hallucinated code, I'm ready to give up.
            The tool kept suggesting fixes that introduced MORE bugs.
            Spent literally 8 hours on one function that I could have written in 30 minutes.
            Total nightmare. Never again for complex codebases.''',
            'score': 245
        },
        {
            'id': 'test2',
            'title': 'Shipped my first SaaS in 2 weeks using Cursor + Claude',
            'text': '''Finally launched! $500 MRR in the first month.
            The key was using Claude for architecture decisions and Cursor for implementation.
            Pro tip: Don't let AI write tests - it's terrible at edge cases.
            But for CRUD operations? Absolutely game changing. 10x faster.''',
            'score': 892
        },
        {
            'id': 'test3',
            'title': 'What I learned after 6 months of vibe coding',
            'text': '''Here's my honest take after building 4 projects with AI tools:
            1. Great for greenfield, terrible for legacy
            2. Always review generated code - found 3 security bugs last week
            3. Best for boilerplate and boring tasks
            4. Still need to understand the code - AI is a tool, not a replacement
            The trick is knowing when to use it and when to write by hand.''',
            'score': 1234
        }
    ]

    print("=== Content Classification Test ===\n")

    for post in test_posts:
        result = classifier.classify(post)
        print(f"Title: {post['title'][:60]}...")
        print(f"  Primary: {result.primary_category}")
        print(f"  Secondary: {result.secondary_categories}")
        print(f"  Tweet Potential: {result.tweet_potential_score}")
        print(f"  Emotional: {result.emotional_intensity}")
        print(f"  Specificity: {result.specificity_score}")
        print(f"  Key Phrases: {result.key_phrases[:2]}")
        print()

    # 高ポテンシャルのみ抽出
    print("=== High Potential Posts (score >= 0.5) ===")
    high_potential = classifier.filter_high_potential(test_posts, min_score=0.5)
    for post, cls in high_potential:
        print(f"  [{cls.primary_category}] {cls.tweet_potential_score}: {post['title'][:50]}...")


if __name__ == '__main__':
    main()
