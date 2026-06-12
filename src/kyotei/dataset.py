"""データ統合・永続化レイヤ。

番組表 (programs)・直前情報 (previews)・結果 (results) を
一意のレースID (YYYYMMDDJJRR; JJ=場コード, RR=レース番号) で結合し、
1艇=1行のフラットなレコードに変換して SQLite / CSV へ永続化する。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

from .constants import DB_PATH, PLACE_TO_LABEL, TRAIN_CSV
from .fetcher import RawDataStore, iter_dates


def make_race_id(race_date: str, stadium: int, race: int) -> str:
    """一意のレースID YYYYMMDDJJRR を生成する。"""
    return f"{race_date.replace('-', '')}{stadium:02d}{race:02d}"


def _race_key(rec: dict) -> tuple[str, int, int]:
    return (rec["race_date"], rec["race_stadium_number"], rec["race_number"])


def _index_by_race(day_json: dict | None, list_key: str) -> dict[tuple, dict]:
    if not day_json:
        return {}
    return {_race_key(r): r for r in day_json.get(list_key, [])}


def build_entry_rows(
    programs: dict | None,
    previews: dict | None,
    results: dict | None,
) -> list[dict]:
    """1日分の JSON 3種を結合し、1艇=1行のレコードリストを返す。

    番組表を基点に、直前情報 (展示・気象) と結果 (着順・ST) を左結合する。
    結果が無い行 (当日未確定レース) はラベル無し (label=None) になる。
    """
    preview_idx = _index_by_race(previews, "previews")
    result_idx = _index_by_race(results, "results")
    rows: list[dict] = []
    if not programs:
        return rows

    for prog in programs.get("programs", []):
        key = _race_key(prog)
        prev = preview_idx.get(key, {})
        res = result_idx.get(key, {})
        race_id = make_race_id(*key)
        # 直前情報の boats は艇番文字列キーの辞書
        prev_boats: dict = prev.get("boats") or {}
        res_boats = {b["racer_boat_number"]: b for b in (res.get("boats") or [])}

        race_common = {
            "race_id": race_id,
            "race_date": prog["race_date"],
            "stadium": prog["race_stadium_number"],
            "race_number": prog["race_number"],
            "race_grade": prog.get("race_grade_number"),
            "race_title": prog.get("race_title"),
            "race_closed_at": prog.get("race_closed_at"),
            # 気象は直前情報を優先 (推論時に入手可能な情報で学習する) し、
            # 欠損時のみ結果データで補完する
            "wind": _first(prev.get("race_wind"), res.get("race_wind")),
            "wind_direction": _first(
                prev.get("race_wind_direction_number"),
                res.get("race_wind_direction_number"),
            ),
            "wave": _first(prev.get("race_wave"), res.get("race_wave")),
            "temperature": _first(prev.get("race_temperature"), res.get("race_temperature")),
            "water_temperature": _first(
                prev.get("race_water_temperature"), res.get("race_water_temperature")
            ),
        }

        for boat in prog.get("boats", []):
            num = boat["racer_boat_number"]
            pb = prev_boats.get(str(num)) or {}
            rb = res_boats.get(num) or {}
            place = rb.get("racer_place_number")
            # 結果レコードが存在する場合のみラベル化 (着順なし=事故等は 0)
            label = _place_to_label(place) if rb else None
            rows.append(
                race_common
                | {
                    "boat_number": num,
                    "racer_number": boat.get("racer_number"),
                    "racer_name": boat.get("racer_name"),
                    "racer_class": boat.get("racer_class_number"),
                    "racer_age": boat.get("racer_age"),
                    "racer_weight": boat.get("racer_weight"),
                    "flying_count": boat.get("racer_flying_count"),
                    "late_count": boat.get("racer_late_count"),
                    "avg_st": boat.get("racer_average_start_timing"),
                    "national_top1": boat.get("racer_national_top_1_percent"),
                    "national_top2": boat.get("racer_national_top_2_percent"),
                    "national_top3": boat.get("racer_national_top_3_percent"),
                    "local_top1": boat.get("racer_local_top_1_percent"),
                    "local_top2": boat.get("racer_local_top_2_percent"),
                    "local_top3": boat.get("racer_local_top_3_percent"),
                    "motor_top2": boat.get("racer_assigned_motor_top_2_percent"),
                    "motor_top3": boat.get("racer_assigned_motor_top_3_percent"),
                    "boat_top2": boat.get("racer_assigned_boat_top_2_percent"),
                    "boat_top3": boat.get("racer_assigned_boat_top_3_percent"),
                    # 直前情報
                    "course": pb.get("racer_course_number"),
                    "st_exhibition": pb.get("racer_start_timing"),
                    "exhibition_time": pb.get("racer_exhibition_time"),
                    "tilt": pb.get("racer_tilt_adjustment"),
                    # 結果 (学習時のみ)
                    "result_course": rb.get("racer_course_number"),
                    "result_st": rb.get("racer_start_timing"),
                    "place": place,
                    "label": label,
                }
            )
    return rows


def build_payout_rows(results: dict | None) -> list[dict]:
    """結果 JSON から払戻金レコード (バックテスト用) を抽出する。"""
    rows: list[dict] = []
    if not results:
        return rows
    for res in results.get("results", []):
        race_id = make_race_id(*_race_key(res))
        payouts = res.get("payouts") or {}
        for bet_type, items in payouts.items():
            for item in items or []:
                rows.append(
                    {
                        "race_id": race_id,
                        "bet_type": bet_type,
                        "combination": item.get("combination"),
                        "payout": item.get("payout"),
                    }
                )
    return rows


def _place_to_label(place: object) -> int:
    """着順をランキング学習ラベルへ変換。事故・欠場 (着順なし) は 0。"""
    if isinstance(place, int) and place in PLACE_TO_LABEL:
        return PLACE_TO_LABEL[place]
    return 0  # F/L/欠場/失格など (着順なし含む)


def _first(*values: object) -> object:
    for v in values:
        if v is not None:
            return v
    return None


def build_dataset(
    start: date,
    end: date,
    store: RawDataStore | None = None,
    db_path: Path = DB_PATH,
    csv_path: Path = TRAIN_CSV,
) -> pd.DataFrame:
    """期間内のキャッシュ済み生データから学習用データセットを構築・保存する。"""
    store = store or RawDataStore()
    entry_rows: list[dict] = []
    payout_rows: list[dict] = []
    for target in iter_dates(start, end):
        programs = store.load_day("programs", target)
        previews = store.load_day("previews", target)
        results = store.load_day("results", target)
        entry_rows.extend(build_entry_rows(programs, previews, results))
        payout_rows.extend(build_payout_rows(results))

    entries = pd.DataFrame(entry_rows)
    payouts = pd.DataFrame(payout_rows)
    if entries.empty:
        raise RuntimeError("データが空です。先に fetch を実行してください。")

    # 結果が確定している行のみ学習対象 (label が無い行は除外)
    entries = entries[entries["label"].notna()].reset_index(drop=True)

    save_to_sqlite(entries, payouts, db_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    entries.to_csv(csv_path, index=False, encoding="utf-8")
    return entries


def save_to_sqlite(
    entries: pd.DataFrame, payouts: pd.DataFrame, db_path: Path = DB_PATH
) -> None:
    """エントリ・払戻金テーブルを SQLite に保存する。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        entries.to_sql("entries", conn, if_exists="replace", index=False)
        if not payouts.empty:
            payouts.to_sql("payouts", conn, if_exists="replace", index=False)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_entries_race ON entries(race_id)"
        )


def load_entries(db_path: Path = DB_PATH) -> pd.DataFrame:
    """SQLite から学習用エントリを読み込む。"""
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql("SELECT * FROM entries", conn)


def load_payouts(db_path: Path = DB_PATH) -> pd.DataFrame:
    """SQLite から払戻金テーブルを読み込む。"""
    with sqlite3.connect(db_path) as conn:
        try:
            return pd.read_sql("SELECT * FROM payouts", conn)
        except (pd.errors.DatabaseError, sqlite3.OperationalError):
            return pd.DataFrame(
                columns=["race_id", "bet_type", "combination", "payout"]
            )


def dump_json(data: dict, path: Path) -> None:
    """JSON を UTF-8 で書き出す共通ユーティリティ。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
