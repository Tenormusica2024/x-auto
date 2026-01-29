"""
Indie Voice Tweet Reviewer
3段階のレビューシステム：
1. 収集投稿のレビュー（AI体験談として価値があるか）
2. 生成ツイートのレビュー（人間らしさ・AI感排除）
3. 最終承認（投稿前チェック）

v2.0: PersonaManagerによるペルソナベースの違和感チェック機能を追加
"""

import os
import sys
import json
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import google.generativeai as genai

# PersonaManagerをインポート
sys.path.insert(0, str(Path(__file__).parent.parent))
from persona_manager import PersonaManager, PersonaWritingStyle


@dataclass
class ReviewResult:
    """レビュー結果を保持するデータクラス"""
    passed: bool                    # レビュー通過したか
    stage: str                      # どのステージか (post_quality, tweet_naturalness, final_approval)
    score: float                    # スコア (0.0-1.0)
    issues: List[str]               # 検出された問題点
    suggestions: List[str]          # 改善提案
    review_comment: str             # レビューコメント


class IndieVoiceTweetReviewer:
    """
    Indie Voice専用のツイートレビューシステム

    レビュー観点（メインブランチとの違い）：
    - メインブランチ: AI業界ニュースの引用リツイート向け
    - Indie Voice: 個人開発者の体験談を元にした共感ツイート向け
    """

    # ========================================
    # STAGE 1: 収集投稿の品質レビュー基準
    # ========================================

    # 良質な体験談の指標
    QUALITY_INDICATORS = {
        'high_value': [
            # 具体的な数字・期間を含む
            r'\d+\s*(hours?|days?|weeks?|months?)',
            r'\$\d+',
            r'\d+%',
            # 感情的な瞬間を示す
            r'finally|at last|breakthrough',
            r'nightmare|disaster|frustrat',
            # 学びを示す
            r'learned|realized|discovered|figured out',
            r'pro tip|key insight|game changer',
        ],
        'red_flags': [
            # 宣伝・スパム
            r'(check out|try|use) my (app|tool|product)',
            r'discount|promo|coupon|free trial',
            r'link in bio|dm me',
            # 質問のみ（体験談ではない）
            r'^(how|what|why|can|should|is it)\s',
            # 単純なニュース転載
            r'(just announced|breaking|news:)',
        ]
    }

    # ========================================
    # STAGE 2: 生成ツイートのレビュー基準
    # ========================================

    # AI感を示す危険な表現（絶対禁止）
    AI_SMELL_PATTERNS = [
        # 過度に丁寧な表現
        r'〜ですね[!！]',
        r'〜ますね[!！]',
        r'〜でしょうか[?？]',
        # 大袈裟な感嘆
        r'本当に素晴らしい',
        r'深く共感',
        r'激しく共感',
        r'心から',
        r'まさにこれ',
        # ビジネス用語
        r'革新的',
        r'画期的',
        r'パラダイムシフト',
        r'競争優位性',
        r'市場の勢力図',
        # 典型的なAI文体
        r'〜と言えるでしょう',
        r'〜と考えられます',
        r'〜することが重要です',
        r'〜する必要があります',
    ]

    # 人間らしい表現（推奨）
    HUMAN_PATTERNS = [
        # カジュアルな語尾
        r'〜かも',
        r'〜と思う',
        r'〜だろう',
        r'〜だな',
        r'〜だよね',
        # 素直な反応
        r'へー',
        r'なるほど',
        r'確かに',
        r'面白い',
        # 未完結感
        r'\.\.\.',
        r'…',
    ]

    # 絵文字パターン
    EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FA6F"  # chess symbols
        "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-a
        "\U00002600-\U000026FF"  # misc symbols
        "]+",
        flags=re.UNICODE
    )

    def __init__(self, gemini_api_key: str = None, persona_path: str = None):
        """
        初期化

        Args:
            gemini_api_key: Gemini APIキー（未指定時は環境変数から取得）
            persona_path: PERSONA.mdのパス（未指定時はデフォルトパス）
        """
        self.api_key = gemini_api_key or os.getenv('GEMINI_API_KEY')
        self.model = None

        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')

        # PersonaManagerを初期化
        self.persona_manager = PersonaManager(persona_path)

    # ========================================
    # STAGE 1: 収集投稿の品質レビュー
    # ========================================

    def review_collected_post(self, post: Dict) -> ReviewResult:
        """
        収集した投稿の品質をレビュー

        観点:
        - AI体験談として価値があるか
        - 具体的なエピソードが含まれているか
        - スパム・宣伝ではないか
        """
        full_text = f"{post.get('title', '')} {post.get('text', '')}"
        issues = []
        suggestions = []
        score = 0.5  # 基準点

        # 高価値指標のチェック
        high_value_count = 0
        for pattern in self.QUALITY_INDICATORS['high_value']:
            if re.search(pattern, full_text, re.IGNORECASE):
                high_value_count += 1
                score += 0.1

        if high_value_count == 0:
            issues.append("具体的な数字・期間・感情的エピソードが不足")
            suggestions.append("より具体的な体験談を含む投稿を優先")

        # レッドフラグのチェック
        for pattern in self.QUALITY_INDICATORS['red_flags']:
            if re.search(pattern, full_text, re.IGNORECASE):
                issues.append(f"レッドフラグ検出: {pattern[:30]}...")
                score -= 0.3

        # 本文の長さチェック
        text_length = len(post.get('text', ''))
        if text_length < 50:
            issues.append("本文が短すぎる（50文字未満）")
            score -= 0.2
        elif text_length > 200:
            score += 0.1  # 詳細な体験談は価値が高い

        # エンゲージメントスコア
        upvote_ratio = post.get('upvote_ratio', 0.5)
        if upvote_ratio > 0.9:
            score += 0.15
        elif upvote_ratio < 0.6:
            issues.append("コミュニティの反応が悪い（upvote_ratio < 0.6）")
            score -= 0.1

        # 最終スコア調整
        score = max(0.0, min(1.0, score))
        passed = score >= 0.4 and len([i for i in issues if 'レッドフラグ' in i]) == 0

        return ReviewResult(
            passed=passed,
            stage='post_quality',
            score=round(score, 2),
            issues=issues,
            suggestions=suggestions,
            review_comment=f"投稿品質スコア: {score:.2f} - {'PASS' if passed else 'REJECT'}"
        )

    # ========================================
    # STAGE 2: 生成ツイートの自然さレビュー
    # ========================================

    def review_generated_tweet(self, tweet_text: str, original_post: Dict = None) -> ReviewResult:
        """
        生成されたツイートの人間らしさをレビュー

        観点:
        - AI感のある表現がないか
        - 絵文字が含まれていないか
        - 文字数が適切か
        - 自然な日本語か
        """
        issues = []
        suggestions = []
        score = 1.0  # 満点から減点方式

        # 文字数チェック
        char_count = len(tweet_text)
        if char_count > 280:
            issues.append(f"文字数オーバー: {char_count}文字（上限280）")
            score -= 0.3
        elif char_count < 30:
            issues.append(f"文字数が少なすぎる: {char_count}文字")
            score -= 0.2

        # 絵文字チェック
        emojis_found = self.EMOJI_PATTERN.findall(tweet_text)
        if emojis_found:
            issues.append(f"絵文字検出: {''.join(emojis_found)}")
            score -= 0.2 * len(emojis_found)
            suggestions.append("絵文字を削除する")

        # AI感のある表現チェック
        ai_smell_count = 0
        for pattern in self.AI_SMELL_PATTERNS:
            if re.search(pattern, tweet_text):
                ai_smell_count += 1
                issues.append(f"AI感のある表現: {pattern}")
                score -= 0.15

        if ai_smell_count > 0:
            suggestions.append("よりカジュアルな表現に変更する")

        # 人間らしい表現のチェック（加点）
        human_count = 0
        for pattern in self.HUMAN_PATTERNS:
            if re.search(pattern, tweet_text):
                human_count += 1

        if human_count > 0:
            score += 0.05 * min(human_count, 3)  # 最大0.15加点

        # 感嘆符の数チェック
        exclamation_count = tweet_text.count('!') + tweet_text.count('！')
        if exclamation_count > 1:
            issues.append(f"感嘆符が多すぎる: {exclamation_count}個（推奨: 0-1個）")
            score -= 0.1

        # 最終スコア調整
        score = max(0.0, min(1.0, score))
        passed = score >= 0.6 and ai_smell_count == 0

        return ReviewResult(
            passed=passed,
            stage='tweet_naturalness',
            score=round(score, 2),
            issues=issues,
            suggestions=suggestions,
            review_comment=f"自然さスコア: {score:.2f} - {'PASS' if passed else 'NEEDS_REVISION'}"
        )

    # ========================================
    # STAGE 2.5: ペルソナベースの違和感チェック（新機能）
    # ========================================

    def review_with_persona(self, tweet_text: str) -> ReviewResult:
        """
        ペルソナ情報に基づいた違和感チェック

        観点:
        - PERSONA.mdの文体特性に沿っているか
        - 避けるべき表現が含まれていないか
        - 推奨表現が適切に使われているか
        """
        issues = []
        suggestions = []
        score = 1.0  # 満点から減点方式

        # PersonaManagerの違和感チェックを実行
        violations = self.persona_manager.check_tweet_violations(tweet_text)

        for v in violations:
            issues.append(v['issue'])
            suggestions.append(v['suggestion'])
            score -= 0.15  # 各違反で0.15減点

        # ペルソナの文体特性から追加チェック
        style = self.persona_manager.get_writing_style()

        # 避ける表現のパターンを動的に生成
        for expr in style.avoid_expressions:
            # 「〜んだな」形式から正規表現を抽出
            if '「' in expr and '」' in expr:
                match = re.search(r'「(.+?)」', expr)
                if match:
                    pattern_text = match.group(1).replace('〜', '.+')
                    if re.search(pattern_text, tweet_text):
                        # 既に検出済みでなければ追加
                        issue_text = f"ペルソナ違反: {expr[:30]}..."
                        if issue_text not in issues:
                            issues.append(issue_text)
                            suggestions.append("PERSONA.mdの文体特性を参照")
                            score -= 0.1

        # トーンガイドラインのチェック
        # 「今気づいた」感が出ていないかをチェック
        discovery_patterns = [
            (r'今日初めて', '「今気づいた」感が出ている'),
            (r'さっき気づいた', '「今気づいた」感が出ている'),
            (r'たった今', '「今気づいた」感が出ている'),
            (r'ようやく分かった', '「今気づいた」感が出ている'),
        ]
        for pattern, issue_desc in discovery_patterns:
            if re.search(pattern, tweet_text):
                issues.append(issue_desc)
                suggestions.append('「前から思ってた」トーンに変更')
                score -= 0.15

        # 最終スコア調整
        score = max(0.0, min(1.0, score))
        passed = score >= 0.6 and len([i for i in issues if 'ペルソナ違反' in i]) < 3

        return ReviewResult(
            passed=passed,
            stage='persona_check',
            score=round(score, 2),
            issues=issues,
            suggestions=suggestions,
            review_comment=f"ペルソナ適合スコア: {score:.2f} - {'PASS' if passed else 'NEEDS_REVISION'}"
        )

    # ========================================
    # STAGE 3: AI駆動の詳細レビュー（Gemini API）
    # ========================================

    def review_with_ai(self, tweet_text: str, original_post: Dict) -> ReviewResult:
        """
        Gemini APIを使った詳細レビュー

        観点:
        - 元の体験談との整合性
        - 共感を得られる内容か
        - 炎上リスクはないか
        """
        if not self.model:
            return ReviewResult(
                passed=True,
                stage='ai_review',
                score=0.5,
                issues=["Gemini API未設定のためスキップ"],
                suggestions=[],
                review_comment="AI詳細レビューをスキップ"
            )

        prompt = f"""以下のツイートを厳格にレビューしてください。

## 元のReddit投稿
タイトル: {original_post.get('title', '')}
本文: {original_post.get('text', '')[:300]}

## 生成されたツイート
{tweet_text}

## レビュー観点
1. **共感度** (0-10): 個人開発者が共感できる内容か？
2. **AI感** (0-10): AI生成っぽさがないか？（10=完全に人間らしい）
3. **炎上リスク** (0-10): 批判を受けそうな内容がないか？（10=リスクなし）
4. **元投稿との整合性** (0-10): 元の体験談の本質を捉えているか？

## 出力形式（JSON）
{{
  "empathy_score": 0-10,
  "human_score": 0-10,
  "risk_score": 0-10,
  "consistency_score": 0-10,
  "overall_pass": true/false,
  "issues": ["問題点1", "問題点2"],
  "suggestions": ["改善案1", "改善案2"],
  "comment": "総評（50文字以内）"
}}

JSONのみを出力。説明不要。
"""

        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()

            # JSONを抽出
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0]
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0]

            result = json.loads(result_text)

            # スコア計算
            avg_score = (
                result.get('empathy_score', 5) +
                result.get('human_score', 5) +
                result.get('risk_score', 5) +
                result.get('consistency_score', 5)
            ) / 40  # 0-1スケール

            return ReviewResult(
                passed=result.get('overall_pass', avg_score >= 0.7),
                stage='ai_review',
                score=round(avg_score, 2),
                issues=result.get('issues', []),
                suggestions=result.get('suggestions', []),
                review_comment=result.get('comment', 'AIレビュー完了')
            )

        except Exception as e:
            return ReviewResult(
                passed=True,  # エラー時は通過扱い
                stage='ai_review',
                score=0.5,
                issues=[f"AIレビューエラー: {str(e)[:50]}"],
                suggestions=[],
                review_comment="AIレビューでエラーが発生"
            )

    # ========================================
    # 統合レビューフロー
    # ========================================

    def full_review(
        self,
        tweet_text: str,
        original_post: Dict,
        use_ai_review: bool = True,
        use_persona_review: bool = True
    ) -> Tuple[bool, List[ReviewResult]]:
        """
        完全レビューを実行（4段階）

        Args:
            tweet_text: レビュー対象のツイート
            original_post: 元のReddit投稿
            use_ai_review: Gemini AIレビューを使用するか
            use_persona_review: ペルソナベースレビューを使用するか

        Returns:
            (最終判定, [各ステージのレビュー結果])
        """
        results = []

        # Stage 1: 投稿品質レビュー
        post_review = self.review_collected_post(original_post)
        results.append(post_review)

        if not post_review.passed:
            return False, results

        # Stage 2: ツイート自然さレビュー
        tweet_review = self.review_generated_tweet(tweet_text, original_post)
        results.append(tweet_review)

        if not tweet_review.passed:
            return False, results

        # Stage 2.5: ペルソナベースレビュー（新機能）
        if use_persona_review:
            persona_review = self.review_with_persona(tweet_text)
            results.append(persona_review)

            if not persona_review.passed:
                return False, results

        # Stage 3: AIレビュー（オプション）
        if use_ai_review:
            ai_review = self.review_with_ai(tweet_text, original_post)
            results.append(ai_review)

            if not ai_review.passed:
                return False, results

        return True, results

    def batch_review(
        self,
        tweets_with_posts: List[Tuple[str, Dict]],
        use_ai_review: bool = True,
        use_persona_review: bool = True
    ) -> List[Tuple[str, Dict, bool, List[ReviewResult]]]:
        """
        複数のツイートを一括レビュー

        Args:
            tweets_with_posts: [(ツイート文, 元投稿), ...]
            use_ai_review: Gemini AIレビューを使用するか
            use_persona_review: ペルソナベースレビューを使用するか

        Returns:
            [(ツイート文, 元投稿, 合格フラグ, レビュー結果リスト), ...]
        """
        results = []

        for tweet_text, post in tweets_with_posts:
            passed, reviews = self.full_review(
                tweet_text, post, use_ai_review, use_persona_review
            )
            results.append((tweet_text, post, passed, reviews))

        return results

    def print_review_report(self, results: List[ReviewResult]) -> None:
        """レビュー結果をフォーマットして表示"""
        print("\n" + "="*60)
        print("REVIEW REPORT")
        print("="*60)

        for result in results:
            status = "[PASS]" if result.passed else "[FAIL]"
            print(f"\n[{result.stage}] {status} (Score: {result.score})")
            print(f"Comment: {result.review_comment}")

            if result.issues:
                print("Issues:")
                for issue in result.issues:
                    print(f"  - {issue}")

            if result.suggestions:
                print("Suggestions:")
                for suggestion in result.suggestions:
                    print(f"  → {suggestion}")


