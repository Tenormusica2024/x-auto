"""
grok_video_prompts.py - Grok Imagine向け動画プロンプト生成エンジン

SF大都市・パルクール・戦闘描写系の派手な動画プロンプトを
5レイヤー構造（Scene + Camera + Style + Motion + Audio）で自動生成する。
バリエーション要素のランダム組み合わせで多様なプロンプトを量産。

Grok Imagine ベストプラクティス:
- 最初の20-30語にコアコンセプトを集中
- シネマティック用語を活用（bokeh, tracking shot, 85mm lens等）
- 否定形を避ける（"no blur"ではなく"crystal-clear sharpness"）
- 1つのコアアクションに集中（複数の連続動作はグリッチしやすい）
- 音声は明示的に指定（指定なしだとデフォルトBGM）
"""

import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# --- テンプレートデータ ---

# 天候バリエーション
WEATHER = [
    "heavy rain pouring down",
    "light snow flurries",
    "dense fog rolling through",
    "clear night sky with stars",
    "dramatic sunset, orange and purple sky",
    "thunderstorm with lightning flashes",
    "misty drizzle, wet everything",
]

# 照明バリエーション
LIGHTING = [
    "neon-lit, cyan and magenta glow",
    "cold moonlight casting sharp shadows",
    "holographic advertisement reflections",
    "golden hour warm light",
    "flickering red emergency lights",
    "bioluminescent blue accents",
    "harsh white searchlights from above",
    "volumetric fog with colored light beams",
]

# カメラワークバリエーション
CAMERA = [
    "smooth tracking shot following the subject",
    "dramatic low-angle shot looking up",
    "sweeping crane shot rising upward",
    "first-person POV camera",
    "slow-motion capture at 120fps look",
    "orbital shot circling the subject",
    "dolly zoom creating vertigo effect",
    "steady wide-angle establishing shot",
    "handheld shaky cam for intensity",
]

# 視覚エフェクトバリエーション
VFX = [
    "sparks flying everywhere",
    "debris and glass shards floating",
    "light trails and motion blur streaks",
    "lens flare from bright lights",
    "particle effects, glowing embers",
    "chromatic aberration at edges",
    "rain droplets hitting camera lens",
    "dust and smoke swirling",
    "electric arcs and plasma effects",
]

# 音声バリエーション
AUDIO = [
    "deep synth bass pulse, distant sirens",
    "intense electronic beat, wind rushing",
    "ambient drone, metallic echoes",
    "heavy impact sounds, glass breaking",
    "cyberpunk synth-wave soundtrack",
    "heartbeat rhythm, tense strings",
    "industrial machinery hum, alarms",
    "epic orchestral swell with electronic elements",
]

# --- カテゴリ別ベースプロンプト ---

CATEGORIES = {
    "sf_parkour": {
        "name": "SF都市パルクール",
        "base_scenes": [
            "A cyberpunk parkour runner leaping between neon-lit skyscraper rooftops in a futuristic megacity",
            "Athletic figure wall-running across a vertical glass building face in a cyberpunk metropolis",
            "Hooded free-runner sliding under holographic barriers on rain-soaked rooftop of a futuristic tower",
            "Parkour athlete vaulting over ventilation systems on a massive sci-fi building, city lights below",
            "Runner performing a precision jump between two crumbling rooftop edges, thousands of feet above ground",
        ],
        "base_motions": [
            "executing a perfect mid-air flip between buildings",
            "wall-running horizontally across a glass facade then launching off",
            "sliding on wet metal surface, sparks trailing behind boots",
            "leaping through a holographic billboard, shattering digital pixels",
            "running at full speed, jumping and grabbing a ledge with one hand",
        ],
    },
    "rooftop_combat": {
        "name": "屋上戦闘",
        "base_scenes": [
            "Two cybernetic warriors clashing swords on a rain-drenched rooftop, futuristic city skyline behind",
            "Armored fighter deflecting energy blasts with a glowing shield atop a mega-skyscraper",
            "Martial artist in a flowing coat delivering a spinning kick on a neon-lit rooftop arena",
            "Lone samurai with a plasma katana facing multiple attackers on a dark futuristic rooftop",
            "Super-powered combatant unleashing an energy wave that shatters rooftop structures",
        ],
        "base_motions": [
            "delivering a devastating spinning roundhouse kick, shockwave rippling outward",
            "blocking an overhead strike then countering with a swift uppercut slash",
            "dodging laser fire with fluid acrobatic movements",
            "charging forward with a glowing fist, impact creating a crater on the rooftop",
            "parrying a blade strike, sparks erupting between weapons",
        ],
    },
    "chase_scene": {
        "name": "チェイスシーン",
        "base_scenes": [
            "Hooded fugitive sprinting across connected rooftops being chased by drone swarm in a cyberpunk city",
            "Motorcycle chase through neon-lit elevated highways of a futuristic megacity at night",
            "Runner being pursued by a hulking mech through narrow rooftop corridors and catwalks",
            "Street-level chase through a crowded futuristic market, dodging holographic vendors",
            "Aerial chase between a jetpack-equipped agent and flying police vehicles over a sprawling city",
        ],
        "base_motions": [
            "leaping from rooftop to rooftop, pursuer closing in from behind",
            "weaving through laser grid security systems at full speed",
            "sliding under closing blast doors at the last second",
            "grappling hook launching to swing between buildings while being fired upon",
            "running along a collapsing bridge structure, sections falling away behind",
        ],
    },
    "hero_landing": {
        "name": "着地・決めポーズ",
        "base_scenes": [
            "Superhero landing pose on a cracked rooftop, shockwave rippling outward, cyberpunk city backdrop",
            "Armored warrior rising from a three-point landing, cape flowing in the wind, city lights below",
            "Cybernetic assassin materializing from stealth on a rooftop ledge, weapons drawn",
            "Mech pilot stepping out of a landed battle suit on a tower rooftop, surveying the city",
            "Dark figure standing at the edge of a skyscraper rooftop, coat billowing, overlooking the city",
        ],
        "base_motions": [
            "impact landing creating a crater, slowly rising with power emanating from body",
            "standing up from crouch, energy field dissipating around them",
            "drawing a glowing weapon from back holster, activating its energy blade",
            "turning to face camera, eyes glowing with power, wind catching their hair",
            "spreading arms wide as energy wings materialize behind them",
        ],
    },
    "environment_shot": {
        "name": "環境ショット",
        "base_scenes": [
            "Breathtaking panoramic view of a colossal cyberpunk megacity at night, layers of flying traffic",
            "Massive futuristic cityscape seen from a rooftop, holographic ads towering between buildings",
            "Sunrise over a sprawling sci-fi metropolis, light reflecting off thousands of glass towers",
            "Underground level of a multi-layered city, neon market stalls stretching into darkness",
            "Orbital view descending into a mega-city through cloud layers, revealing its impossible scale",
        ],
        "base_motions": [
            "camera slowly panning across the vast cityscape, vehicles flying past",
            "camera rising from street level up through the layers of the city",
            "holographic advertisements flickering and changing, city alive with movement",
            "rain beginning to fall across the entire city, lights reflecting in growing puddles",
            "camera pulling back to reveal the full scale of the massive metropolis",
        ],
    },
}


