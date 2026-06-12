"""選手個別分析データの生成。

蓄積済みのレース結果 (SQLite) から選手ごとの成績を集計し、
静的サイト用の JSON (+ file:// フォールバック JS) として出力する。

集計内容:
- 通算成績 (出走数・1着率・2連対率・3連対率)
- 実測ST平均・ST標準偏差 (スタート安定性)・展示タイム平均
- 進入コース別成績 (1〜6コース: 出走数・1着率・3連対率・平均ST)
- 場別成績 (出走数・1着率・3連対率)
- 直近レース履歴
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .constants import RACER_CLASS_NAMES, RACERS_API_DIR, STADIUM_NAMES

RECENT_RACES = 10  # 直近履歴として配信するレース数
MIN_RACES = 1      # 集計対象とする最小出走数


def build_racer_analysis(entries: pd.DataFrame) -> dict:
    """エントリ DataFrame から選手分析データ一式を構築する。"""
    finished = entries[entries["place"].notna()].copy()
    finished = finished.sort_values(["race_date", "race_id"])

    racers: list[dict] = []
    for racer_number, g in finished.groupby("racer_number"):
        if len(g) < MIN_RACES:
            continue
        racers.append(_analyze_racer(int(racer_number), g))

    # 1着率順 (出走数で安定化のため5走以上を優先) に並べる
    racers.sort(key=lambda r: (-r["stats"]["win_rate"], -r["stats"]["races"]))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": [
            str(finished["race_date"].min()),
            str(finished["race_date"].max()),
        ],
        "racer_count": len(racers),
        "racers": racers,
    }


def _analyze_racer(racer_number: int, g: pd.DataFrame) -> dict:
    """1選手分の集計を行う。g は時系列順ソート済みの完走レコード。"""
    latest = g.iloc[-1]
    place = g["place"]

    recent = g.tail(RECENT_RACES)
    recent_races = [
        {
            "race_date": str(row.race_date),
            "stadium": STADIUM_NAMES.get(int(row.stadium), str(row.stadium)),
            "race_number": int(row.race_number),
            "course": _int(row.result_course if pd.notna(row.result_course) else row.boat_number),
            "st": _float(row.result_st),
            "place": _int(row.place),
        }
        for row in recent.itertuples(index=False)
    ][::-1]  # 新しい順

    return {
        "racer_number": racer_number,
        "racer_name": latest["racer_name"],
        "racer_class": RACER_CLASS_NAMES.get(latest["racer_class"], "-"),
        "age": _int(latest["racer_age"]),
        "weight": _float(latest["racer_weight"]),
        "national_top1": _float(latest["national_top1"]),
        "flying_count": _int(latest["flying_count"]),
        "stats": {
            "races": int(len(g)),
            "win_rate": _rate(place == 1, len(g)),
            "top2_rate": _rate(place <= 2, len(g)),
            "top3_rate": _rate(place <= 3, len(g)),
            "avg_st": _float(g["result_st"].mean()),
            "st_std": _float(g["result_st"].std()),
            "avg_exhibition_time": _float(g["exhibition_time"].mean()),
            "recent_win_rate": _rate(recent["place"] == 1, len(recent)),
        },
        "by_course": _course_stats(g),
        "by_stadium": _stadium_stats(g),
        "recent_races": recent_races,
    }


def _course_stats(g: pd.DataFrame) -> list[dict]:
    """進入コース別 (1〜6) の成績を集計する。"""
    df = g.copy()
    df["course_actual"] = df["result_course"].fillna(df["boat_number"])
    out: list[dict] = []
    for course in range(1, 7):
        sub = df[df["course_actual"] == course]
        if sub.empty:
            out.append({"course": course, "races": 0})
            continue
        out.append(
            {
                "course": course,
                "races": int(len(sub)),
                "win_rate": _rate(sub["place"] == 1, len(sub)),
                "top3_rate": _rate(sub["place"] <= 3, len(sub)),
                "avg_st": _float(sub["result_st"].mean()),
            }
        )
    return out


def _stadium_stats(g: pd.DataFrame) -> list[dict]:
    """場別成績を出走数降順で集計する。"""
    out: list[dict] = []
    for stadium, sub in g.groupby("stadium"):
        out.append(
            {
                "stadium": STADIUM_NAMES.get(int(stadium), str(stadium)),
                "races": int(len(sub)),
                "win_rate": _rate(sub["place"] == 1, len(sub)),
                "top3_rate": _rate(sub["place"] <= 3, len(sub)),
            }
        )
    out.sort(key=lambda s: -s["races"])
    return out


def export_racer_data(payload: dict, output_dir: Path = RACERS_API_DIR) -> None:
    """選手分析データを JSON + フォールバック JS として書き出す。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False)
    (output_dir / "racers.json").write_text(text, encoding="utf-8")
    (output_dir / "racers.js").write_text(
        "window.__KYOTEI_RACERS__ = " + text + ";\n", encoding="utf-8"
    )


def _rate(condition: pd.Series, total: int) -> float | None:
    return round(float(condition.sum()) / total, 4) if total else None


def _int(value: object) -> int | None:
    return None if pd.isna(value) else int(value)


def _float(value: object) -> float | None:
    return None if pd.isna(value) else round(float(value), 3)