def main():
    """テスト実行"""
    reviewer = IndieVoiceTweetReviewer()

    # テストデータ
    test_post = {
        'id': 'test1',
        'title': 'I wasted 3 days trying to get Claude Code to work on my legacy codebase',
        'text': '''Honestly, I thought AI coding tools would be a game changer.
        But after 3 days of debugging hallucinated code, I'm ready to give up.
        Spent literally 8 hours on one function.''',
        'upvote_ratio': 0.89,
        'score': 245
    }

    test_tweets = [
        # Good example (人間らしい、ペルソナ適合)
        "3日間AIに振り回された話。レガシーコードにClaude Code使おうとしたら、ハルシネーションの嵐で逆に時間かかった。同じパターンと同じかなんだよね。",
        # Bad example (AI臭い)
        "本当に素晴らしい学びでした！AI開発ツールは革新的ですが、レガシーコードには向かないということが深く理解できました！！",
        # Bad example (「んだな」使用 - ペルソナ違反)
        "AIツールは本当に便利なんだな、もっと早く使えばよかった。",
        # Bad example (共感表現 - ペルソナ違反)
        "共感します！私も同じ経験があります！レガシーコードとAIの相性は最悪ですね！",
        # Bad example (今気づいた感 - ペルソナ違反)
        "今日初めて気づいたんだけど、Claude Codeってレガシーコードに弱いらしい。",
    ]

    print("=== Indie Voice Tweet Reviewer Test (with Persona Check) ===\n")

    for i, tweet in enumerate(test_tweets, 1):
        print(f"\n--- Test {i} ---")
        print(f"Tweet: {tweet[:50]}...")

        # ペルソナベースレビューを有効化
        passed, results = reviewer.full_review(
            tweet, test_post,
            use_ai_review=False,
            use_persona_review=True
        )

        print(f"Final: {'PASS' if passed else 'FAIL'}")
        reviewer.print_review_report(results)


if __name__ == '__main__':
    main()
