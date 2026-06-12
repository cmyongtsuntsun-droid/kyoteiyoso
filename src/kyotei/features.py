"""特徴量エンジニアリング。

設計書のドメイン知識を明示的な特徴量として実装する:
- 全国勝率と当地勝率の差分・レース内偏差値化
- 平均ST / スタート事故 (F/L) フラグ
- モーター・ボート2連率 (エース機判定の基礎)
- 展示タイムのレース内相対値・順位
- 風速×進入コースの交互作用 (追い風時イン逃げ減衰指標の近似)
- 高波×ダッシュ勢の交互作用 (安定板装着相当の荒れ水面フラグ)
- 場×コース別の歴史的1着率 (イン逃げ成功率の場別特性)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .constants import (
    DEFAULT_AVG_ST,
    DEFAULT_TILT,
    HIGH_WAVE_CM,
    STADIUM_STATS_PATH,
    STRONG_WIND_MS,
)

# モデルに入力する特徴量カラム (順序固定)
FEATURE_COLUMNS: list[str] = [
    "boat_number", "course", "racer_class", "racer_age", "racer_weight",
    "flying_count", "late_count", "avg_st",
    "national_top1", "national_top2", "national_top3",
    "local_top1", "local_top2", "local_top3",
    "local_minus_national",
    "motor_top2", "motor_top3", "boat_top2", "boat_top3",
    "is_ace_motor",
    "exhibition_time", "exhibition_rank", "exhibition_diff",
    "st_exhibition", "st_exhibition_rank", "tilt",
    "wind", "wind_direction", "wave", "temperature", "water_temperature",
    "strong_wind_course1", "high_wave_dash",
    "national_top1_dev", "avg_st_rank",
    "stadium", "stadium_course_win_rate",
]


def compute_stadium_course_stats(train_df: pd.DataFrame) -> pd.DataFrame:
    """学習データから場×コース別の1着率を集計する (推論時にも再利用)。"""
    df = train_df[train_df["place"].notna()].copy()
    df["course_filled"] = df["course"].fillna(df["boat_number"])
    grouped = df.groupby(["stadium", "course_filled"], as_index=False).agg(
        races=("race_id", "count"),
        wins=("place", lambda s: (s == 1).sum()),
    )
    grouped["stadium_course_win_rate"] = grouped["wins"] / grouped["races"]
    return grouped.rename(columns={"course_filled": "course_key"})[
        ["stadium", "course_key", "stadium_course_win_rate"]
    ]


def save_stadium_stats(stats: pd.DataFrame, path: Path = STADIUM_STATS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stats.to_csv(path, index=False)


def load_stadium_stats(path: Path = STADIUM_STATS_PATH) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path)


def add_features(
    df: pd.DataFrame, stadium_stats: pd.DataFrame | None = None
) -> pd.DataFrame:
    """フラットなエントリ DataFrame に特徴量カラムを付加して返す (非破壊)。"""
    out = df.copy()

    # --- 欠損値の明示的処理 (設計書: 前処理段階で安全にデフォルト値へ変換) ---
    out["course"] = out["course"].fillna(out["boat_number"])
    out["avg_st"] = out["avg_st"].fillna(DEFAULT_AVG_ST)
    out["tilt"] = out["tilt"].fillna(DEFAULT_TILT)
    for col in (
        "national_top1", "national_top2", "national_top3",
        "local_top1", "local_top2", "local_top3",
        "motor_top2", "motor_top3", "boat_top2", "boat_top3",
        "flying_count", "late_count",
    ):
        out[col] = out[col].fillna(0.0)
    # 展示タイムはレース内中央値 → 全体中央値 → 標準値 6.75 秒で段階的に補完
    race_median = out.groupby("race_id")["exhibition_time"].transform("median")
    out["exhibition_time"] = out["exhibition_time"].fillna(race_median)
    out["exhibition_time"] = out["exhibition_time"].fillna(
        out["exhibition_time"].median()
    )
    out["exhibition_time"] = out["exhibition_time"].fillna(6.75)
    out["st_exhibition"] = out["st_exhibition"].fillna(DEFAULT_AVG_ST)
    for col in ("wind", "wave", "temperature", "water_temperature", "wind_direction"):
        out[col] = out[col].fillna(out[col].median())
        out[col] = out[col].fillna(0.0)

    # --- 当地・全国の実力差分 (難水面での当地実績補正) ---
    out["local_minus_national"] = out["local_top1"] - out["national_top1"]

    # --- 機力: 2連率40%超はエース機扱い ---
    out["is_ace_motor"] = (out["motor_top2"] > 40.0).astype(int)

    # --- レース内相対特徴量 (6艇の相対評価問題として設計) ---
    grp = out.groupby("race_id")
    out["exhibition_rank"] = grp["exhibition_time"].rank(method="min")  # 小さいほど速い
    out["exhibition_diff"] = out["exhibition_time"] - grp["exhibition_time"].transform("mean")
    out["st_exhibition_rank"] = grp["st_exhibition"].rank(method="min")
    out["avg_st_rank"] = grp["avg_st"].rank(method="min")
    # 全国勝率のレース内偏差値化
    mean = grp["national_top1"].transform("mean")
    std = grp["national_top1"].transform("std").replace(0, np.nan)
    out["national_top1_dev"] = (50 + 10 * (out["national_top1"] - mean) / std).fillna(50.0)

    # --- ドメイン交互作用特徴量 ---
    # 追い風時イン逃げ減衰指標の近似: 強風 × 1コース (ターン流れリスク)
    out["strong_wind_course1"] = (
        (out["wind"] >= STRONG_WIND_MS) & (out["course"] == 1)
    ).astype(int)
    # 荒れ水面 (安定板相当) × ダッシュ勢: まくり性能の減衰
    out["high_wave_dash"] = (
        (out["wave"] >= HIGH_WAVE_CM) & (out["course"] >= 4)
    ).astype(int)

    # --- 場×コース別の歴史的1着率 ---
    if stadium_stats is not None and not stadium_stats.empty:
        out = out.merge(
            stadium_stats,
            left_on=["stadium", "course"],
            right_on=["stadium", "course_key"],
            how="left",
        ).drop(columns=["course_key"])
        out["stadium_course_win_rate"] = out["stadium_course_win_rate"].fillna(
            out["stadium_course_win_rate"].mean()
        )
        out["stadium_course_win_rate"] = out["stadium_course_win_rate"].fillna(1 / 6)
    else:
        out["stadium_course_win_rate"] = 1 / 6

    return out


def to_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """特徴量行列 (FEATURE_COLUMNS 順) を取り出す。"""
    return df[FEATURE_COLUMNS].astype(float)


def sort_and_group(df: pd.DataFrame) -> tuple[pd.DataFrame, list[int]]:
    """query_id (race_id) 順にソートし、グループサイズ配列を返す。

    LightGBM のランキング学習はグループが連続して並んでいる必要がある。
    """
    sorted_df = df.sort_values(["race_id", "boat_number"]).reset_index(drop=True)
    group_sizes = sorted_df.groupby("race_id", sort=False).size().tolist()
    return sorted_df, group_sizes
