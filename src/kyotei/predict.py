"""推論・期待値計算・静的JSON配信レイヤ。

当日の番組表・直前情報を取得して予測を行い、結果を
site/api/v1/predict/today.json へ静的 JSON として出力する。
静的サイト側はこの JSON を fetch して描画する (サーバーレス構成)。
"""
from __future__ import annotations

from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path

import numpy as np
import pandas as pd

from .constants import (
    METRICS_PATH,
    PREDICT_API_DIR,
    RACER_CLASS_NAMES,
    STADIUM_NAMES,
)
from .dataset import build_entry_rows, dump_json
from .features import add_features, load_stadium_stats
from .fetcher import fetch_today
from .model import load_model, predict_scores, softmax_probabilities

TRIFECTA_TOP_N = 5  # 配信する3連単推奨買い目数


def plackett_luce_trifecta(
    boat_numbers: list[int], win_probs: np.ndarray, top_n: int = TRIFECTA_TOP_N
) -> list[dict]:
    """Plackett-Luce モデルで3連単 (1-2-3着順列) の確率上位を算出する。"""
    w = np.clip(win_probs, 1e-9, None)
    total = w.sum()
    combos: list[dict] = []
    for i, j, k in permutations(range(len(boat_numbers)), 3):
        p = (
            (w[i] / total)
            * (w[j] / (total - w[i]))
            * (w[k] / (total - w[i] - w[j]))
        )
        combos.append(
            {
                "combination": f"{boat_numbers[i]}-{boat_numbers[j]}-{boat_numbers[k]}",
                "probability": round(float(p), 5),
            }
        )
    combos.sort(key=lambda c: c["probability"], reverse=True)
    return combos[:top_n]


def predict_races(entries: pd.DataFrame) -> list[dict]:
    """エントリ DataFrame からレース毎の予測結果リストを生成する。"""
    booster = load_model()
    stadium_stats = load_stadium_stats()
    featured = add_features(entries, stadium_stats)
    featured["score"] = predict_scores(booster, featured)

    races: list[dict] = []
    for race_id, g in featured.groupby("race_id", sort=True):
        g = g.sort_values("boat_number")
        probs = softmax_probabilities(g["score"].to_numpy())
        order = (-g["score"].to_numpy()).argsort().argsort() + 1  # 予測順位

        boats = []
        for idx, (_, row) in enumerate(g.iterrows()):
            boats.append(
                {
                    "boat_number": int(row["boat_number"]),
                    "racer_number": _int_or_none(row["racer_number"]),
                    "racer_name": row["racer_name"],
                    "racer_class": RACER_CLASS_NAMES.get(row["racer_class"], "-"),
                    "course": _int_or_none(row["course"]),
                    "national_top1": _float_or_none(row["national_top1"]),
                    "motor_top2": _float_or_none(row["motor_top2"]),
                    "exhibition_time": _float_or_none(row["exhibition_time"]),
                    "avg_st": _float_or_none(row["avg_st"]),
                    "score": round(float(row["score"]), 4),
                    "win_probability": round(float(probs[idx]), 4),
                    "predicted_rank": int(order[idx]),
                }
            )

        first = g.iloc[0]
        stadium = int(first["stadium"])
        races.append(
            {
                "race_id": race_id,
                "race_date": first["race_date"],
                "stadium_number": stadium,
                "stadium_name": STADIUM_NAMES.get(stadium, str(stadium)),
                "race_number": int(first["race_number"]),
                "race_title": first["race_title"],
                "race_closed_at": first["race_closed_at"],
                "wind": _float_or_none(first["wind"]),
                "wave": _float_or_none(first["wave"]),
                "boats": boats,
                "trifecta": plackett_luce_trifecta(
                    [b["boat_number"] for b in boats],
                    probs,
                ),
            }
        )
    return races


def predict_today(output_dir: Path = PREDICT_API_DIR) -> dict:
    """当日データを取得して予測し、静的 JSON を出力する。"""
    programs = fetch_today("programs")
    previews = fetch_today("previews")
    if not programs:
        raise RuntimeError("本日の番組表を取得できませんでした。")

    rows = build_entry_rows(programs, previews, None)
    entries = pd.DataFrame(rows)
    races = predict_races(entries)

    model_metrics = _load_metrics_summary()
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "race_date": races[0]["race_date"] if races else None,
        "race_count": len(races),
        "model": model_metrics,
        "races": races,
    }
    dump_json(payload, output_dir / "today.json")
    write_fallback_js(payload, output_dir / "today.js")
    if races:
        date_key = races[0]["race_date"].replace("-", "")
        dump_json(payload, output_dir / f"{date_key}.json")
    return payload


def write_fallback_js(payload: dict, path: Path) -> None:
    """file:// で直接開いた場合用のフォールバック JS を出力する。

    ブラウザは file:// からの fetch をブロックするため、予測データを
    グローバル変数として定義する JS を併せて配信し、サイト側で
    fetch 失敗時に <script> 読み込みへフォールバックする。
    """
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "window.__KYOTEI_PREDICT__ = "
        + json.dumps(payload, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )


def _load_metrics_summary() -> dict:
    """学習済みモデルの評価指標サマリを読み込む (サイト表示用)。"""
    import json

    if not METRICS_PATH.exists():
        return {}
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    keys = (
        "win_hit_rate", "exacta_hit_rate", "trifecta_hit_rate",
        "valid_races", "trained_at", "train_rows",
        "train_date_range", "valid_date_range",
    )
    return {k: metrics.get(k) for k in keys if k in metrics}


def _int_or_none(value: object) -> int | None:
    return None if pd.isna(value) else int(value)


def _float_or_none(value: object) -> float | None:
    return None if pd.isna(value) else round(float(value), 3)
