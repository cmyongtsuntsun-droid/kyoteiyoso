"""バックテスト: 的中率・回収率 (ROI) の検証フレームワーク。

設計書の検証方針に従い、検証期間 (Out-of-Sample) に対して
- 単勝 / 2連単 / 3連単の的中率と回収率
- 場別 (24会場) セグメント分析
を算出する。投票は各レースでモデル予測上位の組み合わせに100円固定とする。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .constants import STADIUM_NAMES
from .features import add_features, load_stadium_stats
from .model import load_model, predict_scores, split_by_date

BET_UNIT = 100  # 1点あたりの投票額 (円)


def run_backtest(entries: pd.DataFrame, payouts: pd.DataFrame) -> dict:
    """検証期間のレースに対して的中率・回収率を計算する。"""
    _, valid_raw = split_by_date(entries)
    if valid_raw.empty:
        raise RuntimeError("検証期間のデータがありません。")

    booster = load_model()
    stadium_stats = load_stadium_stats()
    featured = add_features(valid_raw, stadium_stats)
    featured["score"] = predict_scores(booster, featured)

    payout_idx = _index_payouts(payouts)
    records: list[dict] = []
    for race_id, g in featured.groupby("race_id", sort=True):
        actual = g[g["place"].notna()].sort_values("place")
        if actual.empty or actual.iloc[0]["place"] != 1:
            continue  # 結果不備レースは除外
        pred = g.sort_values("score", ascending=False)["boat_number"].astype(int).tolist()
        if len(pred) < 3:
            continue
        race_pay = payout_idx.get(race_id, {})
        records.append(
            {
                "race_id": race_id,
                "stadium": int(g.iloc[0]["stadium"]),
                "win": _settle(race_pay, "win", f"{pred[0]}"),
                "exacta": _settle(race_pay, "exacta", f"{pred[0]}-{pred[1]}"),
                "trifecta": _settle(race_pay, "trifecta", f"{pred[0]}-{pred[1]}-{pred[2]}"),
            }
        )

    if not records:
        raise RuntimeError("バックテスト対象レースがありません。")
    df = pd.DataFrame(records)

    summary = {
        "races": len(df),
        "bet_unit": BET_UNIT,
        "valid_date_range": [
            valid_raw["race_date"].min(),
            valid_raw["race_date"].max(),
        ],
    }
    for bet_type in ("win", "exacta", "trifecta"):
        payout_total = df[bet_type].sum()
        summary[bet_type] = {
            "hit_rate": round(float((df[bet_type] > 0).mean()), 4),
            "roi": round(float(payout_total / (BET_UNIT * len(df))), 4),
        }

    # 場別セグメント分析 (3連単回収率)
    by_stadium = (
        df.groupby("stadium")
        .agg(races=("race_id", "count"), trifecta_payout=("trifecta", "sum"))
        .reset_index()
    )
    by_stadium["roi"] = by_stadium["trifecta_payout"] / (BET_UNIT * by_stadium["races"])
    summary["by_stadium_trifecta"] = [
        {
            "stadium": STADIUM_NAMES.get(int(r["stadium"]), str(r["stadium"])),
            "races": int(r["races"]),
            "roi": round(float(r["roi"]), 4),
        }
        for _, r in by_stadium.sort_values("roi", ascending=False).iterrows()
    ]
    return summary


def _index_payouts(payouts: pd.DataFrame) -> dict[str, dict[tuple[str, str], int]]:
    """race_id → {(bet_type, combination): payout} の索引を作る。"""
    idx: dict[str, dict[tuple[str, str], int]] = {}
    if payouts is None or payouts.empty:
        return idx
    for row in payouts.itertuples(index=False):
        if row.payout is None or (isinstance(row.payout, float) and np.isnan(row.payout)):
            continue
        idx.setdefault(str(row.race_id), {})[(row.bet_type, str(row.combination))] = int(
            row.payout
        )
    return idx


def _settle(race_pay: dict, bet_type: str, combination: str) -> int:
    """的中時は払戻金 (100円あたり)、不的中は 0 を返す。"""
    return race_pay.get((bet_type, combination), 0)


def format_report(summary: dict) -> str:
    """バックテスト結果を人間可読なレポート文字列に整形する。"""
    lines = [
        "=== バックテスト結果 (検証期間 Out-of-Sample) ===",
        f"対象レース数: {summary['races']}  期間: {summary['valid_date_range'][0]} 〜 {summary['valid_date_range'][1]}",
        f"投票: 各レース予測上位に {summary['bet_unit']} 円固定",
        "",
    ]
    labels = {"win": "単勝", "exacta": "2連単", "trifecta": "3連単"}
    for key, label in labels.items():
        s = summary[key]
        lines.append(
            f"  {label:<4}: 的中率 {s['hit_rate']*100:5.1f}%  回収率 {s['roi']*100:6.1f}%"
        )
    lines.append("")
    lines.append("  [場別 3連単回収率 上位]")
    for seg in summary["by_stadium_trifecta"][:8]:
        lines.append(
            f"    {seg['stadium']:<4} {seg['races']:4d}R  回収率 {seg['roi']*100:6.1f}%"
        )
    return "\n".join(lines)
