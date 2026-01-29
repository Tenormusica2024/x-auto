"""
Persona Manager for Indie Voice
PERSONA.mdの読み込み・更新・参照機能を提供

機能:
1. ペルソナ情報の読み込み（構造化データとして）
2. 新しい経験・知見の追記
3. 文体特性の取得（ツイート生成用）
4. 違和感チェック項目の取得（レビュー用）
"""

import re
import os
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass


@dataclass
class PersonaWritingStyle:
    """文体特性を保持するデータクラス"""
    use_expressions: List[str]      # 使う表現
    avoid_expressions: List[str]    # 避ける表現
    tone_guidelines: List[str]      # トーンガイドライン
    violation_checklist: List[str]  # 違和感チェック項目


@dataclass
class PersonaProfile:
    """ペルソナ全体を保持するデータクラス"""
    name: str
    age: int
    location: str
    occupation: str
    career_goal: str
    skills: List[str]
    cognitive_traits: Dict[str, List[str]]  # ADHD傾向、フロンティア志向など
    communication_style: Dict[str, str]     # 対人スタイル
    writing_style: PersonaWritingStyle
    monetization_view: List[str]            # マネタイズ観
    ai_development_stance: List[str]        # AI駆動開発への姿勢


class PersonaManager:
    """
    PERSONA.mdを管理するクラス

    使用例:
        manager = PersonaManager()
        profile = manager.load_persona()
        style = manager.get_writing_style()
        violations = manager.check_tweet_violations(tweet_text)
    """

    def __init__(self, persona_path: str = None):
        """
        初期化

        Args:
            persona_path: PERSONA.mdのパス（未指定時はデフォルトパス）
        """
        if persona_path:
            self.persona_path = Path(persona_path)
        else:
            self.persona_path = Path(__file__).parent / 'PERSONA.md'

        # キャッシュ
        self._raw_content: Optional[str] = None
        self._profile: Optional[PersonaProfile] = None
        self._last_loaded: Optional[datetime] = None

    def _load_raw_content(self, force_reload: bool = False) -> str:
        """PERSONA.mdの生のコンテンツを読み込み"""
        if not force_reload and self._raw_content is not None:
            return self._raw_content

        if not self.persona_path.exists():
            raise FileNotFoundError(f"PERSONA.md not found at {self.persona_path}")

        with open(self.persona_path, 'r', encoding='utf-8') as f:
            self._raw_content = f.read()
        self._last_loaded = datetime.now()

        return self._raw_content

    def load_persona(self, force_reload: bool = False) -> PersonaProfile:
        """
        PERSONA.mdを読み込み、構造化データとして返す

        Args:
            force_reload: キャッシュを無視して再読み込み

        Returns:
            PersonaProfile: 構造化されたペルソナ情報
        """
        if not force_reload and self._profile is not None:
            return self._profile

        content = self._load_raw_content(force_reload)

        # 各セクションを抽出
        self._profile = PersonaProfile(
            name=self._extract_field(content, r'\*\*名前\*\*:\s*(.+?)(?:\n|$)') or '幸田 晃典',
            age=int(self._extract_field(content, r'約(\d+)歳') or '40'),
            location=self._extract_field(content, r'\*\*居住地\*\*:\s*(.+?)(?:\n|$)') or '千葉県柏市',
            occupation=self._extract_field(content, r'\*\*職業\*\*:\s*(.+?)(?:\n|$)') or 'AIエンジニア',
            career_goal=self._extract_field(content, r'\*\*キャリア目標\*\*:\s*(.+?)(?:\n|$)') or 'フリーランス',
            skills=self._extract_list_items(content, '### スキルセット'),
            cognitive_traits=self._extract_cognitive_traits(content),
            communication_style=self._extract_communication_style(content),
            writing_style=self._extract_writing_style(content),
            monetization_view=self._extract_section_bullets(content, '## マネタイズ観'),
            ai_development_stance=self._extract_section_bullets(content, '## AI駆動開発への姿勢')
        )

        return self._profile

    def _extract_field(self, content: str, pattern: str) -> Optional[str]:
        """正規表現でフィールドを抽出"""
        match = re.search(pattern, content)
        return match.group(1).strip() if match else None

    def _extract_list_items(self, content: str, section_header: str) -> List[str]:
        """セクション内のリスト項目を抽出"""
        lines = content.split('\n')
        in_section = False
        items = []

        for line in lines:
            if section_header in line:
                in_section = True
                continue
            if in_section:
                if line.startswith('### ') or line.startswith('## ') or line.startswith('---'):
                    break
                if line.strip().startswith('- '):
                    items.append(line.strip()[2:])

        return items

    def _extract_section_bullets(self, content: str, section_header: str) -> List[str]:
        """セクション全体のバレット項目を抽出"""
        # セクションの開始位置を探す
        start = content.find(section_header)
        if start == -1:
            return []

        # 次のセクション（## または ---）までの範囲を取得
        section_content = content[start:]
        next_section = re.search(r'\n## |\n---', section_content[len(section_header):])
        if next_section:
            section_content = section_content[:len(section_header) + next_section.start()]

        # バレット項目を抽出
        items = []
        for line in section_content.split('\n'):
            if line.strip().startswith('- '):
                items.append(line.strip()[2:])

        return items

    def _extract_cognitive_traits(self, content: str) -> Dict[str, List[str]]:
        """認知特性セクションを抽出"""
        traits = {}

        # 各サブセクションを抽出
        subsections = ['ADHD傾向と過集中', 'フロンティア志向', '抽象化志向', '選択的完璧主義']
        for subsection in subsections:
            items = self._extract_list_items(content, f'### {subsection}')
            if items:
                traits[subsection] = items

        return traits

    def _extract_communication_style(self, content: str) -> Dict[str, str]:
        """対人スタイルセクションを抽出"""
        style = {}

        # 主な特性を抽出
        communication_items = self._extract_list_items(content, '### コミュニケーション特性')
        if communication_items:
            style['communication'] = '\n'.join(communication_items)

        distance_items = self._extract_list_items(content, '### 距離感の固定')
        if distance_items:
            style['distance'] = '\n'.join(distance_items)

        return style

    def _extract_writing_style(self, content: str) -> PersonaWritingStyle:
        """文体特性セクションを抽出"""
        # 使う表現
        use_items = self._extract_list_items(content, '### 使う表現')

        # 避ける表現
        avoid_items = self._extract_list_items(content, '### 避ける表現')

        # トーンガイドライン
        tone_items = self._extract_list_items(content, '### トーン')

        # 違和感チェックポイント
        checklist_items = self._extract_list_items(content, '### 違和感チェックポイント')

        return PersonaWritingStyle(
            use_expressions=use_items,
            avoid_expressions=avoid_items,
            tone_guidelines=tone_items,
            violation_checklist=checklist_items
        )

    def get_writing_style(self) -> PersonaWritingStyle:
        """
        文体特性を取得（ツイート生成用）

        Returns:
            PersonaWritingStyle: 文体特性
        """
        profile = self.load_persona()
        return profile.writing_style

    def get_avoid_patterns(self) -> List[Tuple[str, str]]:
        """
        避けるべき表現パターンを正規表現形式で取得

        Returns:
            [(パターン, 説明), ...]
        """
        style = self.get_writing_style()
        patterns = []

        for expr in style.avoid_expressions:
            # 「〜んだな」→ 正規表現パターンに変換
            if '「' in expr and '」' in expr:
                match = re.search(r'「(.+?)」', expr)
                if match:
                    # 「〜んだな」形式を正規表現に変換
                    pattern = match.group(1).replace('〜', '.+')
                    patterns.append((pattern, expr))

        return patterns

    def check_tweet_violations(self, tweet_text: str) -> List[Dict[str, str]]:
        """
        ツイートテキストの違和感をチェック

        Args:
            tweet_text: チェック対象のツイート

        Returns:
            [{pattern, issue, suggestion}, ...] 検出された違反リスト
        """
        violations = []

        # 避ける表現パターンでチェック
        avoid_patterns = [
            # 「〜んだな」の多用（今気づいた感）
            (r'.+んだな[。、]?$', '「〜んだな」で終わっている', '「〜んだよね」「〜ではある」に変更'),
            (r'.+んだな、', '「〜んだな、」を使用', '「〜んだよね、」「〜で、」に変更'),

            # 「〜かな...」（ふわっと終わる）
            (r'.+かな[\.\…。]+$', '「〜かな...」で終わっている', '結論を明確にする'),

            # 「逆に言えば」（論理的すぎる）
            (r'逆に言えば', '「逆に言えば」を使用', '感覚的な接続に変更'),
            (r'つまり', '「つまり」を使用', '感覚的な接続に変更'),
            (r'要するに', '「要するに」を使用', '感覚的な接続に変更'),

            # 造語（AIは概念に名前をつけたがる）
            (r'「.+化」', '造語の使用可能性', '既存の言葉で表現'),

            # 読点の多用
            (r'[、,]{3,}', '読点が多すぎる', '読点を減らして主張感を抑える'),

            # 相手に寄り添う表現（AI的）
            (r'共感します', '「共感します」はAI的', '自分の経験として語る'),
            (r'わかります', '「わかります」はAI的', '自分の経験として語る'),
            (r'その気持ち', '「その気持ち」はAI的', '自分の経験として語る'),

            # 過度に丁寧な表現
            (r'〜ですね[!！]', '丁寧すぎる感嘆', 'カジュアルな語尾に'),
            (r'〜ますね[!！]', '丁寧すぎる感嘆', 'カジュアルな語尾に'),
        ]

        for pattern, issue, suggestion in avoid_patterns:
            if re.search(pattern, tweet_text):
                violations.append({
                    'pattern': pattern,
                    'issue': issue,
                    'suggestion': suggestion
                })

        # 推奨表現の欠如チェック
        recommended_patterns = [
            (r'んだよね', '「〜んだよね」（前から思ってた感）'),
            (r'ではある', '「〜ではある」（断定するが押しつけがましくない）'),
            (r'んだろうけど', '「〜んだろうけど」（感覚で繋ぐ）'),
        ]

        has_recommended = False
        for pattern, desc in recommended_patterns:
            if re.search(pattern, tweet_text):
                has_recommended = True
                break

        if not has_recommended and len(tweet_text) > 50:
            violations.append({
                'pattern': 'missing_recommended',
                'issue': '推奨表現が含まれていない',
                'suggestion': '「〜んだよね」「〜ではある」などを検討'
            })

        return violations

    def add_experience(self, category: str, content: str) -> bool:
        """
        新しい経験・知見をPERSONA.mdに追記

        Args:
            category: カテゴリ（マネタイズ観、AI駆動開発など）
            content: 追記する内容

        Returns:
            bool: 成功したか
        """
        try:
            raw_content = self._load_raw_content(force_reload=True)

            # 更新履歴セクションを探す
            update_section = '## 更新履歴'
            if update_section in raw_content:
                # 更新履歴の直前に新しい経験を追加
                today = datetime.now().strftime('%Y-%m-%d')
                new_entry = f"\n### {today} 追記（{category}）\n- {content}\n"

                # 更新履歴セクションの直前に挿入
                insert_pos = raw_content.find(update_section)
                updated_content = raw_content[:insert_pos] + new_entry + raw_content[insert_pos:]

                # 更新履歴も更新
                update_line = f"- **{today}**: {category}に追記"
                updated_content = updated_content.replace(
                    update_section + '\n',
                    update_section + '\n\n' + update_line + '\n'
                )
            else:
                # 更新履歴セクションがない場合は末尾に追加
                today = datetime.now().strftime('%Y-%m-%d')
                updated_content = raw_content + f"\n\n### {today} 追記（{category}）\n- {content}\n"

            # ファイルに書き込み
            with open(self.persona_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)

            # キャッシュをクリア
            self._raw_content = None
            self._profile = None

            return True

        except Exception as e:
            print(f"経験追記エラー: {e}")
            return False

    def get_tweet_generation_context(self) -> str:
        """
        ツイート生成用のコンテキストを取得

        Returns:
            str: Claudeに渡すペルソナコンテキスト
        """
        profile = self.load_persona()
        style = profile.writing_style

        context = f"""## ペルソナ情報
- 名前: {profile.name}
- 年齢: 約{profile.age}歳
- 職業: {profile.occupation}
- キャリア目標: {profile.career_goal}

## 認知特性
- ADHD傾向: 興味対象には過集中、興味がないと全くエネルギーが向かない
- フロンティア志向: まだ誰も踏み入れていない領域に興味
- 選択的完璧主義: 興味がある領域だけ100%まで詰める

## 文体特性（必須）
### 使う表現
{chr(10).join('- ' + e for e in style.use_expressions)}

### 避ける表現（AI感が出るため禁止）
{chr(10).join('- ' + e for e in style.avoid_expressions)}

### トーン
{chr(10).join('- ' + e for e in style.tone_guidelines)}

## 重要なルール
- 「今気づいた」ではなく「前から思ってた」トーンで書く
- 相手に寄り添わない（自分の意見を自分のトーンで出力）
- 距離感を詰めない、押しつけがましくない
- 絵文字は使用禁止
"""
        return context


