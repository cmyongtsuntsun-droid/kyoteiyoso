"""LightGBM LambdaRank によるランキング学習モデル。

設計書の方針:
- objective='lambdarank', metric='ndcg' (同一レース6艇の順序関係を最適化)
- query_id = レースID。group パラメータにレース毎の行数をバインド
- 過学習対策: num_leaves < 31, min_child_samples 引き上げ, L1/L2 正則化
- 時間方向ホールドアウト (末尾日付を検証期間とする)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from .constants import METRICS_PATH, MODEL_PATH
from .features import (
    FEATURE_COLUMNS,
    add_features,
    compute_stadium_course_stats,
    save_stadium_stats,
    sort_and_group,
    to_matrix,
)

# ランキング学習向けベースパラメータ (設計書準拠 + 過学習対策)
LGB_PARAMS: dict = {
    "objective": "lambdarank",
    "metric": "ndcg",
    "ndcg_eval_at": [1, 2, 3],
    "learning_rate": 0.05,
    "num_leaves": 20,            # 31未満に制限 (6艇固定レースの過学習対策)
    "min_child_samples": 60,     # 葉の最小データ数を引き上げ
    "lambda_l1": 0.5,
    "lambda_l2": 1.0,
    "feature_fraction": 0.85,
    "bagging_fraction": 0.85,
    "bagging_freq": 1,
    "force_row_wise": True,
    "verbosity": -1,
    "seed": 42,
}
NUM_BOOST_ROUND = 1000
EARLY_STOPPING_ROUNDS = 50
VALID_DAYS_RATIO = 0.15  # 末尾日付の検証期間割合


def split_by_date(df: pd.DataFrame, valid_ratio: float = VALID_DAYS_RATIO) -> tuple[pd.DataFrame, pd.DataFrame]:
    """日付ベースで学習/検証に分割する (時系列リーク防止)。"""
    dates = sorted(df["race_date"].unique())
    n_valid = max(1, int(len(dates) * valid_ratio))
    valid_dates = set(dates[-n_valid:])
    train = df[~df["race_date"].isin(valid_dates)]
    valid = df[df["race_date"].isin(valid_dates)]
    return train.reset_index(drop=True), valid.reset_index(drop=True)


def train_model(
    entries: pd.DataFrame,
    model_path: Path = MODEL_PATH,
    metrics_path: Path = METRICS_PATH,
    stats_path: Path | None = None,
) -> tuple[lgb.Booster, dict]:
    """エントリデータからモデルを学習し、モデルと評価指標を保存する。"""
    train_raw, valid_raw = split_by_date(entries)

    # 場×コース統計は学習期間のみから算出 (検証期間へのリーク防止)
    stadium_stats = compute_stadium_course_stats(train_raw)
    if stats_path is not None:
        save_stadium_stats(stadium_stats, stats_path)
    else:
        save_stadium_stats(stadium_stats)

    train_df, train_groups = sort_and_group(add_features(train_raw, stadium_stats))
    valid_df, valid_groups = sort_and_group(add_features(valid_raw, stadium_stats))

    train_set = lgb.Dataset(
        to_matrix(train_df),
        label=train_df["label"].astype(int),
        group=train_groups,
        feature_name=FEATURE_COLUMNS,
    )
    valid_set = lgb.Dataset(
        to_matrix(valid_df),
        label=valid_df["label"].astype(int),
        group=valid_groups,
        reference=train_set,
    )

    booster = lgb.train(
        LGB_PARAMS,
        train_set,
        num_boost_round=NUM_BOOST_ROUND,
        valid_sets=[valid_set],
        valid_names=["valid"],
        callbacks=[
            lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False),
            lgb.log_evaluation(0),
        ],
    )

    metrics = evaluate_model(booster, valid_df, valid_groups)
    metrics |= {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "best_iteration": booster.best_iteration,
        "train_rows": len(train_df),
        "valid_rows": len(valid_df),
        "train_date_range": [train_df["race_date"].min(), train_df["race_date"].max()],
        "valid_date_range": [valid_df["race_date"].min(), valid_df["race_date"].max()],
        "feature_importance": dict(
            sorted(
                zip(FEATURE_COLUMNS, booster.feature_importance(importance_type="gain").tolist()),
                key=lambda kv: kv[1],
                reverse=True,
            )
        ),
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(model_path), num_iteration=booster.best_iteration)
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return booster, metrics


def evaluate_model(
    booster: lgb.Booster, valid_df: pd.DataFrame, valid_groups: list[int]
) -> dict:
    """検証期間の NDCG / 1着的中率 (top1 hit) を算出する。"""
    scores = booster.predict(
        to_matrix(valid_df), num_iteration=booster.best_iteration
    )
    df = valid_df.copy()
    df["score"] = scores

    hits_top1 = 0
    hits_top2 = 0  # 予測上位2艇で2連単的中 (順序込み)
    hits_top3 = 0  # 予測上位3艇で3連単的中 (順序込み)
    n_races = 0
    for _, g in df.groupby("race_id", sort=False):
        actual = g[g["place"].notna()].sort_values("place")
        if actual.empty or actual.iloc[0]["place"] != 1:
            continue
        n_races += 1
        pred = g.sort_values("score", ascending=False)["boat_number"].tolist()
        act = actual["boat_number"].tolist()
        if pred[0] == act[0]:
            hits_top1 += 1
            if len(act) >= 2 and pred[1] == act[1]:
                hits_top2 += 1
                if len(act) >= 3 and pred[2] == act[2]:
                    hits_top3 += 1

    return {
        "valid_races": n_races,
        "win_hit_rate": round(hits_top1 / n_races, 4) if n_races else None,
        "exacta_hit_rate": round(hits_top2 / n_races, 4) if n_races else None,
        "trifecta_hit_rate": round(hits_top3 / n_races, 4) if n_races else None,
    }


def load_model(model_path: Path = MODEL_PATH) -> lgb.Booster:
    """保存済みモデルを読み込む。"""
    if not model_path.exists():
        raise FileNotFoundError(f"モデル未学習: {model_path}。先に train を実行してください。")
    return lgb.Booster(model_file=str(model_path))


def predict_scores(booster: lgb.Booster, featured_df: pd.DataFrame) -> np.ndarray:
    """特徴量付与済み DataFrame に対するランキングスコアを返す。"""
    return booster.predict(to_matrix(featured_df))


def softmax_probabilities(scores: np.ndarray) -> np.ndarray:
    """レース内スコアを softmax で勝率 (1着確率) に変換する。"""
    exp = np.exp(scores - np.max(scores))
    return exp / exp.sum()
