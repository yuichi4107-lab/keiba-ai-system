"""ばんえい競馬用特徴量エンジニアリング

ばんえい競馬特有の特徴量を生成する。
- 馬体重（重量級の馬が有利になる場合がある）
- 負担重量（ソリの重さ）
- 騎手・調教師の成績
- 過去走の着順・タイム
- 距離適性
"""

import logging

import numpy as np
import pandas as pd

from config.settings import PAST_RACE_COUNT, PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """特徴量生成クラス"""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._preprocess()

    def _preprocess(self):
        """基本的な前処理"""
        if "race_date" in self.df.columns:
            self.df["race_date"] = pd.to_datetime(self.df["race_date"])
        self.df = self.df.sort_values(["race_date", "race_no", "horse_number"])

        # 1着かどうかのターゲット変数
        self.df["is_win"] = (self.df["finish_order"] == 1).astype(int)

        # タイムを秒に変換
        if "time" in self.df.columns:
            self.df["time_seconds"] = self.df["time"].apply(self._time_to_seconds)

    @staticmethod
    def _time_to_seconds(time_str: str) -> float | None:
        """タイム文字列を秒に変換 (例: '1:23.4' -> 83.4)"""
        if not time_str or not isinstance(time_str, str):
            return None
        try:
            time_str = time_str.strip()
            if ":" in time_str:
                parts = time_str.split(":")
                minutes = int(parts[0])
                seconds = float(parts[1])
                return minutes * 60 + seconds
            return float(time_str)
        except (ValueError, IndexError):
            return None

    def build_features(self) -> pd.DataFrame:
        """全特徴量を生成して返す"""
        df = self.df.copy()

        df = self._add_horse_past_features(df)
        df = self._add_jockey_features(df)
        df = self._add_trainer_features(df)
        df = self._add_weight_features(df)
        df = self._add_race_features(df)

        return df

    def _add_horse_past_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """馬の過去成績に基づく特徴量"""
        df = df.copy()

        # 各馬ごとに過去N走の統計を計算
        horse_stats = []
        for _, row in df.iterrows():
            horse_name = row.get("horse_name", "")
            race_date = row.get("race_date")

            if not horse_name or pd.isna(race_date):
                horse_stats.append(self._empty_horse_stats())
                continue

            # この馬の過去走データ
            past = df[
                (df["horse_name"] == horse_name) & (df["race_date"] < race_date)
            ].tail(PAST_RACE_COUNT)

            if past.empty:
                horse_stats.append(self._empty_horse_stats())
                continue

            stats = {
                "past_runs": len(past),
                "past_win_rate": (past["finish_order"] == 1).mean(),
                "past_top3_rate": (past["finish_order"] <= 3).mean(),
                "past_avg_finish": past["finish_order"].mean(),
                "past_best_finish": past["finish_order"].min(),
                "past_avg_time": past["time_seconds"].mean()
                if "time_seconds" in past.columns
                else None,
                "past_best_time": past["time_seconds"].min()
                if "time_seconds" in past.columns
                else None,
                "days_since_last_race": (race_date - past["race_date"].max()).days
                if not past.empty
                else None,
            }
            horse_stats.append(stats)

        stats_df = pd.DataFrame(horse_stats)
        for col in stats_df.columns:
            df[col] = stats_df[col].values

        return df

    @staticmethod
    def _empty_horse_stats() -> dict:
        return {
            "past_runs": 0,
            "past_win_rate": None,
            "past_top3_rate": None,
            "past_avg_finish": None,
            "past_best_finish": None,
            "past_avg_time": None,
            "past_best_time": None,
            "days_since_last_race": None,
        }

    def _add_jockey_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """騎手成績の特徴量"""
        df = df.copy()
        jockey_stats = []

        for _, row in df.iterrows():
            jockey = row.get("jockey", "")
            race_date = row.get("race_date")

            if not jockey or pd.isna(race_date):
                jockey_stats.append({"jockey_win_rate": None, "jockey_top3_rate": None})
                continue

            past = df[(df["jockey"] == jockey) & (df["race_date"] < race_date)]
            if past.empty:
                jockey_stats.append({"jockey_win_rate": None, "jockey_top3_rate": None})
                continue

            jockey_stats.append(
                {
                    "jockey_win_rate": (past["finish_order"] == 1).mean(),
                    "jockey_top3_rate": (past["finish_order"] <= 3).mean(),
                }
            )

        stats_df = pd.DataFrame(jockey_stats)
        for col in stats_df.columns:
            df[col] = stats_df[col].values

        return df

    def _add_trainer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """調教師成績の特徴量"""
        df = df.copy()
        trainer_stats = []

        for _, row in df.iterrows():
            trainer = row.get("trainer", "")
            race_date = row.get("race_date")

            if not trainer or pd.isna(race_date):
                trainer_stats.append(
                    {"trainer_win_rate": None, "trainer_top3_rate": None}
                )
                continue

            past = df[(df["trainer"] == trainer) & (df["race_date"] < race_date)]
            if past.empty:
                trainer_stats.append(
                    {"trainer_win_rate": None, "trainer_top3_rate": None}
                )
                continue

            trainer_stats.append(
                {
                    "trainer_win_rate": (past["finish_order"] == 1).mean(),
                    "trainer_top3_rate": (past["finish_order"] <= 3).mean(),
                }
            )

        stats_df = pd.DataFrame(trainer_stats)
        for col in stats_df.columns:
            df[col] = stats_df[col].values

        return df

    def _add_weight_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """重量関連の特徴量"""
        df = df.copy()

        if "horse_weight" in df.columns:
            # レース内での馬体重の偏差
            df["weight_rank_in_race"] = df.groupby(
                ["race_date", "race_no"]
            )["horse_weight"].rank(ascending=False)

            race_mean = df.groupby(["race_date", "race_no"])["horse_weight"].transform(
                "mean"
            )
            df["weight_diff_from_mean"] = df["horse_weight"] - race_mean

        if "weight_carry" in df.columns:
            # 負担重量のレース内偏差
            df["carry_rank_in_race"] = df.groupby(
                ["race_date", "race_no"]
            )["weight_carry"].rank(ascending=False)

            # 馬体重に対する負担重量の比率
            if "horse_weight" in df.columns:
                df["carry_to_weight_ratio"] = df["weight_carry"] / df[
                    "horse_weight"
                ].replace(0, np.nan)

        return df

    def _add_race_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """レース条件の特徴量"""
        df = df.copy()

        # 出走頭数
        df["num_runners"] = df.groupby(["race_date", "race_no"])[
            "horse_number"
        ].transform("count")

        # 馬番の正規化（枠順の有利不利）
        df["post_position_norm"] = df["post_position"] / df["num_runners"]

        # 月（季節性）
        if "race_date" in df.columns:
            df["month"] = df["race_date"].dt.month

        # 年齢
        if "age" in df.columns:
            df["age"] = pd.to_numeric(df["age"], errors="coerce")

        # 性別をエンコード
        if "sex" in df.columns:
            sex_map = {"牡": 0, "牝": 1, "セ": 2}
            df["sex_code"] = df["sex"].map(sex_map)

        return df

    def save(self, df: pd.DataFrame, filename: str = "features.csv"):
        """特徴量データを保存"""
        PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        filepath = PROCESSED_DATA_DIR / filename
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        logger.info("特徴量保存完了: %s (%d 件)", filepath, len(df))
        return filepath