def generate_prompt(
    category: Optional[str] = None,
    seed: Optional[int] = None,
) -> dict:
    """
    1つのGrok Imagine動画プロンプトを生成

    Args:
        category: カテゴリ名（None=ランダム選択）
        seed: 乱数シード（再現性が必要な場合）

    Returns:
        {
            "prompt": str,          # 完成プロンプト
            "category": str,        # カテゴリID
            "category_name": str,   # カテゴリ日本語名
            "variation": dict,      # 使用したバリエーション要素
            "generated_at": str,    # 生成日時
        }
    """
    if seed is not None:
        random.seed(seed)

    # カテゴリ選択
    if category is None:
        category = random.choice(list(CATEGORIES.keys()))
    cat = CATEGORIES[category]

    # 各要素をランダム選択
    scene = random.choice(cat["base_scenes"])
    motion = random.choice(cat["base_motions"])
    weather = random.choice(WEATHER)
    lighting = random.choice(LIGHTING)
    camera = random.choice(CAMERA)
    vfx = random.choice(VFX)
    audio = random.choice(AUDIO)

    # 5レイヤー構造でプロンプト組み立て
    # Scene + Motion（コア）→ Camera → Style（天候+照明+VFX）→ Audio
    prompt = (
        f"{scene}, {motion}. "
        f"{camera}, {weather}, {lighting}, {vfx}. "
        f"Cinematic quality, ultra-detailed, photorealistic rendering. "
        f"Audio: {audio}"
    )

    variation = {
        "weather": weather.split(",")[0],
        "lighting": lighting.split(",")[0],
        "camera": camera.split(",")[0] if "," in camera else camera,
        "vfx": vfx.split(",")[0] if "," in vfx else vfx,
        "audio": audio.split(",")[0],
    }

    return {
        "prompt": prompt,
        "category": category,
        "category_name": cat["name"],
        "variation": variation,
        "generated_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    }


def generate_batch(
    count: int = 5,
    categories: Optional[list[str]] = None,
) -> list[dict]:
    """
    複数プロンプトを一括生成

    Args:
        count: 生成数
        categories: 使用カテゴリのリスト（None=全カテゴリから均等に）

    Returns:
        プロンプトリスト
    """
    if categories is None:
        categories = list(CATEGORIES.keys())

    prompts = []
    for i in range(count):
        cat = categories[i % len(categories)]
        prompts.append(generate_prompt(category=cat))

    return prompts


def save_prompts(prompts: list[dict], output_path: Optional[Path] = None) -> Path:
    """プロンプトリストをJSONファイルに保存"""
    if output_path is None:
        data_dir = Path(__file__).parent / "data" / "grok-videos"
        data_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = data_dir / f"prompts_{timestamp}.json"

    output_path.write_text(
        json.dumps(prompts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Grok Imagine動画プロンプト生成")
    parser.add_argument("--count", type=int, default=5, help="生成数（デフォルト: 5）")
    parser.add_argument(
        "--category",
        choices=list(CATEGORIES.keys()),
        help="特定カテゴリのみ生成",
    )
    parser.add_argument("--save", action="store_true", help="JSONファイルに保存")
    parser.add_argument("--seed", type=int, help="乱数シード（再現性用）")
    args = parser.parse_args()

    cats = [args.category] if args.category else None

    if args.seed is not None:
        random.seed(args.seed)

    prompts = generate_batch(count=args.count, categories=cats)

    for i, p in enumerate(prompts, 1):
        print(f"\n{'='*60}")
        print(f"[{i}] {p['category_name']} ({p['category']})")
        print(f"{'='*60}")
        print(p["prompt"])

    if args.save:
        path = save_prompts(prompts)
        print(f"\nSaved to: {path}")

    print(f"\nTotal: {len(prompts)} prompts generated")


if __name__ == "__main__":
    main()