def main():
    """テスト実行"""
    manager = PersonaManager()

    print("=== Persona Manager Test ===\n")

    # ペルソナ読み込み
    profile = manager.load_persona()
    print(f"名前: {profile.name}")
    print(f"年齢: {profile.age}歳")
    print(f"職業: {profile.occupation}")
    print(f"スキル: {', '.join(profile.skills[:3])}...")
    print()

    # 文体特性
    style = manager.get_writing_style()
    print("使う表現:")
    for expr in style.use_expressions[:3]:
        print(f"  - {expr}")
    print()

    print("避ける表現:")
    for expr in style.avoid_expressions[:3]:
        print(f"  - {expr}")
    print()

    # 違和感チェック
    test_tweets = [
        "AIツールは本当に便利なんだな、もっと早く使えばよかった。",  # AI感あり
        "3日間Claude Codeと格闘した結果、レガシーコードには向かないんだよね。同じパターンと同じか。",  # 人間らしい
        "共感します！私も同じ経験があります！",  # AI感あり
    ]

    print("=== 違和感チェックテスト ===")
    for i, tweet in enumerate(test_tweets, 1):
        print(f"\nTweet {i}: {tweet[:40]}...")
        violations = manager.check_tweet_violations(tweet)
        if violations:
            print("  違反検出:")
            for v in violations:
                print(f"    - {v['issue']} -> {v['suggestion']}")
        else:
            print("  違反なし")

    # ツイート生成コンテキスト
    print("\n=== ツイート生成コンテキスト ===")
    context = manager.get_tweet_generation_context()
    print(context[:500] + "...")


if __name__ == '__main__':
    main()
