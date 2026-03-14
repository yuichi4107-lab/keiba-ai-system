"""テスト用サンプルデータ生成スクリプト

スクレイピングが使えない環境でパイプラインを検証するための
サンプルレース結果データを生成する。
"""

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from config.settings import RAW_DATA_DIR

# ばんえい競馬の馬名サンプル
HORSE_NAMES = [
    "キタノユウジロウ", "メムロボブサップ", "アオノブラック", "コマサンエース",
    "マツカゼウンカイ", "ゴールドハンター", "インビクタ", "オレノココロ",
    "センゴクエース", "カイセドクター", "ミソギホマレ", "コウシュハウンカイ",
    "ホクショウマサル", "キンツルモリウチ", "マルミゴウカイ", "ナカゼンガキタ",
    "ゴールデンフウジン", "メジロゴーリキ", "シンエイボブ", "アアモンドグンシン",
    "カネサブラック", "ニシキダイジン", "コマサンブラック", "ハクタイホウ",
    "ミノルシャープ", "ジェイエース", "オーシャンウイナー", "プレジデント",
    "フジダイビクトリー", "キサラキク",
]

JOCKEYS = [
    "鈴木恵介", "阿部武臣", "藤本匠", "松田道明", "西謙一",
    "菊池一樹", "渡来心路", "島津新", "船山蔵人", "赤塚健仁",
]

TRAINERS = [
    "坂本東一", "服部義幸", "槻舘重人", "平田義弘", "松井浩文",
    "岩本利春", "金田勇", "大友栄人", "久田守", "西弘美",
]

SEX_OPTIONS = ["牡", "牝", "セ"]


def generate_sample_data(
    start_date: date = date(2025, 1, 1),
    end_date: date = date(2025, 12, 31),
    races_per_day: int = 10,
    race_interval_days: int = 3,
) -> pd.DataFrame:
    """サンプルレースデータを生成"""
    random.seed(42)
    records = []

    current = start_date
    while current <= end_date:
        for race_no in range(1, races_per_day + 1):
            num_horses = random.randint(6, 10)
            distance = random.choice([200])  # ばんえいは200m

            # 出走馬を選択
            horses = random.sample(HORSE_NAMES, num_horses)

            # 各馬の能力値を設定（着順決定に使用）
            abilities = {h: random.gauss(50, 15) for h in horses}

            # 能力順にソート → 着順
            sorted_horses = sorted(horses, key=lambda h: -abilities[h])

            for finish_order, horse_name in enumerate(sorted_horses, 1):
                horse_weight = random.randint(900, 1100)
                weight_carry = random.choice([560, 570, 580, 590, 600, 610, 620, 630, 640, 650, 660, 670, 680, 690, 700])
                jockey = random.choice(JOCKEYS)
                trainer = random.choice(TRAINERS)
                sex = random.choice(SEX_OPTIONS)
                age = random.randint(3, 9)

                # タイム生成（着順が早いほど速い）
                base_time = 120 + random.gauss(0, 10)
                time_seconds = base_time + (finish_order - 1) * random.uniform(1, 5)
                minutes = int(time_seconds) // 60
                secs = time_seconds - minutes * 60
                time_str = f"{minutes}:{secs:04.1f}"

                # オッズ（能力が高い馬は低オッズ）
                odds = max(1.1, 20 - abilities[horse_name] / 5 + random.gauss(0, 3))

                records.append({
                    "race_date": current.strftime("%Y-%m-%d"),
                    "race_no": str(race_no),
                    "race_name": f"第{race_no}レース",
                    "distance": distance,
                    "finish_order": finish_order,
                    "post_position": finish_order,  # 簡略化
                    "horse_number": finish_order,
                    "horse_name": horse_name,
                    "sex_age": f"{sex}{age}",
                    "horse_weight": horse_weight,
                    "jockey": jockey,
                    "time": time_str,
                    "weight_carry": weight_carry,
                    "trainer": trainer,
                    "odds": round(odds, 1),
                    "popularity": finish_order,
                })

        current += timedelta(days=race_interval_days)

    return pd.DataFrame(records)


def main():
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    df = generate_sample_data()
    output_path = RAW_DATA_DIR / "race_results.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"サンプルデータ生成完了: {output_path}")
    print(f"  レコード数: {len(df):,}")
    print(f"  期間: {df['race_date'].min()} 〜 {df['race_date'].max()}")
    print(f"  レース数: {df.groupby(['race_date', 'race_no']).ngroups}")


if __name__ == "__main__":
    main()
